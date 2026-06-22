from fastapi import APIRouter, Depends

from app.core.auth_context import AuthContext, get_auth_context
from app.schemas.agent_schema import AgentQueryRequest, AgentQueryResponse
from app.services.dashboard_agent import run_dashboard_agent


router = APIRouter(tags=["Agent"])


@router.post(
    "/agent/query",
    response_model=AgentQueryResponse,
)
def query_agent(
    payload: AgentQueryRequest,
    auth_context: AuthContext = Depends(get_auth_context),
):
    return run_dashboard_agent(
        query=payload.query,
        auth_context=auth_context,
    )
