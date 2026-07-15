from __future__ import annotations

from app.models import Course, DegreeProgram, ScheduleResult, StudentProfile, Term

SEASON_CYCLE_NO_SUMMER = [Term.FALL, Term.SPRING]
SEASON_CYCLE_WITH_SUMMER = [Term.FALL, Term.SPRING, Term.SUMMER]


def build_term_calendar(profile: StudentProfile, n_terms: int) -> list[Term]:
    """Return the season (Fall/Spring/Summer) for each of the next n_terms."""
    cycle = SEASON_CYCLE_WITH_SUMMER if profile.include_summers else SEASON_CYCLE_NO_SUMMER
    start_idx = cycle.index(profile.starting_season) if profile.starting_season in cycle else 0
    return [cycle[(start_idx + i) % len(cycle)] for i in range(n_terms)]


def detect_prereq_cycle(courses: dict[str, Course]) -> list[str] | None:
    """DFS cycle detection over the prereq graph. Returns a cycle path if found."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {code: WHITE for code in courses}
    path: list[str] = []

    def dfs(node: str) -> list[str] | None:
        color[node] = GRAY
        path.append(node)
        for p in courses[node].prereqs:
            if p not in courses:
                continue
            if color.get(p, WHITE) == GRAY:
                cycle_start = path.index(p)
                return path[cycle_start:] + [p]
            if color.get(p, WHITE) == WHITE:
                result = dfs(p)
                if result:
                    return result
        path.pop()
        color[node] = BLACK
        return None

    for code in courses:
        if color[code] == WHITE:
            cycle = dfs(code)
            if cycle:
                return cycle
    return None


def resolve_required_set(
    program: DegreeProgram, courses: dict[str, Course], completed: set[str]
) -> tuple[set[str], list[str]]:
    errors = []
    for code in program.mandatory_codes:
        if code not in courses:
            errors.append(f"Mandatory course '{code}' is not in the catalog.")
    for pool in program.electives:
        for code in pool.candidate_codes:
            if code not in courses:
                errors.append(f"Elective pool '{pool.name}' references unknown course '{code}'.")
    mandatory_remaining = {c for c in program.mandatory_codes if c not in completed and c in courses}
    return mandatory_remaining, errors


def validate_prereqs_satisfiable(
    courses: dict[str, Course], candidate_codes: set[str], completed: set[str]
) -> list[str]:
    problems = []
    for code in candidate_codes:
        for p in courses[code].prereqs:
            if p in completed:
                continue
            if p not in courses:
                problems.append(f"{code} requires '{p}', which does not exist in the catalog.")
            elif p not in candidate_codes:
                problems.append(
                    f"{code} requires '{p}', which is neither completed nor otherwise scheduled."
                )
    return problems


def solve_schedule(
    program: DegreeProgram,
    courses: dict[str, Course],
    profile: StudentProfile,
) -> ScheduleResult:
    cycle = detect_prereq_cycle(courses)
    if cycle:
        return ScheduleResult(
            feasible=False,
            reason="Prerequisite cycle detected -- this catalog is contradictory.",
            conflicts=[" -> ".join(cycle)],
        )

    mandatory_remaining, errors = resolve_required_set(program, courses, profile.completed_codes)
    if errors:
        return ScheduleResult(feasible=False, reason="Catalog validation failed.", conflicts=errors)

    candidates = set(mandatory_remaining)
    for pool in program.electives:
        candidates |= {c for c in pool.candidate_codes if c not in profile.completed_codes}

    prereq_problems = validate_prereqs_satisfiable(courses, candidates, profile.completed_codes)
    if prereq_problems:
        return ScheduleResult(
            feasible=False,
            reason="Some prerequisites can never be satisfied with this catalog/history.",
            conflicts=prereq_problems,
        )

    try:
        from app.solver.ortools_solver import solve_with_cpsat

        return solve_with_cpsat(program, courses, profile, mandatory_remaining, candidates)
    except ImportError:
        from app.solver.fallback_solver import solve_with_backtracking

        return solve_with_backtracking(program, courses, profile, mandatory_remaining, candidates)
