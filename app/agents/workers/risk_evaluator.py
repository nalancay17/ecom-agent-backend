from app.schemas.guardrails import FraudRiskAnalysis
from app.core.llm_factory import call_text_llm_with_fallback

async def evaluate_fraud_risk(
    client_name: str,
    client_tier: str,
    trust_score: float,
    total_past_claims: int,
    recent_claims_90d: int,
    order_amount: float,
    product_category: str
) -> FraudRiskAnalysis:
    """
    Agente Evaluador de Riesgos y Fraude (Especializado en texto / memoria episódica).
    
    Usa Groq Llama 3.1 8B Instant como modelo primario:
    - Latencia < 150ms gracias a la LPU de Groq.
    - Ideal para clasificar tablas de historial de clientes y devolver JSON estricto.
    
    Fallback automático a Gemini 3.6 Flash si Groq agota cuota o falla.
    """
    prompt = f"""
    Eres el Agente Evaluador de Riesgos y Fraude de E-Com Agent.
    Analiza el siguiente perfil de cliente y contexto de compra para determinar el riesgo de reclamo fraudulento.
    
    PERFIL DEL CLIENTE (Memoria Episódica):
    - Nombre: {client_name}
    - Nivel/Segmento: {client_tier}
    - Score de Confianza Histórico: {trust_score} (1.0 = excelente, 0.0 = desconocido/sospechoso)
    - Reclamos históricos totales: {total_past_claims}
    - Reclamos en los últimos 90 días: {recent_claims_90d}
    
    CONTEXTO DE LA OPERACIÓN ACTUAL:
    - Monto de la orden: ${order_amount:,.2f}
    - Categoría del producto: {product_category}
    
    CRITERIOS DE DETECCIÓN DE FRAUDE (aplíca estrictamente):
    - Alta frecuencia de reclamos recientes (> 2 en 90 días) es señal de alerta.
    - Montos elevados combinados con clientes nuevos o con trust_score < 0.5 elevan el riesgo.
    - Clientes VIP (trust_score > 0.85) con pocos reclamos históricos (< 3 totales) deben tener riesgo bajo.
    - Si recent_claims_90d == 0 y trust_score > 0.7, el riesgo debe ser BAJO o MUY_BAJO.
    """

    try:
        return await call_text_llm_with_fallback(
            prompt=prompt,
            response_schema=FraudRiskAnalysis,
            task_type="fast"  # Llama 3.1 8B: máxima velocidad para clasificación
        )
    except Exception as e:
        # Contingencia defensiva: si ambos modelos fallan, derivar al supervisor
        return FraudRiskAnalysis(
            fraud_risk_score=0.5,
            risk_level="MEDIO",
            risk_reasons=[f"Evaluación de riesgo no disponible: ambos proveedores fallaron. Error: {str(e)}"],
            is_suspicious=True
        )