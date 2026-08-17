from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status
from pydantic import BaseModel
from app.agents.workers.investigator import analyze_claim_evidence
from app.tools.oms import get_order_details

router = APIRouter()

class ClaimResponse(BaseModel):
    claim_id: str
    status: str
    message: str
    analysis: dict | None = None

@router.post("/", response_model=ClaimResponse)
async def create_claim(
    client_id: str = Form(...),
    order_id: str = Form(...),
    description: str = Form(...),
    image: UploadFile = File(...)
):
    if not image.content_type.startswith("image/"):
        return {"claim_id": "ERROR", "status": "failed", "message": "Solo se permiten imágenes.", "analysis": None}

    # 1. Consultar el OMS
    order_data = await get_order_details(order_id)
    if not order_data:
        raise HTTPException(status_code=404, detail="Orden no encontrada en el sistema.")

    # Validar que el cliente corresponda a la orden
    if order_data["client_id"] != client_id:
        raise HTTPException(status_code=403, detail="El cliente no coincide con la orden.")

    # 2. Leer imagen
    image_bytes = await image.read()
    
    # 3. Invocar al Agente Investigador para el análisis de validez de reclamo
    analysis_result = await analyze_claim_evidence(
        description=description,
        image_bytes=image_bytes,
        product_name=order_data["product_name"],
        category=order_data["category"]
    )    
    # 4. Respuesta al cliente (En el futuro, esto irá al Orquestador)
    return {
        "claim_id": f"CLM-{client_id}-999",
        "status": "investigation_complete",
        "message": f"Evidencia visual procesada exitosamente.",
        "analysis": analysis_result.model_dump()
    }