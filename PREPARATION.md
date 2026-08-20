# Workato Connector — Preparation

**Статус:** Discovery + архитектурные решения завершены. Полное покрытие
выбрано явно пользователем ("напичкай по полной, полное покрытие") —
без дополнительного вопроса про объём, в отличие от Zapier/MuleSoft,
где объём ещё обсуждается.
**Владелец продукта:** vlad@bluebeeweb.com
**Дата подготовки:** 2026-08-20, v0.1

**Почему сейчас:** в портфеле Imperal уже есть коннекторы к Make.com, n8n
и Power Automate (тот же класс интеграций, тот же проверенный BYOK-паттерн:
пользователь подключает свой аккаунт своим ключом, Imperal ничего не
хостит и не проксирует). Workato — крупный enterprise-игрок в той же
категории no-code/iPaaS automation (recipes = workflows), пока не
покрытый ни одним коннектором Imperal. Полное покрытие выбрано сразу,
не поэтапно, по explicit-инструкции пользователя.

---

## 1. Паспорт приложения

**Название в Marketplace (display_name): «Workato»** — по той же логике
сокращения, что и Make.com/n8n/Power Automate (без слова Connector).
Внутренний app_id/папка: `workato-connector`. Проверено:
`search_marketplace` по «Workato» не нашёл ни одного существующего или
похожего приложения — дублей нет.

**Workato Connector** — коннектор к Workato Developer API (`/api/...`).
Даёт Webbee возможность от имени пользователя читать и управлять его
recipes (list/get/create/update/copy/delete/start/stop/reset
trigger/force run/poll now, версии), видеть их jobs (list/get/repeat),
управлять connections (list/create/update/disconnect/delete/picklist),
folders и projects, tags и их назначение на assets, lookup tables (полный
CRUD таблиц и строк), environment properties, recipe lifecycle management
(export manifests, packages, imports) и secrets cache. BYOK: пользователь
подключает свой собственный Workato workspace через свой собственный
API Client token; Imperal ничего не хостит и не проксирует помимо самого
запроса.

---

## 2. Ключевые факты о Workato API (Discovery, см. `CONNECTOR_DISCOVERY.md`)

- **Аутентификация:** API Clients (workspace-level, роль-скоуп) —
  `Authorization: Bearer <api_token>`. Legacy full-access key+email всё
  ещё поддерживается платформой, но не используется этим коннектором —
  Workato сама рекомендует API Clients как текущий способ.
- **Base URL — фиксированный список data center хостов** (US/EU/JP/SG/
  AU/IL/CN/KR/UK/trial) — ближе к модели Make.com (auto-discovery по
  known hosts), чем к n8n (свободный URL). Коннектор пробует `GET
  /api/users/me` по каждому известному хосту с введённым токеном, пока
  один не примет его — тот же паттерн, что `make_client.discover_zone`.
- **Нет одного универсального ресурса "workflow"** — recipes являются
  прямым аналогом сценариев Make/workflows n8n/cloud flows Power
  Automate. Recipe lifecycle management (manifests/packages) — это
  Workato-специфичный многоресурсный процесс промоушена между
  окружениями (DEV -> TEST -> PROD), не имеющий прямого аналога у
  других трёх коннекторов — покрыт отдельным блоком инструментов.
- **Rate limits различаются по ресурсу** (recipe create = 1 req/s,
  большинство остальных = 60 req/min) — обрабатывается как есть, платформа
  сама вернёт 429 при превышении; клиент не делает клиентский throttling
  (то же решение, что в make_client.py/n8n_client.py).
- **401 vs 403** обрабатываются по-разному: 401 = токен не распознан этим
  data center/хостом вообще (или отозван), 403 = токен распознан, но роль
  API Client не даёт доступа к конкретному эндпоинту (Workato всё
  разграничивает по ролям client'а очень детально, вплоть до конкретного
  эндпоинта) — материально иная и более чинимая причина, чем "неверный
  ключ".

---

## 3. Полный список покрываемых ресурсов (по разделам API)

