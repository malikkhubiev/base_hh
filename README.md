# HH Optimizer (FastAPI)

Сервис для подбора кандидатов в HH с двумя сценариями:

1. Классический поиск: из текста вакансии строит 3 уровня булевых запросов, запускает поиск в HH и отображает кандидатов.
2. Светофор: дополнительно оценивает релевантность кандидатов через LLM и возвращает цвет/процент совпадения.
3. HH Chat Bot: автоматизация переписки с кандидатами через HH chat API (webhook + polling fallback).

---

## 1. Возможности

- Генерация 3 уровней boolean-запросов через LLM (`Уровень 1/2/3`).
- Автоматическое добавление anti-manager исключения в запросы.
- Поиск резюме в HH API по фильтрам региона, ролей и опыта.
- Нормализация карточек кандидатов в стабильный JSON для UI.
- "Светофор" по кандидатам (цвет, match %, комментарий, debug).
- Фильтры "прыгун/не в деле" перед светофором.
- Локальный UI для рекрутингового workflow и отдельный UI чат-бота.
- SQLite-хранилище результатов HH поиска и событий чат-бота.

---

## 2. Как это работает (кратко)

Вход: `request_text` (требования вакансии)  
Выход: сформированные булевы запросы, найденные кандидаты, счетчики по уровням, а при светофоре - ранжированный список.

Pipeline:

1. API получает `request_text`.
2. `QueryGenerator` собирает prompt и вызывает LLM.
3. `LLMClient.extract_queries()` вытаскивает 3 уровня запроса.
4. `HHSearchService` добавляет исключения и собирает HH фильтры.
5. `HHClient` запрашивает `https://api.hh.ru/resumes`, при `401` делает повтор с обновленным токеном.
6. Результаты нормализуются и отдаются в API-ответ.
7. Для `/api/svetofor` по top-X кандидатам дополнительно выполняются HH resume fetch + LLM оценка в параллели.

---

## 3. Структура проекта

```text
app/
  main.py
  api/
    router.py
    routes/
      ui.py
      workflow.py
      chat_bot_ui.py
      chat_bot_api.py
  clients/
    llm_client.py
    hh_client.py
    hh_chat_client.py
  core/
    settings.py
    logging.py
    log_store.py
    chat_bot_store.py
  models/
    schemas.py
  services/
    prompts.py
    query_generator.py
    hh_search.py
    traffic_light_service.py
    job_stability.py
    chat_bot_service.py
  utils/
    file_manager.py

txt/
  request.txt
  system_prompt.txt
  user_prompt.txt

hh_optimizer.sqlite
hh_chat_bot.sqlite
```

---

## 4. API маршруты

### UI маршруты

- `GET /` - основной UI поиска/светофора.
- `GET /ui/bot` - UI чат-бота.

### Workflow API (`/api`)

- `GET /api/default_request` - текст запроса по умолчанию (`txt/request.txt`).
- `GET /api/system_prompt` - системный prompt.
- `GET /api/user_prompt` - пользовательский prompt.
- `POST /api/generate_queries` - только генерация 3 булевых уровней.
- `POST /api/search` - генерация + HH поиск кандидатов.
- `POST /api/svetofor` - генерация + HH поиск + светофор-оценка.

### Chat Bot API (`/api/chat_bot`)

- `POST /api/chat_bot/webhook/subscription/create`
- `GET /api/chat_bot/webhook/subscription/list`
- `POST /api/chat_bot/webhook/subscription/cancel`
- `POST /api/chat_bot/chat/create`
- `POST /api/chat_bot/chat/send`
- `POST /api/chat_bot/poller/start`
- `POST /api/chat_bot/poller/stop`
- `POST /api/chat_bot/poller/once`
- `GET /api/chat_bot/state`
- `GET /api/chat_bot/events`
- `POST /api/chat_bot/webhook`

---

## 5. Контракты запросов/ответов (основное)

См. точные схемы в `app/models/schemas.py`.

### `POST /api/generate_queries`

Вход:
- `request_text: str`
- `system_prompt_override: str | null`
- `user_prompt_override: str | null`

Выход:
- `llm_raw`
- `queries` (`Уровень 1`, `Уровень 2`, `Уровень 3`)

### `POST /api/search`

Вход:
- `request_text: str`
- `selected_level: str | null`
- `area_id: int | null`
- `professional_roles: list[str] | null`
- `candidates_limit: int`
- опционально: `min_stay_months`, `allowed_short_jobs`, `jump_mode`, `max_not_employed_months`, `svetofor_top_x`

Выход:
- `llm_raw`
- `queries`
- `queries_with_exclusions`
- `found_counts`
- `selected_level`
- `token_source_used`
- `candidates_by_level`

### `POST /api/svetofor`

Как `/api/search` + поле:
- `traffic_light_candidates` (итоговая оценка кандидатов).

---

## 6. Ключевые модули и ответственность

