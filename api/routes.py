from fastapi import APIRouter, HTTPException

from api.schemas import ProcessRequest, ProcessResponse
from config.logging import get_logger
from llm.client import LLMClient
from services.cache import TTLCache
from services.pipeline import TextProcessingPipeline

logger = get_logger(__name__)
router = APIRouter()

pipeline = TextProcessingPipeline(llm_client=LLMClient(), cache=TTLCache())


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/process", response_model=ProcessResponse)
async def process_text(payload: ProcessRequest):
    logger.info(
        "Incoming POST /process request, text_length=%s",
        len(payload.text),
    )
    try:
        result, is_fallback, from_cache = await pipeline.execute(payload.text)
        logger.info(
            "POST /process done: is_fallback=%s from_cache=%s result_length=%s",
            is_fallback,
            from_cache,
            len(result),
        )
        return ProcessResponse(
            result=result,
            is_fallback=is_fallback,
            from_cache=from_cache,
        )
    except Exception as exc:
        logger.error("Unhandled internal server error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc
