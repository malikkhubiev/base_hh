# HH Optimizer (FastAPI)

Сервис для подбора кандидатов в HH по тексту требований вакансии:

- преобразует требования в 3 булевых запроса через LLM;
- дополняет запросы анти-менеджерским исключением;
- отправляет поиск в HH API;
- возвращает количество найденных резюме и список кандидатов по уровням;
- включает встроенный single-file UI для отладки пайплайна.

---

## 1) Что делает система

На вход подается текст требований вакансии (`request_text`).  
На выходе API отдает:

- `queries` — 3 строки поиска (`Уровень 1/2/3`) из LLM;
- `queries_with_exclusions` — те же запросы + глобальное исключение руководящих ролей;
- `found_counts` — найдено резюме по каждому уровню;
- `candidates_by_level` — список кандидатов для UI;
- `llm_raw` — сырой ответ LLM (для диагностики).

Основной сценарий: рекрутер/сорсер вводит описание вакансии, получает варианты запроса разной строгости и быстро переключается между уровнями для оценки качества выдачи.

---

## 2) Архитектура

### Слои

- `app/main.py` — создание FastAPI приложения.
- `app/api/` — HTTP слой (роуты, схемы обмена).
- `app/services/` — прикладная логика (генерация запросов, orchestration HH поиска, работа с prompt файлами).
- `app/clients/` — интеграции с внешними системами (LLM endpoint, HH API).
- `app/core/` — конфигурация и логирование.
- `app/utils/` — инфраструктурные утилиты (чтение/запись файлов).
- `txt/` — шаблоны prompt-ов и дефолтный текст запроса.
- SQLite — хранение результатов поиска HH (без записи JSON-файлов).

### Поток данных (high level)

1. UI/клиент вызывает `/api/search`.
2. `workflow.search()` запускает `QueryGenerator.generate()`.
3. `QueryGenerator` собирает prompt из `system_prompt.txt` + `user_prompt.txt` и вызывает `LLMClient.call()`.
4. `LLMClient.extract_queries()` парсит 3 уровня булевых запросов.
5. `HHSearchService.search_counts_and_candidates()` строит фильтры HH, добавляет exclusion и для каждого уровня вызывает `HHClient.search()`.
6. `HHClient` получает токен, вызывает `https://api.hh.ru/resumes` и сохраняет компактные результаты поиска в SQLite.
7. Роут нормализует кандидатов до тонкой DTO-модели и возвращает JSON ответ.

---

## 3) Дерево проекта (ключевое)

```text
app/
  main.py
  core/
    logging.py
    log_store.py
    settings.py
  api/
    router.py
    routes/
      ui.py
      workflow.py
  models/
    schemas.py
  services/
    prompts.py
    query_generator.py
    hh_search.py
    job_stability.py
  clients/
    llm_client.py
    hh_client.py
  utils/
    file_manager.py

txt/
  request.txt
  system_prompt.txt
  user_prompt.txt
```

---

## 4) API и контракты

### `GET /`

- Возвращает HTML/JS интерфейс для отладки.
- Источник: `app/api/routes/ui.py`.

### `GET /api/default_request`

- Возвращает текст из `txt/request.txt`.
- Нужен для кнопки "Запрос по умолчанию".

### `GET /api/system_prompt`

- Возвращает текст `txt/system_prompt.txt`.
- Используется для UI-режима редактирования prompt-а.

### `GET /api/user_prompt`

- Возвращает текст `txt/user_prompt.txt`.

### `POST /api/generate_queries`

- Вход: `GenerateQueriesRequest`:
  - `request_text`
  - `system_prompt_override` (optional)
  - `user_prompt_override` (optional)
- Выход: `GenerateQueriesResponse`:
  - `llm_raw`
  - `queries` (`Уровень 1/2/3`)
- Используется, когда нужно только построить булевы запросы без HH поиска.

### `POST /api/search`