- `app/services/query_generator.py` - сбор prompt и генерация 3 уровней.
- `app/clients/llm_client.py` - вызов LLM и resilient-парсинг ответа.
- `app/services/hh_search.py` - фильтры HH, anti-manager исключения, orchestration поиска.
- `app/clients/hh_client.py` - работа с HH resumes API, токен, retry, сохранение результата.
- `app/services/traffic_light_service.py` - светофор-анализ кандидата.
- `app/services/job_stability.py` - фильтрация по стажу/перерывам/прыжкам.
- `app/services/chat_bot_service.py` - бизнес-логика чат-бота (создание/состояние/ответы).
- `app/core/log_store.py` - хранение результатов HH поиска в SQLite.
- `app/core/chat_bot_store.py` - состояния и события чат-бота в SQLite.

---

## 7. Конфигурация окружения

Пример (`.env.example`):

```env
LOG_LEVEL=INFO
LLM_URL=http://int-srv:8085/metrics/ecm/gpt
LLM_TOKEN_PARAM=?token=DebugEcmTest
HH_TOKEN_URL=http://int-srv:8085/metrics/hh/accessToken
AREA_ID=113
PROFESSIONAL_ROLES=96,113
USE_MOCK_LLM=false
USE_MOCK_HH=false
```

Ключевые переменные:

- `LLM_URL` - endpoint LLM.
- `LLM_TOKEN_PARAM` - auth/query-параметр для LLM.
- `HH_TOKEN_URL` - внутренний endpoint, который отдает HH access token.
- `AREA_ID` - регион поиска по умолчанию.
- `PROFESSIONAL_ROLES` - CSV ролей HH по умолчанию.
- `LOG_LEVEL` - уровень логирования.

---

## 8. Локальный запуск

Требования:
- Python 3.11+ (рекомендуется).
- Доступ к внутренним endpoint для LLM и HH token.

Шаги:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

После старта:

- UI поиска: `http://127.0.0.1:8000/`
- UI чат-бота: `http://127.0.0.1:8000/ui/bot`
- Swagger: `http://127.0.0.1:8000/docs`

---

## 9. Пользовательские сценарии

### Сценарий A: Быстрый подбор кандидатов

1. Открыть `/`.
2. Вставить требования вакансии.
3. Нажать "Получить булевый запрос" или сразу "Поиск".
4. Проверить выдачу по уровням и таблицу кандидатов.

### Сценарий B: Светофор

1. Выполнить поиск.
2. Нажать "Светофор".
3. Сервис отберет top-X кандидатов, применит фильтры стажа/перерывов и оценит релевантность через LLM.
4. Проверить цвета/проценты и детализацию.

### Сценарий C: Автоответчик HH Chat

1. Открыть `/ui/bot`.
2. Создать webhook-подписку.
3. Создать/получить чат по resume hash/url.
4. Настроить prompts и polling.
5. Проверять события в разделе лога.

---

## 10. Хранение данных

- `hh_optimizer.sqlite`:
  - таблица `hh_search_runs` с компактными результатами HH поиска.
- `hh_chat_bot.sqlite`:
  - состояния чатов, настройки polling, журнал событий чат-бота.

Преимущество: нет зависимости от JSON-файлов для основных runtime-данных.

---

## 11. Диагностика и типовые проблемы

### Пустые `queries` в ответе

- Проверьте `llm_raw` - в нем обычно есть причина некорректного формата ответа LLM.
- Проверьте корректность `system_prompt` и `user_prompt`.
- Убедитесь в доступности `LLM_URL`.

### 401 от HH API

- Сервис делает retry с повторным получением токена автоматически.
- Если проблема сохраняется, проверьте доступность `HH_TOKEN_URL`.

### Нет кандидатов в светофоре

- Возможно, кандидаты отфильтрованы логикой job stability.
- Проверьте значения `min_stay_months`, `allowed_short_jobs`, `jump_mode`, `max_not_employed_months`.
- Увеличьте `svetofor_top_x` в разумных пределах.

### Чат-бот не отвечает

- Проверьте наличие `chat_id` в state.
- Проверьте, что webhook подписка активна.
- Для fallback убедитесь, что включен polling.

---

## 12. Развертывание

В репозитории есть:

- `Procfile` для запуска через `uvicorn`.
- `render.yaml` с конфигурацией сервиса на Render.

Перед продом проверьте:

- корректность env-переменных;
- доступность внутренних интеграций;
- лимиты и таймауты на внешние вызовы.

---

## 13. Roadmap (что обычно развивают дальше)

- Экспорт результатов в Excel.
- Прогресс-бар этапов поиска в UI.
- Улучшение observability (метрики этапов, latency breakdown).
- E2E/интеграционные тесты для workflow и чат-бота.
- Расширение правил ранжирования кандидатов под конкретные домены.

---

## 14. Короткий FAQ

**Где менять prompts для генерации запросов?**  
В `txt/system_prompt.txt` и `txt/user_prompt.txt`, либо через override в UI/API.

**Где менять фильтры HH по умолчанию?**  
В `app/services/hh_search.py` и переменных `AREA_ID`, `PROFESSIONAL_ROLES`.

**Где смотреть логи/диагностику по генерации?**  
Смотрите `llm_raw` в API ответах и application logs.

**Где смотреть события чат-бота?**  
Через `GET /api/chat_bot/events` и UI `/ui/bot`.

