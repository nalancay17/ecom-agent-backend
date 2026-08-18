# app/tools/oms.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.entities import Order, Claim
import uuid

async def get_order_details_db(order_id: str, db: AsyncSession) -> dict | None:
    """Consulta la orden en la base de datos con su producto y cliente asociados."""
    query = (
        select(Order)
        .options(selectinload(Order.product), selectinload(Order.client))
        .where(Order.id == order_id)
    )
    result = await db.execute(query)
    order = result.scalar_one_or_none()
    print(result)

    if not order:
        return None

    return {
        "order_id": order.id,
        "client_id": order.client_id,
        "client_name": order.client.name,
        "client_trust_score": order.client.trust_score,
        "client_tier": order.client.tier,
        "product_sku": order.product.sku,
        "product_name": order.product.name,
        "category": order.product.category,
        "price": order.product.price,
        "is_returnable": order.product.is_returnable,
        "status": order.status
    }

async def save_claim_to_db(order_id: str, client_id: str, description: str, is_damaged: bool, confidence: float, requires_hitl: bool, status: str, db: AsyncSession) -> str:
    """Persiste el reclamo como Memoria Episódica en la base de datos."""
    claim_id = f"CLM-{uuid.uuid4().hex[:8].upper()}"
    new_claim = Claim(
        id=claim_id,
        order_id=order_id,
        client_id=client_id,
        description=description,
        is_damaged=is_damaged,
        ai_confidence_score=confidence,
        requires_hitl=requires_hitl,
        status=status
    )
    db.add(new_claim)
    await db.commit()
    return claim_id