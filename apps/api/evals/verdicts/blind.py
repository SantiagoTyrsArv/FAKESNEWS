from evals.verdicts.scoring import domain_matches

# Trusted sources that publish fact-check ratings. La Silla Vacía is also an
# outlet, but its «Detector de mentiras» rates claims, so it counts here.
FACTCHECKER_DOMAINS = frozenset(
    {
        "colombiacheck.com",
        "lasillavacia.com",
        "chequeado.com",
        "maldita.es",
        "politifact.com",
        "factcheck.org",
    }
)


def blind_domains(allowed_domains: list[str], factchecker: str) -> list[str]:
    """The trusted domains left once the fact-checkers, and the case's own
    source, are taken out: what a search with no published answer sees."""
    excluded = set(FACTCHECKER_DOMAINS)
    if factchecker.strip():
        excluded.add(factchecker)
    return [d for d in allowed_domains if not any(domain_matches(d, e) for e in excluded)]
