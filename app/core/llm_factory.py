import json
import re
import logging
from typing import Type, TypeVar, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger("ecom_agent.llm_factory")
T = TypeVar("T", bound=BaseModel)

# --- Errores de Cuota y Disponibilidad Reconocidos ---
QUOTA_AND_BUSY_KEYWORDS = [
    "429", "503", "resource_exhausted", "quota", "exhausted", 
    "rate_limit", "rate limit", "overloaded", "unavailable", 
    "too many requests", "tokens per minute", "requests per minute"
]

def is_transient_or_quota_error(error_msg: str) -> bool:
    """Detecta si un error es de cuota agotada, saturación de servidor o rate limit."""
    msg_lower = error_msg.lower()
    return any(keyword in msg_lower for keyword in QUOTA_AND_BUSY_KEYWORDS)


# =========================================================================
# 1. CLIENTES DE LOS MODELOS
# =========================================================================

def get_gemini_client(secondary: bool = False):
    """
    Instancia el cliente de Google Gemini.
    secondary=True usa API_KEY_2 como clave alternativa (mismo proveedor, distinta cuota).
    """
    key = settings.API_KEY_2 if secondary else settings.API_KEY
    if not key:
        return None
    return genai.Client(api_key=key)

def get_groq_client():
    """Instancia el cliente de Groq si la librería y la API key están disponibles."""
    if not settings.GROQ_API_KEY:
        return None
    try:
        from groq import AsyncGroq
        return AsyncGroq(api_key=settings.GROQ_API_KEY)
    except ImportError:
        logger.warning("Librería 'groq' no instalada. Usando fallback exclusivo de Gemini.")
        return None


# =========================================================================
# 2. DESPACHADOR PARA VISIÓN MULTIMODAL CON REDUNDANCIA
# Primario: Gemini 3.6 Flash -> Fallback: Groq GPT-OSS 20B (texto descriptivo)
# Nota: GPT-OSS 20B no procesa imágenes como Gemini, pero puede analizar
# una descripción estructurada de la imagen si el texto del prompt incluye
# los datos extraídos de la imagen por el cliente (ej. nombre de archivo,
# tamaño, tipo MIME). Para una prueba académica, Gemini como primario es suficiente.
# =========================================================================

async def call_vision_llm_with_fallback(
    prompt: str,
    image_bytes: bytes,
    mime_type: str,
    response_schema: Type[T]
) -> T:
    """
    Ejecuta el análisis visual con redundancia automática en 3 niveles:
    1. Gemini 3.6 Flash (API_KEY principal)
    2. Gemini 3.6 Flash (API_KEY_2 - cuota alternativa)
    3. Groq GPT-OSS 20B (análisis contextual sin imagen, modo contingencia)
    """
    errors_encountered = []

    # --- INTENTO 1: Google Gemini 3.6 Flash (Clave Principal) ---
    gemini_client = get_gemini_client(secondary=False)
    if gemini_client:
        try:
            logger.info("Ejecutando análisis visual con Google Gemini 3.6 Flash (API_KEY)...")
            response = gemini_client.models.generate_content(
                model=settings.MODEL,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=0.1
                )
            )
            data = json.loads(response.text)
            return response_schema.model_validate(data)
        except Exception as e:
            error_str = str(e)
            errors_encountered.append(f"Gemini Vision (key1): {error_str}")
            logger.warning(f"⚠️ Gemini (key1) falló ({error_str}). Intentando API_KEY_2...")

    # --- INTENTO 2: Google Gemini 3.6 Flash (Clave Secundaria API_KEY_2) ---
    gemini_client_2 = get_gemini_client(secondary=True)
    if gemini_client_2:
        try:
            logger.info("Ejecutando análisis visual con Google Gemini 3.6 Flash (API_KEY_2)...")
            response = gemini_client_2.models.generate_content(
                model=settings.MODEL,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=0.1
                )
            )
            data = json.loads(response.text)
            return response_schema.model_validate(data)
        except Exception as e:
            error_str = str(e)
            errors_encountered.append(f"Gemini Vision (key2): {error_str}")
            logger.warning(f"⚠️ Gemini (key2) también falló. Conmutando a Groq...")

    # --- INTENTO 3: Groq GPT-OSS 20B (Fallback de texto cuando ambos Gemini fallan) ---
    # GPT-OSS 20B no puede procesar imágenes directamente (multimodal puro),
    # pero puede razonar sobre los metadatos y el contexto textual del reclamo
    # para generar una evaluación de contingencia conservadora.
    groq_client = get_groq_client()
    if groq_client:
        try:
            logger.info("Ejecutando fallback de visión con Groq GPT-OSS 20B (análisis contextual sin imagen)...")
            schema_json = json.dumps(response_schema.model_json_schema())
            fallback_prompt = (
                f"{prompt}\n\n"
                f"NOTA IMPORTANTE: No tienes acceso a la imagen en este momento por falla técnica del proveedor de visión. "
                f"Debes generar una evaluación de CONTINGENCIA CONSERVADORA basándote en el texto del reclamo. "
                f"Asigna confidence_score=0.5 (incertidumbre máxima) e indica en confidence_reasoning que "
                f"el análisis visual no estuvo disponible. Esto derivará el caso a revisión humana."
            )
            system_prompt = (
                f"Eres un evaluador de reclamos de e-commerce. Responde en JSON siguiendo este esquema:\n"
                f"{schema_json}\n"
                f"El último bloque de tu respuesta debe ser el objeto JSON puro y nada más."
            )
            completion = await groq_client.chat.completions.create(
                model=settings.GROQ_VISION_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": fallback_prompt}
                ],
                temperature=0.1
            )
            raw_content = completion.choices[0].message.content or ""
            import re
            cleaned = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL).strip()
            json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if not json_match:
                raise ValueError(f"No se encontró JSON en fallback visual: {raw_content[:200]}")
            parsed = json.loads(json_match.group())
            return response_schema.model_validate(parsed)
        except Exception as e2:
            error_str2 = str(e2)
            errors_encountered.append(f"Groq GPT-OSS 20B Vision Fallback: {error_str2}")
            logger.error(f"❌ Falló el fallback visual de Groq ({error_str2}).")

    # Si ambos fallaron o no hay credenciales, emitir error descriptivo
    joined_errors = " | ".join(errors_encountered)
    raise RuntimeError(f"Falla crítica en todos los modelos de visión: {joined_errors}")