| Раздел | Что покрыто |
|---|---|
| Workspace | получение деталей воркспейса (`GET /users/me`) — используется и для validate-on-connect, и как отдельный инструмент статуса |
| Recipes | list/get/create/update/copy/delete/start/stop/reset_trigger/force_run/poll_now, версии (list/get/update comment) |
| Jobs | list jobs от recipe, get job, repeat job |
| Connections | list/create/update/disconnect/delete, picklist values |
| Folders & Projects | list/get/create/update/delete folders, list/update/delete projects |
| Tags | list/create/update/delete tags, назначение/снятие тегов с recipe/connection (tag assignments) |
| Lookup tables | list/create tables, batch delete tables, list/get/lookup/add/update/delete rows |
| Environment properties | list by prefix, upsert |
| Recipe Lifecycle Management | view folder assets, list/create/update export manifests, create package, list packages, get package, create import, list imports |
| Secrets management | clear secrets cache |

Итого ~52 chat-функции — сопоставимо по масштабу с n8n Connector (48).

---

## 4. Архитектурные решения (по аналогии с Make.com/n8n/Power Automate)

1. **BYOK, `write_mode="both"`** — тот же довод, что у n8n/Make.com: без
   этого первый пользователь не увидел бы объяснения, что такое API
   Client token, и не мог бы проверить его перед сохранением.
2. **Data center — выбирается пользователем ИЛИ автоопределяется** —
   форма подключения просит только сам токен; клиент пробует все известные
   хосты (тот же паттерн, что `make_client.discover_zone`), запоминает
   победивший хост как второй secret (`workato_base_url`), чтобы не
   пробовать все хосты на каждый последующий вызов.
3. **`recipe_id`/`connection_id`/... — всегда integer в API Workato**,
   но params-модели принимают `str` и приводят к `int` перед вызовом
   (той же дисциплины придерживается n8n_client.py для execution_id).
4. **Recipe Lifecycle Management помечен как private-beta-aware**: сама
   документация Workato прямо предупреждает, что часть эндпоинтов recipes
   (`force_run`, `health`, версии) в private beta и доступны не всем
   аккаунтам — обрабатывается как "функция может быть недоступна на этом
   плане", не как общая ошибка (аналог обработки версии self-hosted n8n
   для `run_workflow`).
5. **Прайсинг** — по актуальной дефолтной 8-уровневой шкале
   (`APP_PREPARATION_STANDARD.md`): connect/disconnect/get_connection = 0;
   простой read = 8; тяжёлый read (jobs history, packages) = 16; простой
   write = 20; write с побочным эффектом (create/update/start/stop) = 30;
   destructive одиночный (delete) = 40; bulk write = 60; bulk destructive
   (batch_delete lookup tables) = 80.
6. **UI** — полностью по актуальному `UI_INTERFACE_STANDARD.md`: без
   `ui.Card` в сайдбаре, лейблы на каждом инпуте, форма/CTA
   `align="stretch"` по всей цепочке, никаких вводных
   заголовков/абзацев над формой (кнопка-помощь + модалка вместо этого),
   единая secondary-кнопка "App settings" последней внизу, базовая
   (не-overlay) центральная панель с каноничным текстом "Nothing to show
   here -- this app is managed entirely from the sidebar." и
   `center_overlay=True` для всех overlay-панелей помощи/настроек.

---

## 5. Что сознательно НЕ покрыто в этом заходе

- **On-prem agent groups / on-prem management** — управление собственной
  инфраструктурой Workato (агенты внутри сети клиента) — не операция
  автоматизации, а инфраструктурный DevOps-слой; не тот же класс, что
  "покажи/запусти мои recipes".
- **Enterprise Access Management (пользователи/роли воркспейса)** —
  аналогично решению по Power Automate (Access Management не в этом
  заходе) — это администрирование самого Workato-аккаунта, не мост
  между Imperal и содержимым recipes.
- **Custom connector SDK (разработка своих коннекторов внутри Workato)**
  — отдельный, самостоятельный продукт (аналог решения не делать
  "Imperal внутри Zapier" в этом заходе).

---

## 6. Проверки дублей

`search_marketplace(query="Workato")` — 0 результатов. Общие термины
"automation"/"workflow"/"recipe" не выявили конфликтов с существующими
приложениями (Make.com/n8n/Power Automate — другие display names,
не путаются).
