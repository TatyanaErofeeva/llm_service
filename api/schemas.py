from pydantic import BaseModel, Field


class ProcessRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=20,
        max_length=10000,
        description="Входной текст для суммаризации (от 20 до 10 000 символов)",
        examples=[
            "Архитектура программного обеспечения определяет фундаментальную "
            "организацию системы, её компоненты и принципы проектирования."
        ],
    )


class ProcessResponse(BaseModel):
    result: str = Field(..., description="Суммаризация или fallback-текст")
    is_fallback: bool = Field(
        ...,
        description="True, если ответ сформирован без успешного вызова LLM",
    )
    from_cache: bool = Field(
        ...,
        description="True, если результат взят из TTL-кеша",
    )
