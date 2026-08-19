from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from app.agents.orchestrator import claim_graph

router = APIRouter()

class ClaimResponse(BaseModel):
    claim_id: Optional[str] = None
    status: str
    message: str
    composite_score: Optional[float] = None
    requires_hitl: bool = False
    hitl_reasons: Optional[List[str]] = None
    analysis: Optional[Dict[str, Any]] = None
    risk_evaluation: Optional[Dict[str, Any]] = None
    policy_review: Optional[Dict[str, Any]] = None

@router.post("", response_model=ClaimResponse)
@router.post("/", response_model=ClaimResponse, include_in_schema=False)
async def create_claim(
    client_id: str = Form(...),
    order_id: str = Form(...),
    description: str = Form(...),
    image: UploadFile = File(...)
):
    if not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Solo se permiten archivos de imagen."
        )

    # 1. Leer imagen
    image_bytes = await image.read()

    # 2. Inicializar estado para LangGraph
    initial_state = {
        "client_id": client_id,
        "order_id": order_id,
        "description": description,
        "image_bytes": image_bytes,
        "order_data": None,
        "investigation_analysis": None,
        "fraud_risk_analysis": None,
        "policy_review": None,
        "composite_score": 0.0,
        "requires_hitl": False,
        "hitl_reasons": [],
        "claim_id": "",
        "status": "initiated",
        "final_message": ""
    }

    # 3. Ejecución asíncrona del Grafo de Estados
    final_state = await claim_graph.ainvoke(initial_state)

    # 4. Manejo de errores de validación de orden/cliente
    if final_state.get("status") == "order_not_found":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=final_state["final_message"]
        )
    if final_state.get("status") == "client_mismatch":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail=final_state["final_message"]
        )

    # 5. Respuesta enriquecida para el cliente y observabilidad
    return {
        "claim_id": final_state.get("claim_id"),
        "status": final_state.get("status"),
        "message": final_state.get("final_message"),
        "composite_score": final_state.get("composite_score"),
        "requires_hitl": final_state.get("requires_hitl", False),
        "hitl_reasons": final_state.get("hitl_reasons"),
        "analysis": final_state.get("investigation_analysis"),
        "risk_evaluation": final_state.get("fraud_risk_analysis"),
        "policy_review": final_state.get("policy_review")
    }