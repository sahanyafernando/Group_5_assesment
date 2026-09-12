from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.startup import print_startup_report
from app.routers import ai, dashboard, dispatch, health, incidents, pipeline, stats

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Print configuration and Supabase connectivity once, at boot."""
    print_startup_report()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Decision-support API for Muthuwella Municipal Council Works Dispatch.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(incidents.router, prefix="/api")
app.include_router(dispatch.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(pipeline.router, prefix="/api")
app.include_router(ai.router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": "/api/health",
    }
