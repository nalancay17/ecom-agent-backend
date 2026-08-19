from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import json
import uuid

from app.core.database import AsyncSessionLocal
from app.models.entities import Order, Claim, Client, Product

async def get_order_details_db(order_id: str, db: Optional[AsyncSession] = None) -> dict | None:
    """Consulta la orden con su producto y cliente asociados, calculando historial y días desde la entrega."""
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

        # Cómputo de días desde la entrega
        days_since_delivery = 3
        if order.delivery_date:
            days_since_delivery = max(1, (datetime.utcnow() - order.delivery_date).days)

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
            "days_since_delivery": days_since_delivery,
            "purchase_date": order.purchase_date.isoformat() if order.purchase_date else None,
            "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
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
    hitl_reasons: Optional[List[str]] = None,
    tracking_number: Optional[str] = None,
    label_url: Optional[str] = None,
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
            hitl_reasons=" | ".join(hitl_reasons) if hitl_reasons else None,
            status=status,
            tracking_number=tracking_number,
            label_url=label_url
        )
        session.add(new_claim)
        await session.commit()
        return claim_id

    if db:
        return await _save(db)
    else:
        async with AsyncSessionLocal() as session:
            return await _save(session)

async def get_claim_by_id_db(claim_id: str, db: Optional[AsyncSession] = None) -> dict | None:
    """Recupera el detalle completo de un reclamo por su ID."""
    async def _query(session: AsyncSession):
        query = (
            select(Claim)
            .options(
                selectinload(Claim.order).selectinload(Order.product),
                selectinload(Claim.client)
            )
            .where(Claim.id == claim_id)
        )
        result = await session.execute(query)
        claim = result.scalar_one_or_none()
        if not claim:
            return None

        return {
            "claim_id": claim.id,
            "order_id": claim.order_id,
            "client_id": claim.client_id,
            "client_name": claim.client.name if claim.client else "Cliente",
            "product_name": claim.order.product.name if claim.order and claim.order.product else "Producto",
            "category": claim.order.product.category if claim.order and claim.order.product else "General",
            "order_price": claim.order.product.price if claim.order and claim.order.product else 0.0,
            "description": claim.description,
            "is_damaged": claim.is_damaged,
            "composite_score": claim.ai_confidence_score,
            "requires_hitl": claim.requires_hitl,
            "hitl_reasons": claim.hitl_reasons,
            "status": claim.status,
            "tracking_number": claim.tracking_number,
            "label_url": claim.label_url,
            "human_reviewer_notes": claim.human_reviewer_notes,
            "resolved_at": claim.resolved_at.isoformat() if claim.resolved_at else None,
            "created_at": claim.created_at.isoformat() if claim.created_at else None
        }

    if db:
        return await _query(db)
    else:
        async with AsyncSessionLocal() as session:
            return await _query(session)

async def get_pending_hitl_claims_db(db: Optional[AsyncSession] = None) -> List[Dict[str, Any]]:
    """Recupera todos los reclamos encolados para revisión humana (HITL)."""
    async def _query(session: AsyncSession):
        query = (
            select(Claim)
            .options(
                selectinload(Claim.order).selectinload(Order.product),
                selectinload(Claim.client)
            )
            .where(Claim.requires_hitl == True, Claim.resolved_at == None)
            .order_by(desc(Claim.created_at))
        )
        result = await session.execute(query)
        claims = result.scalars().all()
        
        return [
            {
                "claim_id": c.id,
                "order_id": c.order_id,
                "client_id": c.client_id,
                "client_name": c.client.name if c.client else "Cliente",
                "client_trust_score": c.client.trust_score if c.client else 1.0,
                "product_name": c.order.product.name if c.order and c.order.product else "Producto",
                "category": c.order.product.category if c.order and c.order.product else "General",
                "price": c.order.product.price if c.order and c.order.product else 0.0,
                "description": c.description,
                "composite_score": c.ai_confidence_score,
                "status": c.status,
                "hitl_reasons": c.hitl_reasons,
                "created_at": c.created_at.isoformat() if c.created_at else None
            }
            for c in claims
        ]

    if db:
        return await _query(db)
    else:
        async with AsyncSessionLocal() as session:
            return await _query(session)

async def resolve_claim_by_human_db(
    claim_id: str,
    decision: str,
    reviewer_notes: str,
    tracking_number: Optional[str] = None,
    label_url: Optional[str] = None,
    db: Optional[AsyncSession] = None
) -> dict | None:
    """Aplica la resolución humana (HITL) actualizando el reclamo en la base de datos."""
    async def _resolve(session: AsyncSession):
        query = select(Claim).where(Claim.id == claim_id)
        result = await session.execute(query)
        claim = result.scalar_one_or_none()
        if not claim:
            return None

        claim.status = decision
        claim.human_reviewer_notes = reviewer_notes
        claim.resolved_at = datetime.utcnow()
        claim.requires_hitl = False
        
        if tracking_number:
            claim.tracking_number = tracking_number
        if label_url:
            claim.label_url = label_url

        await session.commit()
        return {
            "claim_id": claim.id,
            "status": claim.status,
            "human_reviewer_notes": claim.human_reviewer_notes,
            "resolved_at": claim.resolved_at.isoformat(),
            "tracking_number": claim.tracking_number,
            "label_url": claim.label_url
        }

    if db:
        return await _resolve(db)
    else:
        async with AsyncSessionLocal() as session:
            return await _resolve(session)

async def get_claims_metrics_db(db: Optional[AsyncSession] = None) -> Dict[str, Any]:
    """Calcula métricas de observabilidad para el dashboard del administrador."""
    async def _metrics(session: AsyncSession):
        total_claims = (await session.execute(select(func.count(Claim.id)))).scalar() or 0
        auto_approved = (await session.execute(select(func.count(Claim.id)).where(Claim.status == "APPROVED_AUTO"))).scalar() or 0
        hitl_pending = (await session.execute(select(func.count(Claim.id)).where(Claim.requires_hitl == True, Claim.resolved_at == None))).scalar() or 0
        human_resolved = (await session.execute(select(func.count(Claim.id)).where(Claim.resolved_at != None))).scalar() or 0
        rejected = (await session.execute(select(func.count(Claim.id)).where(Claim.status.like("%REJECTED%")))).scalar() or 0
        
        avg_confidence = (await session.execute(select(func.avg(Claim.ai_confidence_score)))).scalar() or 0.0

        automation_rate = round((auto_approved / total_claims * 100), 1) if total_claims > 0 else 0.0

        return {
            "total_claims": total_claims,
            "auto_approved": auto_approved,
            "hitl_pending": hitl_pending,
            "human_resolved": human_resolved,
            "rejected": rejected,
            "automation_rate_pct": automation_rate,
            "average_confidence_score": round(avg_confidence, 2)
        }

    if db:
        return await _metrics(db)
    else:
        async with AsyncSessionLocal() as session:
            return await _metrics(session)