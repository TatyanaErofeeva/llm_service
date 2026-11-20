import re


class PostProcessingError(Exception):
    """Ошибка проверки или очистки ответа модели."""


def postprocess_output(raw_text: str) -> str:
    if not raw_text or not raw_text.strip():
        raise PostProcessingError("Empty response from LLM")

    cleaned = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", raw_text.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if len(cleaned) < 5:
        raise PostProcessingError("Response too short after cleaning")

    return cleaned
