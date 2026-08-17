# TODO: Esquemas estrictos para Outlines / Guardrails AI
from pydantic import BaseModel

class OutputSchema(BaseModel):
    is_valid: bool
    refund_amount: float
