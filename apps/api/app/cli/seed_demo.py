"""Seed a demo user (with TOTP already enrolled) and pre-processed sample cases.

Run inside the API container:  make seed
(= docker compose exec api uv run python -m app.cli.seed_demo)

In production, only on purpose:  uv run python -m app.cli.seed_demo --production

Why pre-processed cases: the real pipeline needs ANTHROPIC_API_KEY. With
these rows the report, history and source pages can be demoed without it.

Design decisions:
- Idempotent. The user is created once; its TOTP secret is kept across runs
  (so an authenticator app enrolled earlier keeps working), and demo cases
  are only inserted if the user has none yet. Recovery codes are regenerated
  on every run, since their plaintext is never stored and can't be reprinted.
- Demo cases do NOT go through reputation.update_reputation_for_claim: their
  evidence is illustrative, and letting it move alpha/beta would contaminate
  the real source scores with invented data.
- Every demo input is prefixed with DEMO_MARKER and every snippet is marked
  as illustrative, so seeded evidence can't be mistaken for real citations.
  Evidence URLs point at the sources' public sites, not at invented articles.
- Refuses to run with ENVIRONMENT=production unless --production is passed.
  Then the password is random and rotated on every run (the fixed
  DEMO_PASSWORD lives in this public repo), and is printed only once.
"""

import argparse
import asyncio
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pyotp
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.models_registry  # noqa: F401 - populates Base.metadata in this process
from app.core.config import get_settings
from app.core.security import decrypt_secret, encrypt_secret, hash_password
from app.modules.auth import totp as totp_module
from app.modules.auth.models import MfaRecoveryCode, User
from app.modules.auth.recovery_codes import generate_recovery_codes, hash_recovery_code
from app.modules.pipeline.models import Claim, Evidence
from app.modules.sources.models import Source
from app.modules.sources.seed_loader import load_trusted_sources
from app.modules.submissions.models import Submission

DEMO_EMAIL = "demo@fakesnews.dev"
DEMO_PASSWORD = "DemoFakesNews2026"
DEMO_MARKER = "[DEMO]"
ILLUSTRATIVE = " (fragmento ilustrativo de demostración)"


class ProductionSeedError(RuntimeError):
    pass


@dataclass
class SeedResult:
    email: str
    password: str
    totp_secret: str
    otpauth_uri: str
    recovery_codes: list[str]
    user_created: bool
    cases_created: int
    sources_added: int
    case_ids: list[uuid.UUID] = field(default_factory=list)


