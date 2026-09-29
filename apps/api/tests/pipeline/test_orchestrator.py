import uuid

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.modules.auth.models import User
from app.modules.pipeline import claims as claims_module
from app.modules.pipeline import ingest as ingest_module
from app.modules.pipeline import orchestrator
from app.modules.pipeline import verify as verify_module
from app.modules.pipeline.ingest import IngestError
from app.modules.pipeline.models import Claim, Evidence
from app.modules.pipeline.verify import EvidenceItem, VerifyResult
from app.modules.sources.models import Source, SourceScoreEvent
from app.modules.submissions.models import Submission


async def _create_user_and_submission(db_session_factory, *, email: str) -> str:
    async with db_session_factory() as db:
        user = User(email=email, password_hash=hash_password("Str0ngPassw0rd!"))
        db.add(user)
        db.add(Source(domain="reuters.com", name="Reuters", type="agencia", alpha=1, beta=1))
        await db.commit()
        await db.refresh(user)

        submission = Submission(
            user_id=user.id, input_type="text", raw_input="algún texto", status="queued"
        )
        db.add(submission)
        await db.commit()
        await db.refresh(submission)
        return str(submission.id)


async def test_run_pipeline_happy_path(db_session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    submission_id = await _create_user_and_submission(
        db_session_factory, email="pipeline@example.com"
    )
    monkeypatch.setattr(orchestrator, "async_session_factory", db_session_factory)

    async def fake_ingest_text(_raw_text: str) -> str:
        return "texto extraído del caso"

    async def fake_extract_claims(_text: str, **_kwargs) -> list[str]:
        return ["La afirmación A ocurrió.", "La afirmación B ocurrió."]

    async def fake_verify_claim(_claim_text: str, *, allowed_domains: list[str], **_kwargs):
        assert "reuters.com" in allowed_domains
        return VerifyResult(
            verdict="SUPPORTED",
            rationale="La fuente lo confirma.",
            evidence=[
                EvidenceItem(
                    url="https://reuters.com/x",
                    domain="reuters.com",
                    snippet="cita relevante",
                    published_at=None,
                    stance="supports",
                )
            ],
        )

    monkeypatch.setattr(ingest_module, "ingest_text", fake_ingest_text)
    monkeypatch.setattr(claims_module, "extract_claims", fake_extract_claims)
    monkeypatch.setattr(verify_module, "verify_claim", fake_verify_claim)

    await orchestrator.run_pipeline({}, submission_id)

    async with db_session_factory() as check_db:
        submission = await check_db.get(Submission, uuid.UUID(submission_id))
        assert submission.status == "done"
        assert submission.extracted_text == "texto extraído del caso"

        claims = (
            (await check_db.execute(select(Claim).where(Claim.submission_id == submission.id)))
            .scalars()
            .all()
        )
        assert len(claims) == 2
        for claim in claims:
            assert claim.verdict == "SUPPORTED"
            evidences = (
                (await check_db.execute(select(Evidence).where(Evidence.claim_id == claim.id)))
                .scalars()
                .all()
            )
            assert len(evidences) == 1
            assert evidences[0].url == "https://reuters.com/x"


async def test_run_pipeline_marks_failed_on_ingest_error(
    db_session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    submission_id = await _create_user_and_submission(db_session_factory, email="fail@example.com")
    monkeypatch.setattr(orchestrator, "async_session_factory", db_session_factory)

    async def failing_ingest(_raw_text: str) -> str:
        raise IngestError("no se pudo procesar")

    monkeypatch.setattr(ingest_module, "ingest_text", failing_ingest)

    await orchestrator.run_pipeline({}, submission_id)

    async with db_session_factory() as check_db:
        submission = await check_db.get(Submission, uuid.UUID(submission_id))
        assert submission.status == "failed"
        assert "no se pudo procesar" in submission.error


async def test_run_pipeline_partial_verify_failure_still_completes(
    db_session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    submission_id = await _create_user_and_submission(
        db_session_factory, email="partial@example.com"
    )
    monkeypatch.setattr(orchestrator, "async_session_factory", db_session_factory)

    async def fake_ingest_text(_raw_text: str) -> str:
        return "texto"

    async def fake_extract_claims(_text: str, **_kwargs) -> list[str]:
        return ["Única afirmación del caso."]

    async def failing_verify(_claim_text: str, *, allowed_domains: list[str], **_kwargs):
        raise RuntimeError("verify explotó")

    monkeypatch.setattr(ingest_module, "ingest_text", fake_ingest_text)
    monkeypatch.setattr(claims_module, "extract_claims", fake_extract_claims)
    monkeypatch.setattr(verify_module, "verify_claim", failing_verify)

    await orchestrator.run_pipeline({}, submission_id)

    async with db_session_factory() as check_db:
        submission = await check_db.get(Submission, uuid.UUID(submission_id))
        # The whole case still completes even though one claim's verify blew up.
        assert submission.status == "done"

        claims = (
            (await check_db.execute(select(Claim).where(Claim.submission_id == submission.id)))
            .scalars()
            .all()
        )
        assert len(claims) == 1
        assert claims[0].verdict == "INSUFFICIENT"


async def test_run_pipeline_scores_source_reputation_end_to_end(
    db_session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with db_session_factory() as db:
        user = User(email="reputation@example.com", password_hash=hash_password("Str0ngPassw0rd!"))
        db.add(user)
        reuters = Source(domain="reuters.com", name="Reuters", type="agencia", alpha=8, beta=2)
        apnews = Source(domain="apnews.com", name="AP", type="agencia", alpha=2, beta=8)
        db.add(reuters)
        db.add(apnews)
        await db.commit()
        await db.refresh(user)
        await db.refresh(reuters)
        await db.refresh(apnews)
        reuters_id, apnews_id = reuters.id, apnews.id

        submission = Submission(
            user_id=user.id, input_type="text", raw_input="algún texto", status="queued"
        )
        db.add(submission)
        await db.commit()
        await db.refresh(submission)
        submission_id = str(submission.id)

    monkeypatch.setattr(orchestrator, "async_session_factory", db_session_factory)

    async def fake_ingest_text(_raw_text: str) -> str:
        return "texto"

    async def fake_extract_claims(_text: str, **_kwargs) -> list[str]:
        return ["Una afirmación con dos fuentes independientes."]

    async def fake_verify_claim(_claim_text: str, *, allowed_domains: list[str], **_kwargs):
        return VerifyResult(
            verdict="SUPPORTED",
            rationale="Ambas fuentes coinciden.",
            evidence=[
                EvidenceItem(
                    url="https://reuters.com/a",
                    domain="reuters.com",
                    snippet="cita 1",
                    published_at=None,
                    stance="supports",
                ),
                EvidenceItem(
                    url="https://apnews.com/b",
                    domain="apnews.com",
                    snippet="cita 2",
                    published_at=None,
                    stance="supports",
                ),
            ],
        )

    monkeypatch.setattr(ingest_module, "ingest_text", fake_ingest_text)
    monkeypatch.setattr(claims_module, "extract_claims", fake_extract_claims)
    monkeypatch.setattr(verify_module, "verify_claim", fake_verify_claim)

    await orchestrator.run_pipeline({}, submission_id)

    async with db_session_factory() as check_db:
        submission = await check_db.get(Submission, uuid.UUID(submission_id))
        assert submission.status == "done"

        reuters_after = await check_db.get(Source, reuters_id)
        apnews_after = await check_db.get(Source, apnews_id)
        # Both agreed with each other (both "supports"), so both are hits
        # regardless of which one "won" the weighted consensus.
        assert reuters_after.alpha == 9
        assert apnews_after.alpha == 3

        claim = (
            await check_db.execute(select(Claim).where(Claim.submission_id == submission.id))
        ).scalar_one()
        events = (
            (
                await check_db.execute(
                    select(SourceScoreEvent).where(SourceScoreEvent.claim_id == claim.id)
                )
            )
            .scalars()
            .all()
        )
        assert {e.source_id: e.outcome for e in events} == {
            reuters_id: "hit",
            apnews_id: "hit",
        }
