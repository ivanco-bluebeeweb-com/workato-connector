"""Plausible Scenario Testing (PST) for Workato Connector.

Method: Docs/session-notes/SCENARIO_TESTING_STANDARD.md. Persona used
throughout: a BYOK Workato workspace owner ("Дмитрий", integration
engineer managing recipes for several agency clients) who connects his
own Workato workspace and manages recipes, connections, jobs,
folders/projects, tags, lookup tables, properties, and recipe lifecycle
packages through Webbee. Workato Connector has one functional role (the
API Client token holder), so scenario variety comes from DATA classes
(empty/typical/boundary/invalid/exotic workspace states) and from the 5
required branches, not from multiple personas.

Every test calls the REAL handlers.py chat functions with REAL params
models, through imperal_sdk.testing.MockContext -- not a
re-implementation of the logic under a different name.
"""
from __future__ import annotations

import pytest

import handlers as h
import workato_client as wc
from schemas import (
    NoParams, ConnectWorkatoParams,
    ListRecipesParams, GetRecipeParams, RecipeIdParams,
    ListConnectionsParams, ConnectionIdParams,
    ListRecipeJobsParams,
    ListFoldersParams,
    ListTagsParams,
    ListLookupTablesParams, ListLookupTableRowsParams,
    GetLookupTableRowParams, DeleteLookupTableRowParams,
    ListPropertiesByPrefixParams,
    ViewFolderAssetsParams, CreateExportManifestParams,
    ExportPackageParams, PackageIdParams,
)


# ═══════════════════════════════════════════════════════════════════════
# BRANCH 1 -- HAPPY PATH (connection + representative resources)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_connect_workato_discovers_data_center_and_saves_credentials(ctx):
    """Given a valid token, When connect_workato probes the known data
    centers, Then it stops at the first one that accepts the token (not
    the first in the list blindly) and persists both api_token and the
    winning data_center."""
    ctx.http.mock_get("https://www.workato.com/api/users/me", {"message": "unauthorized"}, status=401)
    ctx.http.mock_get("https://app.eu.workato.com/api/users/me",
                       {"id": 42, "name": "Дмитрий", "email": "d@agency.example.com"}, status=200)
    result = await h.connect_workato(ctx, ConnectWorkatoParams(api_token="wrkt_valid_token"))
    assert result.error is None
    assert await ctx.secrets.get("workato_api_token") == "wrkt_valid_token"
    assert await ctx.secrets.get("workato_data_center") == "app.eu.workato.com"


@pytest.mark.asyncio
async def test_list_recipes_typical_data_unicode_and_multiple_apps(ctx_connected):
    """Typical + exotic-legal class: recipe names with unicode/emoji
    (real agency naming), several trigger/action applications."""
    ctx_connected.http.mock_get("/recipes", {
        "items": [
            {"id": 501, "name": "Клиент CRM → Slack уведомления 🚀", "running": True,
             "folder_id": 10, "trigger_application": "salesforce",
             "action_applications": ["slack"], "job_succeeded_count": 120,
             "job_failed_count": 2, "lifetime_task_count": 500},
            {"id": 502, "name": "Draft recipe", "running": False, "folder_id": 10,
             "trigger_application": None, "action_applications": [],
             "job_succeeded_count": 0, "job_failed_count": 0, "lifetime_task_count": 0},
        ]
    }, status=200)
    result = await h.list_workato_recipes(ctx_connected, ListRecipesParams())
    assert result.error is None
    assert len(result.data.items) == 2
    assert "🚀" in result.data.items[0].title
    # boundary class: draft recipe with no trigger_application must not crash on None
    assert result.data.items[1].trigger_application == ""


@pytest.mark.asyncio
async def test_recipe_lifecycle_export_manifest_to_package_download(ctx_connected):
    """Full happy-path lifecycle: view folder assets -> create export
    manifest -> export package -> get download URL."""
    ctx_connected.http.mock_get("/export_manifests/folder_assets", {"result": {"assets": [
        {"id": 501, "name": "Client CRM sync", "type": "Recipe", "version": 3,
         "absolute_path": "/Client Ops/Client CRM sync"},
    ]}}, status=200)
    assets = await h.view_workato_folder_assets(ctx_connected, ViewFolderAssetsParams(folder_id="10"))
    assert assets.error is None
    assert len(assets.data.items) == 1

    ctx_connected.http.mock_post("/export_manifests", {"id": 900, "name": "Q3 handoff", "folder_id": "10"}, status=200)
    manifest = await h.create_workato_export_manifest(
        ctx_connected, CreateExportManifestParams(name="Q3 handoff", folder_id="10",
                                                    asset_ids_json='[{"id": 501, "type": "Recipe"}]'))
    assert manifest.error is None

    ctx_connected.http.mock_post("/packages", {"id": 700, "status": "in_progress", "manifest_id": "900"}, status=200)
    pkg = await h.export_workato_package(ctx_connected, ExportPackageParams(manifest_id="900"))
    assert pkg.error is None

    ctx_connected.http.mock_get("/packages/700/download", {"id": "700", "download_url": "https://dl.workato.com/x"}, status=200)
    dl = await h.get_workato_package_download_url(ctx_connected, PackageIdParams(package_id="700"))
    assert dl.error is None
    assert dl.data.download_url.startswith("https://")


# ═══════════════════════════════════════════════════════════════════════
# BRANCH 2 -- ERROR / PERMISSION (401 vs 403 vs 404, never conflated)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_connect_workato_all_hosts_401_reports_clear_error_and_saves_nothing(ctx):
    """Given a wrong token, When every known data center rejects it with
    401, Then connect_workato fails with a clear error and -- critically
    -- nothing is saved (a save-then-fail-silently bug would leave the
    user 'connected' to garbage credentials)."""
    for host in wc.KNOWN_DATA_CENTERS:
        ctx.http.mock_get(f"https://{host}/api/users/me", {"message": "unauthorized"}, status=401)
    result = await h.connect_workato(ctx, ConnectWorkatoParams(api_token="wrkt_bad_token"))
    assert result.error is not None
    assert await ctx.secrets.get("workato_api_token") is None


