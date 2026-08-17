from pydantic import BaseModel, Field

class OutputSchema(BaseModel):
    is_valid: bool
    refund_amount: float

# NUEVO: Esquema estricto para el análisis inicial de la imagen
class ClaimAnalysis(BaseModel):
    is_product_damaged: bool = Field(description="¿Se observa daño físico real en el producto en la imagen?")
    damage_description: str = Field(description="Breve descripción del daño observado en la imagen.")
    matches_user_claim: bool = Field(description="¿El daño en la imagen coincide con la descripción del usuario?")
    confidence_score: float = Field(description="Nivel de confianza en el análisis visual (0.0 a 1.0).")