# =========================================================================
# 3. DESPACHADOR PARA TAREAS DE TEXTO Y RAZONAMIENTO CON REDUNDANCIA
# Primario: Groq Llama 3.1 / 3.3 (Ultra Rápido) -> Fallback: Gemini Flash
# =========================================================================

async def call_text_llm_with_fallback(
    prompt: str,
    response_schema: Type[T],
    task_type: str = "reasoning"  # "fast" (Qwen 27B) o "reasoning" (GPT-OSS 120B)
) -> T:
    """
    Ejecuta tareas de clasificación, RAG y análisis de fraude.
    Primario: Groq (Qwen 3.6 27B o GPT-OSS 120B) por su latencia ultrabaja.
    Fallback: Google Gemini Flash si Groq agota cuota o falla.
    
    Manejo especial: Qwen genera bloques <think>...</think> que son
    tokens de razonamiento interno. Se extraen y descartan automáticamente.
    """
    errors_encountered = []

    groq_model = (
        settings.GROQ_TEXT_FAST_MODEL 
        if task_type == "fast" 
        else settings.GROQ_TEXT_REASONING_MODEL
    )

    # --- INTENTO 1: Groq Cloud ---
    groq_client = get_groq_client()
    if groq_client:
        try:
            logger.info(f"Ejecutando tarea [{task_type}] con Groq ({groq_model})...")
            schema_json = json.dumps(response_schema.model_json_schema())
            system_prompt = (
                f"Eres un evaluador analítico experto para sistemas de e-commerce.\n"
                f"Debes responder OBLIGATORIAMENTE en formato JSON siguiendo este esquema exacto:\n"
                f"{schema_json}\n"
                f"NO incluyas bloques de código markdown ```json. "
                f"Si necesitas razonar, hazlo dentro de <think>...</think> ANTES del JSON. "
                f"El último bloque de tu respuesta debe ser el objeto JSON puro y nada más."
            )

            completion = await groq_client.chat.completions.create(
                model=groq_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
                # Nota: NO usamos response_format=json_object porque estos modelos
                # devuelven bloques <think> previos que rompen la validación JSON estricta.
            )

            raw_content = completion.choices[0].message.content or ""
            
            # Extraer solo el bloque JSON final (después de cualquier bloque <think>)
            cleaned = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL).strip()
            # Extraer primer bloque JSON válido
            json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if not json_match:
                raise ValueError(f"No se encontró JSON válido en la respuesta: {raw_content[:200]}")
            
            parsed = json.loads(json_match.group())
            return response_schema.model_validate(parsed)
        except Exception as e:
            error_str = str(e)
            errors_encountered.append(f"Groq ({groq_model}): {error_str}")
            logger.warning(f"⚠️ Groq falló ({error_str}). Conmutando a Gemini Flash...")

    # --- INTENTO 2: Google Gemini Flash (Fallback - Clave Principal) ---
    gemini_client = get_gemini_client(secondary=False)
    if gemini_client:
        try:
            logger.info(f"Ejecutando fallback de texto con Gemini/{settings.MODEL} (API_KEY)...")
            response = gemini_client.models.generate_content(
                model=settings.MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=0.1
                )
            )
            data = json.loads(response.text)
            return response_schema.model_validate(data)
        except Exception as e2:
            error_str2 = str(e2)
            errors_encountered.append(f"Gemini Flash (key1): {error_str2}")
            logger.warning(f"⚠️ Gemini (key1) también falló. Intentando API_KEY_2...")

    # --- INTENTO 3: Google Gemini Flash (Fallback - Clave Secundaria API_KEY_2) ---
    gemini_client_2 = get_gemini_client(secondary=True)
    if gemini_client_2:
        try:
            logger.info(f"Ejecutando fallback de texto con Gemini/{settings.MODEL} (API_KEY_2)...")
            response = gemini_client_2.models.generate_content(
                model=settings.MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=0.1
                )
            )
            data = json.loads(response.text)
            return response_schema.model_validate(data)
        except Exception as e3:
            error_str3 = str(e3)
            errors_encountered.append(f"Gemini Flash (key2): {error_str3}")
            logger.error(f"❌ Todos los proveedores fallaron en tarea de texto.")

    joined_errors = " | ".join(errors_encountered)
    raise RuntimeError(
        f"Todos los proveedores LLM de texto fallaron. Errores: {joined_errors}"
    )
