from google import genai
from google.genai import types
from app.core.config import settings
from app.schemas.guardrails import PolicyReview
from app.rag.agentic_rag import retrieve_policy_context

async def review_claim_policies(
    description: str,
    product_name: str,
    category: str,
    days_since_delivery: int,
    visual_damage_description: str
) -> PolicyReview:
    """
    Agente Validador de Políticas (Reasoning + RAG Semántico):
    Consulta la Memoria Semántica (manual corporativo), extrae la cláusula aplicable
    y justifica la resolución citando textualmente el manual para evitar alucinaciones.
    """
    try:
        # 1. Recuperar contexto documental mediante Agentic RAG
        retrieved_chunks = await retrieve_policy_context(
            description=description,
            product_name=product_name,
            category=category,
            days_since_delivery=days_since_delivery
        )

        context_text = "\n\n".join([
            f"--- {chunk['title']} ---\n{chunk['content']}"
            for chunk in retrieved_chunks
        ])

        # 2. Inicializar cliente Gemini
        client = genai.Client(api_key=settings.API_KEY)

        prompt = f"""
        Eres el Agente Validador de Políticas Corporativas de E-Com Agent.
        Tu misión es contrastar el reclamo del cliente contra las cláusulas vigentes de la empresa.

        INFORMACIÓN DEL CASO:
        - Producto: "{product_name}"
        - Categoría: "{category}"
        - Días transcurridos desde la entrega: {days_since_delivery} días
        - Daño detectado visualmente: "{visual_damage_description}"
        - Reclamo del cliente: "{description}"

        CLÁUSULAS RECUPERADAS DEL MANUAL CORPORATIVO (Memoria Semántica):
        {context_text}

        INSTRUCCIONES:
        1. Determina si el reclamo cumple las condiciones del manual (plazos, categoría, tipo de falla).
        2. CITA TEXTUALMENTE la cláusula o artículo aplicable en 'clause_citation'.
        3. En 'policy_reasoning', fundamenta jurídicamente y operativamente la decisión.
        4. Si el caso está fuera de plazo o en categoría no permitida, marca is_compliant=False.
        """

        response = client.models.generate_content(
            model=settings.MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PolicyReview,
                temperature=0.1
            )
        )

        return PolicyReview.model_validate_json(response.text)

    except Exception as e:
        # Contingencia defensiva con trazabilidad
        return PolicyReview(
            is_compliant=False,
            applied_clause="Artículo General: Contingencia en Validación",
            clause_citation="No se pudo recuperar la cita textual debido a error de conectividad.",
            policy_reasoning=f"Error en validación semántica RAG: {str(e)}",
            confidence_score=0.0,
            requires_human_escalation=True
        )