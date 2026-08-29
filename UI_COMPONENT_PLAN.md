# Workato Connector — UI component plan

Источники: `Docs/session-notes/UI_COMPONENT_VOCABULARY.md`, `UI_INTERFACE_STANDARD.md`,
`concepts/panels.md`. Основано на `POST_CONNECT_EXPERIENCE.md` этого приложения.

## 1. Компоненты

| Экран | Примитивы | Почему именно эти |
|---|---|---|
| Sidebar (left) | `ui.Column`(align="start") + `ui.Text`(workspace) + `ui.Divider` + navigation `ui.ListItem`(Recipes/Connections/Recipe Jobs) + `ui.Button`("App settings") | Без карточек по стандарту. |
| Recipe List (center, `center_overlay=True`) | `ui.Stats`(Running/Stopped/Jobs today) + `ui.DataTable`(name, running Toggle-колонка editable, last run status Badge; sortable) | Запуск/остановка рецепта прямо из таблицы через editable toggle-колонку. |
| Recipe Detail | Back-button + `ui.KeyValue`(trigger app/action apps count) + `ui.Graph`(nodes=recipe steps, edges=flow order) + `ui.Button`("Run Now") | `Graph` — визуализация trigger→action шагов рецепта Workato. |
| Recipe Job List | `ui.Select`(status_filter) + `ui.DataTable`(started_at, status Badge success/error/warning, duration; sortable) | Табличная история запусков (jobs) рецепта. |
| Job Detail | Back-button + `ui.KeyValue`(recipe/status/duration) + `ui.Code`(language="json", input/output per step, readonly) + `ui.Button`("Retry Job") | `Code`(json) для просмотра данных, прошедших через рецепт на конкретном шаге. |
| Connections List | `ui.DataTable`(name, app, status Badge connected/broken; sortable) + `ui.Button`("Reconnect") | Табличный обзор подключений рецептов к внешним сервисам. |
| Lookup Table Viewer | `ui.DataTable`(строки lookup table, колонки по схеме) | Workato Lookup Tables — простые табличные справочники. |
| App Settings | `ui.Accordion`([Connections+Disconnect, Workspace Select, Webhook Endpoint URL]) | Централизованные настройки по стандарту. |

## 2. User flow (валидно по panel lifecycle)

1. **SESSION INIT** → `__panel__workato_sidebar` рендерит workspace + разделы,
   `auto_action` открывает Recipe List с live-статусами.
2. Recipe List: editable toggle "running" → `on_cell_edit` вызывает `start_recipe`/
   `stop_recipe` напрямую (обратимо) → `refresh_panels`.
3. Клик на строку рецепта → Recipe Detail — `Graph` рендерит шаги, кнопка
   "Run Now" запускает разово.
4. Из Recipe Detail клик "Jobs" → Recipe Job List, отфильтрованный по рецепту.
5. Клик на job → Job Detail — `Code`(json) input/output, "Retry Job" при ошибке.
6. Connections List и Lookup Table Viewer — отдельные пункты сайдбара.
7. App Settings — только через кнопку в сайдбаре, единственное место с disconnect.

## 3. Экраны/карточки (артефакты для реализации)

- `panels.py`: `__panel__workato_sidebar` (left).
- `panels_recipes.py`: `__panel__recipe_list` (center, `center_overlay=True`,
  editable toggle), `__panel__recipe_detail` (center, параметризован `recipe_id`, Graph).
- `panels_jobs.py`: `__panel__job_list` (center, параметризован `recipe_id`),
  `__panel__job_detail` (center, параметризован `job_id`, Code json).
- `panels_connections.py`: `__panel__connections_list` (center).
- `panels_lookup_tables.py`: `__panel__lookup_table_viewer` (center, параметризован
  `table_id`).
- `panels_settings.py`: `__panel__app_settings` (center overlay, Accordion,
  единственное место с disconnect).
