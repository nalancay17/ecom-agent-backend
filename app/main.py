from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.api.v1 import claims
from app.core.config import settings
from app.core.seed import init_db_and_seed

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa la base de datos y los datos semilla al iniciar el servidor
    await init_db_and_seed()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend para E-Com Agent: Sistema Agéntico de Postventa con LangGraph y Memoria Persistente",
    version="1.0.0",
    lifespan=lifespan
)

# Habilitar CORS para permitir peticiones desde el Frontend (Local y Cloud)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers de la API
app.include_router(claims.router, prefix="/api/v1/claims", tags=["claims"])

@app.get("/")
def health_check():
    return {"status": "ok", "message": "E-Com Agent API funcionando correctamente"}
