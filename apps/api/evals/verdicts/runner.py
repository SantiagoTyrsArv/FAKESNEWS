import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from app.core.config import get_settings
from app.modules.pipeline.verify import VerifyResult, verify_claim
from app.modules.sources.service import normalize_domain
from evals.verdicts.blind import blind_domains
from evals.verdicts.cases import Case, Kind, Verdict
from evals.verdicts.cost import BudgetGuard, UsageMeter, metering
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
    credits: int
    gemini_calls: int
    error: str | None = None


class RunResult(BaseModel):
    started_at: datetime
    model: str
    max_credits: int
    results: list[CaseResult]
    skipped_case_ids: list[str]
    spent_credits: int
    blind: bool = False


def load_allowed_domains(path: Path) -> list[str]:
    return [entry["domain"] for entry in json.loads(path.read_text(encoding="utf-8"))]


async def run_cases(
    cases: list[Case],
    *,
    allowed_domains: list[str],
    max_credits: int,
    verify: Verify = verify_claim,
    blind: bool = False,
) -> RunResult:
    """Verify each case's claim, one at a time so the budget can stop the
    run between cases. With `blind`, each case searches without the
    fact-checkers, so no verdict can copy a published rating."""
    started_at = datetime.now(UTC)
    meter = UsageMeter()
    guard = BudgetGuard(max_credits)
    results: list[CaseResult] = []
    skipped: list[str] = []

    with metering(meter):
        for index, case in enumerate(cases):
            if not guard.can_start(meter.tavily_credits):
                skipped = [c.id for c in cases[index:]]
                break
            before = (meter.tavily_credits, meter.gemini_calls)
            urls_before = len(meter.search_result_urls)

            got: Verdict | None = None
            rationale, evidence, error = "", [], None
            try:
                domains = (
                    blind_domains(allowed_domains, case.factchecker) if blind else allowed_domains
                )
                result = await verify(case.claim, allowed_domains=domains)
                got, rationale = result.verdict, result.rationale
                if result.verification_failed:
                    error = "la verificación falló"
                evidence = [
                    {"url": e.url, "domain": e.domain, "stance": e.stance} for e in result.evidence
                ]
            except Exception as exc:  # noqa: BLE001 - one case's failure must not lose the run
                error = str(exc)

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
                    credits=meter.tavily_credits - before[0],
                    gemini_calls=meter.gemini_calls - before[1],
                    error=error,
                )
            )

    return RunResult(
        started_at=started_at,
        model=get_settings().gemini_model,
        max_credits=max_credits,
        results=results,
        skipped_case_ids=skipped,
        spent_credits=meter.tavily_credits,
        blind=blind,
    )
