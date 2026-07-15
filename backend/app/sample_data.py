"""A toy but realistic CS degree catalog used for demos and tests."""

from app.models import Course, DegreeProgram, ElectivePool, Term

F = Term.FALL
S = Term.SPRING
SU = Term.SUMMER

COURSES: dict[str, Course] = {
    c.code: c
    for c in [
        Course("CS101", "Intro to Programming", 4, (F, S, SU), (), (), ("core",), 4.2),
        Course("CS102", "Data Structures", 4, (F, S), ("CS101",), (), ("core",), 4.0),
        Course("CS201", "Discrete Math", 3, (F, S), (), (), ("core", "math"), 3.6),
        Course("CS210", "Computer Organization", 4, (F,), ("CS102",), (), ("core",), 3.4, is_early_morning=True),
        Course("CS211", "Algorithms", 4, (F, S), ("CS102", "CS201"), (), ("core",), 4.5),
        Course("CS301", "Operating Systems", 4, (F,), ("CS210", "CS211"), (), ("core",), 3.9),
        Course("CS302", "Databases", 3, (S,), ("CS211",), (), ("core", "systems_elective"), 4.1),
        Course("CS310", "Computer Networks", 3, (S,), ("CS210",), (), ("systems_elective",), 3.7),
        Course("CS320", "Machine Learning", 4, (F,), ("CS211", "MATH220"), (), ("ai_elective",), 4.7),
        Course("CS321", "Artificial Intelligence", 3, (S,), ("CS211",), (), ("ai_elective",), 4.4),
        Course("CS330", "Computer Graphics", 3, (S,), ("CS211", "MATH210"), (), ("ai_elective", "theory_elective"), 4.0),
        Course("CS340", "Theory of Computation", 3, (F,), ("CS201", "CS211"), (), ("theory_elective", "core"), 3.5, is_early_morning=True),
        Course("CS350", "Distributed Systems", 3, (S,), ("CS301",), (), ("systems_elective",), 4.3),
        Course("CS360", "Security & Cryptography", 3, (F,), ("CS211", "MATH220"), (), ("systems_elective", "theory_elective"), 4.2),
        Course("CS400", "Senior Capstone", 4, (F, S), (), (), ("core",), 4.6),
        Course("CS420", "Deep Learning", 3, (S,), ("CS320",), (), ("ai_elective",), 4.8),
        Course("MATH210", "Calculus III", 4, (F, S), (), (), ("math",), 3.3, is_early_morning=True),
        Course("MATH220", "Linear Algebra", 3, (F, S), ("MATH210",), (), ("math",), 3.8),
        Course("MATH230", "Probability & Statistics", 3, (F, S), ("MATH210",), (), ("math", "ai_elective"), 3.9),
        Course("ENG101", "Composition", 3, (F, S, SU), (), (), ("humanities",), 3.5),
        Course("ENG205", "Technical Writing", 3, (F, S), ("ENG101",), (), ("humanities",), 3.7),
        Course("PHIL110", "Ethics", 3, (F, S), (), (), ("humanities",), 4.0),
        Course("HIST150", "Modern History", 3, (F, S), (), (), ("humanities",), 3.6),
        Course("ART120", "Intro to Design", 3, (F, S), (), (), ("humanities",), 3.9),
    ]
}

CS_DEGREE = DegreeProgram(
    name="B.S. Computer Science",
    mandatory_codes=(
        "CS101", "CS102", "CS201", "CS210", "CS211", "CS301", "CS302",
        "CS340", "CS400", "MATH210", "MATH220",
    ),
    electives=(
        ElectivePool("AI Track", ("CS320", "CS321", "CS330", "CS420", "MATH230"), min_credits=7),
        ElectivePool("Systems Track", ("CS310", "CS350", "CS360"), min_credits=6),
        ElectivePool("Humanities", ("ENG101", "ENG205", "PHIL110", "HIST150", "ART120"), min_credits=9),
    ),
)
