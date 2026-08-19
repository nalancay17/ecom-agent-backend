from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.v1 import claims, webhooks
from app.core.config import settings
from app.core.seed import init_db_and_seed

# Inicialización BD en memoria
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Se ejecuta al levantar el servidor
    await init_db_and_seed()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend para proyecto E-Com Agent",
    version="1.0.0",
    lifespan=lifespan
)

# Routers
app.include_router(claims.router, prefix="/api/v1/claims", tags=["claims"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])

@app.get("/")
def health_check():
    return {"status": "ok", "message": "E-Com Agent API funcionando"}
