"""Synthetic catalogs: size n x prerequisite density x seeds. Compares CP-SAT and the
backtracking fallback against a lower bound. Usage: python experiments/exp_synthetic.py --seeds 0 1 2"""
import argparse, json
from common import synthetic_catalog, run_both, lower_bound, proven_optimal
from app.models import StudentProfile
ap = argparse.ArgumentParser(); ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
ap.add_argument("--out", default="results/synthetic.jsonl"); a = ap.parse_args()
with open(a.out, "a") as f:
    for seed in a.seeds:
        for n in (20, 40, 60, 80, 100):
            for d in (0.5, 1.0, 1.5, 2.0):
                program, courses = synthetic_catalog(n, d, seed)
                prof = StudentProfile(max_terms_horizon=20)
                cp, tc, bt, tb = run_both(program, courses, prof)
                lb, chain, credit = lower_bound(program, courses, prof)
                row = {"n": n, "density": d, "seed": seed, "edges": sum(len(c.prereqs) for c in courses.values()),
                       "lb": lb, "lb_chain": chain, "lb_credit": credit,
                       "cpsat_feasible": cp.feasible, "cpsat_terms": cp.terms_used, "cpsat_s": tc, "cpsat_reason": cp.reason,
                       "cpsat_proven": proven_optimal(program, courses, prof, cp.terms_used) if cp.feasible else None,
                       "bt_feasible": bt.feasible, "bt_terms": bt.terms_used, "bt_s": tb, "bt_solver": bt.solver_used}
                print(json.dumps(row), flush=True); f.write(json.dumps(row) + "\n"); f.flush()
