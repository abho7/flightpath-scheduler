"""Decompose the fallback's extra terms into (a) its greedy elective choice and
(b) its time-budgeted search. CP-SAT is re-run with the fallback's chosen course
set fixed as mandatory: the difference from free CP-SAT is the elective cost; the
rest of the gap is the search's. Usage: python experiments/exp_gap.py"""
import json
from common import synthetic_catalog, candidates_for
import app.solver.fallback_solver as fb
from app.models import DegreeProgram, StudentProfile
from app.solver.ortools_solver import solve_with_cpsat
rows = [json.loads(l) for l in open("results/synthetic.jsonl")]
with open("results/gap.jsonl", "w") as f:
    for r in rows:
        program, courses = synthetic_catalog(r["n"], r["density"], r["seed"])
        prof = StudentProfile(max_terms_horizon=20)
        electives, _ = fb._select_electives(program, courses, prof.completed_codes)
        mand, _ = candidates_for(program, courses, prof)
        chosen = fb._expand_prereq_closure(mand | electives, courses, prof.completed_codes)
        fixed = DegreeProgram(name="fixed", mandatory_codes=tuple(sorted(chosen)), electives=())
        g = solve_with_cpsat(fixed, courses, prof, set(chosen), set(chosen))
        out = {k: r[k] for k in ("n", "density", "seed", "cpsat_terms", "bt_terms", "bt_solver")}
        out["cpsat_with_greedy_electives"] = g.terms_used if g.feasible else None
        print(json.dumps(out), flush=True); f.write(json.dumps(out) + "\n")
