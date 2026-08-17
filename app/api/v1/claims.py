from fastapi import APIRouter, File, UploadFile, Form
from pydantic import BaseModel
from app.agents.workers.investigator import analyze_claim_evidence

router = APIRouter()

class ClaimResponse(BaseModel):
    claim_id: str
    status: str
    message: str
    analysis: dict | None = None

@router.post("/", response_model=ClaimResponse)
async def create_claim(
    client_id: str = Form(...),
    description: str = Form(...),
    image: UploadFile = File(...)
):
    if not image.content_type.startswith("image/"):
        return {"claim_id": "ERROR", "status": "failed", "message": "Solo se permiten imágenes.", "analysis": None}

    # 1. Leer los bytes de la imagen de forma asíncrona
    image_bytes = await image.read()
    
    # 2. Invocar al Agente Investigador para el análisis multimodal
    analysis_result = await analyze_claim_evidence(description, image_bytes)
    
    # 3. Respuesta al cliente (En el futuro, esto irá al Orquestador)
    return {
        "claim_id": f"CLM-{client_id}-999",
        "status": "investigation_complete",
        "message": f"Evidencia visual procesada exitosamente.",
        "analysis": analysis_result.model_dump()
    }