- Вход: `SearchRequest`:
  - `request_text`
  - `selected_level`
  - `area_id` / `professional_roles`
  - `system_prompt_override` / `user_prompt_override`
  - (опционально) параметры фильтрации стажа/«прыгуна» и лимит кандидатов для светофора:
    `min_stay_months`, `allowed_short_jobs`, `jump_mode`, `max_not_employed_months`, `svetofor_top_x`
- Выход: `SearchResponse`:
  - `llm_raw`, `queries`, `queries_with_exclusions`
  - `found_counts`
  - `selected_level`
  - `token_source_used`
  - `candidates_by_level`

---

## 5) Workflow (подробно)

### 5.1 Генерация запросов (LLM path)

Файл: `app/services/query_generator.py`

1. Загружает `system_prompt.txt` и `user_prompt.txt` через `FileManager`.
2. Подставляет `request_text` в шаблон `{vac_reqs}`.
3. Отправляет комбинированный prompt в `LLMClient.call()`.
4. Парсит ответ в `LLMClient.extract_queries()`:
   - пытается достать JSON из строки `response`;
   - поддерживает несколько форматов (прямой JSON, nested `markdown`, regex fallback);
   - нормализует значения к строкам.
5. Гарантирует наличие всех 3 ключей (`Уровень 1`, `Уровень 2`, `Уровень 3`).
6. Если LLM не ответила/не распарсился ответ — уровни отдаются пустыми строками; диагностика делается по `llm_raw` в ответе API.

### 5.2 Поиск в HH (search path)

Файл: `app/services/hh_search.py`

1. На каждый уровень добавляет единое исключение:
   - `NOT (lead OR лид OR head OR руковод* OR начальн* OR директор OR CTO)`.
2. Формирует фильтры `_build_search_filters()`:
   - `area` (по умолчанию 113),
   - `age_to=45`,
   - `job_search_status` (3 значения),
   - `experience` (`between3And6`, `moreThan6`),
   - `period=0`,
   - `professional_roles` из входа или keyword mapping из текста.
3. Если вакансия не менеджерская — добавляет анти-менеджерскую строку и в `title`:
   - `not (lead and лид and head and руковод* ...)`.
4. Для каждого уровня вызывает `HHClient.search(...)`.
5. Получает `items` из ответа HH (компактная форма для UI) и добавляет в `candidates_by_level`.
6. Возвращает:
   - счетчики найденного,
   - кандидатов по уровням,
   - полные запросы с exclusion.

### 5.3 Интеграция с HH API

Файл: `app/clients/hh_client.py`

Алгоритм:

1. Получает токен:
   - `ssp`: GET к внутреннему `HH_TOKEN_URL`.
2. Собирает параметры API (`text`, `area`, `experience`, `job_search_status`, `period`, и т.д.).
3. Делает `GET https://api.hh.ru/resumes`.
4. При `401` автоматически обновляет токен и ретраит.
5. Возвращает `found` и компактные элементы кандидатов для UI; также сохраняет их в SQLite (`hh_search_runs`).
6. Роут нормализует кандидатов до тонкой DTO-модели и возвращает JSON ответ.

### 5.4 Нормализация ответа для UI

Файл: `app/api/routes/workflow.py`

- Очищает/упрощает candidate структуру до стабильного набора полей (`id`, `title`, `area`, `salary`, `skills`, `tags`, и т.д.).
- Защищает от неожиданных типов (`skills`/`tags` приводятся к спискам).
- Возвращает совместимую со схемой `SearchResponse` структуру.

---

## 6) Userflow (как работает интерфейс)

Файл: `app/api/routes/ui.py` (встроенный HTML+JS)

1. Пользователь вставляет текст требований в textarea.
2. Кнопка "Запрос по умолчанию" тянет `GET /api/default_request`.
3. Кнопка "Получить булевый запрос":
   - вызывает `POST /api/generate_queries`;
   - показывает `llm_raw` и 3 карточки уровней.
