# app/tools/oms.py
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional
from datetime import datetime, timedelta
import uuid

from app.core.database import AsyncSessionLocal
from app.models.entities import Order, Claim

async def get_order_details_db(order_id: str, db: Optional[AsyncSession] = None) -> dict | None:
    """Consulta la orden en la base de datos con su producto y cliente asociados."""
    async def _query(session: AsyncSession):
        query = (
            select(Order)
            .options(selectinload(Order.product), selectinload(Order.client))
            .where(Order.id == order_id)
        )
        result = await session.execute(query)
        order = result.scalar_one_or_none()
        if not order:
            return None
        # Consultar Memoria Episódica: reclamos previos del cliente
        ninety_days_ago = datetime.utcnow() - timedelta(days=90)
        
        claims_total_query = select(func.count(Claim.id)).where(Claim.client_id == order.client_id)
        claims_90d_query = select(func.count(Claim.id)).where(
            Claim.client_id == order.client_id,
            Claim.created_at >= ninety_days_ago
        )
        
        total_claims = (await session.execute(claims_total_query)).scalar() or 0
        recent_claims = (await session.execute(claims_90d_query)).scalar() or 0
        return {
            "order_id": order.id,
            "client_id": order.client_id,
            "client_name": order.client.name,
            "client_trust_score": order.client.trust_score,
            "client_tier": order.client.tier,
            "total_past_claims": total_claims,
            "recent_claims_90d": recent_claims,
            "product_sku": order.product.sku,
            "product_name": order.product.name,
            "category": order.product.category,
            "price": order.product.price,
            "is_returnable": order.product.is_returnable,
            "status": order.status
        }
    if db:
        return await _query(db)
    else:
        async with AsyncSessionLocal() as session:
            return await _query(session)

async def save_claim_to_db(
    claim_id: str,
    order_id: str,
    client_id: str,
    description: str,
    is_damaged: bool,
    confidence: float,
    requires_hitl: bool,
    status: str,
    db: Optional[AsyncSession] = None
) -> str:
    """Persiste el reclamo como Memoria Episódica en la base de datos."""
    async def _save(session: AsyncSession):
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
        session.add(new_claim)
        await session.commit()
        return claim_id
    if db:
        return await _save(db)
    else:
        async with AsyncSessionLocal() as session:
            return await _save(session)