# Each case: input, status, optional error, and claims as
# (text, verdict, rationale, [(domain, url, snippet, published_at, stance)]).
DEMO_CASES = [
    {
        "input_type": "text",
        "raw_input": (
            f"{DEMO_MARKER} Mensaje viral de WhatsApp: «La OMS declaró en mayo de 2023 el "
            "fin de la emergencia sanitaria internacional por COVID-19. Aun así, beber agua "
            "caliente cada 15 minutos elimina el virus de la garganta. Una universidad local "
            "lo confirmó la semana pasada.»"
        ),
        "status": "done",
        "age": timedelta(days=2),
        "claims": [
            (
                "La OMS declaró en mayo de 2023 el fin de la emergencia de salud pública "
                "de importancia internacional por COVID-19.",
                "SUPPORTED",
                "Tres fuentes independientes, incluida la propia OMS, reportan el anuncio "
                "de mayo de 2023.",
                [
                    (
                        "who.int",
                        "https://www.who.int/",
                        "El Director General declaró que la COVID-19 ya no constituye una "
                        "emergencia de salud pública de importancia internacional.",
                        "May 5, 2023",
                        "supports",
                    ),
                    (
                        "reuters.com",
                        "https://www.reuters.com/",
                        "La OMS pone fin a la emergencia sanitaria global por COVID-19.",
                        "May 5, 2023",
                        "supports",
                    ),
                    (
                        "apnews.com",
                        "https://apnews.com/",
                        "La OMS dice que la COVID-19 ya no es una emergencia global.",
                        "May 5, 2023",
                        "supports",
                    ),
                ],
            ),
            (
                "Beber agua caliente cada 15 minutos elimina el virus de la COVID-19.",
                "CONTRADICTED",
                "Las fuentes consultadas señalan que beber agua caliente no previene ni "
                "elimina la infección.",
                [
                    (
                        "who.int",
                        "https://www.who.int/",
                        "Beber agua caliente no protege contra la COVID-19 ni la cura.",
                        None,
                        "contradicts",
                    ),
                    (
                        "factcheck.org",
                        "https://www.factcheck.org/",
                        "No hay evidencia de que beber agua caliente con frecuencia "
                        "elimine el coronavirus.",
                        None,
                        "contradicts",
                    ),
                ],
            ),
            (
                "Una universidad local confirmó la semana pasada que el agua caliente "
                "elimina el virus.",
                "INSUFFICIENT",
                "No se encontró ninguna fuente de confianza que mencione ese estudio; sin "
                "citas verificables no se emite veredicto.",
                [],
            ),
        ],
    },
    {
        "input_type": "url",
        "raw_input": f"{DEMO_MARKER} https://example.com/demo/telescopio-james-webb",
        "status": "done",
        "age": timedelta(days=1),
        "claims": [
            (
                "El telescopio espacial James Webb fue lanzado el 25 de diciembre de 2021.",
                "SUPPORTED",
                "Fuentes independientes coinciden en la fecha de lanzamiento. Dos de las "
                "citas pertenecen al mismo grupo editorial (BBC) y cuentan como una sola "
                "voz independiente para la reputación.",
                [
                    (
                        "apnews.com",
                        "https://apnews.com/",
                        "El telescopio Webb despegó el día de Navidad de 2021 desde la "
                        "Guayana Francesa.",
                        "December 25, 2021",
                        "supports",
                    ),
                    (
                        "bbc.com",
                        "https://www.bbc.com/",
                        "Lanzado con éxito el telescopio James Webb el 25 de diciembre.",
                        "December 25, 2021",
                        "supports",
                    ),
                    (
                        "bbc.co.uk",
                        "https://www.bbc.co.uk/",
                        "El James Webb inicia su viaje tras el lanzamiento en Navidad.",
                        "December 25, 2021",
                        "supports",
                    ),
                ],
            ),
            (
                "El telescopio James Webb fue construido exclusivamente por la NASA.",
                "CONTRADICTED",
                "Las fuentes indican que es una colaboración de la NASA con las agencias "
                "espaciales europea (ESA) y canadiense (CSA).",
                [
                    (
                        "reuters.com",
                        "https://www.reuters.com/",
                        "El Webb es un proyecto conjunto de la NASA, la ESA y la CSA.",
                        None,
                        "contradicts",
                    ),
                    (
                        "afp.com",
                        "https://www.afp.com/",
                        "El observatorio fue desarrollado por la NASA junto a sus socios "
                        "europeo y canadiense.",
                        None,
                        "contradicts",
                    ),
                ],
            ),
        ],
    },
    {
        "input_type": "text",
        "raw_input": f"{DEMO_MARKER} Caso de ejemplo que falló durante el procesamiento.",
        "status": "failed",
        "error": (
            "Caso de demostración: así se ve un fallo del pipeline (p. ej. sin "
            "ANTHROPIC_API_KEY el paso de extracción de afirmaciones no puede ejecutarse)."
        ),
        "age": timedelta(hours=3),
        "claims": [],
    },
]


async def _ensure_demo_user(db: AsyncSession, password: str) -> tuple[User, str, bool]:
    result = await db.execute(select(User).where(User.email == DEMO_EMAIL))
    user = result.scalar_one_or_none()
    created = user is None

    if user is None:
        user = User(email=DEMO_EMAIL, password_hash=hash_password(password))
        db.add(user)
    else:
        user.password_hash = hash_password(password)

    if user.totp_secret_encrypted:
        secret = decrypt_secret(user.totp_secret_encrypted)
    else:
        secret = totp_module.generate_secret()
        user.totp_secret_encrypted = encrypt_secret(secret)

    user.mfa_enabled = True
    user.failed_attempts = 0
    user.locked_until = None
    await db.flush()
    return user, secret, created


async def _reset_recovery_codes(db: AsyncSession, user: User) -> list[str]:
    await db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
    codes = generate_recovery_codes()
    for code in codes:
        db.add(MfaRecoveryCode(user_id=user.id, code_hash=hash_recovery_code(code)))
    return codes