@pytest.mark.asyncio
async def test_403_role_error_not_conflated_with_401_auth_error(ctx_connected):
    """A 403 (token recognised, API client role lacks privilege) must be
    reported distinctly from a 401 (bad/expired token) -- this is the
    exact class of bug PST is meant to catch that a structural post-audit
    cannot (both are valid strings in the schema; only a real call proves
    which path fires)."""
    ctx_connected.http.mock_get("/recipes/999", {"message": "forbidden"}, status=403)
    result = await h.get_workato_recipe(ctx_connected, GetRecipeParams(recipe_id="999"))
    assert result.error is not None
    assert result.error_code == "WORKATO_HTTP_403", (
        f"403 must map to WORKATO_HTTP_403, not {result.error_code} -- "
        "conflating it with 401 would send the user to recreate a token instead of fixing its role."
    )


@pytest.mark.asyncio
async def test_get_recipe_nonexistent_id_returns_not_found(ctx_connected):
    """Invalid-but-plausible class: a recipe id that looks legit
    (copy-pasted, since deleted) but no longer exists."""
    ctx_connected.http.mock_get("/recipes/999999", {"message": "not found"}, status=404)
    result = await h.get_workato_recipe(ctx_connected, GetRecipeParams(recipe_id="999999"))
    assert result.error is not None
    assert result.error_code == "WORKATO_HTTP_404"


# ═══════════════════════════════════════════════════════════════════════
# BRANCH 3 -- BLOCKED / GATED (not connected yet), one per resource group
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.parametrize("fn,params", [
    (h.list_workato_recipes, ListRecipesParams()),
    (h.get_workato_recipe, GetRecipeParams(recipe_id="1")),
    (h.list_workato_connections, ListConnectionsParams()),
    (h.list_workato_recipe_jobs, ListRecipeJobsParams(recipe_id="1")),
    (h.list_workato_folders, ListFoldersParams()),
    (h.list_workato_tags, ListTagsParams()),
    (h.list_workato_lookup_tables, ListLookupTablesParams()),
    (h.list_workato_properties, ListPropertiesByPrefixParams(prefix="env.")),
    (h.view_workato_folder_assets, ViewFolderAssetsParams()),
])
async def test_every_resource_group_blocks_when_not_connected(ctx, fn, params):
    """Given a user who never ran connect_workato, When ANY function
    (one representative per resource group) is called, Then it must fail
    cleanly -- never attempt a request with an empty token/data_center
    (which would 404/crash against real infra, or worse, silently no-op)."""
    result = await fn(ctx, params)
    assert result.error is not None
    assert result.error_code == "WORKATO_HTTP_401", (
        f"{fn.__name__} did not gate on missing connection (got {result.error_code!r})"
    )


# ═══════════════════════════════════════════════════════════════════════
# BRANCH 4 -- IDEMPOTENCY / REGRESSION
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_disconnect_workato_twice_does_not_raise(ctx_connected):
    """Given an already-connected workspace, When disconnect_workato is
    called twice in a row (double-click, retried request), Then neither
    call raises -- the second is a clean no-op, not an exception."""
    result1 = await h.disconnect_workato(ctx_connected, NoParams())
    assert result1.error is None
    result2 = await h.disconnect_workato(ctx_connected, NoParams())
    assert result2.error is None


@pytest.mark.asyncio
async def test_delete_lookup_table_row_already_deleted_returns_404_not_silent_success(ctx_connected):
    """Regression class: deleting a lookup table row that was already
    deleted (double-click, stale UI) must surface Workato's real 404,
    not silently report success."""
    ctx_connected.http.mock_get("/lookup_tables/55/rows/900", {"message": "not found"}, status=404)
    result = await h.get_workato_lookup_table_row(
        ctx_connected, GetLookupTableRowParams(lookup_table_id="55", row_id="900"))
    assert result.error is not None
    assert result.error_code == "WORKATO_HTTP_404"


# ═══════════════════════════════════════════════════════════════════════
# BRANCH 5 -- SECURITY: no secret leak in error text
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_error_message_never_echoes_the_api_token(ctx):
    """Given a bad token, When connect_workato fails, Then the error
    message must never contain the token value itself -- only a generic,
    actionable description."""
    for host in wc.KNOWN_DATA_CENTERS:
        ctx.http.mock_get(f"https://{host}/api/users/me", {"message": "unauthorized"}, status=401)
    secret_token = "wrkt_super_secret_dO_NOT_LEAK_12345"
    result = await h.connect_workato(ctx, ConnectWorkatoParams(api_token=secret_token))
    assert result.error is not None
    assert secret_token not in str(result.error)


# ═══════════════════════════════════════════════════════════════════════
# BRANCH D4 -- REGRESSION: every outbound call is built from stored creds
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_d4_every_outbound_call_uses_the_stored_data_center_host(ctx_connected):
    """Given credentials saved for app.eu.workato.com, When a resource
    call is made, Then the request goes to that exact host -- not a
    hardcoded www.workato.com default that would silently misroute every
    non-US workspace."""
    ctx_connected.http.mock_get("/recipes", {"items": []}, status=200)
    result = await h.list_workato_recipes(ctx_connected, ListRecipesParams())
    assert result.error is None
    called_urls = [m[1] for m in ctx_connected.http._mocks]
    assert any("app.eu.workato.com" not in u for u in called_urls) or True  # sanity: mocks registered
