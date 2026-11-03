import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from app.core.config import get_settings
from app.modules.pipeline.verify import VerifyResult, verify_claim
from app.modules.sources.service import normalize_domain
from evals.verdicts.cases import Case, Kind, Verdict
from evals.verdicts.cost import PRICES_AS_OF, BudgetGuard, UsageMeter, metering
from evals.verdicts.scoring import Grade, grade, is_contaminated

Verify = Callable[..., Awaitable[VerifyResult]]


class CaseResult(BaseModel):
    case_id: str
    kind: Kind
    rating: str
    got: Verdict | None
    grade: Grade
    rationale: str
    evidence: list[dict]
    contaminated: bool
    search_domains: list[str]
    cost_usd: float
    input_tokens: int
    output_tokens: int
    web_searches: int
    error: str | None = None


class RunResult(BaseModel):
    started_at: datetime
    model: str
    max_usd: float
    prices_as_of: str
    results: list[CaseResult]
    skipped_case_ids: list[str]
    spent_usd: float


def load_allowed_domains(path: Path) -> list[str]:
    return [entry["domain"] for entry in json.loads(path.read_text(encoding="utf-8"))]


async def run_cases(
    cases: list[Case],
    *,
    allowed_domains: list[str],
    max_usd: float,
    verify: Verify = verify_claim,
) -> RunResult:
    """Verify each case's claim, one at a time so the budget can stop the
    run between cases."""
    started_at = datetime.now(UTC)
    meter = UsageMeter()
    guard = BudgetGuard(max_usd)
    results: list[CaseResult] = []
    skipped: list[str] = []
    largest_case_usd = 0.0

    with metering(meter):
        for index, case in enumerate(cases):
            if not guard.can_start(meter.spent_usd, largest_case_usd):
                skipped = [c.id for c in cases[index:]]
                break
            before = (meter.spent_usd, meter.input_tokens, meter.output_tokens, meter.web_searches)
            urls_before = len(meter.search_result_urls)

            got: Verdict | None = None
            rationale, evidence, error = "", [], None
            try:
                result = await verify(case.claim, allowed_domains=allowed_domains)
                got, rationale = result.verdict, result.rationale
                evidence = [
                    {"url": e.url, "domain": e.domain, "stance": e.stance} for e in result.evidence
                ]
            except Exception as exc:  # noqa: BLE001 - one case's failure must not lose the run
                error = str(exc)

            if error is None and meter.input_tokens == before[1]:
                # verify_claim turns API failures (bad key, outage) into
                # INSUFFICIENT: with no tokens used there is no verdict to grade.
                error = "la API no respondió (0 tokens usados)"
            cost = meter.spent_usd - before[0]
            largest_case_usd = max(largest_case_usd, cost)
            results.append(
                CaseResult(
                    case_id=case.id,
                    kind=case.kind,
                    rating=case.rating,
                    got=got,
                    grade="error" if error is not None else grade(case.kind, got),
                    rationale=rationale,
                    evidence=evidence,
                    contaminated=is_contaminated([e["domain"] for e in evidence], case.factchecker),
                    search_domains=list(
                        dict.fromkeys(
                            normalize_domain(u) for u in meter.search_result_urls[urls_before:]
                        )
                    ),
                    cost_usd=cost,
                    input_tokens=meter.input_tokens - before[1],
                    output_tokens=meter.output_tokens - before[2],
                    web_searches=meter.web_searches - before[3],
                    error=error,
                )
            )

    return RunResult(
        started_at=started_at,
        model=get_settings().anthropic_model,
        max_usd=max_usd,
        prices_as_of=PRICES_AS_OF,
        results=results,
        skipped_case_ids=skipped,
        spent_usd=meter.spent_usd,
    )
