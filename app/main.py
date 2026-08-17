from fastapi import FastAPI
from app.api.v1 import claims, webhooks
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend para proyecto E-Com Agent",
    version="1.0.0"
)

# Routers
app.include_router(claims.router, prefix="/api/v1/claims", tags=["claims"])
app.include_router(webhooks.router, prefix="/api/v1/webhooks", tags=["webhooks"])

@app.get("/")
def health_check():
    return {"status": "ok", "message": "E-Com Agent API funcionando"}
