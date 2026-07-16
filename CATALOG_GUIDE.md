# Adding your own school's catalog

The scheduler doesn't know anything about a specific university. It reads
degree catalogs from JSON files in `backend/app/catalogs/`, and three
generic ones ship with the repo (`cs-generic`, `business-generic`,
`psychology-generic`) as templates. To make the tool actually plan your
real degree, you build a catalog file for your school and major.

## Where to get the data

Most registrars publish this somewhere, even if it's not obviously an
"API":

- Your degree audit / "what-if" tool, if your school has one, usually
  lists every requirement category and how many credits each needs
- The course catalog site (search "[your school] course catalog") lists
  every course's credit weight and prerequisites
- The schedule of classes for the last few terms tells you which
  semesters each course is actually offered in
- RateMyProfessors or your school's own course-eval system gives you
  something to use for the `rating` field, or just leave it at a flat
  default if you don't want to bother

This is manual work -- there's no scraper here that does it for you,
partly because catalog page structure differs by school and partly
because scraping a school's site without permission can violate its
terms of service. Copy-pasting the data by hand into the JSON format
below is slower but doesn't have that problem.

## The schema

```json
{
  "id": "my-school-cs",
  "name": "B.S. Computer Science, My University",
  "description": "One or two sentences describing the program.",
  "courses": [
    {
      "code": "CS101",
      "title": "Intro to Programming",
      "credits": 4,
      "terms_offered": ["Fall", "Spring"],
      "prereqs": [],
      "categories": ["core"],
      "rating": 4.2,
      "is_early_morning": false
    }
  ],
  "mandatory_codes": ["CS101"],
  "electives": [
    {
      "name": "AI Track",
      "candidate_codes": ["CS320", "CS321"],
      "min_credits": 6
    }
  ]
}
```

A few notes on the fields:

- `terms_offered` only accepts `"Fall"`, `"Spring"`, and `"Summer"`.
- `prereqs` is a list of course codes, referring to the `code` field of
  other courses in the same file. Leave it empty for courses with no
  prerequisites.
- `categories` is mostly cosmetic right now -- it's used to group the
  "already completed" checklist in the sidebar by section. It doesn't
  need to match anything in `electives`.
- `rating` and `is_early_morning` are optional. `rating` defaults to 3.5
  and `is_early_morning` to `false` if omitted, which is fine if you
  don't want to track this.
- `mandatory_codes` is every course code that must be taken exactly
  once, no matter what.
- `electives` is a list of pools, where each pool needs either
  `min_credits`, `min_count`, or both satisfied from its
  `candidate_codes`. The solver picks *which* courses from the pool to
  take, so you don't need to decide that ahead of time.

## Checking your file is valid

Before wiring it into the UI, you can sanity-check the JSON directly:

```python
from app.catalog_loader import parse_catalog
import json

data = json.load(open("app/catalogs/my-school-cs.json"))
program, courses = parse_catalog(data)
print(f"{len(courses)} courses, {len(program.mandatory_codes)} mandatory")
```

If a course code in `prereqs`, `mandatory_codes`, or a pool's
`candidate_codes` doesn't match any `code` in `courses`, the solver will
catch it and tell you exactly which course and which missing reference
caused the problem -- it won't fail silently.

## Dropping it in

Save the file as `backend/app/catalogs/your-id.json` and restart the
backend. It'll show up automatically in the program picker in the UI --
no code changes needed anywhere else.
