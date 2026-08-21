from app.schemas.guardrails import PolicyReview
from app.rag.agentic_rag import retrieve_policy_context
from app.core.llm_factory import call_text_llm_with_fallback

async def review_claim_policies(
    description: str,
    product_name: str,
    category: str,
    days_since_delivery: int,
    visual_damage_description: str
) -> PolicyReview:
    """
    Agente Validador de Políticas Corporativas (RAG Semántico + Reasoning profundo).

    Usa Groq Llama 3.3 70B Versatile como modelo primario:
    - 70B parámetros para razonamiento legal/contractual sobre cláusulas de garantía.
    - Entrenado para apego estricto a documentos y citas textuales (anti-alucinación).
    - Aun así ultra-rápido en Groq (procesamiento en LPU).

    Fallback automático a Gemini 3.6 Flash si Groq agota cuota o falla.
    """
    # 1. Recuperar contexto documental mediante Agentic RAG (independiente del modelo LLM)
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

    prompt = f"""
    Eres el Agente Validador de Políticas Corporativas de E-Com Agent.
    Tu misión es contrastar el reclamo del cliente contra las cláusulas vigentes de la empresa.

    INFORMACIÓN DEL CASO:
    - Producto: "{product_name}"
    - Categoría: "{category}"
    - Días transcurridos desde la entrega: {days_since_delivery} días
    - Daño detectado visualmente: "{visual_damage_description}"
    - Reclamo del cliente: "{description}"

    CLÁUSULAS RECUPERADAS DEL MANUAL CORPORATIVO (Memoria Semántica RAG):
    {context_text}

    INSTRUCCIONES ESTRICTAS (anti-alucinación):
    1. Determina si el reclamo cumple las condiciones del manual (plazos, categoría, tipo de falla).
    2. CITA TEXTUALMENTE la cláusula o artículo aplicable en 'clause_citation'.
       Si no hay cláusula relevante en el contexto recuperado, indica "Sin cláusula específica recuperada".
    3. En 'policy_reasoning', fundamenta la decisión con los datos del caso y la cláusula.
    4. Si el caso está fuera de plazo o en categoría no permitida, marca is_compliant=False.
    5. NUNCA inventes coberturas o plazos que no estén en las cláusulas provistas arriba.
    """

    try:
        return await call_text_llm_with_fallback(
            prompt=prompt,
            response_schema=PolicyReview,
            task_type="reasoning"  # Llama 3.3 70B: razonamiento profundo sobre texto legal
        )
    except Exception as e:
        # Contingencia defensiva con trazabilidad completa
        return PolicyReview(
            is_compliant=False,
            applied_clause="Artículo General: Contingencia en Validación",
            clause_citation="No se pudo recuperar la cita textual: ambos proveedores de IA fallaron.",
            policy_reasoning=f"Error técnico en validación semántica: {str(e)}",
            confidence_score=0.0,
            requires_human_escalation=True
        )