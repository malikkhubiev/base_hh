Сервис «Найти на hh» — контракт API для внешнего сервиса
---

Обозначения:
- «Найти на hh» — этот FastAPI-сервис (бэкенд).
- «Внешний сервис» — ECM, который вызывает API «Найти на hh».
- HH — api.hh.ru (HeadHunter).

На бэкенде между этапами хранится session_id:
- квалификационные требования (request_text);
- список candidate_ids этапа 1;
- полные JSON резюме HH (таблица resume_cache в Postgres);
- метаданные сессии (таблица workflow_sessions в Postgres);
- результаты светофора этапа 2 (таблица traffic_light_cache в Postgres).

Подключение к Postgres через env:
- DB_HOST (по умолчанию localhost)
- DB_PORT (5432)
- DB_USER (postgres)
- DB_PASSWORD (mysecretpassword)
- DB_NAME (fastapi_db)
- DB_SSL_MODE (disable; на проде — require)

Альтернатива: напрямую DATABASE_URL (имеет приоритет над DB_*).

Схема БД создаётся автоматически при старте приложения.
Проверка: scripts/verify_postgres_resume_store.py

Таблицы Postgres:
| Таблица | Назначение |
|---------|------------|
| workflow_sessions | session_id, request_text, area_ids, candidates_limit, candidate_ids[] |
| resume_cache | resume_id → полный JSON резюме HH (этап 1 без контактов, этап 3 с контактами) |
| traffic_light_cache | session_id + resume_id → светофор (color_score, requirements) для этапа 3 |

Внешнему сервису на этапах 2 и 3 достаточно передавать session_id + candidate_ids[].


---
# ЭТАП 1. Указать требования → поиск и просмотр резюме (бесплатно)
---

### URL (внешний сервис → «Найти на hh»)

POST /api/search

### Вход (JSON)

| Поле               | Тип           | Обяз. | По умолчанию   | Описание |
|--------------------|---------------|-------|----------------|----------|
| request_text       | string        | да*   | —              | Квалификационные требования для LLM |
| candidates_limit   | int (1..200)  | нет   | 10             | «Требуется кандидатов» |
| area_ids           | int[]         | нет   | [113, 16]      | Регионы HH: 113 — Россия, 16 — Беларусь |
| prompt_override    | string        | нет   | null           | Переопределение промпта LLM |
| query_override     | string        | нет   | null           | Готовый булевый запрос (LLM пропускается) |

*Обязателен request_text, если не задан query_override.

Пример:
```json
{
  "request_text": "# Обязательно:\n- Python\n- FastAPI",
  "candidates_limit": 10,
  "area_ids": [113, 16]
}
```

### Выход (JSON)

| Поле                 | Тип     | Описание |
|----------------------|---------|----------|
| session_id           | string  | UUID сессии; нужен на этапах 2 и 3 |
| found_count          | int     | Сколько резюме нашёл HH по итоговому запросу |
| query                | string  | Итоговый булевый запрос (после этапов ослабления) |
| final_search_url     | string  | Ссылка на поиск в веб-UI HH |
| candidates           | array   | До candidates_limit × 3 элементов |
| candidates[].id      | string  | ID резюме HH |
| candidates[].resume_json | object | **Сырой JSON HH** полного резюме (без контактов) |
| llm_raw              | any     | Raw-ответ LLM генерации булевого запроса |
| stage_attempts       | array   | Этапы ослабления булевого запроса |
| stage_attempts[].stage | string | Название этапа, напр. «Этап 1» |
| stage_attempts[].query | string | Булевый запрос этапа |
| stage_attempts[].query_with_exclusion | string | Запрос с исключениями уже просмотренных |
| stage_attempts[].found | int   | found из ответа HH на этом этапе |
| stage_attempts[].collected | int | Сколько резюме уже собрано |
| stage_attempts[].target | int  | Целевое количество (candidates_limit × 3) |
| stage_attempts[].enough | bool | true, если collected ≥ target |
| stage_attempts[].web_url | string | Ссылка на поиск HH для этого этапа |
| total_iterations     | int     | Число итераций планировщика |
| prompt_restarts      | int     | Сколько раз перезапускали генерацию |
| started_at           | datetime | Начало этапа 1 (UTC) |
| bool_finished_at     | datetime | Конец генерации булевого запроса |
| hh_finished_at       | datetime | Конец загрузки полных резюме |
| finished_at          | datetime | Конец всего запроса /api/search |

