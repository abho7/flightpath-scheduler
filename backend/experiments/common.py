"""Shared helpers for the AAI 2026 experiments. Nothing in app/ is modified."""
from __future__ import annotations
import math, random, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ortools.sat.python import cp_model
from app.catalog_loader import parse_catalog
from app.models import StudentProfile, Term
from app.solver.engine import resolve_required_set, build_term_calendar
from app.solver.ortools_solver import solve_with_cpsat, _build_model, _add_elective_constraints
from app.solver.fallback_solver import solve_with_backtracking


def candidates_for(program, courses, profile):
    mand, err = resolve_required_set(program, courses, profile.completed_codes)
    assert not err, err
    cand = set(mand)
    for p in program.electives:
        cand |= {c for c in p.candidate_codes if c not in profile.completed_codes}
    return mand, cand


def lower_bound(program, courses, profile):
    """max(prerequisite-chain bound respecting offered seasons, credit bound), mandatory courses only."""
    mand, _ = candidates_for(program, courses, profile)
    seasons = build_term_calendar(profile, 200)
    memo = {}
    def earliest(c):
        if c in memo: return memo[c]
        lb = 0
        for p in courses[c].prereqs:
            if p in profile.completed_codes or p not in courses: continue
            lb = max(lb, earliest(p) + 1)
        t = lb
        while seasons[t] not in courses[c].terms_offered: t += 1
        memo[c] = t; return t
    chain = max((earliest(c) + 1 for c in mand), default=0)
    credit = math.ceil(sum(courses[c].credits for c in mand) / profile.max_credits_per_term)
    return max(chain, credit), chain, credit


def proven_optimal(program, courses, profile, terms):
    """True if CP-SAT proves that terms-1 is infeasible."""
    if terms <= 1: return True
    mand, cand = candidates_for(program, courses, profile)
    model, x, taken, seasons, codes = _build_model(courses, profile, mand, cand, terms - 1)
    _add_elective_constraints(model, program, courses, taken, codes)
    s = cp_model.CpSolver(); s.parameters.max_time_in_seconds = 30
    return s.Solve(model) == cp_model.INFEASIBLE


def run_both(program, courses, profile):
    mand, cand = candidates_for(program, courses, profile)
    t0 = time.perf_counter(); a = solve_with_cpsat(program, courses, profile, mand, cand); ta = time.perf_counter() - t0
    t0 = time.perf_counter(); b = solve_with_backtracking(program, courses, profile, mand, cand); tb = time.perf_counter() - t0
    return a, ta, b, tb


def synthetic_catalog(n, density, seed):
    rng = random.Random(seed)
    courses = []
    levels = 6  # course levels (100- to 600-level); prerequisites come from the two levels below
    lvl = [min(levels - 1, i * levels // n) for i in range(n)]
    for i in range(n):
        pool = [j for j in range(i) if lvl[i] - 2 <= lvl[j] < lvl[i]]
        k = min(len(pool), 3, _poisson(rng, density))
        prereqs = rng.sample(pool, k) if k else []
        r = rng.random()
        offered = ["Fall", "Spring"] if r < 0.7 else (["Fall"] if r < 0.85 else ["Spring"])
        courses.append({"code": f"C{i:03d}", "title": f"Course {i}", "credits": 3 if rng.random() < 0.6 else 4,
                        "terms_offered": offered, "prereqs": [f"C{p:03d}" for p in prereqs],
                        "rating": round(rng.uniform(3.0, 5.0), 1)})
    codes = [c["code"] for c in courses]
    mand = sorted(rng.sample(codes, int(0.7 * n)))
    rest = [c for c in codes if c not in mand]; rng.shuffle(rest)
    half = len(rest) // 2
    pools = [{"name": f"Pool {j}", "candidate_codes": p, "min_count": math.ceil(len(p) / 3)} for j, p in enumerate((rest[:half], rest[half:])) if p]
    return parse_catalog({"id": f"syn-{n}-{density}-{seed}", "name": "synthetic", "courses": courses,
                          "mandatory_codes": mand, "electives": pools})


def _poisson(rng, lam):
    L, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= L: return k
        k += 1
