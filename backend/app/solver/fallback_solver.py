"""
Fallback scheduler: pure-Python backtracking search with forward checking.

Used automatically when `ortools` isn't installed, so the project still
runs end-to-end with zero external solver dependencies. It is NOT
guaranteed optimal the way the CP-SAT path is -- elective selection is
greedy (highest-rated candidates first, up to the pool minimum) rather
than jointly optimized -- but term assignment itself is a real
constraint-satisfaction search: topological ordering + domain pruning
+ backtracking on credit-load overflow.

This exists for two reasons:
  1. So the repo is runnable and demo-able without needing OR-Tools
     compiled/installed (e.g. in restricted environments).
  2. It's a legitimate "build the algorithm yourself" artifact in its
     own right -- useful to point to in an interview when asked "how
     would you do this without a solver library?"
"""

from __future__ import annotations

import time

from app.models import Course, DegreeProgram, ScheduleResult, StudentProfile
from app.solver.engine import build_term_calendar


def _topological_order(codes: set[str], courses: dict[str, Course]) -> list[str]:
    """Courses with no unresolved prereqs (within the candidate set) come first."""
    remaining = set(codes)
    ordered: list[str] = []
    while remaining:
        ready = [c for c in remaining if all(p not in remaining for p in courses[c].prereqs)]
        if not ready:
            ordered.extend(sorted(remaining))
            break
        ready.sort(key=lambda c: (-len(courses[c].prereqs), c))
        ordered.extend(ready)
        remaining -= set(ready)
    return ordered


def _select_electives(
    program: DegreeProgram, courses: dict[str, Course], completed: set[str]
) -> tuple[set[str], list[str]]:
    """Greedily pick the highest-rated courses from each elective pool
    until its credit/count minimum is met."""
    chosen: set[str] = set()
    notes = []
    for pool in program.electives:
        candidates = [c for c in pool.candidate_codes if c in courses and c not in completed]
        candidates.sort(key=lambda c: -courses[c].rating)
        credits_so_far, count_so_far = 0, 0
        picked = []
        for c in candidates:
            need_more_credits = pool.min_credits and credits_so_far < pool.min_credits
            need_more_count = pool.min_count and count_so_far < pool.min_count
            if not need_more_credits and not need_more_count:
                break
            picked.append(c)
            credits_so_far += courses[c].credits
            count_so_far += 1
        if pool.min_credits and credits_so_far < pool.min_credits:
            notes.append(
                f"Elective pool '{pool.name}' could only reach {credits_so_far}/"
                f"{pool.min_credits} credits from available candidates."
            )
        chosen |= set(picked)
    return chosen, notes


def _expand_prereq_closure(required: set[str], courses: dict[str, Course], completed: set[str]) -> set[str]:
    """If a chosen elective needs a prereq that wasn't otherwise selected,
    pull that prereq in too (recursively). Without this, greedily picking
    e.g. 'Technical Writing' without also scheduling its 'Composition'
    prereq would silently produce an unsatisfiable schedule."""
    closure = set(required)
    frontier = list(required)
    while frontier:
        code = frontier.pop()
        for p in courses[code].prereqs:
            if p in completed or p in closure or p not in courses:
                continue
            closure.add(p)
            frontier.append(p)
    return closure


def _backtrack_assign(
    order: list[str],
    idx: int,
    courses: dict[str, Course],
    seasons: list,
    completed: set[str],
    max_credits: int,
    assignment: dict[str, int],
    term_load: dict[int, int],
    deadline: float,
    counter: list[int],
) -> bool:
    counter[0] += 1
    if counter[0] % 2000 == 0 and time.perf_counter() > deadline:
        return False

    if idx == len(order):
        return True

    code = order[idx]
    course = courses[code]

    lower_bound = 0
    for p in course.prereqs:
        if p in completed:
            continue
        if p in assignment:
            lower_bound = max(lower_bound, assignment[p] + 1)
        elif p in courses:
            # Prereq exists but hasn't been scheduled -- since we assign in
            # topological order this should never happen if `order` was
            # built correctly. Fail loudly rather than silently ignore it.
            return False

    candidate_terms = [
        t for t in range(len(seasons)) if t >= lower_bound and seasons[t] in course.terms_offered
    ]
    candidate_terms.sort(key=lambda t: term_load.get(t, 0))

    for t in candidate_terms:
        if term_load.get(t, 0) + course.credits > max_credits:
            continue
        assignment[code] = t
        term_load[t] = term_load.get(t, 0) + course.credits
        if _backtrack_assign(order, idx + 1, courses, seasons, completed, max_credits, assignment, term_load, deadline, counter):
            return True
        del assignment[code]
        term_load[t] -= course.credits
        if time.perf_counter() > deadline:
            return False

    return False