### Пример каждого поля выхода (этап 1)

```json
{
  "session_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "found_count": 87,
  "query": "(python) AND (fastapi) AND (postgresql)",
  "final_search_url": "https://hh.ru/search/resume?text=%28python%29+AND+%28fastapi%29&area=113&area=16&per_page=30",
  "candidates": [
    {
      "id": "a1b2c3d4e5f6g7h8i9j0",
      "resume_json": {
        "id": "a1b2c3d4e5f6g7h8i9j0",
        "title": "Python-разработчик",
        "first_name": "Иван",
        "last_name": "Петров",
        "area": { "id": "1", "name": "Москва" },
        "salary": { "amount": 250000, "currency": "RUR" },
        "experience": [
          {
            "start": "2021-03-01",
            "end": null,
            "company": "ООО Ромашка",
            "position": "Backend Developer",
            "description": "FastAPI, PostgreSQL, Docker"
          }
        ],
        "skill_set": ["Python", "FastAPI", "PostgreSQL"],
        "contact": null
      }
    }
  ],
  "llm_raw": {
    "choices": [
      {
        "message": {
          "content": "{\"query\": \"(python) AND (fastapi) AND (postgresql)\"}"
        }
      }
    ]
  },
  "stage_attempts": [
    {
      "stage": "Этап 1",
      "query": "(python) AND (fastapi) AND (postgresql)",
      "query_with_exclusion": "(python) AND (fastapi) AND (postgresql)",
      "found": 87,
      "collected": 30,
      "target": 30,
      "enough": true,
      "web_url": "https://hh.ru/search/resume?text=%28python%29+AND+%28fastapi%29&area=113&area=16"
    }
  ],
  "total_iterations": 1,
  "prompt_restarts": 0,
  "started_at": "2026-06-28T10:15:00.123456",
  "bool_finished_at": "2026-06-28T10:15:03.456789",
  "hh_finished_at": "2026-06-28T10:15:45.789012",
  "finished_at": "2026-06-28T10:15:45.789012"
}
```

Пояснения к примеру:
- **session_id** — сохраняется в таблице `workflow_sessions` (Postgres); передаётся на этапы 2 и 3.
- **found_count** — поле `found` из последнего успешного GET /resumes HH.
- **query** — финальный булевый запрос, по которому набраны кандидаты (может отличаться от первого LLM-варианта после ослабления).
- **candidates** — не более `candidates_limit × 3` (при limit=10 → до 30); **resume_json** — полный ответ HH без контактов (`contact` = null).
- **llm_raw** — необработанный ответ LLM; структура зависит от провайдера.
- **stage_attempts** — журнал попыток поиска; если на «Этапе 1» набрали target, следующие этапы не выполняются.

### Алгоритм этапа 1 (функции бэкенда)

1. **search** (`workflow.py`)
   - Принимает SearchRequest.

2. **_run_query_generation**
   - Если `query_override` — использует его.
   - Иначе **RequestQueryPlanner.build** — LLM разбивает требования → булевый запрос + search_plan (этапы ослабления).

3. **_run_search_with_restarts** → **HHSearchService.search_counts_and_candidates**
   - **HHSearchService._build_search_filters** — area_ids[], age_to, experience, job_search_status, period.
   - Цель сбора: `target = candidates_limit × 3` (макс. 200).
   - Для каждого этапа search_plan:
     - **HHClient.search** — GET https://api.hh.ru/resumes
     - Если collected ≥ target — стоп.
   - Возвращает список кратких карточек из выдачи HH.

