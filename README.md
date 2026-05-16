# HH Optimizer API

FastAPI-сервис для подбора кандидатов на hh.ru: генерация булевых запросов по требованиям вакансии, поиск резюме, скоринг (светофор / ColorScore) и скрининг с проверкой общих требований.

Встроенный UI: `GET /` — одностраничная HTML-форма для локальной отладки пайплайна.

## Быстрый старт

### 1. PostgreSQL

Если нужно кэшировать открытые резюме — укажите DSN вашего PostgreSQL в `DATABASE_URL`. Без него сервис работает, но резюме после скоринга в БД не сохраняются. Таблица `resume_cache` создаётся при старте, когда `DATABASE_URL` задан (или скриптом проверки ниже).

```text
postgresql://USER:PASSWORD@HOST:PORT/DBNAME
```

**Проверка, что сохранение работает** (без запуска API и без HH):

```bash
set DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DBNAME
python scripts/verify_postgres_resume_store.py
```

Скрипт создаёт схему, пишет тестовое резюме, читает его обратно и удаляет тестовую строку.

### 2. Окружение

```bash
cp .env.example .env
# DATABASE_URL — DSN вашего Postgres; при необходимости LLM_URL, HH_TOKEN_URL
```

### 3. Запуск API

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- Swagger: http://127.0.0.1:8000/docs  
- ReDoc: http://127.0.0.1:8000/redoc  
- OpenAPI JSON: http://127.0.0.1:8000/openapi.json  

### Тесты

```bash
pytest
```

В тестах БД не поднимается: `SKIP_DB_INIT=1`, хранилище резюме подменяется in-memory (`tests/conftest.py`).

---

## База данных

**СУБД:** PostgreSQL (через `psycopg`).

**Переменная:** `DATABASE_URL` — опциональна; без неё персистентности нет.

```text
postgresql://USER:PASSWORD@HOST:PORT/DBNAME
```

### Подключение при встраивании в другой проект

1. Скопируйте модуль `app/` (и `txt/` при необходимости) в целевой репозиторий.
2. Задайте `DATABASE_URL` тем же способом, что и остальные сервисы проекта (env, settings, secrets).
3. При старте FastAPI вызывается `get_resume_store().ensure_schema()` — отдельная миграция не нужна.
4. Проверьте DSN: `python scripts/verify_postgres_resume_store.py`.

### Что хранится в БД

**Только** полные JSON резюме HH, для которых выполнялся **скоринг** (платное открытие карточки):

| Таблица        | Назначение |
|----------------|------------|
| `resume_cache` | `resume_id`, `fetched_at`, `resume_json` (JSONB) |

Запись происходит в эндпоинтах:

- `POST /api/traffic_light`
- `POST /api/screening`
- `POST /api/svetofor` (поиск + скоринг top-N)

Поиск (`POST /api/search`) и логи HH **в БД не пишутся**.

При повторном скоринге того же `resume_id` сначала читается кэш из БД (без повторного платного открытия в HH).

---

## User flow (UI)

1. **Поиск** — ввести требования → `POST /api/search` → таблица кандидатов (краткие карточки из выдачи HH).
2. Отметить галочками нужных кандидатов.
3. **Скрининг** — `POST /api/screening` → светофор (ColorScore) + общие требования по каждому выбранному.
4. Альтернатива: **Светофор** по уже найденным — `POST /api/traffic_light` без повторного поиска.
5. **Светофор с поиском** — `POST /api/svetofor`: поиск + скоринг top-N, в ответе только успешно оценённые.

Вспомогательные кнопки UI загружают дефолтный текст запроса и шаблоны промптов (`GET /api/default_request`, `/api/system_prompt`, `/api/user_prompt`).

---

## API (`/api`)

### `GET /api/default_request`

Текст требований по умолчанию (plain text).

### `GET /api/system_prompt` / `GET /api/user_prompt`

Шаблоны промптов для генерации булевых запросов (plain text).

### `POST /api/generate_queries`

Сгенерировать булевый запрос без поиска в HH.

**Вход:** `request_text`, `prompt_override?`, `query_override?`  
**Выход:** `llm_raw`, `query`

### `POST /api/search`

Поиск кандидатов в HH.

**Вход (JSON):**

| Поле | Тип | Описание |
|------|-----|----------|
| `request_text` | string? | Текст вакансии/требований |
| `candidates_limit` | int, 1..200, default 20 | Минимум кандидатов для сбора |
| `area_id` | int? | Регион HH (иначе `AREA_ID`) |
| `prompt_override` | string? | Промпт для LLM |
| `query_override` | string? | Готовый булевый запрос (LLM пропускается) |

**Выход:** `query`, `found_count`, `candidates[]`, `final_boolean_query`, `final_search_url`, `stage_attempts[]`, `total_iterations`, `prompt_restarts`, тайминги (`started_at`, `bool_finished_at`, `hh_finished_at`, `finished_at`), `llm_raw`.

`candidates_limit` — **минимум** для итераций ослабления запроса; в ответе до **N×3** кандидатов.

