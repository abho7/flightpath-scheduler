"""
Domain models for the course scheduling engine.

The scheduling problem, formally:

  Given a set of courses C, each with prerequisites, terms-offered,
  credit weight, and quality score, and a set of degree requirements
  (mandatory courses + elective pools with credit/count minimums),
  find an assignment of courses to terms (semesters) such that:

    1. Every mandatory course is scheduled exactly once.
    2. Every elective pool's minimum is satisfied by courses drawn
       from that pool.
    3. A course is only scheduled in a term it is actually offered.
    4. A course's prerequisites are all completed in a strictly
       earlier term (or already completed before term 0).
    5. No term exceeds the student's max credit load.
    6. No course is scheduled more than once.

  Objective (lexicographic, in priority order):
    (a) Minimize the number of terms needed to graduate.
    (b) Within that minimum, maximize total course quality
        (professor rating) subject to a fairness bound on
        per-term credit load imbalance.

This is a bounded-horizon variant of university timetabling, which is
NP-hard in general (it generalizes bin packing + graph coloring under
precedence constraints). We solve it with CP-SAT when available,
falling back to a constraint-propagating backtracking search
otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Term(str, Enum):
    FALL = "Fall"
    SPRING = "Spring"
    SUMMER = "Summer"


@dataclass(frozen=True)
class Course:
    code: str
    title: str
    credits: int
    terms_offered: tuple[Term, ...]
    prereqs: tuple[str, ...] = ()
    coreqs: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()
    rating: float = 3.5
    is_early_morning: bool = False


@dataclass(frozen=True)
class ElectivePool:
    """A degree requirement satisfied by choosing from a set of courses."""
    name: str
    candidate_codes: tuple[str, ...]
    min_credits: int = 0
    min_count: int = 0


@dataclass(frozen=True)
class DegreeProgram:
    name: str
    mandatory_codes: tuple[str, ...]
    electives: tuple[ElectivePool, ...] = ()


@dataclass
class StudentProfile:
    completed_codes: set[str] = field(default_factory=set)
    max_credits_per_term: int = 18
    min_credits_per_term: int = 12
    avoid_early_morning: bool = False
    starting_term_index: int = 0
    starting_season: Term = Term.FALL
    include_summers: bool = False
    max_terms_horizon: int = 10


@dataclass
class ScheduleResult:
    feasible: bool
    terms_used: int = 0
    assignment: dict[str, int] = field(default_factory=dict)
    term_labels: list[str] = field(default_factory=list)
    total_credits: dict[int, int] = field(default_factory=dict)
    avg_rating: float = 0.0
    reason: str | None = None
    conflicts: list[str] = field(default_factory=list)
    solver_used: str = "unknown"
