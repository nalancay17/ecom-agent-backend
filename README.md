# E-Com Agent — Backend (API Agéntica de Postventa)

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-StateGraph-FF6B35)](https://langchain-ai.github.io/langgraph)
[![Vercel](https://img.shields.io/badge/Deployed-Vercel-000000?logo=vercel)](https://ecom-agent-backend.vercel.app)

Sistema backend para **E-Com Agent**: plataforma de resolución autónoma de reclamos de postventa basada en orquestación multi-agente con LangGraph. Desarrollado como Proyecto Final de Ciclo para el curso *Inteligencia Artificial Aplicada a Organizaciones* — UTN FRBA / EPIData (Agosto 2026).

**🌐 API en Producción:** [`https://ecom-agent-backend.vercel.app`](https://ecom-agent-backend.vercel.app)  
**📖 Docs interactivos (Swagger):** [`https://ecom-agent-backend.vercel.app/docs`](https://ecom-agent-backend.vercel.app/docs)  
**🖥️ Frontend:** [`https://ecom-agent-frontend-woad.vercel.app`](https://ecom-agent-frontend-woad.vercel.app)

---

## ¿Qué hace este sistema?

Cuando un cliente presenta un reclamo de devolución o garantía, el sistema orquesta automáticamente 5 agentes especializados:

```
[Cliente] → POST /api/v1/claims
              │
              ▼
    ┌─────────────────────────┐
    │   LangGraph StateGraph  │
    │                         │
    │  1. Investigador        │ ← valida OMS + analiza imagen (Gemini Vision)
    │  2. Eval. de Riesgo     │ ← detecta fraude (Groq Qwen 3.6 27B)
    │  3. Rev. Políticas      │ ← RAG sobre manual de postventa (Groq GPT-OSS 120B)
    │  4. Guardrails          │ ← reglas de negocio (umbral $100k, categorías)
    │  5. Acción Final        │ ← aprueba / rechaza / deriva a HITL
    └─────────────────────────┘
               │
      ┌────────┴────────┐
      ▼                 ▼
  APPROVED_AUTO    PENDING_HITL
   (autónomo)    (supervisor decide)
```

El **66,7% de los reclamos** se resuelven autónomamente en menos de 30 segundos. Los casos complejos (monto > $100.000, sospecha de fraude) se derivan a supervisor humano con todo el razonamiento ya analizado.

---

## Arquitectura Multi-Modelo con Redundancia

Cada agente usa el modelo óptimo para su tarea. Si un proveedor agota cuota, el sistema conmuta automáticamente:

| Agente | Modelo Primario | Fallback 1 | Fallback 2 |
|:---|:---|:---|:---|
| **Investigador** (visión) | Gemini 3.6 Flash (`API_KEY`) | Gemini 3.6 Flash (`API_KEY_2`) | Groq GPT-OSS 20B |
| **Eval. de Riesgo** (fraude) | Groq Qwen 3.6 27B | Gemini 3.6 Flash (`API_KEY`) | Gemini 3.6 Flash (`API_KEY_2`) |
| **Rev. Políticas** (RAG) | Groq GPT-OSS 120B | Gemini 3.6 Flash (`API_KEY`) | Gemini 3.6 Flash (`API_KEY_2`) |

> **¿Por qué dos claves de Gemini?** La API gratuita tiene límites por cuenta (RPM/TPD). Con `API_KEY` + `API_KEY_2` se duplica el throughput gratuito. El módulo `app/core/llm_factory.py` gestiona la conmutación ante errores `429 / 503 / ResourceExhausted`.

> **¿Por qué Groq?** Inferencia en hardware LPU con latencias de 200–500 ms en modelos de 100B+. Gratuito con una API Key que da acceso a múltiples modelos especializados (Qwen de Alibaba, GPT-OSS de OpenAI).

---

## Estructura del Proyecto

```
ecom-agent-backend/
├── app/
│   ├── main.py                         # Entrada FastAPI + CORSMiddleware
│   ├── agents/
│   │   ├── orchestrator.py             # LangGraph StateGraph (grafo principal)
│   │   ├── state.py                    # ClaimState: estado compartido entre agentes
│   │   └── workers/
│   │       ├── investigator.py         # Agente 1: OMS + visión multimodal (Gemini)
│   │       ├── risk_evaluator.py       # Agente 2: evaluación de fraude (Groq Qwen 27B)
│   │       ├── reviewer.py             # Agente 3: RAG políticas (Groq GPT-OSS 120B)
│   │       └── action_agent.py         # Agente 4: guardrails + decisión final
│   ├── api/v1/
│   │   └── claims.py                   # Endpoints REST de la API
│   ├── core/
│   │   ├── config.py                   # Variables de entorno (Pydantic Settings)
│   │   ├── database.py                 # SQLAlchemy async + SQLite (/tmp en Vercel)
│   │   ├── llm_factory.py              # Despachador multi-modelo con fallback automático
│   │   └── seed.py                     # Datos de prueba (4 casos de test predefinidos)
│   ├── models/entities.py              # Modelos SQLAlchemy (Claim, OrderItem)
│   ├── rag/
│   │   ├── agentic_rag.py              # Pipeline RAG (recuperación + generación)
│   │   ├── vector_store.py             # FAISS vector store con embeddings
│   │   └── knowledge_base/policies.md  # Manual de Políticas de Postventa (4 cláusulas)
│   ├── schemas/guardrails.py           # Pydantic schemas para respuestas de agentes
│   └── tools/
│       ├── oms.py                      # Simulación del Order Management System
│       └── logistics.py                # Generación de guías de logística inversa
├── .env.example                        # Variables requeridas (copiar a .env)
├── requirements.txt                    # Dependencias Python
├── vercel.json                         # Configuración de despliegue serverless
├── test_groq.py                        # Script de validación de modelos Groq
└── ecom_agent_postman_collection.json  # Colección Postman para testing
```

---

## Referencia de Endpoints

**Base URL producción:** `https://ecom-agent-backend.vercel.app`  
**Base URL local:** `http://localhost:8000`

---

### `POST /api/v1/claims` — Crear y procesar un reclamo

Inicia el flujo LangGraph completo. Acepta `multipart/form-data`.

| Campo | Tipo | Req. | Descripción |
|:---|:---|:---:|:---|
| `order_id` | `string` | ✅ | ID del pedido (ej: `ORD-1001`) |
| `customer_id` | `string` | ✅ | ID del cliente (ej: `CLI-123`) |
| `description` | `string` | ✅ | Descripción del problema relatado por el cliente |
| `evidence_image` | `file` | ✅ | Fotografía del producto / daño (PNG o JPG, máx 10 MB) |

**Response `201 Created`:**
```json
{
  "claim_id": "CLM-INIT-001",
  "status": "APPROVED_AUTO",
  "confidence_score": 0.92,
  "final_decision": "Reclamo aprobado. Garantía técnica aplicable según Art. 3.",
  "logistics_guide": { "tracking_code": "AND-001-2026", "carrier": "Andreani" },
  "investigation_summary": "Daño detectado: no. Relato coherente: sí.",
  "risk_level": "LOW",
  "policy_clause": "Artículo 3 — Garantía Técnica (180 días)"
}
```

**Posibles valores de `status`:**

| Status | Significado |
|:---|:---|
| `APPROVED_AUTO` | Aprobado autónomamente por el sistema |
| `REJECTED_CATEGORY_GUARDRAIL` | Rechazado: categoría excluida por política (ej: higiene) |
| `REJECTED_EXPIRED_DEADLINE` | Rechazado: plazo de devolución vencido |
| `PENDING_HITL_HIGH_AMOUNT` | Pausado: monto supera el umbral autónomo ($100.000) |
| `PENDING_HITL_FRAUD_RISK` | Pausado: sospecha de fraude detectada por el evaluador |

---

### `GET /api/v1/claims` — Listar todos los reclamos

Devuelve el historial completo de reclamos procesados.

---

### `GET /api/v1/claims/pending` — Cola HITL

Devuelve sólo los reclamos en estado `PENDING_HITL_*` que esperan decisión del supervisor.

```json
[
  {
    "claim_id": "CLM-INIT-HITL-003",
    "customer_name": "Juan Pérez",
    "order_id": "ORD-1002",
    "amount": 180000,
    "status": "PENDING_HITL_HIGH_AMOUNT",
    "pause_reason": "Monto ($180.000,00) supera el umbral autónomo de $100.000.",
    "confidence_score": 0.88
  }
]
```

---

### `GET /api/v1/claims/metrics` — Métricas del sistema

```json
{
  "total_claims": 3,
  "autonomy_rate": 0.333,
  "avg_confidence_score": 0.90,
  "pending_hitl": 1,
  "recent_claims": [...]
}
```

---

### `GET /api/v1/claims/{claim_id}` — Detalle de un reclamo

Devuelve el análisis completo: investigación, evaluación de riesgo, cláusula RAG citada, decisión final y guía logística.

---

### `PATCH /api/v1/claims/{claim_id}/review` — Resolución HITL

Endpoint para que el supervisor humano apruebe o rechace un caso en cola HITL.

**Request body:**
```json
{
  "decision": "APPROVED_BY_HUMAN",
  "supervisor_notes": "Evidencia auditada. Se aprueba cambio de producto por rotura de fábrica."
}
```

Valores válidos para `decision`: `APPROVED_BY_HUMAN` | `REJECTED_BY_HUMAN`

---

### `GET /` — Health check

```json
{ "status": "ok", "service": "E-Com Agent API" }
```

---

## Ejecución Local

### Prerrequisitos

- Python 3.11+
- API Key de [Google AI Studio](https://aistudio.google.com/apikey) (Gemini) — gratuita
- API Key de [Groq Cloud](https://console.groq.com) — gratuita

### 1. Clonar y configurar el entorno virtual

```bash
git clone https://github.com/nalancay17/ecom-agent-backend.git
cd ecom-agent-backend

python3 -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env`:

```env
# Google Gemini — clave principal (requerida)
API_KEY=AIzaSy...
MODEL=gemini-3.6-flash

# Google Gemini — clave secundaria (opcional, duplica el throughput gratuito)
API_KEY_2=AIzaSy...

# Groq Cloud — requerida para los agentes de texto
GROQ_API_KEY=gsk_...
GROQ_TEXT_FAST_MODEL=qwen/qwen3.6-27b
GROQ_TEXT_REASONING_MODEL=openai/gpt-oss-120b
GROQ_VISION_MODEL=openai/gpt-oss-20b
```

### 3. Ejecutar el servidor

```bash
uvicorn app.main:app --reload --port 8000
```

- API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 4. Validar modelos Groq (opcional)

```bash
python3 test_groq.py
# qwen/qwen3.6-27b     — ACTIVO
# openai/gpt-oss-120b  — ACTIVO
# openai/gpt-oss-20b   — ACTIVO
```

---

## Casos de Prueba Incluidos

Pedidos pre-cargados automáticamente al iniciar (`app/core/seed.py`):

| Pedido | Producto | Monto | Escenario | Resultado Esperado |
|:---|:---|---:|:---|:---|
| `ORD-1001` | Auriculares Bluetooth | $45.000 | Garantía técnica — falla de origen | ✅ `APPROVED_AUTO` |
| `ORD-1002` | Monitor Samsung 27″ Curvo | $180.000 | Pantalla rota — monto elevado | ⏸️ `PENDING_HITL_HIGH_AMOUNT` |
| `ORD-1003` | Pack Cremas Hidratantes | $12.500 | Categoría higiene (excluida por política) | ❌ `REJECTED_CATEGORY_GUARDRAIL` |
| `ORD-1004` | Zapatillas Running | $35.000 | Devolución fuera de plazo (45 días) | ❌ `REJECTED_EXPIRED_DEADLINE` |

---

## Despliegue en Vercel

El `vercel.json` ya está preconfigurado para servir FastAPI como función serverless.

```bash
npm i -g vercel
vercel --prod
```

En el Dashboard de Vercel → Settings → Environment Variables, agregar:
- `API_KEY` (requerida)
- `API_KEY_2` (opcional — segunda clave Gemini)
- `GROQ_API_KEY` (requerida)

> La variable `VERCEL=1` se setea automáticamente y redirige la base de datos a `/tmp/ecom_agent.db`.

---

## Testing con Postman

Importar `ecom_agent_postman_collection.json` en Postman. La colección incluye requests preconfigurados para todos los endpoints con body de ejemplo y variables de entorno configurables.

---

## Tecnologías

| Tecnología | Uso |
|:---|:---|
| **Python 3.11** | Lenguaje principal |
| **FastAPI** | Framework API REST asíncrona |
| **LangGraph** | Orquestación del grafo de agentes (StateGraph) |
| **LangChain + FAISS** | Pipeline RAG + vector store para búsqueda semántica |
| **SQLAlchemy + aiosqlite** | ORM async + base de datos SQLite |
| **Pydantic v2** | Validación de schemas y configuración |
| **Google GenAI SDK** | Cliente Gemini 3.6 Flash (visión multimodal + texto) |
| **groq** | Cliente Groq Cloud (Qwen 3.6 27B, GPT-OSS 120B/20B) |
| **Uvicorn** | Servidor ASGI de alta performance |

---

## Contexto Académico

**Curso:** Inteligencia Artificial Aplicada a Organizaciones  
**Institución:** UTN FRBA — EPIData  
**Alumno:** Nicolás J. Alancay Albelo  
**Fecha:** Agosto 2026  
**Video de demostración:** [Google Drive](https://drive.google.com/file/d/11qeewmConFSWAN0aqFidlC7hbWLlMFid/view?usp=sharing)
