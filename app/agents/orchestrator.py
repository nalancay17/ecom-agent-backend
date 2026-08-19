from typing import Dict, Any
from langgraph.graph import StateGraph, END
from app.agents.state import ClaimState
from app.tools.oms import get_order_details_db, save_claim_to_db
from app.agents.workers.investigator import analyze_claim_evidence
from app.agents.workers.risk_evaluator import evaluate_fraud_risk
import uuid

# NODO 1: Recuperación orden en DB y validaciones 
async def node_fetch_order(state: ClaimState) -> Dict[str, Any]:
    """Consulta la orden y la reputación histórica del cliente."""
    order_data = await get_order_details_db(state["order_id"])
    if not order_data:
        return {
            "order_data": None,
            "status": "order_not_found",
            "final_message": f"La orden '{state['order_id']}' no existe en el sistema."
        }
    if order_data["client_id"] != state["client_id"]:
        return {
            "order_data": None,
            "status": "client_mismatch",
            "final_message": "El cliente no coincide con el titular de la orden."
        }
    return {
        "order_data": order_data,
        "status": "order_verified"
    }

# NODO 2: Agente Investigador (análisis visual de evidencia)
async def node_investigate_evidence(state: ClaimState) -> Dict[str, Any]:
    """Audita la foto del producto y detecta calidad y daños."""
    order = state["order_data"]
    analysis = await analyze_claim_evidence(
        description=state["description"],
        image_bytes=state["image_bytes"],
        product_name=order["product_name"],
        category=order["category"]
    )
    return {
        "investigation_analysis": analysis.model_dump(),
        "status": "evidence_analyzed"
    }

# NODO 3: Agente Evaluador de Riesgo y Fraude (Memoria Episódica)
async def node_evaluate_fraud_risk(state: ClaimState) -> Dict[str, Any]:
    """Evalúa patrones de reclamos previos y contexto de riesgo."""
    order = state["order_data"]
    risk_analysis = await evaluate_fraud_risk(
        client_name=order.get("client_name", "Cliente"),
        client_tier=order.get("client_tier", "REGULAR"),
        trust_score=order.get("client_trust_score", 1.0),
        total_past_claims=order.get("total_past_claims", 0),
        recent_claims_90d=order.get("recent_claims_90d", 0),
        order_amount=order.get("price", 0.0),
        product_category=order.get("category", "")
    )
    return {
        "fraud_risk_analysis": risk_analysis.model_dump(),
        "status": "risk_evaluated"
    }

