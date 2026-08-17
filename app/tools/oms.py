# Base de datos simulada en memoria (Mock DB)
MOCK_ORDERS_DB = {
    "ORD-1001": {
        "client_id": "123",
        "product_name": "Monitor Samsung 27 pulgadas",
        "category": "Electrónica",
        "status": "delivered"
    },
    "ORD-1002": {
        "client_id": "456",
        "product_name": "Juego de Vasos de Cristal (6 unidades)",
        "category": "Hogar y Cocina",
        "status": "delivered"
    },
    "ORD-1003": {
        "client_id": "789",
        "product_name": "Remera de algodón básica negra",
        "category": "Indumentaria",
        "status": "delivered"
    }
}

async def get_order_details(order_id: str) -> dict | None:
    """
    Simula una consulta asíncrona al ERP/OMS para obtener los detalles de la compra.
    """
    # En un entorno real, esto sería una consulta SQL o una petición a la API de Shopify/VTEX.
    return MOCK_ORDERS_DB.get(order_id)