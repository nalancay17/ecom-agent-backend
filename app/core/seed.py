# app/core/seed.py
from datetime import datetime, timedelta
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, Base, engine
from app.models.entities import Client, Product, Order

async def init_db_and_seed():
    # 1. Crear tablas si no existen
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Poblar datos iniciales si la BD está vacía
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Client))
        if result.scalars().first() is not None:
            return  # Ya existen datos

        # Clientes
        c1 = Client(id="CLI-123", name="Juan Pérez", email="juan@example.com", trust_score=0.95, tier="REGULAR")
        c2 = Client(id="CLI-456", name="María Gómez", email="maria@example.com", trust_score=0.40, tier="RIESGOSO")
        c3 = Client(id="CLI-789", name="Carlos López", email="carlos@example.com", trust_score=1.0, tier="VIP")

        # Productos (con casos para Guardrails: monto > 100k y categoría prohibida)
        p1 = Product(sku="SKU-MON-27", name="Monitor Samsung 27 pulgadas", category="Electrónica", price=180000.0, is_returnable=True)
        p2 = Product(sku="SKU-VASOS-6", name="Juego de Vasos de Cristal (6u)", category="Hogar y Cocina", price=25000.0, is_returnable=True)
        p3 = Product(sku="SKU-ROPA-INT", name="Boxer Algodón Pack x3", category="Indumentaria Íntima", price=15000.0, is_returnable=False)
        p4 = Product(sku="SKU-SMPHN-NT", name="Smart phone teléfono inteligente", category="Electrónica", price=180000.0, is_returnable=True)


        # Órdenes
        o1 = Order(id="ORD-1001", client_id="CLI-123", product_sku="SKU-MON-27", purchase_date=datetime.utcnow() - timedelta(days=5), delivery_date=datetime.utcnow() - timedelta(days=2), status="delivered")
        o2 = Order(id="ORD-1002", client_id="CLI-456", product_sku="SKU-VASOS-6", purchase_date=datetime.utcnow() - timedelta(days=10), delivery_date=datetime.utcnow() - timedelta(days=4), status="delivered")
        o3 = Order(id="ORD-1003", client_id="CLI-789", product_sku="SKU-ROPA-INT", purchase_date=datetime.utcnow() - timedelta(days=3), delivery_date=datetime.utcnow() - timedelta(days=1), status="delivered")
        o4 = Order(id="ORD-1004", client_id="CLI-123", product_sku="SKU-SMPHN-NT", purchase_date=datetime.utcnow() - timedelta(days=2), delivery_date=datetime.utcnow() - timedelta(days=2), status="delivered")

        session.add_all([c1, c2, c3, p1, p2, p3, p4, o1, o2, o3, o4])
        await session.commit()