async def _insert_demo_cases(db: AsyncSession, user: User) -> list[uuid.UUID]:
    existing = await db.execute(
        select(Submission.id).where(
            Submission.user_id == user.id, Submission.raw_input.startswith(DEMO_MARKER)
        )
    )
    if existing.first() is not None:
        return []

    result = await db.execute(select(Source))
    sources_by_domain = {s.domain: s for s in result.scalars().all()}
    now = datetime.now(UTC)
    case_ids: list[uuid.UUID] = []

    for case in DEMO_CASES:
        created_at = now - case["age"]
        submission = Submission(
            user_id=user.id,
            input_type=case["input_type"],
            raw_input=case["raw_input"],
            extracted_text=case["raw_input"] if case["status"] == "done" else None,
            status=case["status"],
            error=case.get("error"),
            created_at=created_at,
        )
        db.add(submission)
        await db.flush()
        case_ids.append(submission.id)

        for offset, (text, verdict, rationale, evidence) in enumerate(case["claims"]):
            claim = Claim(
                submission_id=submission.id,
                text=text,
                verdict=verdict,
                rationale=rationale,
                confidence_note="Caso de demostración: evidencia ilustrativa.",
                # Stagger timestamps so the report keeps the authored order.
                created_at=created_at + timedelta(seconds=offset),
            )
            db.add(claim)
            await db.flush()

            for ev_offset, (domain, url, snippet, published_at, stance) in enumerate(evidence):
                db.add(
                    Evidence(
                        claim_id=claim.id,
                        source_id=sources_by_domain[domain].id,
                        url=url,
                        snippet=snippet + ILLUSTRATIVE,
                        published_at=published_at,
                        stance=stance,
                        created_at=created_at + timedelta(seconds=offset, milliseconds=ev_offset),
                    )
                )

    return case_ids


async def seed(db: AsyncSession, *, allow_production: bool = False) -> SeedResult:
    production = get_settings().environment == "production"
    if production and not allow_production:
        raise ProductionSeedError(
            "make seed no se ejecuta con ENVIRONMENT=production (usa --production a propósito)."
        )
    password = secrets.token_urlsafe(18) if production else DEMO_PASSWORD

    sources_added = await load_trusted_sources(db)
    user, secret, user_created = await _ensure_demo_user(db, password)
    recovery_codes = await _reset_recovery_codes(db, user)
    case_ids = await _insert_demo_cases(db, user)
    await db.commit()

    return SeedResult(
        email=DEMO_EMAIL,
        password=password,
        totp_secret=secret,
        otpauth_uri=totp_module.build_provisioning_uri(secret, DEMO_EMAIL),
        recovery_codes=recovery_codes,
        user_created=user_created,
        cases_created=len(case_ids),
        sources_added=sources_added,
        case_ids=case_ids,
    )


def _print_result(result: SeedResult) -> None:
    print("=" * 64)
    print("FakesNews - datos de demostración")
    print("=" * 64)
    print(f"Usuario demo:     {result.email} ({'creado' if result.user_created else 'ya existía'})")
    print(f"Contraseña:       {result.password}")
    print(f"Secreto TOTP:     {result.totp_secret}")
    print(f"URI otpauth:      {result.otpauth_uri}")
    print(f"Código TOTP ahora: {pyotp.TOTP(result.totp_secret).now()} (válido ~30 s)")
    print("Códigos de recuperación (regenerados en cada ejecución):")
    for code in result.recovery_codes:
        print(f"  {code}")
    print(f"Casos demo creados: {result.cases_created} (0 = ya existían)")
    print(f"Fuentes nuevas cargadas: {result.sources_added}")
    print("Inicia sesión en /login y agrega el secreto TOTP a tu app de autenticación")
    print("(o usa un código de recuperación). Guarda estos datos: no se vuelven a mostrar.")


async def _main(allow_production: bool) -> None:
    from app.core.db import async_session_factory, engine

    try:
        async with async_session_factory() as db:
            result = await seed(db, allow_production=allow_production)
    finally:
        await engine.dispose()
    _print_result(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--production",
        action="store_true",
        help="permite ejecutarlo con ENVIRONMENT=production (contraseña aleatoria)",
    )
    asyncio.run(_main(parser.parse_args().production))