4. **_fetch_full_resumes_raw**
   - Параллельно (до 10 потоков) для каждого id:
     - **HHClient.get_resume_by_id** — GET https://api.hh.ru/resumes/{id} (бесплатный просмотр, без контактов).
     - **persist_resume** — сохранение в resume_cache.

5. **create_session** (`workflow_session.py`)
   - Сохраняет session_id, request_text, area_ids, candidates_limit, candidate_ids[] в Postgres (`workflow_sessions`).

6. Ответ клиенту: session_id + candidates с сырым resume_json.


---
# ЭТАП 2. Выбрать кандидатов → светофор (ColorScore)
---

UI внешнего сервиса:
- Показывает таблицу из этапа 1.
- По клику на имя/иконку — полное резюме из resume_json.
- Чекбоксы → кнопка «Далее».

### URL (внешний сервис → «Найти на hh»)

POST /api/traffic_light

### Вход (JSON)

| Поле           | Тип      | Обяз. | Описание |
|----------------|----------|-------|----------|
| session_id     | string   | да    | Из этапа 1 |
| candidate_ids  | string[] | да    | ID выбранных кандидатов |

Пример:
```json
{
  "session_id": "a1b2c3d4-....",
  "candidate_ids": ["id1", "id2", "id3"]
}
```

request_text и резюме **не передаются** — берутся из сессии и resume_cache.

### Выход (JSON)

| Поле | Тип | Описание |
|------|-----|----------|
| session_id | string | Та же сессия |
| candidates | array | Отсортировано по color_score_percent ↓ |

Элемент candidates[]:

| Поле                 | Тип    | Описание |
|----------------------|--------|----------|
| id                   | string | ID резюме |
| candidate_name       | string | ФИО или id |
| title                | string | Позиция |
| location             | string | Локация |
| color_score_percent  | int    | ColorScore 0..100 |
| requirements         | array  | Разбор по требованиям (светофор) |
| prompt               | string | Промпт, отправленный в LLM для этого кандидата |
| llm_raw              | any    | Сырой ответ LLM для этого кандидата |

### Пример каждого поля выхода (этап 2)

```json
{
  "session_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "candidates": [
    {
      "id": "a1b2c3d4e5f6g7h8i9j0",
      "candidate_name": "Петров Иван",
      "title": "Python-разработчик",
      "location": "Москва",
      "color_score_percent": 82,
      "requirements": [
        {
          "requirement": "Python",
          "resume_evidence": "Backend Developer, 3 года — Python в описании проекта",
          "match_percent": 100,
          "difference_comment": "Полное совпадение"
        },
        {
          "requirement": "FastAPI",
          "resume_evidence": "FastAPI в стеке последнего места работы",
          "match_percent": 90,
          "difference_comment": "Явно указан в опыте"
        },
        {
          "requirement": "PostgreSQL",
          "resume_evidence": "PostgreSQL упомянут один раз",
          "match_percent": 60,
          "difference_comment": "Опыт не детализирован"
        }
      ],
      "prompt": "Оцени соответствие кандидата требованиям...\n${custReqText}\n...\n${candidatePrjExp}",
      "llm_raw": {
        "color_score_percent": 82,
        "requirements": [
          {
            "requirement": "Python",
            "resume_evidence": "Backend Developer, 3 года — Python в описании проекта",
            "match_percent": 100,
            "difference_comment": "Полное совпадение"
          }
        ]
      }
    },
    {
      "id": "z9y8x7w6v5u4t3s2r1q0",
      "candidate_name": "Сидорова Анна",
      "title": "Junior Python Developer",
      "location": "Минск",
      "color_score_percent": 45,
      "requirements": [],
      "prompt": "Оцени соответствие...",
      "llm_raw": { "color_score_percent": 45, "requirements": [] }
    }
  ]
}
```

