"""Assembles the credibility report for a finished submission.

Read-only: everything here comes from rows the pipeline already persisted
(claims, validated evidence, sources). No LLM calls happen at report time,
so the report is exactly what was verified — nothing is re-derived.
"""

import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pipeline.models import Claim, Evidence
from app.modules.reports.schemas import (
    ReportClaim,
    ReportEvidence,
    ReportResponse,
    ReportSource,
    ReportSubmission,
    ReportSummary,
)
from app.modules.sources import reputation
from app.modules.sources.models import Source
from app.modules.submissions import service as submissions_service

DISCLAIMER = (
    "Este reporte no declara la noticia verdadera ni falsa. Resume qué afirmaciones "
    "pudieron contrastarse con fuentes concretas, qué dicen esas fuentes y su historial "
    "de confiabilidad. Toda conclusión cita su evidencia; sin evidencia válida, el "
    "veredicto es INSUFFICIENT."
)


class ReportNotReadyError(Exception):
    def __init__(self, status: str) -> None:
        super().__init__(status)
        self.status = status


async def build_report(
    db: AsyncSession, *, submission_id: uuid.UUID, user_id: uuid.UUID
) -> ReportResponse:
    # Raises SubmissionNotFoundError for missing or foreign submissions alike,
    # so another user's case id is indistinguishable from a nonexistent one.
    submission = await submissions_service.get_submission(
        db, submission_id=submission_id, user_id=user_id
    )
    if submission.status != "done":
        raise ReportNotReadyError(submission.status)

    claims_result = await db.execute(
        select(Claim).where(Claim.submission_id == submission.id).order_by(Claim.created_at)
    )
    claims = list(claims_result.scalars().all())

    evidence_by_claim: dict[uuid.UUID, list[ReportEvidence]] = {c.id: [] for c in claims}
    if claims:
        evidence_result = await db.execute(
            select(Evidence, Source)
            .join(Source, Evidence.source_id == Source.id)
            .where(Evidence.claim_id.in_(evidence_by_claim.keys()))
            .order_by(Evidence.created_at)
        )
        for evidence, source in evidence_result.all():
            evidence_by_claim[evidence.claim_id].append(
                ReportEvidence(
                    url=evidence.url,
                    snippet=evidence.snippet,
                    published_at=evidence.published_at,
                    stance=evidence.stance,
                    source=ReportSource(
                        domain=source.domain,
                        name=source.name,
                        type=source.type,
                        score=reputation.compute_score(source),
                        cases_count=source.cases_count,
                        low_sample=reputation.is_low_sample(source),
                    ),
                )
            )

    verdicts = Counter(c.verdict for c in claims)
    return ReportResponse(
        submission=ReportSubmission(
            id=submission.id,
            input_type=submission.input_type,
            raw_input=submission.raw_input,
            status=submission.status,
            created_at=submission.created_at,
        ),
        summary=ReportSummary(
            total_claims=len(claims),
            supported=verdicts["SUPPORTED"],
            contradicted=verdicts["CONTRADICTED"],
            insufficient=verdicts["INSUFFICIENT"],
        ),
        claims=[
            ReportClaim(
                id=c.id,
                text=c.text,
                verdict=c.verdict,
                rationale=c.rationale,
                confidence_note=c.confidence_note,
                evidence=evidence_by_claim[c.id],
            )
            for c in claims
        ],
        disclaimer=DISCLAIMER,
    )
