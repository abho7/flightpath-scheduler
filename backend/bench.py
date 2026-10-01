import time, statistics
from app.catalog_loader import list_catalogs, load_catalog_by_id
from app.models import StudentProfile
from app.solver.engine import resolve_required_set
from app.solver.ortools_solver import solve_with_cpsat
from app.solver.fallback_solver import solve_with_backtracking
for meta in list_catalogs():
    cid = meta["id"] if isinstance(meta, dict) else meta
    prog, courses = load_catalog_by_id(cid)
    prof = StudentProfile()
    mand, err = resolve_required_set(prog, courses, prof.completed_codes)
    cand = set(mand)
    for p in prog.electives: cand |= set(p.candidate_codes)
    edges = sum(len(c.prereqs) for c in courses.values())
    row=[cid, len(courses), edges]
    for fn in (solve_with_cpsat, solve_with_backtracking):
        ts=[]; 
        for _ in range(5):
            t=time.perf_counter(); r=fn(prog,courses,prof,mand,cand); ts.append(time.perf_counter()-t)
        row += [r.feasible, r.terms_used, round(statistics.median(ts)*1000,1), round(r.avg_rating,2)]
    print(row)
