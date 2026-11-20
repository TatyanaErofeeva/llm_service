# Отчёт о тестировании

## Автоматические проверки

```bash
ruff check .
pytest -v
```

Ожидаемый результат: линтер без ошибок; все тесты зелёные.

Покрытые сценарии:

| Тест | Что проверяет |
| --- | --- |
| `test_health_check` | `GET /health` → `200` |
| `test_validation_error_on_short_text` | короткий `text` → `422` |
| `test_validation_error_on_missing_text` | пустое тело → `422` |
| `test_pipeline_success_and_cache_hit` | успех + повтор из кеша без второго вызова LLM |
| `test_cache_key_depends_on_model_and_temperature` | корректность ключа кеша |
| `test_cache_expiry` | TTL → miss после истечения |
| `test_pipeline_fallback_on_network_error` | `LLMNetworkError` → fallback |
| `test_llm_client_retries_then_raises` | ретраи при сетевой ошибке |

## Ручные сценарии (`POST /process`)

### 1. Корректный запрос → успешный ответ

- Действие: валидный текст (> 20 символов) при рабочем `LLM_API_KEY`.
- Ожидание: `200`, `is_fallback=false`, `from_cache=false`, краткая выжимка.
- Логи: `Incoming POST /process` → `Cache MISS` → `Prompt constructed` → `LLM request attempt` → `LLM response received` → `Cache SET`.

### 2. Повторный запрос → ответ из кеша

- Действие: тот же JSON в пределах `CACHE_TTL_SECONDS`.
- Ожидание: быстрый `200`, `from_cache=true`, без вызова LLM.
- Логи: `Incoming POST /process` → `Cache HIT`.

### 3. Некорректный ввод → понятная ошибка

- Действие: `{"text": "Коротко"}`.
- Ожидание: `422` с описанием `string_too_short`.

### 4. Сбой внешнего вызова → ретраи и fallback

- Действие: `LLM_BASE_URL=http://127.0.0.1:9` и новый текст.
- Ожидание: несколько попыток в логах (`ERROR`/`WARNING`), затем `200` с `is_fallback=true`.
