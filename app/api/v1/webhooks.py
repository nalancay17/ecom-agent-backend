from fastapi import APIRouter

router = APIRouter()

@router.post("/logistics")
def logistics_webhook(payload: dict):
    # TODO: Endpoint para recibir actualizaciones de estado del ERP/Logística
    return {"status": "received"}
