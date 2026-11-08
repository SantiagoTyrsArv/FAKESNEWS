import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, TypeAdapter

Kind = Literal["false", "true", "mixed", "invented"]
Verdict = Literal["SUPPORTED", "CHANGED", "CONTRADICTED", "INSUFFICIENT"]


class Case(BaseModel):
    """One claim already rated by a published fact-check."""

    id: str
    factchecker: str
    factcheck_url: str
    factcheck_date: date
    rating: str  # the fact-checker's own wording, e.g. "Falso" or "Engañoso"
    kind: Kind
    claim: str  # as the fact-checker phrased it
    # A trusted outlet, not a fact-checker, with the data to decide: proof the
    # case can be answered in blind mode. Not used when grading.
    coverage_url: str | None = None


def load_cases(path: Path) -> list[Case]:
    cases = TypeAdapter(list[Case]).validate_python(json.loads(path.read_text(encoding="utf-8")))
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            raise ValueError(f"id de caso repetido: {case.id}")
        seen.add(case.id)
    return cases
