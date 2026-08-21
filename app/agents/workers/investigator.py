from app.schemas.guardrails import ClaimAnalysis
from app.core.llm_factory import call_vision_llm_with_fallback

async def analyze_claim_evidence(description: str, image_bytes: bytes, product_name: str, category: str) -> ClaimAnalysis:
    """
    Agente Investigador (Visión Multimodal con Redundancia):
    Evalúa la imagen del producto con Google Gemini 3.6 Flash.
    Si Gemini agota cuota (429/503), conmuta automáticamente a Groq Llama 3.2 Vision.
    """
    prompt = f"""
    Eres el Agente Investigador experto en control de calidad y postventa.
    Tu tarea es auditar la imagen adjunta del producto y compararla rigurosamente con los datos de la compra y el reclamo del cliente.
    
    DATOS DE LA COMPRA:
    - Producto: "{product_name}"
    - Categoría: "{category}"
    
    RECLAMO DEL CLIENTE:
    "{description}"
    
    Instrucciones:
    1. Evalúa la calidad de la imagen: ¿es nítida? ¿está borrosa, oscura o recortada?
    2. Verifica si el objeto en la imagen corresponde a la categoría '{category}' y coincide con el producto {product_name}.
    3. Analiza si existe daño real y si coincide con el daño reclamado, teniendo en cuenta las características de la categoría '{category}'.
    4. Asigna un 'confidence_score' (0.0 a 1.0) y JUSTIFICA en 'confidence_reasoning' qué elementos visuales aumentan o disminuyen tu certeza.
    """

    try:
        return await call_vision_llm_with_fallback(
            prompt=prompt,
            image_bytes=image_bytes,
            mime_type="image/jpeg",
            response_schema=ClaimAnalysis
        )
    except Exception as e:
        # Retorno de contingencia seguro en caso de falla de ambos proveedores
        return ClaimAnalysis(
            is_product_damaged=False,
            damage_description=f"Error en análisis visual: {str(e)}",
            matches_user_claim=False,
            confidence_score=0.0,
            confidence_reasoning=f"Error técnico durante la inspección de ambos proveedores (Gemini/Groq): {str(e)}",
            image_quality_issues=["error_conexion_modelos"]
        )