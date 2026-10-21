from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import settings
from app.models.database import init_db, close_db
from app.api.routes import api_router
from app.services.router import router
from app.services.prober import prober

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Sentinel Engine...")
    await init_db()
    logger.info("Database initialized")

    # Start background prober
    await prober.start()
    logger.info("Model prober started")

    yield

    # Shutdown
    logger.info("Shutting down Sentinel Engine...")
    await prober.close()
    await router.close()
    await close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Sentinel Engine",
    description="LLM Gateway with smart routing, failover, and model probing",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
async def root():
    return {
        "service": "sentinel-engine",
        "version": "1.0.0",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)