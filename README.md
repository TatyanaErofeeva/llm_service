# End-to-End LLM Text Summarization Service

HTTP-сервис на **FastAPI** для краткой суммаризации текста через внешнюю LLM.
Включены: Pydantic-валидация, in-memory TTL-кеш, ретраи с backoff, graceful fallback при сбоях сети/API, структурированные логи и CI (lint + tests).

## Архитектура

```text
POST /process ──► api/ (Pydantic валидация)
                    │
                    ▼
             services/pipeline.py
               ├──► services/cache.py (SHA-256 ключ + TTL) ──► [Cache HIT] ──► Ответ
               │
               ▼ [Cache MISS]
             llm/prompts.py (system + user)
               │
               ▼
             llm/client.py (httpx + таймауты + ретраи)
               ├──► [Успех] ──► services/postprocessor.py ──► Запись в кеш ──► Ответ
               └──► [Сбой сети/API] ──► Fallback-ответ (is_fallback: true)
```

| Каталог | Назначение |
| --- | --- |
| `api/` | Роуты (`POST /process`, `GET /health`) и схемы запроса/ответа |
| `services/` | Пайплайн, TTL-кеш, постобработка ответа модели |
| `llm/` | HTTP-клиент LLM (таймауты, ретраи) и промпты |
| `config/` | Настройки из env и логирование |
| `tests/` | Автотесты (валидация, кеш, fallback, health) |
| `.github/` | CI workflow и шаблон PR с чек-листом |

## Требования

- Python **3.9+** (CI использует 3.11)
- Ключ OpenAI-совместимого API

## Быстрый старт (одна команда после настройки)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # укажите реальный LLM_API_KEY
uvicorn main:app --reload
```

После этого сервис доступен по адресу:

- API: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## Конфигурация (переменные окружения)

Секреты хранятся только в `.env` (файл в `.gitignore`). В репозитории есть `.env.example` без реальных ключей.

| Переменная | По умолчанию | Описание |
| --- | --- | --- |
| `APP_ENV` | `dev` | `dev` — читаемые логи, `prod` — JSON-логи |
| `LOG_LEVEL` | `INFO` | Уровень логирования |
| `LLM_API_KEY` | *(обязательно)* | Ключ доступа к LLM API |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | Базовый URL OpenAI-совместимого API |
| `LLM_MODEL` | `gpt-4o-mini` | Модель |
| `LLM_TEMPERATURE` | `0.3` | Температура генерации (входит в ключ кеша) |
| `LLM_TIMEOUT` | `15.0` | Таймаут одного запроса к LLM, сек |
| `LLM_MAX_RETRIES` | `2` | Число повторных попыток при сети/5xx/429 |
| `LLM_RETRY_DELAY` | `1.0` | Базовая задержка между ретраями, сек |
| `CACHE_TTL_SECONDS` | `300` | TTL записи в кеше, сек |

## API

### `GET /health`

```bash
curl http://127.0.0.1:8000/health
```

```json
{"status": "ok"}
```

### `POST /process`

Вход: JSON с полем `text` (длина **20–10000** символов).

**Успешный запрос:**

```bash
curl -X POST http://127.0.0.1:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Архитектура программного обеспечения определяет фундаментальную организацию системы, её компоненты, их взаимодействие между собой и со средой, а также принципы проектирования."
  }'
```

```json
{
  "result": "Архитектура ПО задаёт базовую структуру системы, состав её компонентов, правила их взаимодействия и принципы проектирования.",
  "is_fallback": false,
  "from_cache": false
}
```

Повтор того же текста в пределах TTL вернёт `"from_cache": true` без вызова LLM.

**Ошибка валидации (`422`):**

```bash
curl -X POST http://127.0.0.1:8000/process \
  -H "Content-Type: application/json" \
  -d '{"text": "Коротко"}'
```

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "text"],
      "msg": "String should have at least 20 characters"
    }
  ]
}
```

**Fallback при недоступности LLM (`200`, `is_fallback: true`):**

Если внешний API недоступен (нет сети, таймаут, 5xx), клиент делает ретраи и возвращает резервный ответ:

```json
{
  "result": "Сервис автоматической суммаризации временно недоступен. Начало исходного текста: ...",
  "is_fallback": true,
  "from_cache": false
}
```

Проверка: временно укажите в `.env` `LLM_BASE_URL=http://127.0.0.1:9` и отправьте новый текст.

## Устойчивость и наблюдаемость

- **Кеш:** ключ `SHA-256(model:temperature:text)`, TTL из `CACHE_TTL_SECONDS`; в логах `Cache HIT` / `Cache MISS` / `Cache SET` / `Cache EXPIRED`.
- **Ретраи:** таймауты и сетевые/5xx/429 ошибки; клиентские 4xx (кроме 429) не ретраятся.
- **Fallback:** при исчерпании попыток или ошибке постобработки сервис не падает, а отдаёт понятный резервный текст.
- **Логи:** этапы `Incoming POST /process` → cache → prompt → LLM attempts → post-process / fallback; уровни `INFO` / `WARNING` / `ERROR`.

## Тесты и линтинг

```bash
ruff check .
pytest -v
```

Подробности сценариев и **скриншоты** (запуск, успех, кеш, ошибка валидации, fallback) — в [TESTING.md](TESTING.md).

## CI

GitHub Actions (`.github/workflows/ci.yml`) на каждый push/PR в `main`/`master`:

1. Установка зависимостей
2. `ruff check .`
3. `pytest -v`

Шаблон PR с чек-листом самопроверки: `.github/PULL_REQUEST_TEMPLATE.md`.
