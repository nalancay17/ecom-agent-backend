from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "E-Com Agent API"
    ENVIRONMENT: str = "development"
    API_KEY: str = "" # Variable para el LLM Multimodal
    MODEL: str = "gemini-3.6-flash"
    
    class Config:
        env_file = ".env"

settings = Settings()