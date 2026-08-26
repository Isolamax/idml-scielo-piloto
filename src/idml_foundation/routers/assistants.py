from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from idml_foundation.ai.contracts import ALLOWED_TOOLS
from idml_foundation.ai.outputs import AgentDomain
from idml_foundation.dependencies import Database, require_permission
from idml_foundation.models import AgentProposal, AgentRun
from idml_foundation.rbac import Permission, TenantContext
from idml_foundation.schemas import AgentCapabilitiesRead, AgentProposalRead, AgentRunRead
from idml_foundation.settings import get_settings

router = APIRouter(prefix="/v1/ai", tags=["assistive-ai"])


@router.get("/capabilities", response_model=AgentCapabilitiesRead)
def capabilities(
    context: Annotated[TenantContext, require_permission(Permission.RESOURCE_READ)],
) -> AgentCapabilitiesRead:
    del context
    settings = get_settings()
    return AgentCapabilitiesRead(
        enabled=settings.feature_openclaw,
        swarm_enabled=settings.feature_ai_swarm,
        domains=[domain.value for domain in AgentDomain],
        tools=sorted(ALLOWED_TOOLS),
        max_cost_microusd=settings.ai_max_cost_microusd,
        max_concurrency=settings.ai_max_concurrency,
    )


@router.get("/runs", response_model=list[AgentRunRead])
def list_runs(
    db: Database,
    context: Annotated[TenantContext, require_permission(Permission.RESOURCE_READ)],
    review_item_id: Annotated[str | None, Query()] = None,
) -> list[AgentRun]:
    statement = select(AgentRun).where(AgentRun.organization_id == context.organization_id)
    if review_item_id is not None:
        statement = statement.where(AgentRun.review_item_id == review_item_id)
    return list(db.scalars(statement.order_by(AgentRun.created_at.desc()).limit(200)))


@router.get("/proposals/{proposal_id}", response_model=AgentProposalRead)
def get_proposal(
    proposal_id: str,
    db: Database,
    context: Annotated[TenantContext, require_permission(Permission.RESOURCE_READ)],
) -> AgentProposal:
    proposal = db.scalar(
        select(AgentProposal).where(
            AgentProposal.id == proposal_id,
            AgentProposal.organization_id == context.organization_id,
        )
    )
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="proposal not found")
    return proposal
