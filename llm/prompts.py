from __future__ import annotations

SYSTEM_PROMPT = (
    "Ты — профессиональный редактор. Твоя задача — делать точные и краткие выжимки "
    "(до 3 предложений) на русском языке без вводных слов и лишнего форматирования."
)


def build_messages(user_text: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Сделай выжимку следующего текста:\n\n{user_text}"},
    ]