Пояснения:
- **candidates** отсортированы по **color_score_percent** по убыванию (100 → 45).
- **requirements** — разбор по каждому пункту требований из request_text сессии; **match_percent** 0..100.
- **prompt** и **llm_raw** — для отладки: что отправили в LLM и что вернулось (на каждого кандидата отдельно). **llm_raw** часто содержит `{ "markdown": "..." }` с JSON внутри markdown-блока.
- Если LLM не ответил — кандидат всё равно в списке с **color_score_percent** = 0 и пустым **requirements**.
- Результаты сохраняются в **traffic_light_cache** (Postgres) — нужны для этапа 3.

### Алгоритм этапа 2

1. **traffic_light_from_candidates**
   - **require_session(session_id)** — 404 если нет.
   - **_validate_session_candidate_ids** — id должны быть из этапа 1.

2. Для каждого candidate_id:
   - **_load_resume_json** из resume_cache.
   - **_extract_candidate_prj_exp** — текст проектного опыта.
   - **TrafficLightService.generate_candidate_traffic_light**
     - build_prompt → LLM (**LLMClient.call**) → parse JSON → ColorScore.
   - **persist_scored_resume** (обновление кэша).

3. **_merge_traffic_light_with_source_candidates** — все выбранные id в ответе.
4. Сортировка по color_score_percent по убыванию.
5. Маппинг в TrafficLightResultItem (prompt, llm_raw на каждого кандидата).
6. **persist_traffic_light_batch** — запись всех результатов в traffic_light_cache для этапа 3.

---
# ЭТАП 3. Добавить кандидатов → контакты (платно)
---

UI: таблица светофора, чекбоксы, кнопка «Добавить».

### URL (внешний сервис → «Найти на hh»)

POST /api/contacts

### Вход (JSON)

| Поле           | Тип      | Обяз. | Описание |
|----------------|----------|-------|----------|
| session_id     | string   | да    | Из этапа 1 |
| candidate_ids  | string[] | да    | ID отобранных после светофора |

Пример:
```json
{
  "session_id": "a1b2c3d4-....",
  "candidate_ids": ["id1", "id2",...]
}
```

### Выход (JSON)

| Поле | Тип | Описание |
|------|-----|----------|
| session_id | string | Сессия |
| candidates | array | Кандидаты: светофор + полное резюме HH с контактами |

Элемент candidates[]:

| Поле | Тип | Описание |
|------|-----|----------|
| traffic_light | object | Светофор без prompt и llm_raw |
| traffic_light.id | string | ID резюме |
| traffic_light.candidate_name | string | ФИО или id |
| traffic_light.title | string | Позиция |
| traffic_light.location | string | Локация |
| traffic_light.color_score_percent | int | ColorScore 0..100 |
| traffic_light.requirements | array | Разбор по требованиям |
| resume_json | object | **Сырой JSON HH** полного резюме с контактами |
| error | string | Ошибка открытия (если была) |

### Пример каждого поля выхода (этап 3)

```json
{
  "session_id": "206b175c-beb9-4bc4-b31b-e233ca370d07",
  "candidates": [
    {
      "traffic_light": {
        "id": "c9ef2262000941821700562f60785657723343",
        "candidate_name": "Курбанов Руслан",
        "title": "Data Engineer",
        "location": "Москва",
        "color_score_percent": 100,
        "requirements": [
          {
            "requirement": "Опыт работы с Parquet",
            "resume_evidence": "2024-09-01 (Бюро 1440) Data Engineer: Работа с Parquet.",
            "match_percent": 100,
            "difference_comment": "Кандидат имеет опыт работы с Parquet."
          }
        ]
      },
      "resume_json": {
        "id": "c9ef2262000941821700562f60785657723343",
        "title": "Data Engineer",
        "first_name": "Руслан",
        "last_name": "Курбанов",
        "area": { "id": "1", "name": "Москва" },
        "contact": [
          {
            "kind": "phone",
            "type": { "id": "cell", "name": "Мобильный телефон" },
            "contact_value": "+7 912 929-87-77",
            "verified": true
          },
          {
            "kind": "email",
            "type": { "id": "email", "name": "Эл. почта" },
            "contact_value": "yagami99@yandex.ru",
            "preferred": true
          }
        ],
        "experience": [ "...полный массив опыта HH..." ],
        "skills": "...",
        "actions": { "download": { "pdf": { "url": "..." } } }
      },
      "error": null
    },
    {
      "traffic_light": {
        "id": "z9y8x7w6v5u4t3s2r1q0",
        "candidate_name": "Сидорова Анна",
        "title": "Junior Python Developer",
        "location": "Минск",
        "color_score_percent": 45,
        "requirements": []
      },
      "resume_json": null,
      "error": "HH returned 400: ..."
    }
  ]
}
```

