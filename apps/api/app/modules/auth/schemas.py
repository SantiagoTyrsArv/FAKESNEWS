import uuid
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, EmailStr, Field


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


# Emails are compared case-insensitively everywhere: "Ana@x.com" and
# "ana@x.com" are one account, and per-email rate limits can't be dodged by
# changing case.
NormalizedEmail = Annotated[EmailStr, BeforeValidator(_strip), AfterValidator(str.lower)]


class RegisterRequest(BaseModel):
    email: NormalizedEmail
    password: str = Field(min_length=1, max_length=256)


class RegisterResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr


class LoginRequest(BaseModel):
    email: NormalizedEmail
    password: str = Field(min_length=1, max_length=256)


class PendingTokenResponse(BaseModel):
    token: str
    token_type: str
    expires_in: int


class TotpSetupResponse(BaseModel):
    otpauth_uri: str
    qr_code_base64: str


class TotpConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class TotpConfirmResponse(BaseModel):
    recovery_codes: list[str]


class VerifyRequest(BaseModel):
    code: str | None = Field(default=None, min_length=6, max_length=8)
    recovery_code: str | None = Field(default=None, min_length=8, max_length=32)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    mfa_enabled: bool


class SessionResponse(BaseModel):
    user: UserResponse
