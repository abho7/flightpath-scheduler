"""
FastAPI app exposing the course-scheduling engine.

Endpoints:
  GET  /api/catalogs             -> list available degree catalogs (id, name, description)
  GET  /api/catalog/{catalog_id} -> full course catalog + degree program for one catalog
  POST /api/solve                -> run the solver for a given student profile + catalog
  POST /api/catalog/validate     -> validate a custom uploaded catalog without solving
  GET  /api/health               -> liveness check + which solver backend is active
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.catalog_loader import (
    CatalogError,
    list_catalogs,
    load_catalog_by_id,
    parse_catalog,
)
from app.models import Course, DegreeProgram, StudentProfile, Term
from app.solver.engine import solve_schedule

app = FastAPI(title="Course Scheduling Optimizer", version="1.1.0")

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


def _serialize_catalog(program: DegreeProgram, courses: dict[str, Course]) -> dict:
    return {
        "program": {
            "name": program.name,
            "mandatory_codes": list(program.mandatory_codes),
            "electives": [
                {
                    "name": pool.name,
                    "candidate_codes": list(pool.candidate_codes),
                    "min_credits": pool.min_credits,
                    "min_count": pool.min_count,
                }
                for pool in program.electives
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
            for code, c in courses.items()
        },
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "solver_backend": _active_solver_name()}


@app.get("/api/catalogs")
def get_catalogs():
    """Lightweight list for populating a catalog picker in the UI."""
    return {"catalogs": list_catalogs()}


@app.get("/api/catalog/{catalog_id}")
def get_catalog(catalog_id: str):
    try:
        program, courses = load_catalog_by_id(catalog_id)
    except CatalogError as e:
        raise HTTPException(404, str(e))
    return _serialize_catalog(program, courses)


class SolveRequest(BaseModel):
    catalog_id: str | None = None
    custom_catalog: dict | None = None
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


def _resolve_catalog(req: "SolveRequest") -> tuple[DegreeProgram, dict[str, Course]]:
    if req.custom_catalog:
        try:
            return parse_catalog(req.custom_catalog)
        except CatalogError as e:
            raise HTTPException(400, f"Invalid custom catalog: {e}")
    if req.catalog_id:
        try:
            return load_catalog_by_id(req.catalog_id)
        except CatalogError as e:
            raise HTTPException(404, str(e))
    raise HTTPException(400, "Request must include either 'catalog_id' or 'custom_catalog'.")


@app.post("/api/catalog/validate")
def validate_catalog(catalog: dict):
    try:
        program, courses = parse_catalog(catalog)
    except CatalogError as e:
        return {"valid": False, "error": str(e)}
    return {
        "valid": True,
        "course_count": len(courses),
        "mandatory_count": len(program.mandatory_codes),
        "elective_pool_count": len(program.electives),
    }


@app.post("/api/solve", response_model=SolveResponse)
def solve(req: SolveRequest):
    program, courses = _resolve_catalog(req)

    unknown = [c for c in req.completed_codes if c not in courses]
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

    result = solve_schedule(program, courses, profile)

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

