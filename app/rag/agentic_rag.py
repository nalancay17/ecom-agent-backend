from typing import List, Dict, Any
from app.rag.vector_store import policy_vector_store

async def retrieve_policy_context(
    description: str,
    product_name: str,
    category: str,
    days_since_delivery: int
) -> List[Dict[str, Any]]:
    """
    Agentic RAG: Reformula la consulta combinando la descripción del reclamo,
    la categoría del producto y los días transcurridos desde la entrega.
    """
    # 1. Reformulación inteligente de la consulta para el Vector Store
    query_parts = [description, category, product_name]
    
    if days_since_delivery <= 2:
        query_parts.append("transporte daño 48 horas recepción rotura")
    elif days_since_delivery <= 10:
        query_parts.append("arrepentimiento 10 días devolución voluntaria")
    elif "electrónica" in category.lower() or "electro" in category.lower():
        query_parts.append("garantía técnica 180 días defecto fabricación")
    
    if "íntima" in category.lower() or "higiene" in category.lower() or "ropa" in category.lower():
        query_parts.append("higiene indumentaria íntima exclusión")

    expanded_query = " ".join(query_parts)

    # 2. Búsqueda en la Memoria Semántica
    results = await policy_vector_store.search(expanded_query, top_k=2)
    return results
