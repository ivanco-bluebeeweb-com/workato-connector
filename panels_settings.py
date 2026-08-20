"""The single 'App settings' screen (center slot) -- connection management
(connect/disconnect) for Workato. Split out of panels.py per the same
convention as n8n Connector's/Make.com Connector's panels_settings.py.

Per UI_INTERFACE_STANDARD.md: the left sidebar no longer wraps the
connection status in a Card -- it's a plain stack line, and the *only*
way to disconnect is through this "App settings" screen, reached via the
one secondary "App settings" button that sits LAST at the bottom of the
sidebar.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
import handlers as h


def _connection_section(data_center: str, connected: bool) -> ui.UINode:
    if not connected:
        return ui.Stack(direction="v", gap=2, align="stretch", children=[
            ui.Text("Connection", variant="heading"),
            ui.Text(
                "Paste your Workato API Client token below -- your data "
                "center is discovered and verified automatically.",
                variant="caption",
            ),
            ui.Form(
                action="connect_workato",
                submit_label="Verify and connect",
                children=[
                    ui.Stack(direction="v", gap=1, align="stretch", children=[
                        ui.Text("API Client token", variant="caption"),
                        ui.Password(param_name="api_token",
                                    placeholder="Workato API Client Bearer token"),
                    ]),
                ],
            ),
        ])
    return ui.Stack(direction="v", gap=2, children=[
        ui.Text("Connection", variant="heading"),
        ui.Text(f"Connected -- data center: {data_center}", variant="caption"),
        ui.Button("Disconnect", variant="danger", size="sm",
                  on_click=ui.Call("disconnect_workato")),
    ])


@ext.panel("workato_settings", slot="center", title="App settings", icon="⚙️",
           center_overlay=True)
async def workato_settings_panel(ctx, **kwargs) -> object:
    api_token, data_center = await h._creds_or_empty(ctx)
    connected = bool(api_token and data_center)
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Text("Workato -- App settings", variant="title"),
        _connection_section(data_center, connected),
    ])
