from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VitalReport(BaseModel):
    """One Core Web Vitals measurement from the browser (Next's
    useReportWebVitals). The route is a template (/reports/[id]), never the
    real URL, so the logs carry no case ids."""

    model_config = ConfigDict(extra="forbid")

    name: Literal["CLS", "FCP", "INP", "LCP", "TTFB"]
    value: float = Field(ge=0, le=600_000)
    rating: Literal["good", "needs-improvement", "poor"]
    id: str = Field(max_length=64)
    navigation_type: str | None = Field(default=None, max_length=32)
    route: str = Field(max_length=100, pattern=r"^/[A-Za-z0-9/_\[\]-]*$")
