from typing import Dict, Any
from langgraph.graph import StateGraph, END
from app.agents.state import ClaimState
from app.tools.oms import get_order_details_db, save_claim_to_db
from app.agents.workers.investigator import analyze_claim_evidence
from app.agents.workers.risk_evaluator import evaluate_fraud_risk
from app.agents.workers.reviewer import review_claim_policies
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
    """Audita la foto del producto, calidad de imagen y daño físico."""
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
    """Evalúa el historial de compras y reclamos del cliente para detectar anomalías."""
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

# NODO 4: Agente Validador de Políticas (Memoria Semántica RAG)
async def node_review_policies(state: ClaimState) -> Dict[str, Any]:
    """Contrasta el reclamo con el manual corporativo mediante Agentic RAG."""
    order = state["order_data"]
    visual = state.get("investigation_analysis", {})
    
    policy_review = await review_claim_policies(
        description=state["description"],
        product_name=order["product_name"],
        category=order["category"],
        days_since_delivery=order.get("days_since_delivery", 3),
        visual_damage_description=visual.get("damage_description", "")
    )
    return {
        "policy_review": policy_review.model_dump(),
        "status": "policies_reviewed"
    }

# NODO 5: Motor de Decisión Ponderado y Guardrails (HITL)
async def node_apply_guardrails_and_decision(state: ClaimState) -> Dict[str, Any]:
    """Calcula el Score Compuesto y evalúa Guardrails inmutables."""
    order = state["order_data"]
    visual = state["investigation_analysis"]
    risk = state["fraud_risk_analysis"]
    policy = state.get("policy_review", {})
    
    # 1. Cálculo de Score Compuesto Transparente
    v_score = visual.get("confidence_score", 0.0)
    p_score = 1.0 if policy.get("is_compliant", False) else 0.0
    r_score = risk.get("fraud_risk_score", 0.0)
    t_score = order.get("client_trust_score", 1.0)
    
    # Ponderación: 35% Visión + 35% Cumplimiento Política RAG + 20% Bajo Riesgo + 10% Trust
    composite_score = round((v_score * 0.35) + (p_score * 0.35) + ((1.0 - r_score) * 0.20) + (t_score * 0.10), 2)
    
    # 2. Evaluación de Guardrails y Esquema HITL
    claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"
    requires_hitl = False
    hitl_reasons = []
    status = "APPROVED_AUTO"
    message = f"Reclamo aprobado automáticamente. Cumple con: {policy.get('applied_clause', 'Política Estándar')}."
    
    # Guardrail 1: Categoría restringida por bioseguridad / higiene
    if not order.get("is_returnable", True):
        requires_hitl = True
        status = "REJECTED_CATEGORY_GUARDRAIL"
        hitl_reasons.append(f"Categoría '{order['category']}' restringida según {policy.get('applied_clause', 'manual de higiene')}.")
        message = f"Rechazado por política de higiene. {policy.get('policy_reasoning', '')}"
        
    # Guardrail 2: Monto superior al límite de autonomía ($100.000)
    elif order.get("price", 0.0) > 100000.0:
        requires_hitl = True
        status = "PENDING_HITL_HIGH_AMOUNT"
        hitl_reasons.append(f"Monto (${order['price']:,.2f}) supera el umbral autónomo de $100.000.")
        message = "Derivado a supervisión humana por alto valor económico de la orden."
        
    # Guardrail 3: Incumplimiento de políticas corporativas
    elif not policy.get("is_compliant", True):
        requires_hitl = True
        status = "PENDING_HITL_POLICY_NON_COMPLIANT"
        hitl_reasons.append(f"Incumple política: {policy.get('applied_clause', '')}. Cita: '{policy.get('clause_citation', '')}'")
        message = f"No cumple con las condiciones del manual: {policy.get('policy_reasoning', '')}"

    # Guardrail 4: Calidad deficiente de la evidencia visual
    elif visual.get("image_quality_issues") and "ninguno" not in visual.get("image_quality_issues", []):
        requires_hitl = True
        status = "PENDING_HITL_EVIDENCE_QUALITY"
        issues = ", ".join(visual.get("image_quality_issues"))
        hitl_reasons.append(f"Problemas de imagen ({issues}). {visual.get('confidence_reasoning', '')}")
        message = f"La foto no es clara ({issues}). Se requiere nueva evidencia."
        
    # Guardrail 5: Sospecha de fraude o score compuesto bajo
    elif risk.get("risk_level") == "ALTO" or composite_score < 0.65:
        requires_hitl = True
        status = "PENDING_HITL_RISK_SUSPICION"
        hitl_reasons.append(f"Score bajo ({composite_score}). Riesgos: {', '.join(risk.get('risk_reasons', []))}")
        message = "Marcado para auditoría de seguridad por nivel de riesgo de cliente."
        
    # Guardrail 6: Inconsistencia entre evidencia y relato
    elif not visual.get("matches_user_claim", False):
        requires_hitl = True
        status = "PENDING_HITL_CLAIM_MISMATCH"
        hitl_reasons.append("La evidencia visual no coincide con el daño reportado.")
        message = "La fotografía no refleja la falla descripta por el cliente."

    return {
        "claim_id": claim_id,
        "status": status,
        "composite_score": composite_score,
        "requires_hitl": requires_hitl,
        "hitl_reasons": hitl_reasons,
        "final_message": message
    }

# NODO 6: Persistencia en Memoria Episódica
async def node_persist_episodic_memory(state: ClaimState) -> Dict[str, Any]:
    """Guarda la resolución del reclamo con trazabilidad completa en la base de datos."""
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

# CONDICIÓN: Validar orden en OMS
def condition_order_valid(state: ClaimState) -> str:
    if state.get("order_data") is None:
        return "abort"
    return "continue"

# CONSTRUCCIÓN Y COMPILACIÓN DEL GRAFO DE LANGGRAPH
def build_claim_workflow():
    workflow = StateGraph(ClaimState)
    
    # 1. Registrar Nodos de los Agentes
    workflow.add_node("fetch_order", node_fetch_order)
    workflow.add_node("investigate_evidence", node_investigate_evidence)
    workflow.add_node("evaluate_fraud_risk", node_evaluate_fraud_risk)
    workflow.add_node("review_policies", node_review_policies)
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
    
    # 4. Flujo Secuencial Multi-Agente
    workflow.add_edge("investigate_evidence", "evaluate_fraud_risk")
    workflow.add_edge("evaluate_fraud_risk", "review_policies")
    workflow.add_edge("review_policies", "apply_guardrails")
    workflow.add_edge("apply_guardrails", "persist_memory")
    workflow.add_edge("persist_memory", END)
    
    return workflow.compile()

# Instancia ejecutable del Grafo
claim_graph = build_claim_workflow()