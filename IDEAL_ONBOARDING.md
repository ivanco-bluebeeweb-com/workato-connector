# Workato Connector — идеальный первый запуск

Источник: `ONBOARDING_FIRST_LAUNCH_STANDARD.md`. Целевой пользователь: Ops/IT-
специалист среднего/крупного бизнеса на Workato (enterprise iPaaS).

## 1. Credential type
API Client Bearer token (создаётся с ролью и project scope — governance-first
подход Workato, отличается от простого API key других iPaaS).

## 2. Идеальный флоу
1. **Первое открытие** — `Empty` со ссылкой "Workspace admin > API clients > Create
   API client" + явное объяснение необходимости назначить роль и project scope ПРИ
   создании клиента в Workato (иначе токен окажется бесполезным при первом вызове).
2. **Форма** — api_token (password-type) с лейблом.
3. **После успеха** — список recipes (статус активен/пауза) + сколько jobs упало за
   период — сразу.
4. **Project/Folder navigation** — Workato организован по Projects/Folders — идеально:
   иерархический браузер вместо плоского списка recipes, т.к. enterprise-инстансы
   Workato легко содержат сотни recipes.
5. **Ошибка "insufficient project scope"** — если токен ограничен конкретным проектом,
   а запрошен другой — конкретное сообщение об этом ограничении governance-модели.

## 3. Разница с реализацией сейчас
См. `UI_COMPONENT_PLAN.md` §0.
