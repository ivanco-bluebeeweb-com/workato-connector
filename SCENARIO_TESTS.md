# Scenario Tests (PST) — Workato Connector

Метод: `Docs/session-notes/SCENARIO_TESTING_STANDARD.md`. Этот файл — обязательный
журнал прогонов Plausible Scenario Testing для этого приложения, дополняющий
(не заменяющий) статическую сверку manifest↔schemas↔handler↔client: PST реально
**вызывает** код через `imperal_sdk.testing.MockContext` и ловит то, что
статическая сверка структурно не видит (неверное число позиционных
аргументов при вызове, несуществующие kwargs SDK, некорректное
восстановление после ошибок, двойные вызовы деструктивных операций,
утечка секретов в текст ошибки).

---

## Прогон 2026-08-20

**Почему через MockContext, а не через живой Workato workspace.** У
пользователя нет подключённого BYOK Workato workspace (`get_workato_connection`
→ `connected: false`). Поднять настоящий Workato workspace для теста
невозможно в принципе — это SaaS-платформа без self-hosted/локального
режима. Следующий по строгости честный вариант — реальные вызовы
`handlers.py`/`workato_client.py` (тот же код, что исполняется в
продакшене) через официальный `imperal_sdk.testing.MockContext` +
`MockHTTP`, подставляя контролируемые ответы, соответствующие реальному
REST-контракту Workato (задокументированному и подтверждённому в
`CONNECTOR_DISCOVERY.md`/`PREPARATION.md` против docs.workato.com). Это
не имитация логики — код приложения исполняется по-настоящему, только
сетевой транспорт — тестовый двойник вместо чужого живого сервера.

**Персона.** У Workato Connector функционально одна роль: BYOK-владелец
собственного Workato workspace с API Client Bearer token ("Дмитрий",
integration engineer управляющий десятками recipes для нескольких
клиентов агентства). Разнообразие сценариев идёт от классов данных
workspace (пустой/типичный/пограничный/невалидный/экзотический) и от
широты покрытия ресурсов (recipes, connections, jobs, folders/projects,
tags, lookup tables, properties, recipe lifecycle packages), а не от
множества персон.

**Масштаб покрытия.** 61 chat-функция во всём приложении. Полное
покрытие тестами каждой функции по отдельности непропорционально —
следуем тому же подходу, что n8n Connector/Make.com Connector: репрезен-
тативная выборка из каждой ресурсной группы, применяя обязательные 5
веток на неё, плюс сквозные проверки (gating, idempotency, no-secret-leak),
которые по конструкции относятся ко ВСЕМ функциям сразу (общий `_creds`
helper, единая `_err` функция).

### Обязательные 5 веток — покрытие

1. **Happy path (типичные данные).** `connect_workato` успешный discovery
   + подключение; `list_workato_recipes` с реалистичными recipe (unicode
   имена, разные trigger apps); `list_workato_lookup_table_rows` с
   несколькими строками; `create_workato_export_manifest` →
   `export_workato_package` → `get_workato_package_download_url` (полный
   lifecycle).
2. **Error / permission (403 vs 401 vs 404).** `connect_workato` с
   неверным токеном (все хосты 401) → `WORKATO_ERROR`/`WORKATO_HTTP_401`;
   403 (валидный токен, недостаточная роль API client) →
   `WORKATO_HTTP_403` с отдельным, понятным текстом (не спутан с 401);
   `get_workato_recipe` на несуществующий id → `WORKATO_HTTP_404`.
3. **Blocked / gated (не подключено).** Представительный набор функций
   из КАЖДОЙ ресурсной группы (recipes/connections/jobs/folders/tags/
   lookup tables/properties/packages), вызванный без предварительного
   `connect_workato` — все должны падать с одним и тем же кодом ошибки
   через общий `_creds()` гейт, а не пытаться сходить в сеть с пустыми
   учётными данными.
4. **Idempotency / regression.** Повторный `disconnect_workato` (уже
   отключён) не падает и не бросает исключение; повторное удаление
   lookup table row с уже удалённым id корректно транслирует 404
   Workato, а не тихо "успевает".
5. **Security — no secret leak.** Текст ошибки при неверном токене НЕ
   содержит сам токен (`ProviderError.message` строится из статус-кода и
   общей фразы, никогда не эхом самого запроса/токена).

### Данные-классы, покрытые внутри веток выше

- Пустой workspace (0 recipes, 0 connections) — happy path list.
- Типичный workspace: unicode/emoji в названиях recipes (агентские
  клиенты часто именуют recipes на кириллице), несколько tag'ов,
  multi-step lookup table rows.
- Пограничный: recipe без `trigger_application` (черновик, ещё не
  настроен) — не должно падать на `None`.
- Невалидный: несуществующий connection_id / recipe_id → 404.
- Экзотический: data center discovery перебирает несколько хостов
  подряд, прежде чем найти правильный (типичная ситуация — пользователь
  не знает, что он на `app.eu.workato.com`, а не на `www.workato.com`).

### Результат прогона

`tests/test_pst_scenarios.py` — 29 тестов, все проходят
(`pytest -q` → `29 passed`). См. коммит для точного вывода.

**Известные ограничения этого прогона:** не покрыты тестами напрямую
(но используют тот же общий код путь, что покрытые функции, так что
регрессия того же класса поймана бы косвенно): `update_workato_*`,
`copy_workato_recipe`, `reconnect_workato_recipe_application`,
`get_workato_connection_picklist`, `repeat_workato_jobs`,
`batch_delete_workato_lookup_tables`, `clear_workato_secrets_cache`,
`view_workato_folder_assets`, `update_workato_export_manifest`,
`import_workato_package`. Все эти проходят через тот же `_creds()` /
`_err()` / `wc._api()`/`wc._check_status()` инфраструктурный код,
уже проверенный прямыми тестами на соседних функциях той же группы.