4. Кнопка "Поиск":
   - вызывает `POST /api/search`;
   - показывает количество найденных по каждому уровню;
   - выбирает лучший уровень эвристикой (сначала уровень 3, затем 2, затем 1 по наличию кандидатов);
   - рендерит таблицу кандидатов.
5. Кнопка "Светофор":
   - вызывает `POST /api/svetofor` (внутри светофор-LLM вызывается параллельно для первых `svetofor_top_x` кандидатов);
   - применяет фильтры стажа/«прыгуна» и «максимум не в деле» к резюме кандидатов;
   - показывает таблицу светофора (color + match_percent) и позволяет открыть промпты/ответ агента.
6. Чекбокс "показать промпт":
   - загружает `system_prompt` и `user_prompt`;
   - позволяет отправить override в API.

Дополнительно UI:

- строит прямые ссылки в HH с параметрами;
- умеет копировать URL;
- показывает "расшифровку" параметров поиска.
- (для кнопки "Светофор") показывает ориентировочный тайминг этапов.
- (для `POST /api/svetofor`) верхняя панель задаёт: `svetofor_top_x`; `min_stay_months`/`allowed_short_jobs`/`jump_mode` (фильтрация “подряд/вообще прыгун”); `max_not_employed_months` (отсечение кандидатов с слишком давним последним `end`).

---

## 7) Ответственность файлов и функций

### `app/main.py`

- `create_app()` — точка сборки приложения: логирование + подключение роутера.

### `app/api/router.py`

- объединяет маршруты:
  - `ui.router` без префикса,
  - `workflow.router` с префиксом `/api`.

### `app/api/routes/workflow.py`

- `default_request()` — выдача дефолтного текста вакансии.
- `system_prompt()` / `user_prompt()` — выдача prompt-файлов.
- `generate_queries()` — оркестрация LLM генерации.
- `search()` — полный end-to-end сценарий LLM + HH + нормализация кандидатов.

### `app/api/routes/ui.py`

- `index()` — отдаёт отладочный интерфейс одним HTML-документом.

### `app/models/schemas.py`

- Pydantic контракты запросов/ответов (`GenerateQueries*`, `Search*`, `Candidate`).
- типизация уровней (`LevelName`) и источников токена (`TokenSource`).

### `app/services/prompts.py`

- `PromptService` — thin service для чтения prompt/request файлов.

### `app/services/query_generator.py`

- `_build_prompt()` — сборка system+user prompt.
- `generate()` — основной алгоритм генерации и нормализации 3 уровней; при проблемах отдаёт пустые строки (без mock-данных), а `llm_raw` помогает разобраться.

### `app/services/hh_search.py`

- `add_exclusion()` — добавляет глобальный NOT блок.
- `_is_managerial_position()` — детектор руководящей вакансии по маркерам.
- `_extract_title()` — ограничивает title до 120 символов.
- `_map_professional_roles()` — keyword mapping в HH `professional_role`.
- `_build_search_filters()` — единый набор фильтров для HH API.
- `search_counts_and_candidates()` — полный цикл поиска и сборки ответа по уровням.

### `app/services/job_stability.py`

- `candidate_passes_job_stability()` — фильтры “подряд прыгун / вообще прыгун” и “максимум не в деле” для кандидатов перед вызовом светофора.

### `app/core/log_store.py`

- `SqliteLogStore` (через интерфейс `LogStore`) — persistence компактных результатов HH поиска в sqlite (без JSON-файлов в `logs/`).

### `app/clients/llm_client.py`

- `call()` — HTTP вызов LLM endpoint.
- `extract_queries()` — resilient parser 3-х уровней из разных форм ответа.
- `_parse_json_from_text()` — regex + json.loads разбор текстового payload.
- `_extract_from_object()` — рекурсивный поиск уровней в nested JSON.

### `app/clients/hh_client.py`