# NODO 4: Decisión y Guardrails (HITL) ---
async def node_apply_guardrails_and_decision(state: ClaimState) -> Dict[str, Any]:
    """Calcula el Score Compuesto y evalúa Guardrails inmutables."""
    order = state["order_data"]
    visual = state["investigation_analysis"]
    risk = state["fraud_risk_analysis"]
    
    # 1. Cálculo de Score Compuesto Transparente
    v_score = visual.get("confidence_score", 0.0)
    r_score = risk.get("fraud_risk_score", 0.0)
    t_score = order.get("client_trust_score", 1.0)
    
    composite_score = round((v_score * 0.50) + ((1.0 - r_score) * 0.30) + (t_score * 0.20), 2)
    
    # 2. Evaluación de Guardrails
    claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"
    requires_hitl = False
    hitl_reasons = []
    status = "APPROVED_AUTO"
    message = "Reclamo pre-aprobado exitosamente. Se procede a coordinar la logística de devolución."
    
    # Guardrail 1: Categoría restringida por higiene
    if not order.get("is_returnable", True):
        requires_hitl = True
        status = "REJECTED_CATEGORY_GUARDRAIL"
        hitl_reasons.append(f"Categoría '{order['category']}' restringida por política de higiene.")
        message = "El producto pertenece a una categoría no retornable por motivos de higiene."
        
    # Guardrail 2: Monto supera umbral de autonomía ($100.000)
    elif order.get("price", 0.0) > 100000.0:
        requires_hitl = True
        status = "PENDING_HITL_HIGH_AMOUNT"
        hitl_reasons.append(f"Monto (${order['price']:,.2f}) supera el umbral autónomo de $100.000.")
        message = "Reclamo derivado a supervisión humana debido al alto valor del producto."
        
    # Guardrail 3: Calidad deficiente de la evidencia
    elif visual.get("image_quality_issues") and "ninguno" not in visual.get("image_quality_issues", []):
        requires_hitl = True
        status = "PENDING_HITL_EVIDENCE_QUALITY"
        issues = ", ".join(visual.get("image_quality_issues"))
        hitl_reasons.append(f"Problemas de calidad en la imagen: {issues}.")
        message = f"La foto enviada no es nítida ({issues}). Se requiere revisión o reenvío."
        
    # Guardrail 4: Alto riesgo de fraude o score compuesto bajo
    elif risk.get("risk_level") == "ALTO" or composite_score < 0.65:
        requires_hitl = True
        status = "PENDING_HITL_RISK_SUSPICION"
        hitl_reasons.append(f"Score compuesto bajo ({composite_score}). Riesgo de fraude detectado.")
        message = "Reclamo marcado para revisión de seguridad por patrones inusuales."
        
    # Guardrail 5: Evidencia no coincide con el daño reportado
    elif not visual.get("matches_user_claim", False):
        requires_hitl = True
        status = "PENDING_HITL_CLAIM_MISMATCH"
        hitl_reasons.append("La evidencia visual no coincide con el daño reportado por el cliente.")
        message = "La imagen no muestra la falla descripta en el reclamo."
    return {
        "claim_id": claim_id,
        "status": status,
        "composite_score": composite_score,
        "requires_hitl": requires_hitl,
        "hitl_reasons": hitl_reasons,
        "final_message": message
    }

# NODO 5: Persistencia en Memoria Episódica
async def node_persist_episodic_memory(state: ClaimState) -> Dict[str, Any]:
    """Guarda la resolución final y su trazabilidad en la base de datos."""
    visual = state["investigation_analysis"]
    await save_claim_to_db(
        claim_id=state["claim_id"],
        order_id=state["order_id"],
        client_id=state["client_id"],
        description=state["description"],
        is_damaged=visual.get("is_product_damaged", False),
        confidence=state["composite_score"],
        requires_hitl=state["requires_hitl"],
        status=state["status"]
    )
    return {"status": state["status"]}

# CONDICIÓN: Verificar si la orden es válida para continuar o abortar
def condition_order_valid(state: ClaimState) -> str:
    if state.get("order_data") is None:
        return "abort"
    return "continue"


# CONSTRUCCIÓN Y COMPILACIÓN DEL GRAFO
def build_claim_workflow():
    workflow = StateGraph(ClaimState)
    
    # 1. Registro de Nodos
    workflow.add_node("fetch_order", node_fetch_order)
    workflow.add_node("investigate_evidence", node_investigate_evidence)
    workflow.add_node("evaluate_fraud_risk", node_evaluate_fraud_risk)
    workflow.add_node("apply_guardrails", node_apply_guardrails_and_decision)
    workflow.add_node("persist_memory", node_persist_episodic_memory)
    
    # 2. Punto de Entrada
    workflow.set_entry_point("fetch_order")
    
    # 3. Rama Condicional
    workflow.add_conditional_edges(
        "fetch_order",
        condition_order_valid,
        {
            "continue": "investigate_evidence",
            "abort": END
        }
    )
    
    # 4. Flujo Secuencial
    workflow.add_edge("investigate_evidence", "evaluate_fraud_risk")
    workflow.add_edge("evaluate_fraud_risk", "apply_guardrails")
    workflow.add_edge("apply_guardrails", "persist_memory")
    workflow.add_edge("persist_memory", END)
    
    return workflow.compile()

# Instancia del Grafo
claim_graph = build_claim_workflow()