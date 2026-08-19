from fastapi import APIRouter, File, UploadFile, Form, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.agents.orchestrator import claim_graph
from app.tools.oms import (
    get_claim_by_id_db,
    get_pending_hitl_claims_db,
    resolve_claim_by_human_db,
    get_claims_metrics_db
)
from app.tools.logistics import generate_return_shipping_label

router = APIRouter()

# --- Modelos Pydantic para Peticiones y Respuestas ---

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
    action_details: Optional[Dict[str, Any]] = None

class HumanResolutionRequest(BaseModel):
    decision: str = Field(description="Decisión del supervisor: 'APPROVED_BY_HUMAN' o 'REJECTED_BY_HUMAN'")
    reviewer_notes: str = Field(description="Justificación y notas de auditoría del supervisor humano.")

# --- 1. Crear y Procesar Nuevo Reclamo (Flujo Agéntico LangGraph) ---
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
        "action_details": None,
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

    # 5. Respuesta enriquecida
    return {
        "claim_id": final_state.get("claim_id"),
        "status": final_state.get("status"),
        "message": final_state.get("final_message"),
        "composite_score": final_state.get("composite_score"),
        "requires_hitl": final_state.get("requires_hitl", False),
        "hitl_reasons": final_state.get("hitl_reasons"),
        "analysis": final_state.get("investigation_analysis"),
        "risk_evaluation": final_state.get("fraud_risk_analysis"),
        "policy_review": final_state.get("policy_review"),
        "action_details": final_state.get("action_details")
    }

# --- 2. Listar Reclamos Pendientes de Auditoría Humana (HITL Queue) ---
@router.get("/pending", response_model=List[Dict[str, Any]])
async def get_pending_hitl_claims(db: AsyncSession = Depends(get_db)):
    """Devuelve la cola de reclamos derivados a Human-In-The-Loop para el panel de administración."""
    pending_claims = await get_pending_hitl_claims_db(db)
    return pending_claims

# --- 3. Métricas y Observabilidad para el Dashboard ---
@router.get("/metrics", response_model=Dict[str, Any])
async def get_claims_metrics(db: AsyncSession = Depends(get_db)):
    """Métricas de rendimiento, automatización y derivación del sistema para el supervisor."""
    metrics = await get_claims_metrics_db(db)
    return metrics

# --- 4. Consultar Estado de un Reclamo por ID (Portal Cliente) ---
@router.get("/{claim_id}", response_model=Dict[str, Any])
async def get_claim_status(claim_id: str, db: AsyncSession = Depends(get_db)):
    """Permite al cliente o supervisor consultar el estado y guía de un reclamo en cualquier momento."""
    claim = await get_claim_by_id_db(claim_id, db)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Reclamo '{claim_id}' no encontrado.")
    return claim

# --- 5. Resolución Humana de un Reclamo HITL (Supervisor Action) ---
@router.post("/{claim_id}/resolve", response_model=Dict[str, Any])
async def resolve_hitl_claim(
    claim_id: str,
    payload: HumanResolutionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Permite al supervisor humano aprobar o rechazar un reclamo pendiente.
    Si se aprueba, genera automáticamente la guía y etiqueta de logística inversa.
    """
    claim = await get_claim_by_id_db(claim_id, db)
    if not claim:
        raise HTTPException(status_code=404, detail=f"Reclamo '{claim_id}' no encontrado.")

    tracking_number = None
    label_url = None

    # Si el humano aprueba, gatillamos la herramienta de logística
    if payload.decision == "APPROVED_BY_HUMAN":
        logistics = await generate_return_shipping_label(
            claim_id=claim_id,
            order_id=claim["order_id"],
            client_name=claim["client_name"],
            product_name=claim["product_name"]
        )
        tracking_number = logistics["tracking_number"]
        label_url = logistics["label_url"]

    resolution = await resolve_claim_by_human_db(
        claim_id=claim_id,
        decision=payload.decision,
        reviewer_notes=payload.reviewer_notes,
        tracking_number=tracking_number,
        label_url=label_url,
        db=db
    )

    return {
        "message": f"Reclamo {claim_id} resuelto por operador humano.",
        "resolution": resolution
    }