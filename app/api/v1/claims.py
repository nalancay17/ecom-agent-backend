from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.database import get_db
from app.agents.workers.investigator import analyze_claim_evidence
from app.tools.oms import get_order_details_db, save_claim_to_db

router = APIRouter()

class ClaimResponse(BaseModel):
    claim_id: str
    status: str
    message: str
    analysis: dict | None = None,
    requires_hitl: bool = False

@router.post("/", response_model=ClaimResponse)
async def create_claim(
    client_id: str = Form(...),
    order_id: str = Form(...),
    description: str = Form(...),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    if not image.content_type.startswith("image/"):
        return {"claim_id": "ERROR", "status": "failed", "message": "Solo se permiten imágenes.", "analysis": None, "requires_hitl": False}

    # 1. Consultar la orden a la BD
    order_data = await get_order_details_db(order_id, db)
    if not order_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Orden '{order_id}' no encontrada en el sistema.")

    # Validar que el cliente corresponda a la orden
    if order_data["client_id"] != client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="El cliente no coincide con la orden.")

    # 2. Leer imagen
    image_bytes = await image.read()
    
    # 3. Invocar al Agente Investigador para el análisis de validez de reclamo
    analysis_result = await analyze_claim_evidence(
        description=description,
        image_bytes=image_bytes,
        product_name=order_data["product_name"],
        category=order_data["category"]
    )

    # 4. Aplicación de Guardrails (Monto > $100.000 o Categoría Prohibida)
    requires_hitl = False
    claim_status = "APPROVED_AUTO"
    if not order_data["is_returnable"]:
        requires_hitl = True
        claim_status = "REJECTED_CATEGORY_GUARDRAIL"
    elif order_data["price"] > 100000:
        requires_hitl = True
        claim_status = "PENDING_HITL_HIGH_AMOUNT"
    elif analysis_result.confidence_score < 0.7 or not analysis_result.matches_user_claim:
        requires_hitl = True
        claim_status = "PENDING_HITL_LOW_CONFIDENCE"

    # 5. Persistir en Memoria Episódica (DB)
    claim_id = await save_claim_to_db(
        order_id=order_id,
        client_id=client_id,
        description=description,
        is_damaged=analysis_result.is_product_damaged,
        confidence=analysis_result.confidence_score,
        requires_hitl=requires_hitl,
        status=claim_status,
        db=db
    )

    # 6. Respuesta al cliente (En el futuro, esto irá al Orquestador)
    return {
        "claim_id": claim_id,
        "status": claim_status,
        "message": "Evidencia visual procesada exitosamente. Reclamo evaluado y guardado en memoria episódica.",
        "analysis": analysis_result.model_dump(),
        "requires_hitl": requires_hitl
    }