from fastapi import APIRouter


router = APIRouter(tags=["Examples"])


@router.get("/agent/examples")
def get_agent_examples():
    """
    Example prompts and integration notes for the frontend team.
    """

    return {
        "endpoint": "POST /api/v1/agent/query",
        "local_base_url": "http://127.0.0.1:8000",
        "development_headers": {
            "tenant_user": {
                "Content-Type": "application/json",
                "x-user-role": "tenant_user",
                "x-tenant-id": "suzuki"
            },
            "service_centre_admin": {
                "Content-Type": "application/json",
                "x-user-role": "service_centre_admin"
            }
        },
        "production_auth_rule": (
            "In production, tenant_id and user_role must come from verified "
            "auth/JWT/session. The frontend must not send tenant_id or role "
            "as editable request-body fields."
        ),
        "examples": [
            {
                "label": "Tenant sales query",
                "role": "tenant_user",
                "tenant_id": "suzuki",
                "request": {
                    "query": "What was the sales in the last 5 months?"
                }
            },
            {
                "label": "Tenant service query",
                "role": "tenant_user",
                "tenant_id": "suzuki",
                "request": {
                    "query": "Show service records for the last 3 months"
                }
            },
            {
                "label": "Tenant inventory query",
                "role": "tenant_user",
                "tenant_id": "suzuki",
                "request": {
                    "query": "Show current inventory stock"
                }
            },
            {
                "label": "Admin cross-tenant comparison",
                "role": "service_centre_admin",
                "tenant_id": None,
                "request": {
                    "query": "Compare sales in the last 5 months across tenants"
                }
            }
        ],
        "response_fields": {
            "intent": "Detected backend intent",
            "filters_applied": "Metric, time range, tenant scope, and additional filters",
            "widgets_to_show": "Widget IDs frontend should show or highlight",
            "widgets_to_hide": "Widget IDs frontend should hide, collapse, or dim",
            "text_response": "Natural-language summary for the user",
            "widget_payloads": "Pre-aggregated chart/table data keyed by widget ID"
        }
    }
