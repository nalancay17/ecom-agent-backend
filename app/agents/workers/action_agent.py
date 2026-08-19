from typing import Dict, Any, Optional
from app.tools.logistics import generate_return_shipping_label

async def execute_claim_action(
    claim_id: str,
    order_id: str,
    status: str,
    client_name: str,
    product_name: str,
    requires_hitl: bool
) -> Optional[Dict[str, Any]]:
    """
    Agente Ejecutor de Acciones (Action Agent):
    Dispara las operaciones en sistemas externos según la resolución final del reclamo.
    - Si es aprobado: Genera la etiqueta de logística inversa.
    - Si es rechazado o HITL: Registra la derivación correspondiente.
    """
    if status in ["APPROVED_AUTO", "APPROVED_BY_HUMAN"]:
        logistics_result = await generate_return_shipping_label(
            claim_id=claim_id,
            order_id=order_id,
            client_name=client_name,
            product_name=product_name
        )
        return {
            "action_executed": "GENERATE_RETURN_LABEL",
            "logistics": logistics_result,
            "message": f"Etiqueta de devolución generada exitosamente con {logistics_result['courier']}."
        }
    
    elif requires_hitl:
        return {
            "action_executed": "ESCALATE_TO_HITL_QUEUE",
            "logistics": None,
            "message": "Reclamo encolado para auditoría manual por supervisor de postventa."
        }
    
    else:
        return {
            "action_executed": "NOTIFY_REJECTION",
            "logistics": None,
            "message": "Notificación de reclamo no procedente emitida al cliente."
        }