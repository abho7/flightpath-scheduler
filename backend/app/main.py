"""
FastAPI app exposing the course-scheduling engine.

Endpoints:
  GET  /api/catalog          -> full course catalog + degree program
  POST /api/solve            -> run the solver for a given student profile
  GET  /api/health           -> liveness check + which solver backend is active
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.models import DegreeProgram, StudentProfile, Term
from app.sample_data import COURSES, CS_DEGREE
from app.solver.engine import solve_schedule

app = FastAPI(title="Course Scheduling Optimizer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _active_solver_name() -> str:
    try:
        import ortools  # noqa: F401

        return "cp-sat (OR-Tools) -- optimal"
    except ImportError:
        return "backtracking fallback -- heuristic, install ortools for optimal solving"


@app.get("/api/health")
def health():
    return {"status": "ok", "solver_backend": _active_solver_name()}


@app.get("/api/catalog")
def get_catalog():
    return {
        "program": {
            "name": CS_DEGREE.name,
            "mandatory_codes": list(CS_DEGREE.mandatory_codes),
            "electives": [
                {
                    "name": pool.name,
                    "candidate_codes": list(pool.candidate_codes),
                    "min_credits": pool.min_credits,
                    "min_count": pool.min_count,
                }
                for pool in CS_DEGREE.electives
            ],
        },
        "courses": {
            code: {
                "code": c.code,
                "title": c.title,
                "credits": c.credits,
                "terms_offered": [t.value for t in c.terms_offered],
                "prereqs": list(c.prereqs),
                "categories": list(c.categories),
                "rating": c.rating,
                "is_early_morning": c.is_early_morning,
            }
            for code, c in COURSES.items()
        },
    }


class SolveRequest(BaseModel):
    completed_codes: list[str] = Field(default_factory=list)
    max_credits_per_term: int = 18
    min_credits_per_term: int = 12
    avoid_early_morning: bool = False
    starting_season: str = "Fall"
    include_summers: bool = False
    max_terms_horizon: int = 10


class SolveResponse(BaseModel):
    feasible: bool
    terms_used: int
    assignment: dict[str, int]
    term_labels: list[str]
    total_credits: dict[str, int]
    avg_rating: float
    reason: str | None
    conflicts: list[str]
    solver_used: str


@app.post("/api/solve", response_model=SolveResponse)
def solve(req: SolveRequest):
    unknown = [c for c in req.completed_codes if c not in COURSES]
    if unknown:
        raise HTTPException(400, f"Unknown completed course codes: {unknown}")

    try:
        starting_season = Term(req.starting_season)
    except ValueError:
        raise HTTPException(400, f"Invalid starting_season '{req.starting_season}'")

    profile = StudentProfile(
        completed_codes=set(req.completed_codes),
        max_credits_per_term=req.max_credits_per_term,
        min_credits_per_term=req.min_credits_per_term,
        avoid_early_morning=req.avoid_early_morning,
        starting_season=starting_season,
        include_summers=req.include_summers,
        max_terms_horizon=req.max_terms_horizon,
    )

    result = solve_schedule(CS_DEGREE, COURSES, profile)

    return SolveResponse(
        feasible=result.feasible,
        terms_used=result.terms_used,
        assignment=result.assignment,
        term_labels=result.term_labels,
        total_credits={str(k): v for k, v in result.total_credits.items()},
        avg_rating=result.avg_rating,
        reason=result.reason,
        conflicts=result.conflicts,
        solver_used=result.solver_used,
    )
