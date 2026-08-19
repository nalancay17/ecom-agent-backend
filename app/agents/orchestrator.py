from app.agents.state import ClaimState
from app.agents.workers.investigator import analyze_claim_evidence
from app.agents.workers.risk_evaluator import evaluate_fraud_risk
from app.schemas.guardrails import FinalDecision
import uuid

async def run_claim_orchestration(state: ClaimState) -> FinalDecision:
    """
    Orquestador Central:
    1. Ejecuta el Agente Investigador (Visión).
    2. Ejecuta el Agente Evaluador de Riesgo (Memoria Episódica).
    3. Calcula el Score de Confianza Compuesto (Explicable).
    4. Aplica Guardrails y determina si requiere revisión humana (HITL).
    """
    order = state.order_data
    
    # 1. Análisis Visual
    state.visual_analysis = await analyze_claim_evidence(
        description=state.description,
        image_bytes=state.image_bytes,
        product_name=order["product_name"],
        category=order["category"]
    )
    
    # 2. Análisis de Riesgo
    state.risk_analysis = await evaluate_fraud_risk(
        client_name=order.get("client_name", "Cliente"),
        client_tier=order.get("client_tier", "REGULAR"),
        trust_score=order.get("client_trust_score", 1.0),
        total_past_claims=order.get("total_past_claims", 0),
        recent_claims_90d=order.get("recent_claims_90d", 0),
        order_amount=order.get("price", 0.0),
        product_category=order.get("category", "")
    )
    
    # 3. Cálculo Matemático del Score Compuesto (Fórmula Transparente)
    # 50% Evidencia Visual + 30% Reputación/Bajo Riesgo + 20% Antigüedad/Trust Score
    visual_weight = state.visual_analysis.confidence_score * 0.50
    risk_weight = (1.0 - state.risk_analysis.fraud_risk_score) * 0.30
    trust_weight = order.get("client_trust_score", 1.0) * 0.20
    
    composite_score = round(visual_weight + risk_weight + trust_weight, 2)
    
    # 4. Evaluación de Guardrails y Reglas de Negocio
    claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"
    requires_hitl = False
    hitl_reasons = []
    status = "APPROVED_AUTO"
    
    # Guardrail 1: Categoría no retornable (Higiene / Ropa interior)
    if not order.get("is_returnable", True):
        requires_hitl = True
        status = "REJECTED_CATEGORY_GUARDRAIL"
        hitl_reasons.append(f"Categoría '{order['category']}' restringida por política de higiene.")
        
    # Guardrail 2: Monto superior al umbral ($100.000)
    elif order.get("price", 0) > 100000.0:
        requires_hitl = True
        status = "PENDING_HITL_HIGH_AMOUNT"
        hitl_reasons.append(f"Monto de orden (${order['price']:,.2f}) supera el límite de autonomía ($100.000).")
        
    # Guardrail 3: Calidad de evidencia insuficiente
    elif state.visual_analysis.image_quality_issues and "ninguno" not in state.visual_analysis.image_quality_issues:
        requires_hitl = True
        status = "PENDING_HITL_EVIDENCE_QUALITY"
        hitl_reasons.append(f"Problemas en foto: {', '.join(state.visual_analysis.image_quality_issues)}. {state.visual_analysis.confidence_reasoning}")
        
    # Guardrail 4: Riesgo de fraude alto o score compuesto bajo
    elif state.risk_analysis.risk_level == "ALTO" or composite_score < 0.65:
        requires_hitl = True
        status = "PENDING_HITL_RISK_SUSPICION"
        hitl_reasons.append(f"Score compuesto bajo ({composite_score}). Motivos de riesgo: {', '.join(state.risk_analysis.risk_reasons)}")
        
    elif not state.visual_analysis.matches_user_claim:
        requires_hitl = True
        status = "PENDING_HITL_CLAIM_MISMATCH"
        hitl_reasons.append("La evidencia visual no coincide con el daño reportado.")
        
    decision = FinalDecision(
        claim_id=claim_id,
        status=status,
        composite_score=composite_score,
        requires_hitl=requires_hitl,
        hitl_reason=" | ".join(hitl_reasons) if hitl_reasons else None,
        summary_for_agent=(
            f"Evaluación completada. Score Compuesto: {composite_score}. "
            f"Visión: {state.visual_analysis.confidence_score}. "
            f"Riesgo: {state.risk_analysis.fraud_risk_score} ({state.risk_analysis.risk_level})."
        )
    )
    
    state.final_decision = decision
    return decision