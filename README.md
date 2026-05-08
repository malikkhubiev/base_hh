# HH Optimizer API

FastAPI сервис для:
- генерации булевых запросов по требованиям вакансии;
- поиска резюме в HH;
- расчета светофора (ColorScore);

## Запуск

```bash
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Основные эндпоинты

### Workflow API (`/api`)

- `GET /api/default_request` - вернуть дефолтный текст запроса.
- `GET /api/system_prompt` - вернуть системный prompt для генерации булевых выражений.
- `GET /api/user_prompt` - вернуть user prompt шаблон.
- `POST /api/generate_queries` - сгенерировать булев запрос.
- `POST /api/search` - выполнить поиск кандидатов в HH.
- `POST /api/traffic_light` - светофор по уже найденным кандидатам (без повторного HH-поиска).
- `POST /api/screening` - скрининг выбранных кандидатов: светофор + общие требования.

## Важные изменения

- `professional_role` полностью убран из API и внутренних фильтров.
- Поиск в HH и Светофор теперь строится только на блоке `Обязательно`.
- UI больше не отправляет редактируемые prompt'ы на backend.

## Примеры запросов/ответов

### 1) Сгенерировать булев запрос

```bash
curl -X POST "http://127.0.0.1:8000/api/generate_queries" \
  -H "Content-Type: application/json" \
  -d "{\"request_text\":\"# Обязательно:\n- Python\n- FastAPI\"}"
```

Пример ответа:

```json
{
  "llm_raw": {"response": "(python) AND (fastapi)"},
  "query": "(python) AND (fastapi)"
}
```

### 2) Поиск кандидатов

```bash
curl -X POST "http://127.0.0.1:8000/api/search" \
  -H "Content-Type: application/json" \
  -d "{\"request_text\":\"# Обязательно:\n- Python\n- FastAPI\",\"candidates_limit\":20}"
```

Важно про `candidates_limit`:

- `candidates_limit` — это **минимум** \(N\), который мы пытаемся собрать за счёт итераций ослабления булевого запроса (удаление пункта).
- В UI/ответ `candidates` возвращаем и показываем **до `N*3`** кандидатов (например, \(N=20 \Rightarrow 60\), \(N=7 \Rightarrow 21\)).
- Если HH на каком-то этапе вернул 2000+ результатов — в UI всё равно попадут только первые `N*3` (а `found_count` покажет реальное `found`).

Пример ответа:

```json
{
  "query": "(python) AND (fastapi)",
  "found_count": 2000,
  "candidates": [{"id": "123"}],
  "final_boolean_query": "(python) AND (fastapi)"
}
```

### 3) Светофор по уже найденным кандидатам

```bash
curl -X POST "http://127.0.0.1:8000/api/traffic_light" \
  -H "Content-Type: application/json" \
  -d "{\"request_text\":\"Python/FastAPI\",\"candidates\":[{\"id\":\"123\",\"title\":\"Python Dev\"}]}"
```

Пример ответа:

```json
{
  "traffic_light_candidates": [
    {
      "id": "123",
      "candidate_name": "Иван Иванов",
      "color_score_percent": 82,
      "requirements": []
    }
  ]
}
```

### 4) Скрининг выбранных кандидатов (светофор + общие требования)

UI сценарий:

- Нажать **Поиск** → получить таблицу.
- Отметить кандидатов галочками.
- Нажать **Скрининг**.

Пример запроса:

```bash
curl -X POST "http://127.0.0.1:8000/api/screening" \
  -H "Content-Type: application/json" \
  -d "{
    \"request_text\":\"# Обязательно:\\n- Python\\n- FastAPI\",
    \"general_requirements_text\":\"Опыт коммерческой разработки от 3 лет\",
    \"candidates\":[{\"id\":\"123\",\"title\":\"Python Dev\"}]
  }"
```

Пример ответа (схематично):

```json
{
  "traffic_light_candidates": [{"id":"123","candidate_name":"Иван Иванов","color_score_percent":82,"requirements":[]}],
  "general_requirements": [{"id":"123","candidate_name":"Иван Иванов","review_text":"..."}]
}
```

## Swagger/OpenAPI

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- Статический файл: `openapi.yaml`

## База данных (PostgreSQL) и кэш резюме

Для кэширования резюме (ограничения HH на открытие) сервис поддерживает Postgres-таблицу `resume_cache`.

- **ENV**: `DATABASE_URL` (пример: `postgresql://user:pass@localhost:5432/hh_optimizer`)
- `DATABASE_URL` **обязателен**: SQLite удалён, логи поиска пишутся только в Postgres.
