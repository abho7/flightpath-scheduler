# Flightpath

A tool that plans out which courses to take, and in which term, to finish a
college degree as fast as possible without breaking any prerequisites,
credit limits, or elective requirements. It's not a checklist app. It's an
actual constraint solver.

## Difficulty

Scheduling courses across a degree is a version of the university
timetabling problem, which is NP-hard: it's got a bin-packing element
(credit limits per term) and a graph-coloring element (prerequisites have
to happen in the right order). Given a course catalog, a degree's
requirements, and what a student has already completed, you have to find
a term-by-term plan that satisfies everything and does it in as few
semesters as possible, while also trying to pick good electives.

That's genuinely hard to brute-force once a catalog has more than a
handful of courses, which is most of why this project exists: to build
and test a real solver for it, not to fake one with nested if-statements.

## How it actually solves it

There are two solver backends, and the app picks whichever one is
available.

The main one uses Google's OR-Tools CP-SAT solver. The problem gets
modeled as an integer program: a boolean variable for every
(course, term) pair, prerequisite constraints that force a course's
prereqs into strictly earlier terms, credit-cap constraints per term, and
constraints for elective pools where the solver actually chooses which
courses to take, not just how many. It solves in two passes: first it
finds the minimum number of terms needed, then it locks that in and
re-solves to maximize course quality (using instructor ratings) without
overloading any one term.

If OR-Tools isn't installed, there's a fallback: a backtracking search
written from scratch, no external solver. It does topological ordering
on prerequisites, prunes terms that don't fit credit-wise, and backtracks
when it hits a dead end. It's not guaranteed optimal the way CP-SAT is,
and on denser catalogs it can run into the same exponential blowup any
naive backtracking search runs into, so there's a time budget on it that
falls back to a simple greedy placement if the real search doesn't finish
in time. This exists so the project runs with zero dependencies out of
the box, and honestly it's also just a legitimate thing to point to if
someone asks how you'd solve this without a library.

Before either solver runs, the engine checks the catalog for
contradictions, like a prerequisite cycle (course A needs course B needs
course A), and reports exactly where the cycle is instead of just failing.

## Multiple degrees, not just one

The scheduler doesn't hardcode a single major. Catalogs live as JSON
files in `backend/app/catalogs/`, and there are three included as
templates: a generic CS degree, a generic business degree, and a generic
psychology degree. None of them are copied from a real university, they're
representative structures meant to be swapped out. See
[CATALOG_GUIDE.md](./CATALOG_GUIDE.md) for how to build one for your
actual school.

## Project layout

```
backend/
  app/
    models.py            # Course, DegreeProgram, ElectivePool, StudentProfile
    catalog_loader.py     # loads/validates catalogs from app/catalogs/*.json
    catalogs/              # cs-generic.json, business-generic.json, psychology-generic.json
    solver/
      engine.py           # validation, cycle detection, term-calendar building, dispatch
      ortools_solver.py    # CP-SAT model, the optimal path
      fallback_solver.py   # backtracking search, no external deps
    main.py               # FastAPI app: /api/catalogs, /api/catalog/{id}, /api/solve, /api/health
  tests/
    test_engine.py         # prereq ordering, credit caps, no double-scheduling, cycle detection
    test_catalogs.py        # every shipped catalog solves and doesn't hang

frontend/
  src/
    App.jsx               # program picker + control panel + route board + dependency graph
    api.js
    styles.css
```

## Running it

Backend:
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The dev server proxies `/api` calls to
`localhost:8000`.

Tests:
```bash
cd backend
pytest tests/ -v
```

## About the frontend

The UI treats the schedule like a flight plan instead of a spreadsheet.
Each term is a column, each course is a chip, and prerequisite chains are
drawn as connecting lines between chips, computed live from where the
course cards actually land on the page. The chain of prerequisites that's
actually forcing the number of terms (the critical path) gets highlighted
so it's obvious what's driving the timeline, not just what's in it.