**Candidate** (элемент `candidates`): `id`, `title`, `url`, `alternate_url`, `created_at`, `updated_at`, `age`, `area`, `employer`, `salary`, `experience`, `experience_full?`, `skills[]`, `tags[]`, `first_name`, `last_name`.

### `POST /api/traffic_light`

Скоринг по переданным кандидатам (без повторного поиска). Резюме догружается по `id` из HH (или из `resume_cache`).

**Вход:** `request_text` (required), `candidates[]`  
**Выход:** `traffic_light_candidates[]`

### `POST /api/screening`

Скоринг + общие требования для выбранных кандидатов.

**Вход:** `request_text`, `general_requirements_text?`, `candidates[]`  
**Выход:** `traffic_light_candidates[]`, `general_requirements[]`

### `POST /api/svetofor`

Поиск + скоринг top-N (`candidates_limit`). В ответе только кандидаты, прошедшие скоринг.

**Вход:** как у `search`  
**Выход:** как у `search` + `traffic_light_candidates[]`

### TrafficLightCandidate

`id`, `candidate_name`, `title`, `location`, `resume_url`, `color_score_percent` (0..100), `requirements[]`, `candidate_prj_exp`, `experience_full[]`, `debug_prompt`, `debug_llm_raw`

### TrafficLightRequirement

`requirement`, `resume_evidence`, `match_percent`, `difference_comment`

---

## Переменные окружения

| Переменная | Обязательна | Описание |
|------------|-------------|----------|
| `DATABASE_URL` | нет | PostgreSQL DSN; если пусто — кэш резюме отключён |
| `AREA_ID` | нет | Регион HH по умолчанию (например `113`) |
| `LLM_URL` | нет | URL LLM для булевых запросов и скоринга |
| `LLM_TOKEN_PARAM` | нет | Query-параметр токена LLM |
| `HH_TOKEN_URL` | нет | SSP-эндпоинт токена HH |
| `LOG_LEVEL` | нет | Уровень логов |
| `SKIP_DB_INIT` | нет | `1` — не подключаться к БД при старте (тесты) |

Токен HH всегда берётся из `HH_TOKEN_URL` (внутренний SSP).

---

## Структура проекта

```text
app/
  main.py                 # FastAPI, middleware трассировки, init схемы БД
  api/
    router.py             # Сборка роутов
    routes/
      workflow.py         # REST: search, screening, traffic_light, svetofor
      ui.py               # GET / — встроенный HTML UI
  clients/
    hh_client.py          # HH API: токен, поиск, get_resume_by_id (+ чтение кэша)
    llm_client.py         # Вызовы LLM
  core/
    settings.py           # Настройки из env
    resume_store.py       # PostgreSQL: resume_cache, persist_scored_resume
    logging.py, tracing.py
  models/
    schemas.py            # Pydantic-модели запросов/ответов
  services/
    hh_search.py          # Итерации поиска, ослабление булевого запроса
    request_query_planner.py  # Разбор требований → булевый запрос (LLM)
    query_generator.py    # Низкоуровневая генерация запросов
    traffic_light_service.py  # ColorScore (светофор)
    general_requirements_service.py  # Проверка общих требований
    prompts.py            # Чтение txt-промптов
  utils/
    file_manager.py
txt/                      # Промпты и дефолтный request_text
tests/
scripts/
  verify_postgres_resume_store.py  # smoke-тест записи в Postgres
```

### Ответственность модулей

| Модуль | Задача |
|--------|--------|
| `workflow.py` | HTTP-слой: оркестрация поиска, скоринга, скрининга; сохранение резюме после открытия |
| `HHSearchService` | План этапов поиска, сбор кандидатов, URL для HH |
| `RequestQueryPlanner` | LLM: требования → булевый запрос и план этапов |
| `HHClient` | HTTP к api.hh.ru; кэш **чтение** из `resume_cache` |
| `TrafficLightService` | LLM-оценка соответствия (светофор) |
| `GeneralRequirementsService` | LLM-проверка общих требований |
| `PostgresResumeStore` | Единственная персистентность: полные резюме после скоринга |

---

## Примеры curl

```bash
# Поиск
curl -X POST "http://127.0.0.1:8000/api/search" \
  -H "Content-Type: application/json" \
  -d "{\"request_text\":\"# Обязательно:\\n- Python\\n- FastAPI\",\"candidates_limit\":20}"

# Светофор по выбранным
curl -X POST "http://127.0.0.1:8000/api/traffic_light" \
  -H "Content-Type: application/json" \
  -d "{\"request_text\":\"Python/FastAPI\",\"candidates\":[{\"id\":\"123\",\"title\":\"Python Dev\"}]}"

# Скрининг
curl -X POST "http://127.0.0.1:8000/api/screening" \
  -H "Content-Type: application/json" \
  -d "{\"request_text\":\"Python\",\"general_requirements_text\":\"Опыт от 3 лет\",\"candidates\":[{\"id\":\"123\"}]}"
```

Подробные примеры тел запросов/ответов — в `letter.txt`.