# Wall-clock budget (seconds) for a single term-count attempt, not a raw
# node-count cap -- worst-case search trees for this problem can need well
# over a million nodes even on instances that are "easy" in wall-clock
# terms, so a node cap alone under- or over-shoots depending on the
# instance. This keeps the fallback solver from hanging on denser catalogs
# where naive backtracking is exponential in the worst case (this is a
# real bin-packing-under-precedence problem -- see the CP-SAT solver for a
# version that doesn't need this escape hatch).
_SEARCH_TIME_BUDGET_SECONDS = 2.0


def _greedy_only_assign(
    order: list[str],
    courses: dict[str, Course],
    seasons: list,
    completed: set[str],
    max_credits: int,
) -> dict[str, int] | None:
    """No backtracking at all -- assign each course (in topological order)
    to the first term that satisfies prereqs and credit load. O(courses *
    terms), always terminates. Used as a last resort when the budgeted
    backtracking search can't reach a verdict on a dense catalog: a
    schedule found this way is valid but not load-balanced or optimal."""
    assignment: dict[str, int] = {}
    term_load: dict[int, int] = {}
    for code in order:
        course = courses[code]
        lower_bound = 0
        for p in course.prereqs:
            if p in completed:
                continue
            if p not in assignment:
                return None
            lower_bound = max(lower_bound, assignment[p] + 1)
        placed = False
        for t in range(lower_bound, len(seasons)):
            if seasons[t] not in course.terms_offered:
                continue
            if term_load.get(t, 0) + course.credits > max_credits:
                continue
            assignment[code] = t
            term_load[t] = term_load.get(t, 0) + course.credits
            placed = True
            break
        if not placed:
            return None
    return assignment


def solve_with_backtracking(
    program: DegreeProgram,
    courses: dict[str, Course],
    profile: StudentProfile,
    mandatory: set[str],
    candidates: set[str],
) -> ScheduleResult:
    electives, notes = _select_electives(program, courses, profile.completed_codes)
    required = _expand_prereq_closure(mandatory | electives, courses, profile.completed_codes)
    order = _topological_order(required, courses)

    budget_exhausted_anywhere = False

    for n_terms in range(1, profile.max_terms_horizon + 1):
        seasons = build_term_calendar(profile, n_terms)
        assignment: dict[str, int] = {}
        term_load: dict[int, int] = {}
        deadline = time.perf_counter() + _SEARCH_TIME_BUDGET_SECONDS
        counter = [0]
        ok = _backtrack_assign(
            order, 0, courses, seasons, profile.completed_codes,
            profile.max_credits_per_term, assignment, term_load, deadline, counter,
        )
        if not ok and time.perf_counter() > deadline:
            budget_exhausted_anywhere = True
        if ok:
            return _build_result(seasons, n_terms, assignment, term_load, courses, notes, optimal_search=True)

    # The budgeted search couldn't reach a verdict at some term count(s) --
    # don't report "infeasible" outright, since that may just mean the
    # search ran out of budget rather than proving no schedule exists. Try
    # a fast, always-terminating greedy pass before giving up.
    if budget_exhausted_anywhere:
        for n_terms in range(1, profile.max_terms_horizon + 1):
            seasons = build_term_calendar(profile, n_terms)
            assignment = _greedy_only_assign(
                order, courses, seasons, profile.completed_codes, profile.max_credits_per_term
            )
            if assignment is not None:
                term_load = {}
                for code, t in assignment.items():
                    term_load[t] = term_load.get(t, 0) + courses[code].credits
                return _build_result(
                    seasons, n_terms, assignment, term_load, courses, notes, optimal_search=False
                )

    return ScheduleResult(
        feasible=False,
        reason=(
            f"No feasible schedule found within {profile.max_terms_horizon} terms."
            + (" (search budget exceeded on a dense catalog -- try installing ortools for the optimal solver)" if budget_exhausted_anywhere else "")
        ),
        conflicts=notes,
        solver_used="backtracking (fallback)",
    )


def _build_result(seasons, n_terms, assignment, term_load, courses, notes, optimal_search: bool) -> ScheduleResult:
    term_labels = [f"{seasons[t].value} (Term {t + 1})" for t in range(n_terms)]
    ratings = [courses[c].rating for c in assignment]
    label = (
        "backtracking (fallback -- install ortools for optimal solving)"
        if optimal_search
        else "greedy (search budget exceeded, unbalanced -- install ortools for optimal solving)"
    )
    return ScheduleResult(
        feasible=True,
        terms_used=n_terms,
        assignment=assignment,
        term_labels=term_labels,
        total_credits={t: term_load.get(t, 0) for t in range(n_terms)},
        avg_rating=round(sum(ratings) / len(ratings), 2) if ratings else 0.0,
        conflicts=notes,
        solver_used=label,
    )
