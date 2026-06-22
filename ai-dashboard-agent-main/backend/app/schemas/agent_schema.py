from typing import Any

from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    query: str = Field(
        min_length=2,
        max_length=500,
        examples=["What was the sales in the last 5 months?"]
    )


class FiltersApplied(BaseModel):
    metric: str | None = None
    time_range: str | None = None
    tenant_id: str | None = None
    other: dict[str, Any] | None = None


class AgentQueryResponse(BaseModel):
    intent: str
    filters_applied: FiltersApplied
    widgets_to_show: list[str]
    widgets_to_hide: list[str]
    text_response: str

    # Extra backend-to-frontend payload.
    # This contains pre-aggregated data only, not raw DB rows.
    widget_payloads: dict[str, Any] = {}
