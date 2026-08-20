# Pricing History — Workato Connector

Обязательный журнал: каждое выставление или изменение цен на функции этого
приложения фиксируется здесь — что изменилось, почему, и на основании
чего. Не переписывать прошлые записи — только дописывать новые сверху.

---

## 2026-08-20 — процесс-инцидент: первые 3 попытки прайсинга не сохранились

**Что произошло:** приложение было отправлено на `submit_for_review` уже
после трёх попыток выставить цену — но ни одна из трёх не сохранила
`pricing_config` на платформе. Влад лично подтвердил в панели, что цена
не отображается, дважды подряд после разных попыток. Разбор причины:

1. Первая попытка — `developer.update_pricing(pricing_config={...плоская
   карта tool→price...}, pricing_model="per_action")` **без**
   `revenue_split_dev`. Вернула `success` (эхо манифеста в ответе), но
   цена не сохранилась.
2. Вторая попытка — `developer.save_pricing` с тем же вложенным форматом.
   Тоже `success`, тоже не сохранилось. `save_pricing` — известный баг
   платформы (см. канонический `PRICING_POLICY.md` §3): возвращает
   success, но не гарантированно сохраняет `pricing_config`.
3. Третья попытка — явный `suspend_app` → `save_pricing` с ПЛОСКИМИ
   top-level kwargs (каждая функция отдельным параметром вызова) вместо
   `pricing_config`. Снова success, снова не сохранилось.

**Корневая причина, найденная при сверке с рабочим прецедентом
(MuleSoft Connector, тот же день):** `pricing_config` должен быть
**вложенным объектом** `{"tool_prices": {...}, "free_tools": [...],
"monthly_price": 0}`, переданным инструменту `update_pricing` (не
`save_pricing`), и **`revenue_split_dev` обязателен как явный отдельный
параметр вызова** (95 — partner-тир этого разработчика), а не только
внутри `pricing_config`. Все три первых попытки нарушали хотя бы одно из
двух условий. Задокументировано в каноническом `PRICING_POLICY.md` §3 —
именно тот пункт, который в этот раз не был соблюдён с первого раза.

**Исправление:** четвёртый вызов — `developer.update_pricing(
app_id="workato-connector", pricing_model="per_action",
pricing_config={"tool_prices": {...все 61 функции...}, "free_tools":
["connect_workato", "disconnect_workato"], "monthly_price": 0},
revenue_split_dev=95)` — по точному образцу MuleSoft Connector.

**Цены — фиксированная платформенная шкала {0, 8, 16, 20, 40, 60}, без
исключений и без x1.8-маркапа (Workato не Google-backed API):**

| Цена | Функции |
|---|---|
| 0 | `connect_workato`, `disconnect_workato` (настройка/удаление доступа) |
| 8 | Все `list_*`/`get_*`/`view_*` — простое чтение состояния (recipes, connections, jobs, folders, projects, tags, lookup tables, rows, properties, export manifests, packages) |
| 16 | Стандартные одиночные write/CRUD-действия: `create_*`, `update_*`, `delete_*`, `copy_*`, `start_*`, `stop_*`, `reset_*`, `add_*`, `remove_*`, `upsert_*`, `clear_*`, `disconnect_workato_connection`, `reconnect_workato_recipe_application` |
| 20 | `force_run_workato_recipe`, `poll_now_workato_recipe`, `repeat_workato_jobs` — реально запускают работу в проде пользователя прямо сейчас |
| 40 | `export_workato_package`, `import_workato_package` — тяжёлая пакетная операция, снимок/восстановление целого набора активов |
| 60 | `batch_delete_workato_lookup_tables` — деструктивная batch-операция сразу по многим сущностям |

`pricing_model = "per_action"`, `monthly_price = 0`, `revenue_split_dev = 95`
(partner-тир).

**Примечание по проверке:** ни один read-инструмент (`get_app_details`,
`apps_by_developer`) не подтверждает программно, что `tool_prices` реально
сохранились на платформе (известное ограничение, задача #2113) — они лишь
эхом отражают отправленный запрос. Финальное визуальное подтверждение
остаётся за человеком: Developer → My Apps → Workato → Pricing. Отдельно
задокументирован как баг-репорт таск #2176 (создан до обнаружения
корневой причины revenue_split_dev — актуализировать после визуального
подтверждения от Влада).
