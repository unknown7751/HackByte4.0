"""
SmartAccident — FastAPI Application Entry Point

Run with:
    uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import settings
from src.routes import accidents_router, volunteers_router, tasks_router, voice_router,rewards_router


# ── Lifespan (startup / shutdown) ──────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — runs on startup and shutdown."""
    # Startup: engine is already created on import; nothing extra needed.
    print("🚀 SmartAccident API starting up...")
    print(f"   Environment : {settings.APP_ENV}")
    print(f"   Database    : {settings.DATABASE_URL.split('@')[-1]}")

    # Initialize blockchain reward service (non-blocking, logs warnings if unconfigured)
    try:
        from src.services import blockchain_service
        blockchain_service.initialize()
        print("   Blockchain  : ✅ connected")
    except Exception as e:
        print(f"   Blockchain  : ⚠️  {e} (rewards disabled)")

    yield
    # Shutdown: dispose the engine to release connections.
    from src.config.database import engine
    await engine.dispose()
    print("🛑 SmartAccident API shut down.")


# ── App ────────────────────────────────────────────────────────
app = FastAPI(
    title="SmartAccident API",
    description=(
        "Real-time accident reporting, AI-prioritized response, "
        "and blockchain-incentivized volunteer coordination."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ─────────────────────────────────────────────────────
app.include_router(accidents_router, prefix="/api/v1")
app.include_router(volunteers_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(rewards_router, prefix="/api/v1")
app.include_router(voice_router, prefix="/api/v1")


# ── Health Check ───────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "smartaccident-api"}
