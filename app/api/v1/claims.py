from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.core.database import get_db
from app.tools.oms import get_order_details_db, save_claim_to_db
from app.agents.state import ClaimState
from app.agents.orchestrator import run_claim_orchestration

router = APIRouter()

class ClaimResponse(BaseModel):
    claim_id: str
    status: str
    composite_score: float
    requires_hitl: bool
    hitl_reason: Optional[str] = None
    summary: str
    details: Dict[str, Any]

@router.post("/", response_model=ClaimResponse)
async def create_claim(
    client_id: str = Form(...),
    order_id: str = Form(...),
    description: str = Form(...),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos de imagen.")

    # 1. Consultar la orden a la BD
    order_data = await get_order_details_db(order_id, db)
    if not order_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Orden '{order_id}' no existe.")

    # Validar que el cliente corresponda a la orden
    if order_data["client_id"] != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El cliente no coincide con la orden.")

    # 2. Leer imagen
    image_bytes = await image.read()

    # 3. Construcción del Estado
    state = ClaimState(
        client_id=client_id,
        order_id=order_id,
        description=description,
        image_bytes=image_bytes,
        order_data=order_data
    )

    # 4. Ejecución del Orquestador Agéntico Multi-Agente
    decision = await run_claim_orchestration(state)

    # 5. Persistir en Memoria Episódica (DB)
    await save_claim_to_db(
        order_id=order_id,
        client_id=client_id,
        description=description,
        is_damaged=state.visual_analysis.is_product_damaged,
        confidence=decision.composite_score,
        requires_hitl=decision.requires_hitl,
        status=decision.status,
        db=db
    )

    # 6. Respuesta al cliente
    return {
        "claim_id": decision.claim_id,
        "status": decision.status,
        "composite_score": decision.composite_score,
        "requires_hitl": decision.requires_hitl,
        "hitl_reason": decision.hitl_reason,
        "summary": decision.summary_for_agent,
        "details": {
            "visual_analysis": state.visual_analysis.model_dump(),
            "fraud_risk_analysis": state.risk_analysis.model_dump()
        }
    }