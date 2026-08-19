from pydantic import BaseModel, Field
from typing import List, Optional

# Esquema estricto para el análisis inicial de la imagen
class ClaimAnalysis(BaseModel):
    is_product_damaged: bool = Field(description="¿Se observa daño físico real en el producto en la imagen?")
    damage_description: str = Field(description="Breve descripción del daño observado en la imagen.")
    matches_user_claim: bool = Field(description="¿El daño en la imagen coincide con la descripción del usuario?")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Nivel de confianza en el análisis visual (0.0 a 1.0).")
    confidence_reasoning: str = Field(description="Explicación detallada de por qué se asignó este score de confianza.")
    image_quality_issues: Optional[List[str]] = Field(
        default=[],
        description="Problemas detectados en la evidencia (ej: 'borrosa', 'baja_iluminacion', 'objeto_lejano', 'ninguno')."
    )

# Esquema para análisis de fraude
class FraudRiskAnalysis(BaseModel):
    fraud_risk_score: float = Field(ge=0.0, le=1.0, description="Nivel de riesgo de fraude estimado (0.0 = seguro, 1.0 = alto riesgo).")
    risk_level: str = Field(description="Nivel categórico: 'BAJO', 'MEDIO' o 'ALTO'.")
    risk_reasons: List[str] = Field(description="Factores que justifican el nivel de riesgo asignado.")
    is_suspicious: bool = Field(description="Indica si el caso presenta anomalías que requieren intervención humana.")

# Esquema de decisión final del análisis
class FinalDecision(BaseModel):
    claim_id: str
    status: str
    composite_score: float
    requires_hitl: bool
    hitl_reason: Optional[str] = None
    summary_for_agent: str