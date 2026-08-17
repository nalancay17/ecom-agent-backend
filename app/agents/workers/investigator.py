from google import genai
from google.genai import types
from PIL import Image
import io
from app.core.config import settings
from app.schemas.guardrails import ClaimAnalysis

async def analyze_claim_evidence(description: str, image_bytes: bytes) -> ClaimAnalysis:
    """
    Agente Investigador: Analiza la evidencia visual utilizando la SDK moderna google-genai
    y fuerza la respuesta estructurada mediante esquemas de Pydantic.
    """
    try:
        # 1. Inicializar el cliente oficial con la API Key
        client = genai.Client(api_key=settings.API_KEY)
        
        # 2. Cargar la imagen desde los bytes
        image = Image.open(io.BytesIO(image_bytes))
        
        prompt = f"""
        Eres el Agente Investigador de un sistema automatizado de postventa.
        Tu tarea es evaluar la imagen adjunta del producto y compararla estrictamente con el reclamo del cliente.
        
        Reclamo del cliente: "{description}"
        """
        
        # 3. Invocar al modelo multimodal solicitando una salida estructurada (JSON Schema nativo)
        response = client.models.generate_content(
            model='gemini-3.6-flash',
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
            confidence_score=0.0
        )