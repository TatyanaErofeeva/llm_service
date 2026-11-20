from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes import router
from config.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Service started: endpoints GET /health, POST /process")
    yield


app = FastAPI(
    title="End-to-End LLM Service",
    description="Сервис суммаризации текста с кешированием, ретраями и fallback",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router)