- `get_token()` — получение токена из `ssp`.
- `_build_api_params()` — сборка параметров HH API.
- `_api_to_url_params()` — маппинг API-параметров к web-URL (для логики/диагностики).
- `search()` — запрос в HH resumes API, retry на 401, возврат компактных элементов для UI; запись результатов в sqlite.
- `get_resume_by_id()` — получение полного резюме по ID.

### `app/core/settings.py`

- `Settings` — конфигурация через env-переменные.
- `settings` — singleton объекта настроек.

### `app/core/logging.py`

- `setup_logging()` — базовая конфигурация logging.

### `app/utils/file_manager.py`

- `FileManager` — утилита для чтения prompt-шаблонов из `txt/` (запись логов в файловую систему в production лучше отключать).
- `read_txt()` и сервисные утилиты.

---

## 8) Алгоритмические решения и эвристики

- **3 уровня строгости запроса**: позволяет балансировать recall/precision.
- **Глобальный anti-manager NOT**: исключает lead/head/cto и аналоги в full-text.
- **Повторный anti-manager в `title`** для неруководящих вакансий: усиливает фильтрацию.
- **Keyword mapping → professional roles**: авто-выбор роли HH по словам вакансии.
- **Диагностика при сбоях LLM**: если LLM не вернула/не распарсила запросы, уровни отдаются пустыми, а `llm_raw` используется для разборов.
- **Retry на 401 для HH API**: улучшает устойчивость при истечении токена.
- **Нормализация кандидатов в API**: фронт получает стабильную форму данных.
- **Фильтрация “прыгун/не в деле”**: применяется перед вызовом светофор-LLM на основе `resume.experience`.
- **Асинхронный светофор**: для первых `svetofor_top_x` кандидатов выполняются параллельные операции (HH resume fetch + LLM вызов) через `asyncio.gather` и `Semaphore`.

### Как улучшать
- Настраивайте бизнес-логику: редактируйте `candidate_passes_job_stability()` или добавляйте новые проверки перед вызовом светофора.
- Подменяйте хранилище без рефакторинга: реализуйте интерфейс `LogStore` и заменяйте `SqliteLogStore`.
- Регулируйте нагрузку: меняйте `Semaphore` (в `workflow.py`) и `svetofor_top_x` в UI.
- Улучшайте парсинг LLM: корректируйте `LLMClient.extract_queries()` под актуальные форматы ответов.

---

## 9) Конфигурация окружения

Пример в `.env.example`:

- `LOG_LEVEL` — уровень логов.
- `LLM_URL`, `LLM_TOKEN_PARAM` — endpoint и токен-параметр LLM.
- `HH_TOKEN_URL` — внутренний endpoint токена.
- `AREA_ID` — регион поиска (дефолт 113).
- `PROFESSIONAL_ROLES` — роли по умолчанию (CSV).
- `LOG_DB_PATH` — путь к sqlite-файлу для хранения результатов HH (дефолт `hh_optimizer.sqlite`).

---

## 10) Логи и диагностика

- При HH поиске сохраняются:
  - компактные результаты поиска в sqlite (таблица `hh_search_runs`);
  - остальная диагностика — через `llm_raw` и поля debug в "Светофоре".
- Логи Python управляются через `LOG_LEVEL`.

---

## 11) Локальный запуск

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Открыть:

- UI: `http://127.0.0.1:8000/`
- OpenAPI: `http://127.0.0.1:8000/docs`

---

## 12) Deploy

- `Procfile`: `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`
- `render.yaml`: готовая конфигурация для Render (web service, build/start команды и env vars).

---

## 13) Краткий FAQ

- **Где менять правила генерации булевого запроса?**  
  В `txt/system_prompt.txt` и `txt/user_prompt.txt`, либо через override в UI/API.

- **Где менять фильтры HH по умолчанию?**  
  В `HHSearchService._build_search_filters()` и env (`AREA_ID`, `PROFESSIONAL_ROLES`).

- **Где смотреть проблемы интеграции?**  
  Логи приложения + данные в sqlite (`hh_search_runs` в первую очередь).

