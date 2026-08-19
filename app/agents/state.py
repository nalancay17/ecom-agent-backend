from typing import Optional, Dict, Any, TypedDict, List

# Estructura de estado para el ciclo de decisión
class ClaimState(TypedDict):
    # 1. Datos iniciales ingresados por el usuario
    client_id: str
    order_id: str
    description: str
    image_bytes: bytes
    
    # 2. Datos contextuales recuperados (OMS / Memoria Episódica)
    order_data: Optional[Dict[str, Any]]
    
    # 3. Informes generados por los agentes especializados
    investigation_analysis: Optional[Dict[str, Any]]
    fraud_risk_analysis: Optional[Dict[str, Any]]
    
    # 4. Métricas de decisión y Guardrails
    composite_score: float
    requires_hitl: bool
    hitl_reasons: List[str]
    
    # 5. Salida final
    claim_id: str
    status: str
    final_message: str