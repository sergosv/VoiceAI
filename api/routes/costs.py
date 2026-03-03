"""Endpoint de estimación de costos."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.cost_rates import estimate_cost
from api.middleware.auth import CurrentUser, get_current_user
from api.schemas import CostEstimateRequest, CostEstimateResponse, CostLineItem

router = APIRouter()


@router.post("/estimate", response_model=CostEstimateResponse)
async def estimate_costs(
    body: CostEstimateRequest,
    user: CurrentUser = Depends(get_current_user),
) -> CostEstimateResponse:
    """Estima costos para una combinación de proveedores y duración."""
    result = estimate_cost(
        stt_provider=body.stt_provider,
        llm_provider=body.llm_provider,
        tts_provider=body.tts_provider,
        minutes=body.minutes,
    )
    return CostEstimateResponse(
        minutes=result["minutes"],
        platform_cost=result["platform_cost"],
        external_cost_estimate=result["external_cost_estimate"],
        total_estimate=result["total_estimate"],
        lines=[CostLineItem(**line) for line in result["lines"]],
        note=result["note"],
    )
