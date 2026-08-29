"""Panel UI -- connection (Срез 1) + recipes list (Срез 2).

SKETCH, following n8n Connector's/Make.com Connector's current no-card
sidebar shape:
  ui.Stack (v, gap=4, align=stretch)
    ui.Header
    [not connected] _connect_section() -- plain content, ui.Form(connect_workato)
    [connected]     _connected_section() -- plain text, then recipes list
    ui.Divider()
    _settings_button() -- ALWAYS the last element, secondary style
  -- separate center_overlay dialogs --
  @ext.panel("workato_connect_help", slot="center", center_overlay=True)
  @ext.panel("workato_settings", slot="center", center_overlay=True) -- panels_settings.py

WHY ONLY ONE FIELD (api_token), NOT ALSO A data_center DROPDOWN.

Workato has a small FIXED set of data-center hosts (same shape as Make.com's
zone list), so this connector follows Make.com Connector's pattern, not
n8n Connector's (which must ask for base_url up front since n8n has no
finite host list). connect_workato discovers the data center itself by
probing the known hosts with the token -- the user only ever pastes the
one thing they hold.

SIDEBAR CONTENT -- NO CARDS ANYWHERE, per UI_INTERFACE_STANDARD.md.

Every section is a plain ui.Stack, content stacked vertically and
left-aligned, sections separated by ui.Divider() -- no Card
border/background/shadow anywhere in this slot. Disconnect lives in the
"App settings" screen (panels_settings.py), not inline in the sidebar.
The one secondary "App settings" button is always the LAST element at
the bottom of the sidebar. No instructional text here duplicates what's
in workato_connect_help's modal.
"""
from __future__ import annotations

from imperal_sdk import ui

import workato_client as wc
from app import ext
import handlers as h


def _settings_button() -> ui.UINode:
    """The one required secondary entry point into the settings screen --
    always the last element at the bottom of the sidebar."""
    return ui.Button(
        "App settings", variant="secondary", size="sm", full_width=True,
        icon="settings", on_click=ui.Call("__panel__workato_settings"),
    )


def _connected_section(data_center: str) -> ui.UINode:
    """Plain content, no Card wrapper -- disconnect lives in App settings now."""
    return ui.Stack(direction="v", gap=1, align="start", children=[
        ui.Text("Workato", variant="body"),
        ui.Text(f"Data center: {data_center}", variant="caption"),
    ])


def _recipe_row(r) -> ui.UINode:
    """One recipe row -- plain content, no Card wrapper, no padding/border.
    A Divider() between rows (added by the caller) is the ONLY separator."""
    status = "Running" if r.running else "Stopped"
    subtitle = f"{status}" + (f" · {r.trigger_application}" if r.trigger_application else "")
    return ui.Stack(direction="v", gap=1, children=[
        ui.Text(r.title, variant="body"),
        ui.Text(subtitle, variant="caption"),
    ])


def _recipes_section(recipes: list) -> ui.UINode:
    if not recipes:
        return ui.Text("No recipes yet.", variant="caption")
    children: list[ui.UINode] = []
    for i, r in enumerate(recipes):
        if i > 0:
            children.append(ui.Divider())
        children.append(_recipe_row(r))
    return ui.Stack(direction="v", gap=2, children=children)


def _connect_section() -> ui.UINode:
    """Plain content, no Card wrapper -- shown only while not connected.
    Stretched full-width per UI_INTERFACE_STANDARD.md. No intro heading/
    description text here -- that instruction lives ONLY in
    workato_connect_help's modal (button below opens it)."""
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Button("How do I get an API Client token?", variant="ghost", size="sm",
                  icon="HelpCircle",
                  on_click=ui.Call("__panel__workato_connect_help")),
        ui.Form(
            action="connect_workato",
            submit_label="Verify and connect",
            children=[
                ui.Stack(direction="v", gap=1, align="stretch", children=[
                    ui.Text("API Client token", variant="caption"),
                    ui.Password(param_name="api_token",
                                 placeholder="Paste your Workato API Client Bearer token"),
                ]),
            ],
        ),
    ])


