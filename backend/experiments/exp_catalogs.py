"""Bundled catalogs: both solvers at several per-term credit caps, and with
AP/transfer credit for every introductory (no-prerequisite) required course.
Usage: python experiments/exp_catalogs.py"""
import json
from common import run_both, lower_bound, proven_optimal, candidates_for
from app.catalog_loader import list_catalogs, load_catalog_by_id
from app.models import StudentProfile
with open("results/catalogs.jsonl", "w") as f:
    for meta in list_catalogs():
        cid = meta["id"] if isinstance(meta, dict) else meta
        program, courses = load_catalog_by_id(cid)
        intro = {c for c in program.mandatory_codes if not courses[c].prereqs}
        for cap in (12, 15, 18, 21):
            for scenario, done in (("none", set()), ("intro_credit", intro)):
                prof = StudentProfile(max_credits_per_term=cap, completed_codes=set(done), max_terms_horizon=16)
                cp, tc, bt, tb = run_both(program, courses, prof)
                lb = lower_bound(program, courses, prof)[0]
                row = {"catalog": cid, "courses": len(courses), "cap": cap, "scenario": scenario, "n_credit": len(done), "lb": lb,
                       "cpsat_terms": cp.terms_used if cp.feasible else None, "cpsat_s": tc, "cpsat_rating": cp.avg_rating,
                       "cpsat_proven": proven_optimal(program, courses, prof, cp.terms_used) if cp.feasible else None,
                       "bt_terms": bt.terms_used if bt.feasible else None, "bt_s": tb, "bt_solver": bt.solver_used, "bt_rating": bt.avg_rating}
                print(json.dumps(row), flush=True); f.write(json.dumps(row) + "\n")
