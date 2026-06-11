import os
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import get_settings
from app.database import create_tables
from app.routers import upload, books

settings = get_settings()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    os.makedirs(settings.output_dir, exist_ok=True)
    os.makedirs(settings.temp_dir, exist_ok=True)
    if settings.app_env == "development":
        await create_tables()
        logger.info("dev_tables_created")
    logger.info("app_started", env=settings.app_env)
    yield
    # Shutdown
    logger.info("app_shutdown")


app = FastAPI(
    title="PDF to EPUB3 Converter",
    version="1.0.0",
    description="Converte PDFs em EPUB3 Fixed Layout preservando diagramação original",
    lifespan=lifespan,
)

# ─── CORS ────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Global error handler ─────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_error", path=request.url.path, error=str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "Erro interno do servidor"}},
    )


# ─── Routes ──────────────────────────────────────────────────────────────────
app.include_router(upload.router)
app.include_router(books.router)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
