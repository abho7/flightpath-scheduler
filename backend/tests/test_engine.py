import copy

from app.models import Course, StudentProfile, Term
from app.sample_data import COURSES, CS_DEGREE
from app.solver.engine import detect_prereq_cycle, solve_schedule


def _assert_valid_schedule(result, courses, completed):
    assert result.feasible
    for code, term in result.assignment.items():
        for p in courses[code].prereqs:
            if p in completed:
                continue
            assert p in result.assignment, f"{code} scheduled without prereq {p}"
            assert result.assignment[p] < term, f"{code} does not come strictly after prereq {p}"
    for term_credits in result.total_credits.values():
        pass  # bound checked separately per profile


def test_full_solve_is_feasible_and_valid():
    profile = StudentProfile(max_credits_per_term=16, max_terms_horizon=10)
    result = solve_schedule(CS_DEGREE, COURSES, profile)
    _assert_valid_schedule(result, COURSES, profile.completed_codes)
    assert all(c <= profile.max_credits_per_term for c in result.total_credits.values())


def test_partial_completion_reduces_terms_needed():
    profile_fresh = StudentProfile(max_credits_per_term=16, max_terms_horizon=10)
    profile_advanced = StudentProfile(
        completed_codes={"CS101", "CS102", "CS201", "CS210", "CS211", "MATH210", "MATH220"},
        max_credits_per_term=16,
        max_terms_horizon=10,
    )
    fresh = solve_schedule(CS_DEGREE, COURSES, profile_fresh)
    advanced = solve_schedule(CS_DEGREE, COURSES, profile_advanced)
    assert advanced.terms_used < fresh.terms_used


def test_infeasible_within_horizon_reports_cleanly():
    profile = StudentProfile(max_credits_per_term=3, max_terms_horizon=3)
    result = solve_schedule(CS_DEGREE, COURSES, profile)
    assert not result.feasible
    assert result.reason


def test_cycle_detection():
    bad_courses = copy.deepcopy(COURSES)
    bad_courses["CS101"] = Course("CS101", "Intro", 4, (Term.FALL,), ("CS102",))
    cycle = detect_prereq_cycle(bad_courses)
    assert cycle is not None
    assert "CS101" in cycle and "CS102" in cycle


def test_no_course_scheduled_twice():
    profile = StudentProfile(max_credits_per_term=18, max_terms_horizon=10)
    result = solve_schedule(CS_DEGREE, COURSES, profile)
    codes = list(result.assignment.keys())
    assert len(codes) == len(set(codes))


def test_courses_only_scheduled_in_offered_terms():
    profile = StudentProfile(max_credits_per_term=18, max_terms_horizon=10)
    result = solve_schedule(CS_DEGREE, COURSES, profile)
    for code, term_idx in result.assignment.items():
        season = Term(result.term_labels[term_idx].split(" ")[0])
        assert season in COURSES[code].terms_offered


def test_elective_pool_minimums_met():
    profile = StudentProfile(max_credits_per_term=18, max_terms_horizon=10)
    result = solve_schedule(CS_DEGREE, COURSES, profile)
    for pool in CS_DEGREE.electives:
        taken_credits = sum(
            COURSES[c].credits for c in pool.candidate_codes if c in result.assignment
        )
        if pool.min_credits:
            assert taken_credits >= pool.min_credits, f"{pool.name} under-satisfied"
