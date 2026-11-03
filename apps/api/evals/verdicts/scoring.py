from typing import Literal

from app.modules.sources.service import normalize_domain
from evals.verdicts.cases import Kind, Verdict

Grade = Literal["ok", "fail", "severe", "error"]

# Verdicts that count as right for each kind of fact-check rating.
EXPECTED: dict[Kind, frozenset[Verdict]] = {
    "false": frozenset({"CONTRADICTED"}),
    "true": frozenset({"SUPPORTED"}),
    "mixed": frozenset({"CONTRADICTED", "INSUFFICIENT"}),
}

# The verdict that is not just wrong but backwards for each kind.
_SEVERE: dict[Kind, Verdict] = {
    "false": "SUPPORTED",
    "true": "CONTRADICTED",
    "mixed": "SUPPORTED",
}


def grade(kind: Kind, got: Verdict) -> Grade:
    if got in EXPECTED[kind]:
        return "ok"
    if got == _SEVERE[kind]:
        return "severe"
    return "fail"


def domain_matches(domain: str, factchecker: str) -> bool:
    """Same domain, or one a subdomain of the other: evidence is stored
    under the trusted domain (afp.com) while a case names the desk
    (factual.afp.com)."""
    a, b = normalize_domain(domain), normalize_domain(factchecker)
    return a == b or a.endswith("." + b) or b.endswith("." + a)


def is_contaminated(evidence_domains: list[str], factchecker: str) -> bool:
    """Whether the verdict leaned on the fact-checker's own article."""
    return any(domain_matches(d, factchecker) for d in evidence_domains)
