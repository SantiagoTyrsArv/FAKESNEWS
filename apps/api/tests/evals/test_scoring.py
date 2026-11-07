import pytest

from evals.verdicts.scoring import domain_matches, grade, is_contaminated


@pytest.mark.parametrize(
    ("kind", "got", "expected"),
    [
        ("false", "CONTRADICTED", "ok"),
        ("false", "INSUFFICIENT", "fail"),
        ("false", "SUPPORTED", "severe"),
        ("false", "CHANGED", "fail"),
        ("true", "SUPPORTED", "ok"),
        ("true", "INSUFFICIENT", "fail"),
        ("true", "CONTRADICTED", "severe"),
        ("true", "CHANGED", "fail"),
        ("mixed", "CHANGED", "ok"),
        ("mixed", "CONTRADICTED", "fail"),
        ("mixed", "INSUFFICIENT", "fail"),
        ("mixed", "SUPPORTED", "severe"),
        ("invented", "INSUFFICIENT", "ok"),
        ("invented", "CONTRADICTED", "fail"),
        ("invented", "SUPPORTED", "severe"),
        ("invented", "CHANGED", "fail"),
    ],
)
def test_grade(kind: str, got: str, expected: str) -> None:
    assert grade(kind, got) == expected


def test_domain_matches_subdomain() -> None:
    assert domain_matches("factual.afp.com", "afp.com")
    assert domain_matches("afp.com", "afp.com")
    assert not domain_matches("notafp.com", "afp.com")
    # Evidence is stored under the trusted domain (PR #51); the case names the desk.
    assert domain_matches("afp.com", "factual.afp.com")


def test_is_contaminated() -> None:
    assert is_contaminated(["reuters.com", "colombiacheck.com"], "colombiacheck.com")
    assert not is_contaminated(["reuters.com"], "colombiacheck.com")
    assert not is_contaminated([], "colombiacheck.com")
