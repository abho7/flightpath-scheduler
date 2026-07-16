import time

from app.catalog_loader import list_catalogs, load_catalog_by_id
from app.models import StudentProfile
from app.solver.engine import solve_schedule


def test_all_shipped_catalogs_are_listed():
    catalogs = list_catalogs()
    ids = {c["id"] for c in catalogs}
    assert {"cs-generic", "business-generic", "psychology-generic"}.issubset(ids)


def test_all_shipped_catalogs_solve_within_time_budget():
    """Every catalog we ship must produce a feasible schedule, and must
    not hang -- this is the regression test for the backtracking solver's
    worst-case blowup on denser catalogs."""
    for meta in list_catalogs():
        program, courses = load_catalog_by_id(meta["id"])
        profile = StudentProfile(max_credits_per_term=16, max_terms_horizon=10)
        start = time.time()
        result = solve_schedule(program, courses, profile)
        elapsed = time.time() - start
        assert result.feasible, f"{meta['id']} did not find a feasible schedule"
        assert elapsed < 20, f"{meta['id']} took {elapsed:.1f}s -- solver may be hanging"

        for code, term in result.assignment.items():
            for p in courses[code].prereqs:
                if p in profile.completed_codes:
                    continue
                assert p in result.assignment, f"{meta['id']}: {code} missing prereq {p}"
                assert result.assignment[p] < term, f"{meta['id']}: {code} not after prereq {p}"
