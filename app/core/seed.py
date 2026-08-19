from datetime import datetime, timedelta
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, Base, engine
from app.models.entities import Client, Product, Order, Claim

async def init_db_and_seed():
    """
    Inicializa las tablas y puebla la base de datos con un conjunto exhaustivo
    de clientes, productos, órdenes y reclamos para la demostración completa del sistema.
    """
    # 1. Crear tablas si no existen
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Poblar datos iniciales si la BD está vacía
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Client))
        if result.scalars().first() is not None:
            return  # Ya existen datos

        # --- A. Clientes (Memoria Episódica de Reputación) ---
        c1 = Client(id="CLI-123", name="Juan Pérez", email="juan.perez@example.com", trust_score=0.95, tier="REGULAR")
        c2 = Client(id="CLI-456", name="María Gómez", email="maria.gomez@example.com", trust_score=0.40, tier="RIESGOSO")
        c3 = Client(id="CLI-789", name="Carlos López (VIP)", email="carlos.vip@example.com", trust_score=1.00, tier="VIP")
        c4 = Client(id="CLI-999", name="Roberto F. (Sospechoso)", email="roberto.f@example.com", trust_score=0.15, tier="BLOQUEADO")

        # --- B. Productos (Mapeados a Guardrails y Políticas RAG) ---
        # 1. Producto > $100k para Guardrail de Monto
        p1 = Product(sku="SKU-MON-27", name="Monitor Samsung 27 pulgadas Curvo", category="Electrónica", price=180000.0, is_returnable=True)
        # 2. Producto estándar < $100k para Aprobación Automática (Camino Feliz)
        p2 = Product(sku="SKU-AURIC-BT", name="Auriculares Inalámbricos Bluetooth Pro", category="Electrónica", price=45000.0, is_returnable=True)
        # 3. Producto de Higiene / Indumentaria Íntima (Guardrail de Bioseguridad Art. 4)
        p3 = Product(sku="SKU-ROPA-INT", name="Boxer de Algodón Pack x3", category="Indumentaria Íntima", price=15000.0, is_returnable=False)
        # 4. Producto Hogar / Cristalería
        p4 = Product(sku="SKU-VASOS-6", name="Juego de Vasos de Cristal Premium (6u)", category="Hogar y Cocina", price=25000.0, is_returnable=True)
        # 5. Producto Electrohogar para prueba de Garantía
        p5 = Product(sku="SKU-CAFETERA", name="Cafetera Espresso Automática", category="Electrohogar", price=85000.0, is_returnable=True)
        # 6. Producto Electrónica con fecha antigua para prueba de Garantía Vencida (> 180 días)
        p6 = Product(sku="SKU-SMARTWATCH", name="Smartwatch Deportivo GPS", category="Electrónica", price=60000.0, is_returnable=True)

        # --- C. Órdenes de Compra (Casos de Demostración) ---
        now = datetime.utcnow()
        
        # ORD-1001: Juan Pérez -> Monitor $180k (Entrega hace 2 días) -> Prueba: PENDING_HITL_HIGH_AMOUNT
        o1 = Order(id="ORD-1001", client_id="CLI-123", product_sku="SKU-MON-27", purchase_date=now - timedelta(days=5), delivery_date=now - timedelta(days=2), status="delivered")
        
        # ORD-1002: Juan Pérez -> Auriculares $45k (Entrega hace 3 días) -> Prueba: APPROVED_AUTO (Camino Feliz)
        o2 = Order(id="ORD-1002", client_id="CLI-123", product_sku="SKU-AURIC-BT", purchase_date=now - timedelta(days=6), delivery_date=now - timedelta(days=3), status="delivered")
        
        # ORD-1003: Carlos López (VIP) -> Boxer $15k (Entrega hace 1 día) -> Prueba: REJECTED_CATEGORY_GUARDRAIL
        o3 = Order(id="ORD-1003", client_id="CLI-789", product_sku="SKU-ROPA-INT", purchase_date=now - timedelta(days=3), delivery_date=now - timedelta(days=1), status="delivered")
        
        # ORD-1004: María Gómez -> Vasos $25k (Entrega hace 4 días) -> Prueba: PENDING_HITL_RISK_SUSPICION (Riesgo Fraude)
        o4 = Order(id="ORD-1004", client_id="CLI-456", product_sku="SKU-VASOS-6", purchase_date=now - timedelta(days=7), delivery_date=now - timedelta(days=4), status="delivered")
        
        # ORD-1005: Juan Pérez -> Smartwatch $60k (Entrega hace 220 días) -> Prueba: PENDING_HITL_POLICY_NON_COMPLIANT (Garantía vencida Art. 3)
        o5 = Order(id="ORD-1005", client_id="CLI-123", product_sku="SKU-SMARTWATCH", purchase_date=now - timedelta(days=230), delivery_date=now - timedelta(days=220), status="delivered")
        
        # ORD-1006: Carlos López (VIP) -> Cafetera $85k (Entrega hace 4 días) -> Prueba: APPROVED_AUTO (Cliente VIP)
        o6 = Order(id="ORD-1006", client_id="CLI-789", product_sku="SKU-CAFETERA", purchase_date=now - timedelta(days=8), delivery_date=now - timedelta(days=4), status="delivered")

        # --- D. Reclamos Históricos Pre-existentes (Para alimentar Métricas y Cola HITL inicial) ---
        # 1. Reclamo previo ya aprobado automáticamente con guía
        clm1 = Claim(
            id="CLM-INIT-001",
            order_id="ORD-1002",
            client_id="CLI-123",
            description="El auricular izquierdo no carga en el estuche.",
            is_damaged=True,
            ai_confidence_score=0.92,
            requires_hitl=False,
            hitl_reasons=None,
            status="APPROVED_AUTO",
            tracking_number="TRK-ANDREANI-SEED001",
            label_url="https://api.andreani.com/labels/return/TRK-ANDREANI-SEED001.pdf",
            created_at=now - timedelta(days=15),
            resolved_at=now - timedelta(days=15)
        )
        
        # 2. Reclamo previo rechazado por guardrail de higiene
        clm2 = Claim(
            id="CLM-INIT-002",
            order_id="ORD-1003",
            client_id="CLI-789",
            description="El talle del boxer me queda chico.",
            is_damaged=False,
            ai_confidence_score=0.90,
            requires_hitl=True,
            hitl_reasons="Categoría 'Indumentaria Íntima' restringida según manual de higiene.",
            status="REJECTED_CATEGORY_GUARDRAIL",
            created_at=now - timedelta(days=10),
            resolved_at=now - timedelta(days=10)
        )

        # 3. Reclamo PENDIENTE en cola HITL (Listo para probar POST /claims/{id}/resolve)
        clm3 = Claim(
            id="CLM-INIT-HITL-003",
            order_id="ORD-1001",
            client_id="CLI-123",
            description="La pantalla del monitor parpadea con líneas horizontales tras 2 días de uso.",
            is_damaged=True,
            ai_confidence_score=0.88,
            requires_hitl=True,
            hitl_reasons="Monto ($180,000.00) supera el umbral autónomo de $100.000.",
            status="PENDING_HITL_HIGH_AMOUNT",
            created_at=now - timedelta(hours=3),
            resolved_at=None  # Pendiente de resolución por supervisor
        )

        session.add_all([c1, c2, c3, c4, p1, p2, p3, p4, p5, p6, o1, o2, o3, o4, o5, o6, clm1, clm2, clm3])
        await session.commit()