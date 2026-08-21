from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "E-Com Agent API"
    ENVIRONMENT: str = "development"
    
    # Proveedor 1: Google Gemini (Multimodal Vision & Reasoning)
    API_KEY: str = ""  # Google AI Studio Key
    MODEL: str = "gemini-3.6-flash"
    
    # Proveedor 2: Groq Cloud (Inferencia Gratuita con LPU)
    GROQ_API_KEY: Optional[str] = None
    # Vision fallback: usa gpt-oss-20b de OpenAI (disponible en Groq gratuitamente)
    GROQ_VISION_MODEL: str = "openai/gpt-oss-20b"
    # Fraude/clasificación rápida: qwen3.6-27b (27B parámetros, liviano y rápido)
    GROQ_TEXT_FAST_MODEL: str = "qwen/qwen3.6-27b"
    # RAG/razonamiento profundo: gpt-oss-120b (modelo grande disponible en Groq)
    GROQ_TEXT_REASONING_MODEL: str = "openai/gpt-oss-120b"
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()