import asyncio
import uuid
from typing import Any

from app.core.config import get_settings
from app.core.db import async_session_factory
from app.core.logging import get_logger
from app.modules.pipeline import claims as claims_module
from app.modules.pipeline import ingest as ingest_module
from app.modules.pipeline import verify as verify_module
from app.modules.pipeline.models import Claim, Evidence
from app.modules.pipeline.transcribe import FasterWhisperTranscriber
from app.modules.sources import reputation as reputation_module
from app.modules.sources import service as sources_service
from app.modules.submissions.models import Submission

settings = get_settings()
logger = get_logger(__name__)


async def _set_status(
    db: Any, submission: Submission, new_status: str, *, error: str | None = None
) -> None:
    submission.status = new_status
    if error is not None:
        submission.error = error
    await db.commit()


async def _verify_one(
    semaphore: asyncio.Semaphore, claim_text: str, allowed_domains: list[str]
) -> verify_module.VerifyResult:
    async with semaphore:
        try:
            return await asyncio.wait_for(
                verify_module.verify_claim(claim_text, allowed_domains=allowed_domains),
                timeout=settings.verify_timeout_seconds,
            )
        except TimeoutError:
            return verify_module.VerifyResult(
                verdict="INSUFFICIENT",
                rationale="Se agotó el tiempo de espera al verificar esta afirmación.",
                evidence=[],
            )
        except Exception as exc:  # noqa: BLE001 - one claim's failure must not kill the batch
            logger.warning("verify_claim_unexpected_error", error=str(exc))
            return verify_module.VerifyResult(
                verdict="INSUFFICIENT",
                rationale=f"No se pudo verificar esta afirmación: {exc}",
                evidence=[],
            )


async def _ingest(submission: Submission, db: Any) -> str:
    if submission.input_type == "text":
        return await ingest_module.ingest_text(submission.raw_input)
    if submission.input_type == "url":
        return await ingest_module.ingest_url(submission.raw_input)

    await _set_status(db, submission, "transcribing")
    transcriber = FasterWhisperTranscriber()
    return await ingest_module.ingest_video(submission.raw_input, transcriber)


async def run_pipeline(_ctx: dict, submission_id: str) -> None:
    async with async_session_factory() as db:
        submission = await db.get(Submission, uuid.UUID(submission_id))
        if submission is None:
            logger.error("run_pipeline_submission_not_found", submission_id=submission_id)
            return

        try:
            await _set_status(db, submission, "ingesting")
            extracted_text = await _ingest(submission, db)
            submission.extracted_text = extracted_text
            await _set_status(db, submission, "extracting")

            claim_texts = await claims_module.extract_claims(extracted_text)

            await _set_status(db, submission, "verifying")
            allowed_domains = await sources_service.get_allowed_domains(db)

            semaphore = asyncio.Semaphore(settings.verify_concurrency_limit)
            results = await asyncio.gather(
                *[_verify_one(semaphore, text, allowed_domains) for text in claim_texts]
            )

            claim_evidence: list[tuple[uuid.UUID, str, list[tuple[uuid.UUID, str]]]] = []

            for claim_text, result in zip(claim_texts, results, strict=True):
                claim = Claim(
                    submission_id=submission.id,
                    text=claim_text,
                    verdict=result.verdict,
                    rationale=result.rationale,
                )
                db.add(claim)
                await db.flush()

                source_stances: list[tuple[uuid.UUID, str]] = []
                for ev in result.evidence:
                    source = await sources_service.get_source_by_domain(db, ev.domain)
                    if source is None:
                        continue
                    db.add(
                        Evidence(
                            claim_id=claim.id,
                            source_id=source.id,
                            url=ev.url,
                            snippet=ev.snippet,
                            published_at=ev.published_at,
                            stance=ev.stance,
                        )
                    )
                    source_stances.append((source.id, ev.stance))

                claim_evidence.append((claim.id, result.verdict, source_stances))

            await db.commit()

            await _set_status(db, submission, "scoring")
            for claim_id, verdict, source_stances in claim_evidence:
                await reputation_module.update_reputation_for_claim(
                    db, claim_id=claim_id, verdict=verdict, evidence=source_stances
                )

            await _set_status(db, submission, "done")
        except Exception as exc:  # noqa: BLE001 - top-level guard: mark the case failed, don't crash the worker
            logger.error("run_pipeline_failed", submission_id=submission_id, error=str(exc))
            await db.rollback()
            failed_submission = await db.get(Submission, uuid.UUID(submission_id))
            if failed_submission is not None:
                await _set_status(db, failed_submission, "failed", error=str(exc))