@ext.panel("workato_connect", slot="left", title="Workato", icon="🔗",
           default_width=320, min_width=260, max_width=420)
async def workato_connect_panel(ctx, **kwargs) -> object:
    api_token, data_center = await h._creds_or_empty(ctx)
    connected = bool(api_token and data_center)

    header = ui.Header(text="Workato", level=2,
                        subtitle="Manage your Workato recipes from Imperal")

    if not connected:
        return ui.Stack(direction="v", gap=4, align="stretch", children=[
            header,
            _connect_section(),
            ui.Divider(),
            _settings_button(),
        ])

    recipes: list = []
    try:
        data = await wc.list_recipes(ctx, data_center, api_token, per_page=50)
        items = data.get("items", data) if isinstance(data, dict) else data
        recipes = [h._recipe_entity(r) for r in (items or [])]
    except wc.ProviderError:
        recipes = []

    return ui.Stack(direction="v", gap=4, align="stretch", children=[
        header,
        _connected_section(data_center),
        ui.Divider(),
        ui.Text("Recipes", variant="subtitle"),
        _recipes_section(recipes),
        ui.Divider(),
        ui.Button("View recipe overview", variant="primary", size="sm", full_width=True,
                  icon="LayoutDashboard", on_click=ui.Call("__panel__workato_center")),
        ui.Divider(),
        _settings_button(),
    ])


@ext.panel("workato_connect_help", slot="center",
           title="How to get a Workato API Client token", center_overlay=True)
async def workato_connect_help(ctx, **kwargs) -> object:
    content = ui.Stack(direction="v", gap=3, children=[
        ui.Text("1. Open your Workato workspace and go to Workspace admin."),
        ui.Text("2. Open API clients, then Create API client."),
        ui.Text("3. Assign it a client role (which endpoints it may call) and a project scope."),
        ui.Text("4. Copy the token -- Workato only shows it once."),
        ui.Divider(),
        ui.Alert(
            title="Access is scoped by role",
            message=(
                "A Workato API Client can only call the endpoints its "
                "assigned role enables. If a function here fails with a "
                "permissions error, revisit Workspace admin -> API clients "
                "-> Client roles and enable the endpoint it needs."
            ),
            type="warning",
        ),
        ui.Divider(),
        ui.Link(
            label="Open Workato's official API documentation",
            href="https://docs.workato.com/workato-api.html",
        ),
    ])
    return ui.Dialog(
        title="How to get a Workato API Client token",
        content=content,
        confirm_label="",
        cancel_label="Close",
    )


@ext.panel("workato_center", slot="center", title="Workato", icon="🔗", center_overlay=True)
async def workato_center_panel(ctx, **kwargs) -> object:
    """Base center panel -- per UI_INTERFACE_STANDARD.md. This app has no
    list/detail content of its own to show in the center by default
    (everything lives in the sidebar). MUST carry center_overlay=True:
    per docs.imperal.io/en/concepts/panels, a plain slot="center" panel
    is registered but the Panel app never fetches it at session-init
    without that flag. Text is the shared canonical wording -- must stay
    identical across every app in this situation, not app-specific."""
    from schemas import ListRecipesParams
    result = await h.list_workato_recipes(ctx, ListRecipesParams())
    body: list[ui.UINode] = [ui.Text("Recipe overview", variant="subtitle")]
    if result.success and result.data and result.data.items:
        items = result.data.items
        running = sum(1 for r in items if r.running)
        body.append(ui.Stats(children=[
            ui.Stat(label="Total", value=str(len(items))),
            ui.Stat(label="Running", value=str(running)),
            ui.Stat(label="Stopped", value=str(len(items) - running)),
        ]))
        for r in items[:15]:
            color = "green" if r.running else "gray"
            body.append(ui.Stack(direction="h", gap=2, align="center", children=[
                ui.Badge(label="RUNNING" if r.running else "STOPPED", color=color),
                ui.Text(r.title or r.name, variant="body"),
                ui.Text(r.trigger_application, variant="caption"),
            ]))
    else:
        body.append(ui.Text("No recipes found, or not yet connected.", variant="caption"))

    return ui.Stack(direction="v", gap=3, align="stretch", children=body)
