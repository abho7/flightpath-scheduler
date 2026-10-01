# Experiments

Scripts behind the AAI 2026 paper "Optimal Degree Planning as Constraint
Satisfaction". Run from `backend/`. Nothing in `app/` is modified. Raw outputs are in `results/`.

| Script | What it does |
|---|---|
| `exp_catalogs.py` | Bundled catalogs x credit caps 12/15/18/21, with and without credit for introductory required courses. Both solvers, lower bound, optimality certificate. |
| `exp_synthetic.py --seeds 0 1 2 3 4` | 100 generated catalogs (20-100 courses x 4 prerequisite densities x 5 seeds). Takes about 30 minutes. |
| `exp_gap.py` | Splits the fallback's extra terms into elective-choice cost and search cost (run after exp_synthetic). |
| `common.py` | Catalog generator, lower bound, optimality certificate (CP-SAT proves T-1 terms infeasible). |

A CP-SAT plan is "certified optimal" when the same model with one fewer term is proven infeasible.
