import os
import re
import math
import unicodedata
from typing import List, Dict, Any, Optional

def normalize_text(text: str) -> str:
    """Normaliza texto eliminando tildes y caracteres especiales."""
    text = unicodedata.normalize('NFD', text.lower())
    text = re.sub(r'[\u0300-\u036f]', '', text)
    return text

class PolicyVectorStore:
    """
    Memoria Semántica (Capa 3): Base vectorial local para indexar y consultar
    las políticas corporativas de postventa, garantías y devoluciones.
    """
    def __init__(self, file_path: Optional[str] = None):
        if file_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(base_dir, "knowledge_base", "policies.md")
        self.file_path = file_path
        self.documents: List[Dict[str, Any]] = []
        self._load_and_chunk()

    def _load_and_chunk(self):
        """Carga el documento y lo segmenta por Artículos (Chunking Semántico)."""
        if not os.path.exists(self.file_path):
            return

        with open(self.file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Separar por títulos de Artículos
        articles = re.split(r'\n(?=## Artículo )', content)
        for idx, art in enumerate(articles):
            art = art.strip()
            if not art or not art.startswith("## Artículo"):
                continue
            
            lines = art.split("\n")
            title = lines[0].replace("##", "").strip()
            body = "\n".join(lines[1:]).strip()

            # Extraer categoría
            norm_title = normalize_text(title)
            category = "General"
            if "garantia" in norm_title or "electronica" in norm_title:
                category = "Electrónica"
            elif "higiene" in norm_title or "seguridad" in norm_title:
                category = "Indumentaria Íntima / Higiene"
            elif "transporte" in norm_title:
                category = "Logística"
            elif "arrepentimiento" in norm_title:
                category = "Devolución General"

            self.documents.append({
                "id": f"chunk_{idx}",
                "title": title,
                "category": category,
                "content": art,
                "body": body,
                "normalized_content": normalize_text(art)
            })

    def _compute_similarity(self, query: str, doc_norm_text: str) -> float:
        """Cálculo de similitud semántica/léxica con normalización."""
        q_norm = normalize_text(query)
        q_tokens = set(re.findall(r'\w+', q_norm))
        d_tokens = re.findall(r'\w+', doc_norm_text)
        if not q_tokens or not d_tokens:
            return 0.0
        
        matches = sum(1 for token in q_tokens if token in d_tokens)
        return matches / math.sqrt(len(q_tokens) * len(d_tokens))

    async def search(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """
        Búsqueda Semántica en la Base de Políticas.
        """
        if not self.documents:
            self._load_and_chunk()

        scored_docs = []
        for doc in self.documents:
            score = self._compute_similarity(query, doc["normalized_content"])
            scored_docs.append({
                "id": doc["id"],
                "title": doc["title"],
                "category": doc["category"],
                "content": doc["content"],
                "score": round(score, 4)
            })

        # Ordenar por relevancia descendente
        scored_docs.sort(key=lambda x: x["score"], reverse=True)
        return scored_docs[:top_k]

# Instancia singleton del vector store de políticas
policy_vector_store = PolicyVectorStore()
