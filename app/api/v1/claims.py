from fastapi import APIRouter, File, UploadFile, Form
from pydantic import BaseModel

router = APIRouter()

class ClaimResponse(BaseModel):
    claim_id: str
    status: str
    message: str

@router.post("/", response_model=ClaimResponse)
async def create_claim(
    client_id: str = Form(...),
    description: str = Form(...),
    image: UploadFile = File(...)
):
    # TODO: Aquí se integrará la orquestación agéntica en el futuro.
    # Por ahora, solo simula la recepción exclusiva vía web/imagen.
    
    # Validar que sea una imagen
    if not image.content_type.startswith("image/"):
        return {"claim_id": "ERROR", "status": "failed", "message": "Solo se permiten imágenes."}

    return {
        "claim_id": "CLM-12345",
        "status": "received",
        "message": f"Reclamo de {client_id} recibido correctamente con evidencia visual."
    }
