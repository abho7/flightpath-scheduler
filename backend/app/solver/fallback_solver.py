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
) -> bool:
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
        if _backtrack_assign(order, idx + 1, courses, seasons, completed, max_credits, assignment, term_load):
            return True
        del assignment[code]
        term_load[t] -= course.credits

    return False


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

    for n_terms in range(1, profile.max_terms_horizon + 1):
        seasons = build_term_calendar(profile, n_terms)
        assignment: dict[str, int] = {}
        term_load: dict[int, int] = {}
        ok = _backtrack_assign(
            order, 0, courses, seasons, profile.completed_codes,
            profile.max_credits_per_term, assignment, term_load,
        )
        if ok:
            term_labels = [f"{seasons[t].value} (Term {t + 1})" for t in range(n_terms)]
            ratings = [courses[c].rating for c in assignment]
            return ScheduleResult(
                feasible=True,
                terms_used=n_terms,
                assignment=assignment,
                term_labels=term_labels,
                total_credits={t: term_load.get(t, 0) for t in range(n_terms)},
                avg_rating=round(sum(ratings) / len(ratings), 2) if ratings else 0.0,
                conflicts=notes,
                solver_used="backtracking (fallback -- install ortools for optimal solving)",
            )

    return ScheduleResult(
        feasible=False,
        reason=f"No feasible schedule found within {profile.max_terms_horizon} terms.",
        conflicts=notes,
        solver_used="backtracking (fallback)",
    )
