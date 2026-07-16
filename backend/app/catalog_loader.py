"""
Loads degree catalogs from JSON files in app/catalogs/.

This is what makes the scheduler usable for more than one hardcoded
degree: instead of a single Python module with one baked-in program,
any school/major can be represented as a JSON file following this
schema, dropped into app/catalogs/, and it's immediately selectable.

Schema (see app/catalogs/*.json for real examples):

{
  "id": "cs-generic",
  "name": "B.S. Computer Science (generic 4-year)",
  "description": "A representative CS degree structure ...",
  "courses": [
    {
      "code": "CS101",
      "title": "Intro to Programming",
      "credits": 4,
      "terms_offered": ["Fall", "Spring", "Summer"],
      "prereqs": [],
      "categories": ["core"],
      "rating": 4.2,
      "is_early_morning": false
    }
  ],
  "mandatory_codes": ["CS101", "..."],
  "electives": [
    {
      "name": "AI Track",
      "candidate_codes": ["CS320", "CS321"],
      "min_credits": 7,
      "min_count": 0
    }
  ]
}

See CATALOG_GUIDE.md at the repo root for a walkthrough of building a
catalog for your own school.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models import Course, DegreeProgram, ElectivePool, Term

CATALOG_DIR = Path(__file__).parent / "catalogs"


class CatalogError(Exception):
    pass


def _parse_course(raw: dict) -> Course:
    try:
        terms = tuple(Term(t) for t in raw["terms_offered"])
    except ValueError as e:
        raise CatalogError(f"Course '{raw.get('code')}' has an invalid term name: {e}")

    return Course(
        code=raw["code"],
        title=raw["title"],
        credits=raw["credits"],
        terms_offered=terms,
        prereqs=tuple(raw.get("prereqs", [])),
        coreqs=tuple(raw.get("coreqs", [])),
        categories=tuple(raw.get("categories", [])),
        rating=raw.get("rating", 3.5),
        is_early_morning=raw.get("is_early_morning", False),
    )


def parse_catalog(data: dict) -> tuple[DegreeProgram, dict[str, Course]]:
    required_keys = {"id", "name", "courses", "mandatory_codes"}
    missing = required_keys - data.keys()
    if missing:
        raise CatalogError(f"Catalog is missing required fields: {sorted(missing)}")

    courses = {}
    for raw in data["courses"]:
        if "code" not in raw:
            raise CatalogError("A course entry is missing 'code'.")
        courses[raw["code"]] = _parse_course(raw)

    electives = tuple(
        ElectivePool(
            name=pool["name"],
            candidate_codes=tuple(pool["candidate_codes"]),
            min_credits=pool.get("min_credits", 0),
            min_count=pool.get("min_count", 0),
        )
        for pool in data.get("electives", [])
    )

    program = DegreeProgram(
        name=data["name"],
        mandatory_codes=tuple(data["mandatory_codes"]),
        electives=electives,
    )

    return program, courses


def load_catalog_file(path: Path) -> tuple[str, DegreeProgram, dict[str, Course]]:
    data = json.loads(path.read_text())
    program, courses = parse_catalog(data)
    return data["id"], program, courses


def list_catalogs() -> list[dict]:
    """Metadata for every catalog in app/catalogs/, without fully parsing courses."""
    results = []
    for path in sorted(CATALOG_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        results.append({
            "id": data.get("id", path.stem),
            "name": data.get("name", path.stem),
            "description": data.get("description", ""),
            "course_count": len(data.get("courses", [])),
        })
    return results


def load_catalog_by_id(catalog_id: str) -> tuple[DegreeProgram, dict[str, Course]]:
    for path in CATALOG_DIR.glob("*.json"):
        data = json.loads(path.read_text())
        if data.get("id") == catalog_id:
            return parse_catalog(data)
    raise CatalogError(f"No catalog found with id '{catalog_id}'.")
