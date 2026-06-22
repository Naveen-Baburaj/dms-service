from fastapi import APIRouter

from app.services.widget_registry import WIDGET_REGISTRY


router = APIRouter(tags=["Widgets"])


@router.get("/widgets/registry")
def get_widget_registry():
    """
    Frontend-facing widget registry.

    The frontend should use these widget IDs exactly when mapping
    backend responses to visible dashboard components.
    """

    return {
        "widgets": list(WIDGET_REGISTRY.values()),
        "widget_ids": list(WIDGET_REGISTRY.keys()),
        "usage_rule": (
            "Frontend must use widgets_to_show and widgets_to_hide from "
            "the agent response. Frontend should not perform its own intent detection."
        )
    }
