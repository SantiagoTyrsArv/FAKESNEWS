"""Source reputation scoring (Beta-Bernoulli posterior over hit/miss events).

This module intentionally takes plain (source_id, stance) tuples rather than
pipeline.models.Evidence/Claim ORM objects: sources must not import pipeline
models (see the module boundary rule in AGENTS/README — modules talk to each
other only through service layers). The pipeline orchestrator, which already
owns both the Claim/Evidence rows it just created and the call into this
module, is responsible for translating its own ORM objects into these plain
values.

See docs/reputation.md for the formula, its assumptions, and its known
limitations (circularity, conformity bias).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sources.models import Source, SourceScoreEvent

MIN_WEIGHT = 0.05
LOW_SAMPLE_THRESHOLD = 10
_Z_95 = 1.96


def _utcnow() -> datetime:
    return datetime.now(UTC)


def compute_score(source: Source) -> float:
    return source.alpha / (source.alpha + source.beta)


def compute_score_interval(source: Source) -> tuple[float, float]:
    """Approximate 95% interval around the score, using the normal
    approximation to the Beta(alpha, beta) posterior. This is an
    approximation, not the exact Beta quantile interval — good enough for a
    "roughly how confident should you be" badge, not for rigorous inference.
    """
    alpha, beta = source.alpha, source.beta
    total = alpha + beta
    mean = alpha / total
    variance = (alpha * beta) / (total**2 * (total + 1))
    stddev = variance**0.5
    low = max(0.0, mean - _Z_95 * stddev)
    high = min(1.0, mean + _Z_95 * stddev)
    return low, high


def is_low_sample(source: Source) -> bool:
    return source.cases_count < LOW_SAMPLE_THRESHOLD


def _independence_key(source: Source) -> str:
    return f"syn:{source.syndication_group}" if source.syndication_group else f"src:{source.id}"


async def update_reputation_for_claim(
    db: AsyncSession,
    *,
    claim_id: uuid.UUID,
    verdict: str,
    evidence: list[tuple[uuid.UUID, str]],
) -> None:
    """Score every source that supplied directional (non-neutral) evidence
    for one claim, against the weighted consensus of that evidence.

    No-ops (no rows written, no scores changed) when: the verdict is
    INSUFFICIENT, fewer than 2 independent sources took a directional
    stance, or the weighted consensus is an exact tie. Safe to call more
    than once for the same claim — already-scored sources are skipped via
    the (source_id, claim_id) unique constraint on source_score_events.
    """
    if verdict == "INSUFFICIENT" or not evidence:
        return

    directional = [
        (sid, stance) for sid, stance in evidence if stance in ("supports", "contradicts")
    ]
    if not directional:
        return

    source_ids = {sid for sid, _ in directional}
    result = await db.execute(select(Source).where(Source.id.in_(source_ids)))
    sources_by_id = {s.id: s for s in result.scalars().all()}

    # One vote per source (first stance wins if the same source shows up
    # more than once in this claim's evidence).
    per_source_stance: dict[uuid.UUID, tuple[Source, str]] = {}
    for source_id, stance in directional:
        source = sources_by_id.get(source_id)
        if source is not None and source_id not in per_source_stance:
            per_source_stance[source_id] = (source, stance)

    # Group by independence key so syndicated re-reports of the same wire
    # story count as one voice, both for the >=2 threshold and the
    # weighted-consensus vote below.
    groups: dict[str, list[tuple[Source, str]]] = {}
    for source, stance in per_source_stance.values():
        groups.setdefault(_independence_key(source), []).append((source, stance))

    if len(groups) < 2:
        return

    weighted_sum = 0.0
    for items in groups.values():
        rep_source, rep_stance = items[0]
        weight = max(compute_score(rep_source), MIN_WEIGHT)
        value = 1.0 if rep_stance == "supports" else -1.0
        weighted_sum += value * weight

    if weighted_sum == 0:
        return  # exact tie: no clear consensus to score against

    consensus = "supports" if weighted_sum > 0 else "contradicts"

    for source, stance in per_source_stance.values():
        existing = await db.execute(
            select(SourceScoreEvent.id).where(
                SourceScoreEvent.source_id == source.id,
                SourceScoreEvent.claim_id == claim_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue  # already scored this source for this claim

        outcome = "hit" if stance == consensus else "miss"
        db.add(SourceScoreEvent(source_id=source.id, claim_id=claim_id, outcome=outcome))
        if outcome == "hit":
            source.alpha += 1
        else:
            source.beta += 1
        source.cases_count += 1
        source.last_updated = _utcnow()

    await db.commit()
