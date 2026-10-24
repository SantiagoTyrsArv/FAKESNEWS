from app.core.security import hash_password, validate_password_strength, verify_password


def test_verify_password_matches_its_hash() -> None:
    assert verify_password("Correcta123", hash_password("Correcta123"))


def test_verify_password_rejects_a_wrong_password() -> None:
    assert not verify_password("Otra123456", hash_password("Correcta123"))


def test_verify_password_rejects_an_unreadable_hash() -> None:
    assert not verify_password("Correcta123", "not-an-argon2-hash")


def test_common_password_is_rejected_even_if_it_meets_the_rules() -> None:
    # Ten characters, upper, lower and a digit, but on every breach list.
    violations = validate_password_strength("Password123")
    assert violations == ["Es una de las contraseñas más usadas: elige otra."]


def test_uncommon_password_passes() -> None:
    assert validate_password_strength("Str0ngPassw0rd!") == []
