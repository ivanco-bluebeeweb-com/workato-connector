# Workato Connector — Connector Discovery

**Дата:** 2026-08-20
**Методология:** `Docs/session-notes/CONNECTOR_DISCOVERY_STANDARD.md`
**Источник:** официальный Workato Developer API reference, docs.workato.com/workato-api/*
(прочитано систематически по каждому разделу навигации, не выборочно).

---

## 0. Архитектурный вердикт (сравнение с уже освоенными паттернами)

Workato REST API — **BYOK, открытый, без стороннего ревью** — тот же класс, что
Make.com/n8n/Power Automate, НЕ как Zapier (где нужен листинг в каталоге и внешнее
ревью, прежде чем появляется реальный API-доступ). Путь свободен для полноценного
коннектора с первого захода.

**Аутентификация:** API Clients (workspace-level, роль-скоуп, опционально
IP allowlist и project-scope) — `Authorization: Bearer <api_token>`. Legacy
full-access API key + email в заголовках/query всё ещё поддерживается, но Workato
прямо рекомендует API Clients; коннектор использует только текущий способ.

**Base URL — фиксированный список data center хостов** (ближе к модели Make.com
с dropdown зоны, чем к n8n со свободным URL):

| Data center | Base URL |
|---|---|
| US (Enterprise) | `https://www.workato.com/api/` |
| EU | `https://app.eu.workato.com/api/` |
| JP | `https://app.jp.workato.com/api/` |
| SG | `https://app.sg.workato.com/api/` |
| AU | `https://app.au.workato.com/api/` |
| IL | `https://app.il.workato.com/api/` |
| CN | `https://app.workatoapp.cn/api/` |
| KR | `https://app.kr.workato.com/api/` |
| UK | `https://app.uk.workato.com/api/` |
| Self-service (Free/Pro/Sandbox) | `https://app.trial.workato.com/api/` |

Нет единого "узнать зону автоматически" эндпоинта, задокументированного публично
(в отличие от Make.com, где `GET /users/me` пробуется по каждому известному zone-хосту)
— но тот же паттерн технически применим: пробовать `GET /api/users/me` по каждому
известному хосту с введённым токеном, пока один не примет его. Решено сделать так же,
чтобы не заставлять пользователя искать свой data center вручную (см. PREPARATION.md
раздел 4).

**Тест-эндпоинт для connect:** `GET /api/users/me` ("Get workspace details") —
дешёвый, без побочных эффектов, подтверждает и валидность токена, и корректность
data center за один вызов. Требует явной привилегии `Workspace details > Get details`
в роли API Client — если она не выдана, разумно ожидать 403 при подключении и явно
сообщить пользователю, что нужно включить эту привилегию для клиента.

---

## 1. Классификация возможностей API (Ingress / Egress / Both)

| Ресурс | Возможности | Класс |
|---|---|---|
| Recipes | list/get/create/update/copy/delete/start/stop/force_run/poll_now/reset_trigger/versions/health | Both (write операции над состоянием recipe = Egress в Workato; чтение = Ingress к нам) |
| Connections | list/create/update/delete/disconnect/pick_list | Both |
| Jobs | list per recipe / get one / repeat (retry) | Ingress (read) + Egress (repeat) |
| Folders & Projects | list/get/create/update/delete (folders and projects) | Both |
| Lookup tables | list tables/rows, add/update/delete row | Both |
| Environment properties | list by prefix, upsert | Both |
| Tags & tag assignments | CRUD tags, assign/unassign to recipes | Both |
| Environment management (secrets cache) | clear secrets management cache | Egress (action, no data returned) |
| Recipe Lifecycle Management (packages) | export manifest CRUD, export package, import package, get package status, download | Both (async, poll-based) |
| Workspace details | get details (`/users/me`) | Ingress (read-only, used also as connect self-test) |

---

## 2. Ярус 1 — ключевые функции (P0, ~14 функций)

Минимальный операционный набор, аналог "признать recipe как сценарий Make/workflow n8n":

1. `connect_workato` — data_center (dropdown) + api_token, probes `/users/me`
2. `disconnect_workato`
3. `get_workato_connection`
4. `list_workato_recipes` (filter by folder_id, running)
5. `get_workato_recipe`
6. `start_workato_recipe`
7. `stop_workato_recipe`
8. `create_workato_recipe`
9. `update_workato_recipe`
10. `delete_workato_recipe`
11. `list_workato_recipe_jobs`
12. `get_workato_job`
13. `list_workato_connections`
14. `list_workato_folders`

## 3. Ярус 2 — полное покрытие возможностей сервиса (P0+P1, добавляет ~24)

Замыкает весь официальный Developer API reference:

15. `copy_workato_recipe`
16. `force_run_workato_recipe`
17. `reset_workato_recipe_trigger`
18. `poll_now_workato_recipe`
19. `get_workato_recipe_health`
20. `list_workato_recipe_versions`
21. `get_workato_recipe_version`
22. `update_workato_recipe_version_comment`
23. `create_workato_connection`
24. `update_workato_connection`
25. `disconnect_workato_connection` (disconnects the *Workato-side* connection object — a
    connected app inside the user's Workato workspace, distinct from #2 which disconnects
    OUR connector from Workato)
26. `delete_workato_connection`
27. `get_workato_connection_picklist`
28. `create_workato_folder`
29. `update_workato_folder`
30. `delete_workato_folder`
31. `list_workato_projects`
32. `update_workato_project`
33. `delete_workato_project`
34. `list_workato_lookup_tables`
35. `list_workato_lookup_table_rows`
36. `add_workato_lookup_table_row`
37. `update_workato_lookup_table_row`
38. `delete_workato_lookup_table_row`
39. `list_workato_environment_properties`
40. `upsert_workato_environment_properties`
41. `repeat_workato_job` (retry a failed job)
42. `clear_workato_secrets_cache`

## 4. Ярус 3 — value-add функции (P2, наши собственные, добавляет ~8)

Функции, которых нет напрямую в Workato API как единого вызова, но которые решают
реальную боль объёмной/скоординированной работы с recipes — тот же принцип, что
`bulk_restart_cloudhub_applications`/`audit_cloudhub_environment` у MuleSoft-discovery
и `bulk_*`/`generate_*_audit` у n8n/Power Automate:

43. `bulk_start_workato_recipes` — start N recipes in one call, per-recipe success/failure report
44. `bulk_stop_workato_recipes` — same for stop
45. `audit_workato_workspace` — aggregate report across all recipes: how many running/stopped,
    which have failed jobs in the recent window, which haven't run recently (staleness),
    which folders/projects have no active recipes at all
46. `get_stale_workato_recipes` — recipes with `last_run_at` older than N days while still
    marked running (silently-dead automation signal)
47. `export_workato_recipe_package` — one-call wrapper: create manifest for a single
    recipe + export it + poll until done + return download_url (collapses the
    manifest → export → poll dance into one action)
48. `import_workato_package_and_wait` — wrapper: import + poll until completed/failed,
    single call instead of manual poll loop
49. `list_workato_tags` / `create_workato_tag` / `delete_workato_tag` / `tag_workato_recipe` /
    `untag_workato_recipe` (Tag assignments — technically part of the official API surface
    under "Environment management", grouped here since the reference page for tag CRUD
    itself 404'd during discovery and had to be inferred from environment-management.html's
    description: "create, retrieve, update, and delete tags within your workspace" — treated
    as Tier 2 in spirit but implemented defensively with graceful 404 handling if the exact
    path differs from assumption)

**Итого при "по полной, полное покрытие" (Ярус 1+2+3): ~53 функции.**

---

## 5. Открытые технические риски, помеченные явно (не молчаливые допущения)

- **Recipe create/update/copy/versions/health эндпоинты помечены самим Workato как
  "PRIVATE BETA"** в Quick Reference таблицы Recipes — доступны в проде, но только
  выбранным клиентам, которые явно включили beta. Коннектор реализует их (раз они
  документированы официально), но `PREPARATION.md` явно фиксирует: часть Ярус-1/2
  функций может вернуть 403/404 на аккаунтах без доступа к этой приватной бете —
  обрабатывается как "функция недоступна на этом плане/бете", не как generic-ошибка.
- **Endpoint access per API Client Role.** Почти каждый ресурс (folders, users/me,
  и вероятно остальные) требует явно включённой привилегии в роли API Client —
  это не "все или ничего": пользователь может дать коннектору только часть доступа.
  403 должен по умолчанию трактоваться как "у этого API-клиента нет привилегии на
  это конкретное действие", а не как "неверный токен" (то же разделение 401 vs 403,
  что уже принято в n8n_client.py/make_client.py).
- **Tag CRUD exact paths не подтверждены документацией** (страница вернула 404 при
  discovery) — реализация будет defensive: при 404 на предполагаемом пути вернуть
  понятную ошибку "эта функция пока недоступна для вашего workato instance/плана",
  не притворяться, что сработало.
- **Recipe Lifecycle Management — асинхронный по природе** (export/import возвращают
  `status: in_progress`, нужен последующий poll `GET /packages/:id`). Ярус 3
  функции (`export_workato_recipe_package`/`import_workato_package_and_wait`)
  инкапсулируют короткий поллинг с разумным таймаутом и явным сообщением, если
  операция не завершилась в отведённое время (не бесконечный цикл).
