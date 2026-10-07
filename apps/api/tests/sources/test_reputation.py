import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.sources import reputation
from app.modules.sources.models import Source, SourceScoreEvent


async def _make_source(
    db: AsyncSession,
    *,
    alpha: float,
    beta: float,
    syndication_group: str | None = None,
    domain: str | None = None,
) -> Source:
    source = Source(
        domain=domain or f"{uuid.uuid4().hex[:8]}.example",
        name="Test Source",
        type="medio",
        alpha=alpha,
        beta=beta,
        syndication_group=syndication_group,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


async def _events_for_claim(db: AsyncSession, claim_id: uuid.UUID) -> list[SourceScoreEvent]:
    result = await db.execute(select(SourceScoreEvent).where(SourceScoreEvent.claim_id == claim_id))
    return list(result.scalars().all())


async def test_two_independent_sources_agree_both_get_hits(db_session: AsyncSession) -> None:
    a = await _make_source(db_session, alpha=8, beta=2)  # score .8
    b = await _make_source(db_session, alpha=2, beta=8)  # score .2
    claim_id = uuid.uuid4()

    await reputation.update_reputation_for_claim(
        db_session,
        claim_id=claim_id,
        verdict="SUPPORTED",
        evidence=[(a.id, "supports"), (b.id, "supports")],
    )

    await db_session.refresh(a)
    await db_session.refresh(b)
    assert a.alpha == 9 and a.beta == 2
    assert b.alpha == 3 and b.beta == 8
    assert a.cases_count == 1 and b.cases_count == 1

    events = await _events_for_claim(db_session, claim_id)
    assert {e.source_id: e.outcome for e in events} == {a.id: "hit", b.id: "hit"}


async def test_dominant_source_sets_consensus_dissenter_gets_miss(db_session: AsyncSession) -> None:
    strong = await _make_source(db_session, alpha=8, beta=2)  # weight .8
    weak = await _make_source(db_session, alpha=2, beta=8)  # weight .2
    claim_id = uuid.uuid4()

    # weighted sum = 0.8*(+1) + 0.2*(-1) = +0.6 -> consensus = supports
    await reputation.update_reputation_for_claim(
        db_session,
        claim_id=claim_id,
        verdict="CONTRADICTED",
        evidence=[(strong.id, "supports"), (weak.id, "contradicts")],
    )

    await db_session.refresh(strong)
    await db_session.refresh(weak)
    assert strong.alpha == 9 and strong.beta == 2  # agreed with consensus: hit
    assert weak.alpha == 2 and weak.beta == 9  # disagreed with consensus: miss


async def test_idempotent_on_repeated_call(db_session: AsyncSession) -> None:
    a = await _make_source(db_session, alpha=5, beta=5)
    b = await _make_source(db_session, alpha=5, beta=5)
    claim_id = uuid.uuid4()
    evidence = [(a.id, "supports"), (b.id, "supports")]

    await reputation.update_reputation_for_claim(
        db_session, claim_id=claim_id, verdict="SUPPORTED", evidence=evidence
    )
    await db_session.refresh(a)
    first_alpha = a.alpha

    # Call again for the exact same claim: must be a no-op.
    await reputation.update_reputation_for_claim(
        db_session, claim_id=claim_id, verdict="SUPPORTED", evidence=evidence
    )
    await db_session.refresh(a)
    await db_session.refresh(b)

    assert a.alpha == first_alpha
    events = await _events_for_claim(db_session, claim_id)
    assert len(events) == 2  # not 4


async def test_skips_when_fewer_than_two_independent_sources(db_session: AsyncSession) -> None:
    a = await _make_source(db_session, alpha=5, beta=5)
    claim_id = uuid.uuid4()

    await reputation.update_reputation_for_claim(
        db_session, claim_id=claim_id, verdict="SUPPORTED", evidence=[(a.id, "supports")]
    )

    await db_session.refresh(a)
    assert a.alpha == 5 and a.beta == 5
    assert await _events_for_claim(db_session, claim_id) == []


async def test_syndicated_sources_count_as_one_independent_voice(db_session: AsyncSession) -> None:
    wire_1 = await _make_source(db_session, alpha=8, beta=2, syndication_group="wire")
    wire_2 = await _make_source(db_session, alpha=8, beta=2, syndication_group="wire")
    independent = await _make_source(db_session, alpha=5, beta=5)
    claim_id = uuid.uuid4()

    # Only 2 sources, but both syndicated -> 1 independent group -> should skip.
    await reputation.update_reputation_for_claim(
        db_session,
        claim_id=claim_id,
        verdict="SUPPORTED",
        evidence=[(wire_1.id, "supports"), (wire_2.id, "supports")],
    )
    await db_session.refresh(wire_1)
    assert wire_1.alpha == 8  # unchanged: still only 1 independent voice

    # Add a genuinely independent, disagreeing third source: now 2 groups.
    claim_id_2 = uuid.uuid4()
    await reputation.update_reputation_for_claim(
        db_session,
        claim_id=claim_id_2,
        verdict="SUPPORTED",
        evidence=[
            (wire_1.id, "supports"),
            (wire_2.id, "supports"),
            (independent.id, "contradicts"),
        ],
    )

    await db_session.refresh(wire_1)
    await db_session.refresh(wire_2)
    await db_session.refresh(independent)

    # weighted sum = 0.8*(+1) [wire group, one vote] + 0.5*(-1) [independent] = +0.3 -> consensus supports
    assert wire_1.alpha == 9  # agreed with consensus: hit
    assert wire_2.alpha == 9  # each syndicated source still scored individually
    assert independent.beta == 6  # disagreed: miss


async def test_insufficient_verdict_is_skipped(db_session: AsyncSession) -> None:
    a = await _make_source(db_session, alpha=5, beta=5)
    b = await _make_source(db_session, alpha=5, beta=5)
    claim_id = uuid.uuid4()

    await reputation.update_reputation_for_claim(
        db_session,
        claim_id=claim_id,
        verdict="INSUFFICIENT",
        evidence=[(a.id, "supports"), (b.id, "contradicts")],
    )

    await db_session.refresh(a)
    await db_session.refresh(b)
    assert a.alpha == 5 and b.beta == 5
    assert await _events_for_claim(db_session, claim_id) == []


async def test_neutral_evidence_does_not_count_toward_independence(
    db_session: AsyncSession,
) -> None:
    a = await _make_source(db_session, alpha=5, beta=5)
    b = await _make_source(db_session, alpha=5, beta=5)
    claim_id = uuid.uuid4()

    await reputation.update_reputation_for_claim(
        db_session,
        claim_id=claim_id,
        verdict="SUPPORTED",
        evidence=[(a.id, "supports"), (b.id, "neutral")],
    )

    await db_session.refresh(a)
    assert a.alpha == 5  # only one directional source -> below the threshold, skipped


async def test_exact_tie_is_skipped(db_session: AsyncSession) -> None:
    a = await _make_source(db_session, alpha=5, beta=5)  # score .5
    b = await _make_source(db_session, alpha=5, beta=5)  # score .5
    claim_id = uuid.uuid4()

    await reputation.update_reputation_for_claim(
        db_session,
        claim_id=claim_id,
        verdict="SUPPORTED",
        evidence=[(a.id, "supports"), (b.id, "contradicts")],
    )

    await db_session.refresh(a)
    await db_session.refresh(b)
    assert a.alpha == 5 and b.beta == 5
    assert await _events_for_claim(db_session, claim_id) == []


def test_compute_score() -> None:
    source = Source(domain="x.com", name="X", type="medio", alpha=3, beta=1)
    assert reputation.compute_score(source) == 0.75


def test_low_sample_flag() -> None:
    fresh = Source(domain="x.com", name="X", type="medio", alpha=1, beta=1, cases_count=3)
    seasoned = Source(domain="y.com", name="Y", type="medio", alpha=1, beta=1, cases_count=42)
    assert reputation.is_low_sample(fresh) is True
    assert reputation.is_low_sample(seasoned) is False


def test_score_interval_is_wide_for_small_samples_narrow_for_large() -> None:
    small = Source(domain="x.com", name="X", type="medio", alpha=2, beta=2)
    large = Source(domain="y.com", name="Y", type="medio", alpha=200, beta=200)

    small_low, small_high = reputation.compute_score_interval(small)
    large_low, large_high = reputation.compute_score_interval(large)

    assert small_high - small_low > large_high - large_low
    assert 0.0 <= small_low <= small_high <= 1.0
