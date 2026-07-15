"""
Optimal course scheduler via CP-SAT (Google OR-Tools).

Two-phase lexicographic optimization:
  Phase 1 -- minimize the number of terms needed to satisfy every
             mandatory course and every elective pool's minimum.
  Phase 2 -- fix that minimum term count, then re-solve maximizing
             total course quality (rating) subject to a per-term
             credit-load fairness bound, and a penalty for
             early-morning courses if the student opted out of them.

Elective selection is part of the model: for each elective pool the
solver chooses *which* candidate courses to take, not just how many.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from app.models import Course, DegreeProgram, ScheduleResult, StudentProfile
from app.solver.engine import build_term_calendar


def _build_model(
    courses: dict[str, Course],
    profile: StudentProfile,
    mandatory: set[str],
    candidates: set[str],
    n_terms: int,
):
    model = cp_model.CpModel()
    seasons = build_term_calendar(profile, n_terms)
    codes = sorted(candidates)

    x = {
        (c, t): model.NewBoolVar(f"x_{c}_{t}")
        for c in codes
        for t in range(n_terms)
        if seasons[t] in courses[c].terms_offered
    }

    taken = {c: model.NewBoolVar(f"taken_{c}") for c in codes}
    for c in codes:
        terms_for_c = [t for t in range(n_terms) if (c, t) in x]
        model.Add(sum(x[(c, t)] for t in terms_for_c) == taken[c])
        if not terms_for_c:
            model.Add(taken[c] == 0)

    for c in mandatory:
        model.Add(taken[c] == 1)

    # Elective pool minimums are added by the caller, since they need
    # the DegreeProgram, not just the course dict.

    for c in codes:
        for p in courses[c].prereqs:
            if p in profile.completed_codes:
                continue
            if p not in codes:
                continue
            for t in range(n_terms):
                if (c, t) not in x:
                    continue
                earlier = [x[(p, tp)] for tp in range(t) if (p, tp) in x]
                if earlier:
                    model.Add(x[(c, t)] <= sum(earlier))
                else:
                    model.Add(x[(c, t)] == 0)

    for t in range(n_terms):
        load = sum(courses[c].credits * x[(c, t)] for c in codes if (c, t) in x)
        model.Add(load <= profile.max_credits_per_term)

    return model, x, taken, seasons, codes


def _add_elective_constraints(model, program, courses, taken, codes):
    for pool in program.electives:
        pool_codes = [c for c in pool.candidate_codes if c in codes]
        if pool.min_credits:
            model.Add(sum(courses[c].credits * taken[c] for c in pool_codes) >= pool.min_credits)
        if pool.min_count:
            model.Add(sum(taken[c] for c in pool_codes) >= pool.min_count)


def solve_with_cpsat(
    program: DegreeProgram,
    courses: dict[str, Course],
    profile: StudentProfile,
    mandatory: set[str],
    candidates: set[str],
) -> ScheduleResult:
    for n_terms in range(1, profile.max_terms_horizon + 1):
        model, x, taken, seasons, codes = _build_model(courses, profile, mandatory, candidates, n_terms)
        _add_elective_constraints(model, program, courses, taken, codes)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 15
        status = solver.Solve(model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return _extract_and_optimize_quality(program, courses, profile, mandatory, candidates, n_terms)

    return ScheduleResult(
        feasible=False,
        reason=f"No feasible schedule found within {profile.max_terms_horizon} terms.",
        solver_used="cp-sat",
    )


def _extract_and_optimize_quality(program, courses, profile, mandatory, candidates, n_terms) -> ScheduleResult:
    """Phase 2: re-solve at the minimal n_terms, this time maximizing quality."""
    model, x, taken, seasons, codes = _build_model(courses, profile, mandatory, candidates, n_terms)
    _add_elective_constraints(model, program, courses, taken, codes)

    term_load = []
    for t in range(n_terms):
        load = model.NewIntVar(0, profile.max_credits_per_term, f"load_{t}")
        model.Add(load == sum(courses[c].credits * x[(c, t)] for c in codes if (c, t) in x))
        term_load.append(load)
    max_load = model.NewIntVar(0, profile.max_credits_per_term, "max_load")
    min_load = model.NewIntVar(0, profile.max_credits_per_term, "min_load")
    model.AddMaxEquality(max_load, term_load)
    model.AddMinEquality(min_load, term_load)
    model.Add(max_load - min_load <= 6)

    RATING_SCALE = 10
    quality_terms = []
    for c in codes:
        for t in range(n_terms):
            if (c, t) not in x:
                continue
            score = int(round(courses[c].rating * RATING_SCALE))
            if profile.avoid_early_morning and courses[c].is_early_morning:
                score -= 30
            quality_terms.append(score * x[(c, t)])
    model.Maximize(sum(quality_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 15
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return ScheduleResult(feasible=False, reason="Quality optimization phase failed unexpectedly.")

    assignment = {}
    total_credits: dict[int, int] = {t: 0 for t in range(n_terms)}
    ratings = []
    for c in codes:
        for t in range(n_terms):
            if (c, t) in x and solver.Value(x[(c, t)]) == 1:
                assignment[c] = t
                total_credits[t] += courses[c].credits
                ratings.append(courses[c].rating)

    term_labels = [f"{seasons[t].value} (Term {t + 1})" for t in range(n_terms)]

    return ScheduleResult(
        feasible=True,
        terms_used=n_terms,
        assignment=assignment,
        term_labels=term_labels,
        total_credits=total_credits,
        avg_rating=round(sum(ratings) / len(ratings), 2) if ratings else 0.0,
        solver_used="cp-sat",
    )
