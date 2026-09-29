import secrets
import string

from app.core.security import hash_password, verify_password

_ALPHABET = string.ascii_uppercase + string.digits
_GROUP_LENGTH = 5
_GROUPS = 2
_CODE_COUNT = 10


def _generate_one() -> str:
    groups = [
        "".join(secrets.choice(_ALPHABET) for _ in range(_GROUP_LENGTH)) for _ in range(_GROUPS)
    ]
    return "-".join(groups)


def generate_recovery_codes(count: int = _CODE_COUNT) -> list[str]:
    return [_generate_one() for _ in range(count)]


def hash_recovery_code(code: str) -> str:
    return hash_password(code)


def verify_recovery_code(code: str, code_hash: str) -> bool:
    return verify_password(code, code_hash)