Пояснения:
- Запрос **платный** — каждый id списывает контакт работодателя в HH.
- **traffic_light** — результат этапа 2 из `traffic_light_cache` (без `prompt` и `llm_raw`).
- **resume_json** — полный ответ HH после GET по `actions.get_with_contact.url`; контакты в массиве `contact[]` (поле `contact_value`; устаревшее `value` — deprecated).
- Телефон и email внешний сервис извлекает сам из `resume_json.contact[]` (по `kind` / `type.id`).
- **error** — заполняется при неудаче (текст от HH или «HH did not provide get_with_contact action»); при успехе null или отсутствует.
- Если светофора нет в кэше — **400** (нужно сначала вызвать `/api/traffic_light` для этих id).
- HTTP-ответ этапа 3 всегда **200**, даже если у отдельных кандидатов `error` ≠ null.

### Алгоритм этапа 3

1. **open_contacts** — проверка session_id и candidate_ids (id должны быть из этапа 1).
2. Загрузка светофора из **traffic_light_cache** для каждого id (**400** если нет записи).
3. Для каждого id параллельно (**HHClient._fetch_resume_with_contacts**):
   a. Если в **resume_cache** уже есть резюме с контактами — вернуть из кэша (без повторного списания).
   b. **Свежий GET** `/resumes/{id}` (не из кэша этапа 1) — получить актуальный `actions.get_with_contact.url`.
   c. Если контакты уже открыты в ответе HH — сохранить и вернуть.
   d. **GET** по URL из `actions.get_with_contact.url` (платно; параметр `with_contact` — хеш-токен, не `true`).
   e. **persist_resume** — обновление кэша с контактами.
4. Ответ: `candidates[]` = `{ traffic_light, resume_json, error? }`.

---
# «Найти на hh» → HH (api.hh.ru)
---

### 0. Получение токена (внутренний SSP)

