from evals.verdicts.blind import FACTCHECKER_DOMAINS, blind_domains

ALLOWED = [
    "reuters.com",
    "afp.com",
    "bbc.com",
    "colombiacheck.com",
    "lasillavacia.com",
    "chequeado.com",
    "maldita.es",
    "politifact.com",
    "factcheck.org",
    "eltiempo.com",
]
WITHOUT_FACTCHECKERS = ["reuters.com", "afp.com", "bbc.com", "eltiempo.com"]


def test_factchecker_list_is_the_specs() -> None:
    assert {
        "colombiacheck.com",
        "lasillavacia.com",
        "chequeado.com",
        "maldita.es",
        "politifact.com",
        "factcheck.org",
    } == FACTCHECKER_DOMAINS


def test_blind_removes_every_factchecker() -> None:
    assert blind_domains(ALLOWED, "newtral.es") == WITHOUT_FACTCHECKERS


def test_blind_removes_the_cases_own_outlet() -> None:
    assert blind_domains(ALLOWED, "bbc.com") == ["reuters.com", "afp.com", "eltiempo.com"]


def test_blind_removes_parent_of_a_subdomain_factchecker() -> None:
    assert "afp.com" not in blind_domains(ALLOWED, "factual.afp.com")


def test_blind_normalizes_the_factchecker() -> None:
    assert "bbc.com" not in blind_domains(ALLOWED, "WWW.BBC.com")


def test_blind_with_empty_factchecker_only_drops_factcheckers() -> None:
    assert blind_domains(ALLOWED, "") == WITHOUT_FACTCHECKERS


def test_blind_does_not_mutate_its_input() -> None:
    before = list(ALLOWED)
    blind_domains(ALLOWED, "bbc.com")
    assert before == ALLOWED
