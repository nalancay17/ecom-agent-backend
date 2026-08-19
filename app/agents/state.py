from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.schemas.guardrails import ClaimAnalysis, FraudRiskAnalysis, FinalDecision

# Estructura de estado para el ciclo de decisión
class ClaimState(BaseModel):
    client_id: str
    order_id: str
    description: str
    image_bytes: bytes
    order_data: Optional[Dict[str, Any]] = None
    visual_analysis: Optional[ClaimAnalysis] = None
    risk_analysis: Optional[FraudRiskAnalysis] = None
    final_decision: Optional[FinalDecision] = None