GET {HH_TOKEN_URL}  (env: HH_TOKEN_URL, по умолчанию http://int-srv:8085/metrics/hh/accessToken)

Выход: plain text — Bearer-токен для HH API.

Функция: **HHClient.get_token**

---

### 1. Поиск резюме (этап 1, бесплатно)

GET https://api.hh.ru/resumes

Заголовки:
- Authorization: Bearer {token}

Query (основные):
| Параметр | Пример | Описание |
|----------|--------|----------|
| text     | (python) AND (fastapi) | Булевый запрос |
| area     | 113, 16 (повторяемый) | Регионы |
| per_page | 30 | До target |
| age_to   | 45 | |
| experience | between3And6, moreThan6 | |
| job_search_status | unknown, active_search, looking_for_offers | |
| period   | 0 | За всё время |

Выход HH (JSON): `{ "found": int, "items": [ {...краткая карточка...} ] }`

Функция: **HHClient.search**

---

### 2. Просмотр полного резюме (этап 1, бесплатно, без контактов)

GET https://api.hh.ru/resumes/{resume_id}

Заголовки: Authorization: Bearer {token}

Выход: полный JSON резюме (контакты скрыты/null).

Функция: **HHClient.get_resume_by_id(with_contacts=False)**

Кэш: **persist_resume** → resume_cache (PostgreSQL JSONB).

---

### 3. Открытие контактов (этап 3, платно)

Порядок вызовов в **HHClient._fetch_resume_with_contacts**:

1. Проверка **resume_cache** — если контакты уже открыты, вернуть кэш.
2. **Свежий GET** `https://api.hh.ru/resumes/{resume_id}` — не из кэша этапа 1 (нужен актуальный `actions`).
3. Если в ответе уже есть `contact[]` с данными — контакты ранее открыты, сохранить и вернуть.
4. Взять URL из `actions.get_with_contact.url` и выполнить **GET** по нему.

Пример URL:
```
https://api.hh.ru/resumes/{resume_id}?with_contact=ab65a8562d85e1798ad90d67fe8f5253
```

Важно: параметр `with_contact` — **хеш-токен из actions**, не литерал `true`. Запрос `?with_contact=true` HH отклоняет с **400**.

Заголовки: Authorization: Bearer {token}

Выход: полный JSON резюме с контактами (списание контакта у работодателя в HH).
Поле `contact` — массив объектов с `contact_value` (актуальное поле; устаревшее `value` — deprecated).
Дополнительно в ответе: `first_name`, `last_name`, `middle_name`, `photo`, `contact_view_status`, `contacts_open_until_date`.

Функция: **HHClient.get_resume_by_id(with_contacts=True)** → **_fetch_resume_with_contacts**

Типичные ошибки (поле `error` в candidates[]):
- `failed to load resume from HH` — не удалось получить свежее резюме.
- `HH did not provide get_with_contact action (contacts may be unavailable)` — в actions нет get_with_contact.
- `HH returned 4xx: ...` — ответ HH при платном открытии (лимит контактов, резюме недоступно и т.д.).

---

### 4. LLM — генерация булевого запроса (этап 1)

POST {LLM_URL}{LLM_TOKEN_PARAM}  (env: LLM_URL, LLM_TOKEN_PARAM)

Функции: **RequestQueryPlanner.build**, **LLMClient.call**

---

### 5. LLM — светофор ColorScore (этап 2)

POST {LLM_URL}{LLM_TOKEN_PARAM}

Функция: **TrafficLightService.generate_candidate_traffic_light**

Промпт: txt/traffic_light_prompt.txt с подстановкой ${custReqText}, ${candidatePrjExp}.

---
# Поток данных (кратко)
---

```
[Внешний UI]
    │ POST /api/search { request_text, candidates_limit, area_ids }
    ▼
[Найти на hh] ──LLM──► булевый запрос
    │ ──GET /resumes──► HH (поиск)
    │ ──GET /resumes/{id}──► HH × N (просмотр, бесплатно)
    │ session_id + candidates[{ id, resume_json }]
    ▼
[Внешний UI] выбор id → POST /api/traffic_light { session_id, candidate_ids }
    ▼
[Найти на hh] ──кэш резюме + LLM──► candidates[] sorted by ColorScore
    │ persist_traffic_light_batch → traffic_light_cache
    ▼
[Внешний UI] выбор id → POST /api/contacts { session_id, candidate_ids }
    ▼
[Найти на hh] ──traffic_light_cache + GET with_contact──► HH (платно)
    │ → candidates[{ traffic_light, resume_json, error? }]
    │ persist_resume → resume_cache (с контактами)
```

Авторизация между внешним сервисом и «Найти на hh»: **не требуется** (на текущем этапе).

# HTTP-коды ошибок API

| Эндпоинт | Код | Когда |
|----------|-----|-------|
| /api/search | 400 | Нет request_text и query_override |
| /api/search | 502 | HH API недоступен |
| /api/traffic_light | 404 | session_id не найден |
| /api/traffic_light | 400 | candidate_ids не из сессии; resume не в кэше |
| /api/contacts | 404 | session_id не найден |
| /api/contacts | 400 | candidate_ids не из сессии; нет светофора в traffic_light_cache |

Этап 3 при частичных ошибках HH возвращает **200** с `error` внутри элемента `candidates[]`.
