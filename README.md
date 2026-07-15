# Flightpath — Optimal Degree Scheduling

Find the fastest, highest-quality path through a college degree, respecting
prerequisites, course availability, credit-load limits, and elective
requirements — solved as a real constraint satisfaction / optimization
problem, not a heuristic checklist.

## The problem

University course scheduling is a bounded-horizon variant of the
[university timetabling problem](https://en.wikipedia.org/wiki/School_timetabling),
which is **NP-hard** — it generalizes bin packing (credit loads per term)
and graph coloring under precedence constraints (prerequisites). Given:

- A course catalog, where each course has a term-offering pattern (e.g.
  "only offered in Fall"), a prerequisite chain, a credit weight, and a
  quality score (instructor rating)
- A degree program with mandatory courses and elective pools ("take 7+
  credits from this AI/ML list")
- A student's completed courses and constraints (max credit load,
  starting term, whether they'll avoid 8am classes)

...find a term-by-term schedule that satisfies every requirement, in the
fewest number of terms, while maximizing course quality.

## How it's solved

Two solver backends, selected automatically:

**Primary — CP-SAT (Google OR-Tools)**
The scheduling problem is modeled as an integer program: boolean decision
variables `x[course, term]`, with prerequisite-ordering constraints,
credit-load capacity constraints, and elective-selection constraints (the
solver *chooses* which electives to take, not just how many). Solved in
two lexicographic phases:
  1. Minimize the number of terms needed to graduate.
  2. Fix that minimum, then maximize total course quality subject to a
     term-balance fairness bound.

**Fallback — pure-Python backtracking**
If OR-Tools isn't installed, a dependency-free backtracking search
(topological ordering + domain pruning + credit-load backtracking) finds
a feasible schedule instead. It isn't provably optimal, but it's a real
constraint-propagating search, not a greedy hack — and it means this repo
runs end-to-end with zero external solver dependencies.

Either way, the engine also does real correctness work up front:
cycle detection in the prerequisite graph (a catalog that requires A
before B before A is rejected with the exact cycle shown), and
satisfiability checks that surface *why* a plan is infeasible rather than
just returning "no."

## Architecture

```
backend/
  app/
    models.py            # Course, DegreeProgram, ElectivePool, StudentProfile
    sample_data.py        # toy CS degree catalog (24 courses, realistic prereq chains)
    solver/
      engine.py           # validation, cycle detection, term-calendar building, dispatch
      ortools_solver.py    # CP-SAT model (optimal)
      fallback_solver.py   # backtracking search (no external deps)
    main.py               # FastAPI app: /api/catalog, /api/solve, /api/health
  tests/
    test_engine.py         # correctness properties: prereq ordering, credit caps,
                            # no double-scheduling, elective minimums met, cycle detection

frontend/
  src/
    App.jsx               # control panel + route board + live dependency graph
    api.js
    styles.css            # "flight plan" visual system
```

### Why two solvers

This is a deliberate engineering decision, not a fallback-because-I-had-to:
OR-Tools gives a *provably optimal* schedule, but requiring it as a hard
dependency makes the project fragile to demo. The backtracking solver is a
legitimate constraint-satisfaction implementation in its own right (real
topological ordering, real domain pruning, real backtracking on
credit-overflow) — useful to walk through in an interview if asked "how
would you solve this without a solver library?"

## Running it

**Backend**
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

Then open `http://localhost:5173`. The dev server proxies `/api` to
`localhost:8000`.

**Tests**
```bash
cd backend
pytest tests/ -v
```

## The frontend

The UI reframes the schedule as a flight plan: each term is a column
("flight strip"), each course a chip, and prerequisite chains are drawn as
connecting routes between chips — with the *critical path* (the actual
chain of prerequisites determining how many terms you need) highlighted in
amber. It's computed live from the DOM positions of the rendered course
chips, not hardcoded coordinates.

## Extending it

- Swap `sample_data.py` for a real university catalog (most registrars
  publish course data as JSON/CSV or via an API)
- Add professor-specific sections instead of one rating per course
- Add a "what-if" mode: change your major and see which credits transfer
- Persist student profiles instead of re-entering completed courses each
  session
