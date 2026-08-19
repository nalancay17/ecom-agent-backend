from google import genai
from google.genai import types
from app.core.config import settings
from app.schemas.guardrails import FraudRiskAnalysis

# Evaluación de riesgo de fraude (análisis de fraude)
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
    Agente Evaluador de Riesgos: Analiza la Memoria Episódica del cliente
    para determinar si el reclamo presenta patrones sospechosos de fraude.
    """
    try:
        client = genai.Client(api_key=settings.API_KEY)
        
        prompt = f"""
        Eres el Agente Evaluador de Riesgos y Fraude de E-Com Agent.
        Analiza el siguiente perfil de cliente y contexto de compra para determinar el riesgo de reclamo fraudulento:
        
        PERFIL DEL CLIENTE (Memoria Episódica):
        - Nombre: {client_name}
        - Nivel/Segmento: {client_tier}
        - Score de Confianza Histórico: {trust_score} (1.0 = excelente)
        - Reclamos históricos totales: {total_past_claims}
        - Reclamos en los últimos 90 días: {recent_claims_90d}
        
        CONTEXTO DE LA OPERACIÓN ACTUAL:
        - Monto de la orden: ${order_amount:,.2f}
        - Categoría del producto: {product_category}
        
        CRITERIOS DE DETECCIÓN:
        - Alta frecuencia de reclamos recientes (> 2 en 90 días) es señal de alerta.
        - Montos elevados combinados con clientes nuevos o con bajo trust_score elevan el riesgo.
        - Clientes VIP con pocos reclamos históricos deben tener riesgo bajo.
        """
        
        response = client.models.generate_content(
            model=settings.MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=FraudRiskAnalysis,
                temperature=0.1
            )
        )
        
        return FraudRiskAnalysis.model_validate_json(response.text)
        
    except Exception as e:
        # Contingencia defensiva
        return FraudRiskAnalysis(
            fraud_risk_score=0.5,
            risk_level="MEDIO",
            risk_reasons=[f"Evaluación de riesgo automática no disponible: {str(e)}"],
            is_suspicious=True
        )