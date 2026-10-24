from app.core.security import hash_password, verify_password


def test_verify_password_matches_its_hash() -> None:
    assert verify_password("Correcta123", hash_password("Correcta123"))


def test_verify_password_rejects_a_wrong_password() -> None:
    assert not verify_password("Otra123456", hash_password("Correcta123"))


def test_verify_password_rejects_an_unreadable_hash() -> None:
    assert not verify_password("Correcta123", "not-an-argon2-hash")
