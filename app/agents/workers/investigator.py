from google import genai
from google.genai import types
from PIL import Image
import io
from app.core.config import settings
from app.schemas.guardrails import ClaimAnalysis

async def analyze_claim_evidence(description: str, image_bytes: bytes, product_name: str, category: str) -> ClaimAnalysis:
    """
    Agente Investigador (Visión): Evalúa la imagen adjunta (evidencia visual), detecta problemas de calidad
    y justifica su nivel de confianza para evitar decisiones de 'caja negra'.
    """
    try:
        # 1. Inicializar el cliente oficial con la API Key
        client = genai.Client(api_key=settings.API_KEY)
        
        # 2. Cargar la imagen desde los bytes
        image = Image.open(io.BytesIO(image_bytes))
        
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
        3. Analiza si existe daño real y si coincide con el daño reclamado, teniendo en cuenta las características típicas de un producto de la categoría '{category}'.
        4. Asigna un 'confidence_score' (0.0 a 1.0) y JUSTIFICA en 'confidence_reasoning' qué elementos visuales aumentan o disminuyen tu certeza.
        """
        
        # 3. Invocar al modelo multimodal solicitando una salida estructurada (JSON Schema nativo)
        response = client.models.generate_content(
            model=settings.MODEL,
            contents=[image, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ClaimAnalysis,
                temperature=0.1
            ),
        )
        
        # 4. Retornar el objeto ya parseado y validado
        return ClaimAnalysis.model_validate_json(response.text)
        
    except Exception as e:
        # Retorno de contingencia seguro en caso de error de red o API Key
        return ClaimAnalysis(
            is_product_damaged=False,
            damage_description=f"Error en análisis visual: {str(e)}",
            matches_user_claim=False,
            confidence_score=0.0,
            confidence_reasoning=f"Error técnico durante la inspección: {str(e)}",
            image_quality_issues=["error_procesamiento"]
        )