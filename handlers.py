"""Chat functions for Workato Connector: connection, recipes, connections,
jobs, folders/projects, tags, lookup tables, environment properties,
recipe lifecycle management. Built on workato_client.py / schemas.py."""
from __future__ import annotations

from imperal_sdk import ActionResult

import workato_client as wc
from app import ext, chat
from schemas import (
    NoParams, ConnectWorkatoParams, ProviderConnection, DeleteResult,
    ListRecipesParams, WorkatoRecipe, WorkatoRecipeList,
    GetRecipeParams, CreateRecipeParams, UpdateRecipeParams,
    CopyRecipeParams, RecipeIdParams, RecipeActionResult,
    ReconnectRecipeParams, ListRecipeVersionsParams, WorkatoRecipeVersion,
    WorkatoRecipeVersionList, GetRecipeVersionParams, RecipeHealthReport,
    ListConnectionsParams, WorkatoConnection, WorkatoConnectionList,
    CreateConnectionParams, UpdateConnectionParams, ConnectionIdParams,
    ConnectionActionResult, GetConnectionPicklistParams, PicklistValue,
    PicklistValueList,
    ListRecipeJobsParams, WorkatoJob, WorkatoJobList, GetJobParams,
    RepeatJobsParams, RepeatJobsResult,
    ListFoldersParams, WorkatoFolder, WorkatoFolderList, FolderIdParams,
    CreateFolderParams, UpdateFolderParams,
    ListProjectsParams, WorkatoProject, WorkatoProjectList,
    UpdateProjectParams, ProjectIdParams,
    ListTagsParams, WorkatoTag, WorkatoTagList, CreateTagParams,
    UpdateTagParams, TagIdParams, TagAssignmentParams, TagAssignmentResult,
    ListLookupTablesParams, WorkatoLookupTable, WorkatoLookupTableList,
    CreateLookupTableParams, BatchDeleteLookupTablesParams,
    BatchDeleteResult, ListLookupTableRowsParams, WorkatoLookupTableRow,
    WorkatoLookupTableRowList, LookupRowParams, GetLookupTableRowParams,
    AddLookupTableRowParams, UpdateLookupTableRowParams,
    DeleteLookupTableRowParams,
    ListPropertiesByPrefixParams, WorkatoProperty, WorkatoPropertyList,
    UpsertPropertiesParams, UpsertPropertiesResult, ClearSecretsCacheResult,
    ViewFolderAssetsParams, WorkatoAsset, WorkatoAssetList,
    CreateExportManifestParams, UpdateExportManifestParams,
    ManifestIdParams, WorkatoManifest, ExportPackageParams, WorkatoPackage,
    ImportPackageParams, PackageIdParams, PackageDownloadUrl,
)

import json

def _recipe_entity(r: dict) -> WorkatoRecipe:
    rid = str(r.get("id") or "")
    return WorkatoRecipe(
        id=rid,
        title=r.get("name") or rid,
        name=str(r.get("name") or ""),
        running=bool(r.get("running")),
        folder_id=str(r.get("folder_id") or ""),
        project_id=str(r.get("project_id") or ""),
        trigger_application=str(r.get("trigger_application") or ""),
        action_applications=list(r.get("action_applications") or []),
        job_succeeded_count=int(r.get("job_succeeded_count") or 0),
        job_failed_count=int(r.get("job_failed_count") or 0),
        lifetime_task_count=int(r.get("lifetime_task_count") or 0),
        last_run_at=str(r.get("last_run_at") or ""),
        webhook_url=str(r.get("webhook_url") or ""),
    )


def _connection_entity(c: dict) -> WorkatoConnection:
    cid = str(c.get("id") or "")
    return WorkatoConnection(
        id=cid,
        title=c.get("name") or cid,
        name=str(c.get("name") or ""),
        provider=str(c.get("provider") or ""),
        folder_id=str(c.get("folder_id") or ""),
        authorized=bool(c.get("authorized")),
        external_id=str(c.get("external_id") or ""),
    )


def _job_entity(j: dict) -> WorkatoJob:
    jid = str(j.get("id") or "")
    return WorkatoJob(
        id=jid,
        title=j.get("title") or jid,
        job_id=jid,
        recipe_id=str(j.get("recipe_id") or ""),
        status=str(j.get("status") or ""),
        started_at=str(j.get("started_at") or ""),
        completed_at=str(j.get("completed_at") or ""),
        is_error=bool(j.get("is_error")),
    )


def _folder_entity(f: dict) -> WorkatoFolder:
    fid = str(f.get("id") or "")
    return WorkatoFolder(
        id=fid,
        title=f.get("name") or fid,
        name=str(f.get("name") or ""),
        parent_id=str(f.get("parent_id") or ""),
        is_project=bool(f.get("is_project")),
        project_id=str(f.get("project_id") or ""),
    )


def _project_entity(p: dict) -> WorkatoProject:
    pid = str(p.get("id") or "")
    return WorkatoProject(
        id=pid,
        title=p.get("name") or pid,
        name=str(p.get("name") or ""),
        folder_id=str(p.get("folder_id") or ""),
    )


def _tag_entity(t: dict) -> WorkatoTag:
    tid = str(t.get("id") or "")
    return WorkatoTag(id=tid, title=t.get("name") or tid, name=str(t.get("name") or ""))


def _lookup_table_entity(lt: dict) -> WorkatoLookupTable:
    ltid = str(lt.get("id") or "")
    return WorkatoLookupTable(
        id=ltid,
        title=lt.get("name") or ltid,
        name=str(lt.get("name") or ""),
        project_id=str(lt.get("project_id") or ""),
        created_at=str(lt.get("created_at") or ""),
    )


def _property_entity(name: str, value: str) -> WorkatoProperty:
    return WorkatoProperty(id=name, title=name, name=name, value=value)


# ──────────────────────────────────────────────────────────────────────────
# Connection / account management
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "connect_workato",
    "Connect your Workato workspace by saving your own API Client Bearer "
    "token, after discovering which data center your workspace lives on "
    "and checking the token actually works there. Create the token in "
    "your workspace: Workspace admin -> API clients -> Create API client, "
    "assign it a role and project scope, then copy its token. No need to "
    "know your own data center -- it's discovered automatically.",
    action_type="write",
    chain_callable=True,
    data_model=ProviderConnection,
    event="workato-connector.connect_workato",
    effects=["workato.provider.connected"],
)
async def connect_workato(ctx, params: ConnectWorkatoParams) -> ActionResult:
    """Discover the data center for this token, verify it, then persist
    both as secrets so every later call reuses them."""
    api_token = params.api_token.strip()
    if not api_token:
        return ActionResult.error(
            "Please provide your Workato API Client Bearer token -- create "
            "one in your workspace: Workspace admin -> API clients -> "
            "Create API client.",
            code="WORKATO_MISSING_API_TOKEN",
        )
    try:
        data_center = await wc.discover_data_center(ctx, api_token)
    except wc.ProviderError as exc:
        return _err(exc)

    await ctx.secrets.set("workato_api_token", api_token)
    await ctx.secrets.set("workato_data_center", data_center)
    return ActionResult.success(
        ProviderConnection(connected=True, data_center=data_center,
                           title="Workato", detail=f"Connected to {data_center}"),
        summary=f"Connected to your Workato workspace on {data_center}.",
        refresh_panels=["workato_connect", "workato_settings"],
    )


@chat.function(
    "get_workato_connection",
    "Check whether Workato is currently connected (does not reveal the saved token).",
    action_type="read",
    chain_callable=True,
    data_model=ProviderConnection,
    event="workato-connector.get_workato_connection",
)
async def get_workato_connection(ctx, params: NoParams) -> ActionResult:
    """Chat function: get workato connection."""
    api_token = await ctx.secrets.get("workato_api_token")
    data_center = await ctx.secrets.get("workato_data_center")
    if not api_token or not data_center:
        return ActionResult.success(
            ProviderConnection(connected=False, title="Workato"),
            summary="Workato is not connected yet.",
        )
    return ActionResult.success(
        ProviderConnection(connected=True, data_center=data_center, title="Workato",
                           detail=f"Connected to {data_center}"),
        summary=f"Workato is connected on {data_center}.",
    )


@chat.function(
    "disconnect_workato",
    "Disconnect Workato: deletes the saved API Client token and data center. "
    "Existing recipes, connections and jobs in your own Workato workspace are "
    "not affected -- only Imperal's saved credential is removed.",
    action_type="write",
    chain_callable=True,
    data_model=DeleteResult,
    event="workato-connector.disconnect_workato",
    effects=["workato.provider.disconnected"],
)
async def disconnect_workato(ctx, params: NoParams) -> ActionResult:
    """Chat function: disconnect workato."""
    await ctx.secrets.delete("workato_api_token")
    await ctx.secrets.delete("workato_data_center")
    return ActionResult.success(
        DeleteResult(id="workato", title="Workato", deleted=True),
        summary="Disconnected Workato. Your workspace itself is unaffected.",
        refresh_panels=["workato_connect", "workato_settings"],
    )


async def _creds(ctx):
    """Fetch the saved (api_token, data_center) pair or raise a clear error."""
    api_token = await ctx.secrets.get("workato_api_token")
    data_center = await ctx.secrets.get("workato_data_center")
    if not api_token or not data_center:
        raise wc.ProviderError(
            "Workato is not connected yet. Use connect_workato first.", 401
        )
    return api_token, data_center


async def _creds_or_empty(ctx):
    """Non-throwing variant for panel rendering -- returns ("", "") when not
    connected instead of raising, so a panel can render its logged-out state."""
    api_token = await ctx.secrets.get("workato_api_token")
    data_center = await ctx.secrets.get("workato_data_center")
    return api_token or "", data_center or ""


def _err(exc: wc.ProviderError) -> ActionResult:
    return ActionResult.error(exc.message, code=f"WORKATO_HTTP_{exc.status}" if exc.status else "WORKATO_ERROR")


def _recipe_entity(r: dict) -> WorkatoRecipe:
    return WorkatoRecipe(
        id=str(r.get("id", "")), title=r.get("name", ""), name=r.get("name", ""),
        running=bool(r.get("running", False)),
        folder_id=str(r.get("folder_id", "") or ""),
        project_id=str(r.get("project_id", "") or ""),
        trigger_application=r.get("trigger_application", "") or "",
        action_applications=r.get("action_applications", []) or [],
        job_succeeded_count=r.get("job_succeeded_count", 0) or 0,
        job_failed_count=r.get("job_failed_count", 0) or 0,
        lifetime_task_count=r.get("lifetime_task_count", 0) or 0,
        last_run_at=r.get("last_run_at", "") or "",
        webhook_url=r.get("webhook_url", "") or "",
    )


# ──────────────────────────────────────────────────────────────────────────
# Recipes
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_workato_recipes",
    "List recipes (Workato's term for workflows) in the connected workspace -- "
    "name, running state, folder/project, trigger app, and lifetime job counts.",
    action_type="read", chain_callable=True, data_model=WorkatoRecipeList,
    event="workato-connector.list_workato_recipes",
)
async def list_workato_recipes(ctx, params: ListRecipesParams) -> ActionResult:
    """Chat function: list workato recipes."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.list_recipes(ctx, dc, tok, params.folder_id, params.project_id,
                                      params.running, params.page, params.per_page)
    except wc.ProviderError as exc:
        return _err(exc)
    items = data.get("items", data) if isinstance(data, dict) else data
    recipes = [_recipe_entity(r) for r in (items or [])]
    return ActionResult.success(
        WorkatoRecipeList(items=recipes),
        summary=f"Found {len(recipes)} recipe(s).",
    )


@chat.function(
    "get_workato_recipe",
    "Read one Workato recipe in full -- its running state, trigger/action apps, "
    "folder/project, and lifetime job counts.",
    action_type="read", chain_callable=True, data_model=WorkatoRecipe,
    event="workato-connector.get_workato_recipe",
)
async def get_workato_recipe(ctx, params: GetRecipeParams) -> ActionResult:
    """Chat function: get workato recipe."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.get_recipe(ctx, dc, tok, params.recipe_id, params.include_tags)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_recipe_entity(data), summary=f"Recipe '{data.get('name','')}'.")


@chat.function(
    "create_workato_recipe",
    "Create a brand-new, empty Workato recipe in a folder. You'll still need to "
    "build its trigger/action steps in the Workato recipe editor -- this creates "
    "the container, not a working automation.",
    action_type="write", chain_callable=True, data_model=WorkatoRecipe,
    event="workato-connector.create_workato_recipe", effects=["workato.recipe.created"],
)
async def create_workato_recipe(ctx, params: CreateRecipeParams) -> ActionResult:
    """Chat function: create workato recipe."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.create_recipe(ctx, dc, tok, params.name, params.folder_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_recipe_entity(data), summary=f"Created recipe '{params.name}'.",
                                 refresh_panels=["workato_recipes"])


@chat.function(
    "update_workato_recipe",
    "Rename an existing Workato recipe.",
    action_type="write", chain_callable=True, data_model=WorkatoRecipe,
    event="workato-connector.update_workato_recipe", effects=["workato.recipe.updated"],
)
async def update_workato_recipe(ctx, params: UpdateRecipeParams) -> ActionResult:
    """Chat function: update workato recipe."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.update_recipe(ctx, dc, tok, params.recipe_id, params.name)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_recipe_entity(data), summary="Recipe updated.",
                                 refresh_panels=["workato_recipes"])


@chat.function(
    "copy_workato_recipe",
    "Copy an existing Workato recipe -- same steps/logic, a new id and name, "
    "optionally into a different folder.",
    action_type="write", chain_callable=True, data_model=WorkatoRecipe,
    event="workato-connector.copy_workato_recipe", effects=["workato.recipe.created"],
)
async def copy_workato_recipe(ctx, params: CopyRecipeParams) -> ActionResult:
    """Chat function: copy workato recipe."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.copy_recipe(ctx, dc, tok, params.recipe_id, params.folder_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_recipe_entity(data), summary="Recipe copied.",
                                 refresh_panels=["workato_recipes"])


@chat.function(
    "delete_workato_recipe",
    "Permanently delete a Workato recipe. Cannot be undone.",
    action_type="write", chain_callable=True, data_model=DeleteResult,
    event="workato-connector.delete_workato_recipe", effects=["workato.recipe.deleted"],
)
async def delete_workato_recipe(ctx, params: RecipeIdParams) -> ActionResult:
    """Chat function: delete workato recipe."""
    try:
        tok, dc = await _creds(ctx)
        await wc.delete_recipe(ctx, dc, tok, params.recipe_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(DeleteResult(id=params.recipe_id, title="Recipe", deleted=True),
                                 summary="Recipe deleted.", refresh_panels=["workato_recipes"])


@chat.function(
    "start_workato_recipe",
    "Start (turn on) a Workato recipe so its trigger begins running.",
    action_type="write", chain_callable=True, data_model=RecipeActionResult,
    event="workato-connector.start_workato_recipe", effects=["workato.recipe.started"],
)
async def start_workato_recipe(ctx, params: RecipeIdParams) -> ActionResult:
    """Chat function: start workato recipe."""
    try:
        tok, dc = await _creds(ctx)
        await wc.start_recipe(ctx, dc, tok, params.recipe_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        RecipeActionResult(id=params.recipe_id, title="Recipe", recipe_id=params.recipe_id, running=True),
        summary="Recipe started.", refresh_panels=["workato_recipes"])


@chat.function(
    "stop_workato_recipe",
    "Stop (turn off) a running Workato recipe.",
    action_type="write", chain_callable=True, data_model=RecipeActionResult,
    event="workato-connector.stop_workato_recipe", effects=["workato.recipe.stopped"],
)
async def stop_workato_recipe(ctx, params: RecipeIdParams) -> ActionResult:
    """Chat function: stop workato recipe."""
    try:
        tok, dc = await _creds(ctx)
        await wc.stop_recipe(ctx, dc, tok, params.recipe_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        RecipeActionResult(id=params.recipe_id, title="Recipe", recipe_id=params.recipe_id, running=False),
        summary="Recipe stopped.", refresh_panels=["workato_recipes"])


@chat.function(
    "reset_workato_recipe_trigger",
    "Reset a recipe's trigger -- clears its stored polling/watermark state so "
    "the next run re-evaluates from scratch. Use after fixing a stuck trigger.",
    action_type="write", chain_callable=True, data_model=RecipeActionResult,
    event="workato-connector.reset_workato_recipe_trigger", effects=["workato.recipe.trigger_reset"],
)
async def reset_workato_recipe_trigger(ctx, params: RecipeIdParams) -> ActionResult:
    """Chat function: reset workato recipe trigger."""
    try:
        tok, dc = await _creds(ctx)
        await wc.reset_recipe_trigger(ctx, dc, tok, params.recipe_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        RecipeActionResult(id=params.recipe_id, title="Recipe", recipe_id=params.recipe_id),
        summary="Recipe trigger reset.")


@chat.function(
    "force_run_workato_recipe",
    "Force a Workato recipe to run right now, on demand, regardless of its "
    "trigger schedule. Executes real actions in your connected apps.",
    action_type="write", chain_callable=True, data_model=RecipeActionResult,
    event="workato-connector.force_run_workato_recipe", effects=["workato.recipe.force_run"],
)
async def force_run_workato_recipe(ctx, params: RecipeIdParams) -> ActionResult:
    """Chat function: force run workato recipe."""
    try:
        tok, dc = await _creds(ctx)
        await wc.force_run_recipe(ctx, dc, tok, params.recipe_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        RecipeActionResult(id=params.recipe_id, title="Recipe", recipe_id=params.recipe_id),
        summary="Recipe force-run triggered.")


@chat.function(
    "poll_now_workato_recipe",
    "Activate a recipe's polling trigger immediately, instead of waiting for "
    "its next scheduled poll interval.",
    action_type="write", chain_callable=True, data_model=RecipeActionResult,
    event="workato-connector.poll_now_workato_recipe", effects=["workato.recipe.polled"],
)
async def poll_now_workato_recipe(ctx, params: RecipeIdParams) -> ActionResult:
    """Chat function: poll now workato recipe."""
    try:
        tok, dc = await _creds(ctx)
        await wc.poll_now_recipe(ctx, dc, tok, params.recipe_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        RecipeActionResult(id=params.recipe_id, title="Recipe", recipe_id=params.recipe_id),
        summary="Recipe polled now.")


@chat.function(
    "reconnect_workato_recipe_application",
    "Update which connection a stopped recipe uses for one of its applications "
    "-- e.g. swap a Salesforce sandbox connection for production. The recipe "
    "must be stopped first.",
    action_type="write", chain_callable=True, data_model=RecipeActionResult,
    event="workato-connector.reconnect_workato_recipe_application", effects=["workato.recipe.reconnected"],
)
async def reconnect_workato_recipe_application(ctx, params: ReconnectRecipeParams) -> ActionResult:
    """Chat function: reconnect workato recipe application."""
    try:
        tok, dc = await _creds(ctx)
        await wc.reconnect_recipe_application(ctx, dc, tok, params.recipe_id, params.connection_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        RecipeActionResult(id=params.recipe_id, title="Recipe", recipe_id=params.recipe_id),
        summary="Recipe application connection updated.")


@chat.function(
    "list_workato_recipe_versions",
    "List the saved version history of one Workato recipe.",
    action_type="read", chain_callable=True, data_model=WorkatoRecipeVersionList,
    event="workato-connector.list_workato_recipe_versions",
)
async def list_workato_recipe_versions(ctx, params: ListRecipeVersionsParams) -> ActionResult:
    """Chat function: list workato recipe versions."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.list_recipe_versions(ctx, dc, tok, params.recipe_id)
    except wc.ProviderError as exc:
        return _err(exc)
    items = data.get("items", data) if isinstance(data, dict) else data
    versions = [
        WorkatoRecipeVersion(id=str(v.get("id", "")), title=f"v{v.get('id','')}",
                              recipe_id=params.recipe_id, comment=v.get("comment", "") or "",
                              created_at=v.get("created_at", "") or "")
        for v in (items or [])
    ]
    return ActionResult.success(WorkatoRecipeVersionList(items=versions),
                                 summary=f"Found {len(versions)} version(s).")


@chat.function(
    "get_workato_recipe_version",
    "Read one specific saved version of a Workato recipe in full.",
    action_type="read", chain_callable=True, data_model=WorkatoRecipeVersion,
    event="workato-connector.get_workato_recipe_version",
)
async def get_workato_recipe_version(ctx, params: GetRecipeVersionParams) -> ActionResult:
    """Chat function: get workato recipe version."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.get_recipe_version(ctx, dc, tok, params.recipe_id, params.version_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        WorkatoRecipeVersion(id=str(data.get("id", "")), title=f"v{data.get('id','')}",
                              recipe_id=params.recipe_id, comment=data.get("comment", "") or "",
                              created_at=data.get("created_at", "") or ""),
        summary="Recipe version read.")


@chat.function(
    "get_workato_recipe_health",
    "Retrieve the most recent optimization/health analysis for a Workato recipe.",
    action_type="read", chain_callable=True, data_model=RecipeHealthReport,
    event="workato-connector.get_workato_recipe_health",
)
async def get_workato_recipe_health(ctx, params: RecipeIdParams) -> ActionResult:
    """Chat function: get workato recipe health."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.get_recipe_health(ctx, dc, tok, params.recipe_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        RecipeHealthReport(id=params.recipe_id, title="Recipe health", recipe_id=params.recipe_id,
                            summary=str(data)),
        summary="Recipe health report read.")


def _connection_entity(c: dict) -> WorkatoConnection:
    return WorkatoConnection(
        id=str(c.get("id", "")), title=c.get("name", ""), name=c.get("name", ""),
        provider=c.get("provider", "") or "", folder_id=str(c.get("folder_id", "") or ""),
        authorized=bool(c.get("authorized", False)), external_id=c.get("external_id", "") or "",
    )


# ──────────────────────────────────────────────────────────────────────────
# Connections
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_workato_connections",
    "List the app connections in your Workato workspace -- what a recipe's "
    "trigger/action steps actually authenticate through.",
    action_type="read", chain_callable=True, data_model=WorkatoConnectionList,
    event="workato-connector.list_workato_connections",
)
async def list_workato_connections(ctx, params: ListConnectionsParams) -> ActionResult:
    """Chat function: list workato connections."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.list_connections(ctx, dc, tok, params.folder_id, params.project_id,
                                          params.include_tags)
    except wc.ProviderError as exc:
        return _err(exc)
    items = data.get("items", data) if isinstance(data, dict) else data
    conns = [_connection_entity(c) for c in (items or [])]
    return ActionResult.success(WorkatoConnectionList(items=conns),
                                 summary=f"Found {len(conns)} connection(s).")


@chat.function(
    "create_workato_connection",
    "Create a new connection in your Workato workspace -- the credential a "
    "recipe's steps authenticate through. Input fields are provider-specific "
    "(e.g. a Salesforce connection needs different fields than a Slack one).",
    action_type="write", chain_callable=True, data_model=WorkatoConnection,
    event="workato-connector.create_workato_connection", effects=["workato.connection.created"],
)
async def create_workato_connection(ctx, params: CreateConnectionParams) -> ActionResult:
    """Chat function: create workato connection."""
    import json as _json
    try:
        input_dict = _json.loads(params.input_json) if params.input_json else {}
    except Exception:
        return ActionResult.error("input_json must be valid JSON.", code="WORKATO_BAD_JSON")
    try:
        tok, dc = await _creds(ctx)
        data = await wc.create_connection(ctx, dc, tok, params.name, params.provider,
                                           params.folder_id, input_dict)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_connection_entity(data), summary=f"Created connection '{params.name}'.",
                                 refresh_panels=["workato_connections"])


@chat.function(
    "update_workato_connection",
    "Update an existing Workato connection's name and/or provider-specific input fields.",
    action_type="write", chain_callable=True, data_model=WorkatoConnection,
    event="workato-connector.update_workato_connection", effects=["workato.connection.updated"],
)
async def update_workato_connection(ctx, params: UpdateConnectionParams) -> ActionResult:
    """Chat function: update workato connection."""
    import json as _json
    input_dict = None
    if params.input_json:
        try:
            input_dict = _json.loads(params.input_json)
        except Exception:
            return ActionResult.error("input_json must be valid JSON.", code="WORKATO_BAD_JSON")
    try:
        tok, dc = await _creds(ctx)
        data = await wc.update_connection(ctx, dc, tok, params.connection_id, params.name, input_dict)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_connection_entity(data), summary="Connection updated.",
                                 refresh_panels=["workato_connections"])


@chat.function(
    "disconnect_workato_connection",
    "Disconnect a Workato connection (breaks its live authorization without deleting it). "
    "Recipes using it will fail until it's reconnected or replaced.",
    action_type="write", chain_callable=True, data_model=ConnectionActionResult,
    event="workato-connector.disconnect_workato_connection", effects=["workato.connection.disconnected"],
)
async def disconnect_workato_connection(ctx, params: ConnectionIdParams) -> ActionResult:
    """Chat function: disconnect workato connection."""
    try:
        tok, dc = await _creds(ctx)
        await wc.disconnect_connection(ctx, dc, tok, params.connection_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        ConnectionActionResult(id=params.connection_id, title="Connection", connection_id=params.connection_id,
                                authorized=False),
        summary="Connection disconnected.", refresh_panels=["workato_connections"])


@chat.function(
    "delete_workato_connection",
    "Permanently delete a Workato connection. Recipes using it will stop working "
    "once it's gone. Cannot be undone.",
    action_type="write", chain_callable=True, data_model=DeleteResult,
    event="workato-connector.delete_workato_connection", effects=["workato.connection.deleted"],
)
async def delete_workato_connection(ctx, params: ConnectionIdParams) -> ActionResult:
    """Chat function: delete workato connection."""
    try:
        tok, dc = await _creds(ctx)
        await wc.delete_connection(ctx, dc, tok, params.connection_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        DeleteResult(id=params.connection_id, title="Connection", deleted=True),
        summary="Connection permanently deleted.", refresh_panels=["workato_connections"])


@chat.function(
    "get_workato_connection_picklist",
    "Get picklist values for a Workato connection -- the dropdown options a "
    "recipe step's field would show (e.g. valid Salesforce object names).",
    action_type="read", chain_callable=True, data_model=PicklistValueList,
    event="workato-connector.get_workato_connection_picklist",
)
async def get_workato_connection_picklist(ctx, params: GetConnectionPicklistParams) -> ActionResult:
    """Chat function: get workato connection picklist."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.get_connection_picklist(ctx, dc, tok, params.connection_id, params.picklist_name)
    except wc.ProviderError as exc:
        return _err(exc)
    items = data if isinstance(data, list) else data.get("result", []) if isinstance(data, dict) else []
    values = [PicklistValue(id=str(v[0]) if isinstance(v, (list, tuple)) else str(v),
                             title=str(v[1]) if isinstance(v, (list, tuple)) and len(v) > 1 else str(v))
              for v in (items or [])]
    return ActionResult.success(PicklistValueList(items=values), summary=f"Found {len(values)} picklist value(s).")


def _job_entity(j: dict) -> WorkatoJob:
    return WorkatoJob(
        id=str(j.get("id", "")), title=j.get("title", "") or str(j.get("id", "")),
        recipe_id=str(j.get("recipe_id", "") or ""), status=j.get("status", "") or "",
        is_error=bool(j.get("is_error", False)), started_at=j.get("started_at", "") or "",
        completed_at=j.get("completed_at", "") or "",
    )


# ──────────────────────────────────────────────────────────────────────────
# Jobs
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_workato_recipe_jobs",
    "List past/current jobs (runs) for a Workato recipe -- status, timing, and "
    "whether each was a poll error.",
    action_type="read", chain_callable=True, data_model=WorkatoJobList,
    event="workato-connector.list_workato_recipe_jobs",
)
async def list_workato_recipe_jobs(ctx, params: ListRecipeJobsParams) -> ActionResult:
    """Chat function: list workato recipe jobs."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.list_recipe_jobs(ctx, dc, tok, params.recipe_id, params.since,
                                          params.until, params.status, params.page, params.per_page)
    except wc.ProviderError as exc:
        return _err(exc)
    items = data.get("items", []) if isinstance(data, dict) else data
    jobs = [_job_entity(j) for j in (items or [])]
    return ActionResult.success(WorkatoJobList(items=jobs), summary=f"Found {len(jobs)} job(s).")


@chat.function(
    "get_workato_job",
    "Read one Workato job in full, including its run-time input/output data.",
    action_type="read", chain_callable=True, data_model=WorkatoJob,
    event="workato-connector.get_workato_job",
)
async def get_workato_job(ctx, params: GetJobParams) -> ActionResult:
    """Chat function: get workato job."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.get_job(ctx, dc, tok, params.job_id, params.include_var)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_job_entity(data), summary=f"Job {params.job_id} read.")


@chat.function(
    "repeat_workato_jobs",
    "Re-run one or more Workato jobs with the same trigger inputs they originally "
    "received -- useful for retrying failed jobs after fixing the underlying issue.",
    action_type="write", chain_callable=True, data_model=RepeatJobsResult,
    event="workato-connector.repeat_workato_jobs", effects=["workato.job.repeated"],
)
async def repeat_workato_jobs(ctx, params: RepeatJobsParams) -> ActionResult:
    """Chat function: repeat workato jobs."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.repeat_jobs(ctx, dc, tok, params.job_ids)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        RepeatJobsResult(id=",".join(params.job_ids), title="Repeat jobs",
                          requested_count=len(params.job_ids),
                          repeated_count=len(params.job_ids)),
        summary=f"Repeated {len(params.job_ids)} job(s).")


def _folder_entity(f: dict) -> WorkatoFolder:
    return WorkatoFolder(
        id=str(f.get("id", "")), title=f.get("name", ""), name=f.get("name", ""),
        parent_id=str(f.get("parent_id", "") or ""), is_project=bool(f.get("is_project", False)),
        project_id=str(f.get("project_id", "") or ""),
    )


def _project_entity(p: dict) -> WorkatoProject:
    return WorkatoProject(
        id=str(p.get("id", "")), title=p.get("name", "") or p.get("folder_name", ""),
        name=p.get("name", "") or p.get("folder_name", ""),
        folder_id=str(p.get("folder_id", "") or ""),
    )


# ──────────────────────────────────────────────────────────────────────────
# Folders / Projects
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_workato_folders",
    "List folders in your Workato workspace -- how recipes, connections and "
    "other assets are organized.",
    action_type="read", chain_callable=True, data_model=WorkatoFolderList,
    event="workato-connector.list_workato_folders",
)
async def list_workato_folders(ctx, params: ListFoldersParams) -> ActionResult:
    """Chat function: list workato folders."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.list_folders(ctx, dc, tok, params.parent_id)
    except wc.ProviderError as exc:
        return _err(exc)
    items = data if isinstance(data, list) else data.get("items", []) if isinstance(data, dict) else []
    folders = [_folder_entity(f) for f in (items or [])]
    return ActionResult.success(WorkatoFolderList(items=folders), summary=f"Found {len(folders)} folder(s).")


@chat.function(
    "get_workato_folder",
    "Read one Workato folder in full.",
    action_type="read", chain_callable=True, data_model=WorkatoFolder,
    event="workato-connector.get_workato_folder",
)
async def get_workato_folder(ctx, params: FolderIdParams) -> ActionResult:
    """Chat function: get workato folder."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.get_folder(ctx, dc, tok, params.folder_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_folder_entity(data), summary=f"Folder '{data.get('name','')}'.")


@chat.function(
    "create_workato_folder",
    "Create a new folder (or a top-level project, when parent_id is left empty and "
    "is_project is true) in your Workato workspace.",
    action_type="write", chain_callable=True, data_model=WorkatoFolder,
    event="workato-connector.create_workato_folder", effects=["workato.folder.created"],
)
async def create_workato_folder(ctx, params: CreateFolderParams) -> ActionResult:
    """Chat function: create workato folder."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.create_folder(ctx, dc, tok, params.name, params.parent_id, is_project=params.is_project)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_folder_entity(data), summary=f"Created folder '{params.name}'.",
                                 refresh_panels=["workato_folders"])


@chat.function(
    "update_workato_folder",
    "Rename a Workato folder.",
    action_type="write", chain_callable=True, data_model=WorkatoFolder,
    event="workato-connector.update_workato_folder", effects=["workato.folder.updated"],
)
async def update_workato_folder(ctx, params: UpdateFolderParams) -> ActionResult:
    """Chat function: update workato folder."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.update_folder(ctx, dc, tok, params.folder_id, params.name)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_folder_entity(data), summary="Folder renamed.",
                                 refresh_panels=["workato_folders"])


@chat.function(
    "delete_workato_folder",
    "Permanently delete a Workato folder. Assets inside it are not deleted by "
    "this endpoint on Workato's side unless empty is required -- check Workato's "
    "own behavior before relying on this for cleanup. Cannot be undone.",
    action_type="write", chain_callable=True, data_model=DeleteResult,
    event="workato-connector.delete_workato_folder", effects=["workato.folder.deleted"],
)
async def delete_workato_folder(ctx, params: FolderIdParams) -> ActionResult:
    """Chat function: delete workato folder."""
    try:
        tok, dc = await _creds(ctx)
        await wc.delete_folder(ctx, dc, tok, params.folder_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(DeleteResult(id=params.folder_id, title="Folder", deleted=True),
                                 summary="Folder deleted.", refresh_panels=["workato_folders"])


@chat.function(
    "list_workato_projects",
    "List projects (top-level folders) in your Workato workspace.",
    action_type="read", chain_callable=True, data_model=WorkatoProjectList,
    event="workato-connector.list_workato_projects",
)
async def list_workato_projects(ctx, params: ListProjectsParams) -> ActionResult:
    """Chat function: list workato projects."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.list_projects(ctx, dc, tok)
    except wc.ProviderError as exc:
        return _err(exc)
    items = data if isinstance(data, list) else data.get("items", []) if isinstance(data, dict) else []
    projects = [_project_entity(p) for p in (items or [])]
    return ActionResult.success(WorkatoProjectList(items=projects), summary=f"Found {len(projects)} project(s).")


@chat.function(
    "update_workato_project",
    "Rename a Workato project.",
    action_type="write", chain_callable=True, data_model=WorkatoProject,
    event="workato-connector.update_workato_project", effects=["workato.project.updated"],
)
async def update_workato_project(ctx, params: UpdateProjectParams) -> ActionResult:
    """Chat function: update workato project."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.update_project(ctx, dc, tok, params.project_id, params.name)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_project_entity(data), summary="Project renamed.",
                                 refresh_panels=["workato_folders"])


@chat.function(
    "delete_workato_project",
    "Permanently delete a Workato project. Cannot be undone.",
    action_type="write", chain_callable=True, data_model=DeleteResult,
    event="workato-connector.delete_workato_project", effects=["workato.project.deleted"],
)
async def delete_workato_project(ctx, params: ProjectIdParams) -> ActionResult:
    """Chat function: delete workato project."""
    try:
        tok, dc = await _creds(ctx)
        await wc.delete_project(ctx, dc, tok, params.project_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(DeleteResult(id=params.project_id, title="Project", deleted=True),
                                 summary="Project deleted.", refresh_panels=["workato_folders"])


@chat.function(
    "delete_workato_folder",
    "Permanently delete a Workato folder. Cannot be undone.",
    action_type="write", chain_callable=True, data_model=DeleteResult,
    event="workato-connector.delete_workato_folder", effects=["workato.folder.deleted"],
)
async def delete_workato_folder(ctx, params: FolderIdParams) -> ActionResult:
    """Chat function: delete workato folder."""
    try:
        tok, dc = await _creds(ctx)
        await wc.delete_folder(ctx, dc, tok, params.folder_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(DeleteResult(id=params.folder_id, title="Folder", deleted=True),
                                 summary="Folder deleted.", refresh_panels=["workato_folders"])


def _tag_entity(t: dict) -> WorkatoTag:
    return WorkatoTag(id=str(t.get("id", "")), title=t.get("name", ""), name=t.get("name", ""))


# ──────────────────────────────────────────────────────────────────────────
# Tags + Tag assignments
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_workato_tags",
    "List tags defined in your Workato workspace.",
    action_type="read", chain_callable=True, data_model=WorkatoTagList,
    event="workato-connector.list_workato_tags",
)
async def list_workato_tags(ctx, params: ListTagsParams) -> ActionResult:
    """Chat function: list workato tags."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.list_tags(ctx, dc, tok, params.page, params.per_page)
    except wc.ProviderError as exc:
        return _err(exc)
    items = data if isinstance(data, list) else data.get("items", []) if isinstance(data, dict) else []
    tags = [_tag_entity(t) for t in (items or [])]
    return ActionResult.success(WorkatoTagList(items=tags), summary=f"Found {len(tags)} tag(s).")


@chat.function(
    "create_workato_tag",
    "Create a new tag in your Workato workspace.",
    action_type="write", chain_callable=True, data_model=WorkatoTag,
    event="workato-connector.create_workato_tag", effects=["workato.tag.created"],
)
async def create_workato_tag(ctx, params: CreateTagParams) -> ActionResult:
    """Chat function: create workato tag."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.create_tag(ctx, dc, tok, params.name)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_tag_entity(data), summary=f"Created tag '{params.name}'.",
                                 refresh_panels=["workato_tags"])


@chat.function(
    "update_workato_tag",
    "Rename a Workato tag.",
    action_type="write", chain_callable=True, data_model=WorkatoTag,
    event="workato-connector.update_workato_tag", effects=["workato.tag.updated"],
)
async def update_workato_tag(ctx, params: UpdateTagParams) -> ActionResult:
    """Chat function: update workato tag."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.update_tag(ctx, dc, tok, params.tag_id, params.name)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_tag_entity(data), summary="Tag renamed.", refresh_panels=["workato_tags"])


@chat.function(
    "delete_workato_tag",
    "Permanently delete a tag from your Workato workspace. Assets keep working, "
    "they simply lose that tag.",
    action_type="write", chain_callable=True, data_model=DeleteResult,
    event="workato-connector.delete_workato_tag", effects=["workato.tag.deleted"],
)
async def delete_workato_tag(ctx, params: TagIdParams) -> ActionResult:
    """Chat function: delete workato tag."""
    try:
        tok, dc = await _creds(ctx)
        await wc.delete_tag(ctx, dc, tok, params.tag_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(DeleteResult(id=params.tag_id, title="Tag", deleted=True),
                                 summary="Tag deleted.", refresh_panels=["workato_tags"])


@chat.function(
    "add_workato_tag_assignment",
    "Attach one or more tags to a Workato asset (recipe, connection, lookup table, etc).",
    action_type="write", chain_callable=True, data_model=TagAssignmentResult,
    event="workato-connector.add_workato_tag_assignment", effects=["workato.tag_assignment.added"],
)
async def add_workato_tag_assignment(ctx, params: TagAssignmentParams) -> ActionResult:
    """Chat function: add workato tag assignment."""
    try:
        tok, dc = await _creds(ctx)
        await wc.add_tag_assignment(ctx, dc, tok, params.taggable_type, params.taggable_id, params.tag_ids)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        TagAssignmentResult(id=params.taggable_id, title="Tag assignment",
                             taggable_id=params.taggable_id, tag_count=len(params.tag_ids)),
        summary=f"Added {len(params.tag_ids)} tag(s).")


@chat.function(
    "remove_workato_tag_assignment",
    "Detach one or more tags from a Workato asset.",
    action_type="write", chain_callable=True, data_model=TagAssignmentResult,
    event="workato-connector.remove_workato_tag_assignment", effects=["workato.tag_assignment.removed"],
)
async def remove_workato_tag_assignment(ctx, params: TagAssignmentParams) -> ActionResult:
    """Chat function: remove workato tag assignment."""
    try:
        tok, dc = await _creds(ctx)
        await wc.remove_tag_assignment(ctx, dc, tok, params.taggable_type, params.taggable_id, params.tag_ids)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        TagAssignmentResult(id=params.taggable_id, title="Tag assignment",
                             taggable_id=params.taggable_id, tag_count=len(params.tag_ids)),
        summary=f"Removed {len(params.tag_ids)} tag(s).")


def _lookup_table_entity(t: dict) -> WorkatoLookupTable:
    return WorkatoLookupTable(
        id=str(t.get("id", "")), title=t.get("name", ""), name=t.get("name", ""),
        project_id=str(t.get("project_id", "") or ""), table_schema=str(t.get("schema", "") or ""),
    )


def _lookup_row_entity(row_id_key: str, r: dict) -> WorkatoLookupTableRow:
    rid = str(r.get(row_id_key, r.get("id", "")))
    return WorkatoLookupTableRow(id=rid, title=rid, data=r.get("data", r))


# ──────────────────────────────────────────────────────────────────────────
# Lookup tables (full CRUD, including rows)
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_workato_lookup_tables",
    "List lookup tables (key/value reference tables a recipe can read from) "
    "in your Workato workspace.",
    action_type="read", chain_callable=True, data_model=WorkatoLookupTableList,
    event="workato-connector.list_workato_lookup_tables",
)
async def list_workato_lookup_tables(ctx, params: ListLookupTablesParams) -> ActionResult:
    """Chat function: list workato lookup tables."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.list_lookup_tables(ctx, dc, tok, params.page, params.per_page)
    except wc.ProviderError as exc:
        return _err(exc)
    items = data if isinstance(data, list) else data.get("items", []) if isinstance(data, dict) else []
    tables = [_lookup_table_entity(t) for t in (items or [])]
    return ActionResult.success(WorkatoLookupTableList(items=tables),
                                 summary=f"Found {len(tables)} lookup table(s).")


@chat.function(
    "create_workato_lookup_table",
    "Create a new lookup table in your Workato workspace with the column "
    "schema you specify.",
    action_type="write", chain_callable=True, data_model=WorkatoLookupTable,
    event="workato-connector.create_workato_lookup_table",
    effects=["workato.lookup_table.created"],
)
async def create_workato_lookup_table(ctx, params: CreateLookupTableParams) -> ActionResult:
    """Chat function: create workato lookup table."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.create_lookup_table(ctx, dc, tok, params.name, params.folder_id,
                                             params.table_schema)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_lookup_table_entity(data), summary="Lookup table created.",
                                 refresh_panels=["workato_lookup_tables"])


@chat.function(
    "batch_delete_workato_lookup_tables",
    "Permanently delete SEVERAL Workato lookup tables at once, by explicit ids. "
    "Cannot be undone.",
    action_type="write", chain_callable=True, data_model=BatchDeleteResult,
    event="workato-connector.batch_delete_workato_lookup_tables",
    effects=["workato.lookup_table.deleted"],
)
async def batch_delete_workato_lookup_tables(ctx, params: BatchDeleteLookupTablesParams) -> ActionResult:
    """Chat function: batch delete workato lookup tables."""
    try:
        tok, dc = await _creds(ctx)
        await wc.batch_delete_lookup_tables(ctx, dc, tok, params.lookup_table_ids)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        BatchDeleteResult(id=",".join(params.lookup_table_ids), title="Lookup tables",
                           deleted_count=len(params.lookup_table_ids)),
        summary=f"Deleted {len(params.lookup_table_ids)} lookup table(s).",
        refresh_panels=["workato_lookup_tables"])


@chat.function(
    "list_workato_lookup_table_rows",
    "List rows from a Workato lookup table, with optional column filtering "
    "and pagination.",
    action_type="read", chain_callable=True, data_model=WorkatoLookupTableRowList,
    event="workato-connector.list_workato_lookup_table_rows",
)
async def list_workato_lookup_table_rows(ctx, params: ListLookupTableRowsParams) -> ActionResult:
    """Chat function: list workato lookup table rows."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.list_lookup_table_rows(ctx, dc, tok, params.lookup_table_id,
                                                params.page, params.per_page)
    except wc.ProviderError as exc:
        return _err(exc)
    items = data if isinstance(data, list) else data.get("items", []) if isinstance(data, dict) else []
    rows = [_lookup_row_entity("row_id", r) for r in (items or [])]
    return ActionResult.success(WorkatoLookupTableRowList(items=rows),
                                 summary=f"Found {len(rows)} row(s).")


@chat.function(
    "get_workato_lookup_table_row",
    "Read one row from a Workato lookup table by its row id.",
    action_type="read", chain_callable=True, data_model=WorkatoLookupTableRow,
    event="workato-connector.get_workato_lookup_table_row",
)
async def get_workato_lookup_table_row(ctx, params: GetLookupTableRowParams) -> ActionResult:
    """Chat function: get workato lookup table row."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.get_lookup_table_row(ctx, dc, tok, params.lookup_table_id, params.row_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_lookup_row_entity("row_id", data), summary="Row read.")


@chat.function(
    "add_workato_lookup_table_row",
    "Add a new row to a Workato lookup table.",
    action_type="write", chain_callable=True, data_model=WorkatoLookupTableRow,
    event="workato-connector.add_workato_lookup_table_row",
    effects=["workato.lookup_table.row_added"],
)
async def add_workato_lookup_table_row(ctx, params: AddLookupTableRowParams) -> ActionResult:
    """Chat function: add workato lookup table row."""
    try:
        row = json.loads(params.row_json)
    except Exception:
        return ActionResult.error("row_json must be valid JSON.", code="WORKATO_BAD_JSON")
    try:
        tok, dc = await _creds(ctx)
        data = await wc.add_lookup_table_row(ctx, dc, tok, params.lookup_table_id, row)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_lookup_row_entity("row_id", data), summary="Row added.",
                                 refresh_panels=["workato_lookup_tables"])


@chat.function(
    "update_workato_lookup_table_row",
    "Update an existing row in a Workato lookup table.",
    action_type="write", chain_callable=True, data_model=WorkatoLookupTableRow,
    event="workato-connector.update_workato_lookup_table_row",
    effects=["workato.lookup_table.row_updated"],
)
async def update_workato_lookup_table_row(ctx, params: UpdateLookupTableRowParams) -> ActionResult:
    """Chat function: update workato lookup table row."""
    try:
        row = json.loads(params.row_json)
    except Exception:
        return ActionResult.error("row_json must be valid JSON.", code="WORKATO_BAD_JSON")
    try:
        tok, dc = await _creds(ctx)
        data = await wc.update_lookup_table_row(ctx, dc, tok, params.lookup_table_id,
                                                 params.row_id, row)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(_lookup_row_entity("row_id", data), summary="Row updated.",
                                 refresh_panels=["workato_lookup_tables"])


@chat.function(
    "delete_workato_lookup_table_row",
    "Permanently delete one row from a Workato lookup table.",
    action_type="write", chain_callable=True, data_model=DeleteResult,
    event="workato-connector.delete_workato_lookup_table_row",
    effects=["workato.lookup_table.row_deleted"],
)
async def delete_workato_lookup_table_row(ctx, params: DeleteLookupTableRowParams) -> ActionResult:
    """Chat function: delete workato lookup table row."""
    try:
        tok, dc = await _creds(ctx)
        await wc.delete_lookup_table_row(ctx, dc, tok, params.lookup_table_id, params.row_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(DeleteResult(id=params.row_id, title="Lookup table row", deleted=True),
                                 summary="Row deleted.", refresh_panels=["workato_lookup_tables"])


# ──────────────────────────────────────────────────────────────────────────
# Environment properties
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_workato_properties",
    "List environment properties defined in your Workato workspace, "
    "filtered by a key prefix (e.g. 'env.').",
    action_type="read", chain_callable=True, data_model=WorkatoPropertyList,
    event="workato-connector.list_workato_properties",
)
async def list_workato_properties(ctx, params: ListPropertiesByPrefixParams) -> ActionResult:
    """Chat function: list workato properties."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.list_properties_by_prefix(ctx, dc, tok, params.prefix)
    except wc.ProviderError as exc:
        return _err(exc)
    props = data.get("properties", data) if isinstance(data, dict) else {}
    entities = [_property_entity(k, str(v)) for k, v in (props or {}).items()]
    return ActionResult.success(WorkatoPropertyList(items=entities),
                                 summary=f"Found {len(entities)} propert{'y' if len(entities) == 1 else 'ies'}.")


@chat.function(
    "upsert_workato_properties",
    "Create or update one or more environment properties in your Workato "
    "workspace. Existing keys are overwritten; new keys are created.",
    action_type="write", chain_callable=True, data_model=WorkatoPropertyList,
    event="workato-connector.upsert_workato_properties",
    effects=["workato.properties.updated"],
)
async def upsert_workato_properties(ctx, params: UpsertPropertiesParams) -> ActionResult:
    """Chat function: upsert workato properties."""
    try:
        properties = json.loads(params.properties_json)
    except Exception:
        return ActionResult.error("properties_json must be valid JSON.", code="WORKATO_BAD_JSON")
    try:
        tok, dc = await _creds(ctx)
        await wc.upsert_properties(ctx, dc, tok, properties)
    except wc.ProviderError as exc:
        return _err(exc)
    entities = [_property_entity(k, str(v)) for k, v in properties.items()]
    return ActionResult.success(WorkatoPropertyList(items=entities),
                                 summary=f"Upserted {len(entities)} propert{'y' if len(entities) == 1 else 'ies'}.")


@chat.function(
    "clear_workato_secrets_cache",
    "Clear Workato's own secrets management cache for the connected "
    "workspace -- forces fresh secret values to be re-read on next use.",
    action_type="write", chain_callable=True, data_model=DeleteResult,
    event="workato-connector.clear_workato_secrets_cache",
    effects=["workato.secrets_cache.cleared"],
)
async def clear_workato_secrets_cache(ctx, params: NoParams) -> ActionResult:
    """Chat function: clear workato secrets cache."""
    try:
        tok, dc = await _creds(ctx)
        await wc.clear_secrets_cache(ctx, dc, tok)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(DeleteResult(id="secrets_cache", title="Secrets cache", deleted=True),
                                 summary="Secrets cache cleared.")


import json as _json


def _asset_entity(a: dict) -> WorkatoAsset:
    return WorkatoAsset(
        id=str(a.get("id", "")), title=a.get("name", ""), name=a.get("name", ""),
        asset_type=a.get("type", "") or "", version=a.get("version", 0) or 0,
        absolute_path=a.get("absolute_path", "") or "",
    )


# ──────────────────────────────────────────────────────────────────────────
# Recipe lifecycle management: export manifests + packages
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "view_workato_folder_assets",
    "View the assets (recipes, connections, lookup tables, etc.) in a "
    "Workato folder -- use this to build the asset list for an export "
    "manifest.",
    action_type="read", chain_callable=True, data_model=WorkatoAssetList,
    event="workato-connector.view_workato_folder_assets",
)
async def view_workato_folder_assets(ctx, params: ViewFolderAssetsParams) -> ActionResult:
    """Chat function: view workato folder assets."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.view_folder_assets(ctx, dc, tok, params.folder_id)
    except wc.ProviderError as exc:
        return _err(exc)
    result = data.get("result", data) if isinstance(data, dict) else data
    assets = result.get("assets", []) if isinstance(result, dict) else (result or [])
    entities = [_asset_entity(a) for a in assets]
    return ActionResult.success(WorkatoAssetList(items=entities),
                                 summary=f"Found {len(entities)} asset(s).")


@chat.function(
    "create_workato_export_manifest",
    "Create an export manifest -- a named container of specific Workato "
    "assets (recipes, connections, lookup tables) to later build into a "
    "deployable package.",
    action_type="write", chain_callable=True, data_model=WorkatoManifest,
    event="workato-connector.create_workato_export_manifest",
    effects=["workato.export_manifest.created"],
)
async def create_workato_export_manifest(ctx, params: CreateExportManifestParams) -> ActionResult:
    """Chat function: create workato export manifest."""
    try:
        asset_ids = _json.loads(params.asset_ids_json)
    except Exception:
        return ActionResult.error(
            "asset_ids_json must be a valid JSON array of asset references.",
            code="WORKATO_BAD_ASSET_IDS_JSON")
    try:
        tok, dc = await _creds(ctx)
        data = await wc.create_export_manifest(ctx, dc, tok, params.name, params.folder_id, asset_ids)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        WorkatoManifest(id=str(data.get("id", "")), title=data.get("name", params.name),
                         name=data.get("name", params.name), folder_id=params.folder_id),
        summary="Export manifest created.")


@chat.function(
    "update_workato_export_manifest",
    "Replace the asset list of an existing Workato export manifest.",
    action_type="write", chain_callable=True, data_model=WorkatoManifest,
    event="workato-connector.update_workato_export_manifest",
    effects=["workato.export_manifest.updated"],
)
async def update_workato_export_manifest(ctx, params: UpdateExportManifestParams) -> ActionResult:
    """Chat function: update workato export manifest."""
    try:
        asset_ids = _json.loads(params.asset_ids_json)
    except Exception:
        return ActionResult.error(
            "asset_ids_json must be a valid JSON array of asset references.",
            code="WORKATO_BAD_ASSET_IDS_JSON")
    try:
        tok, dc = await _creds(ctx)
        data = await wc.update_export_manifest(ctx, dc, tok, params.manifest_id, asset_ids)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        WorkatoManifest(id=params.manifest_id, title=data.get("name", ""), name=data.get("name", "")),
        summary="Export manifest updated.")


@chat.function(
    "get_workato_export_manifest",
    "Read one Workato export manifest in full -- its asset list and folder.",
    action_type="read", chain_callable=True, data_model=WorkatoManifest,
    event="workato-connector.get_workato_export_manifest",
)
async def get_workato_export_manifest(ctx, params: ManifestIdParams) -> ActionResult:
    """Chat function: get workato export manifest."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.get_export_manifest(ctx, dc, tok, params.manifest_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        WorkatoManifest(id=params.manifest_id, title=data.get("name", ""), name=data.get("name", ""),
                         folder_id=str(data.get("folder_id", "") or "")),
        summary="Export manifest read.")


@chat.function(
    "delete_workato_export_manifest",
    "Permanently delete a Workato export manifest. This does not delete the "
    "underlying assets, only the manifest container.",
    action_type="write", chain_callable=True, data_model=DeleteResult,
    event="workato-connector.delete_workato_export_manifest",
    effects=["workato.export_manifest.deleted"],
)
async def delete_workato_export_manifest(ctx, params: ManifestIdParams) -> ActionResult:
    """Chat function: delete workato export manifest."""
    try:
        tok, dc = await _creds(ctx)
        await wc.delete_export_manifest(ctx, dc, tok, params.manifest_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        DeleteResult(id=params.manifest_id, title="Export manifest", deleted=True),
        summary="Export manifest deleted.")


@chat.function(
    "export_workato_package",
    "Build a deployable package from an export manifest -- the actual "
    "source-code snapshot of every asset in it, at its latest version.",
    action_type="write", chain_callable=True, data_model=WorkatoPackage,
    event="workato-connector.export_workato_package",
    effects=["workato.package.exported"],
)
async def export_workato_package(ctx, params: ExportPackageParams) -> ActionResult:
    """Chat function: export workato package."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.export_package(ctx, dc, tok, params.manifest_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        WorkatoPackage(id=str(data.get("id", "")), title="Package",
                        status=data.get("status", "") or "", manifest_id=params.manifest_id),
        summary="Package export started.")


@chat.function(
    "import_workato_package",
    "Import a previously exported package into a destination folder -- the "
    "same mechanism Workato's own environment promotion (dev -> production) "
    "uses under the hood.",
    action_type="write", chain_callable=True, data_model=WorkatoPackage,
    event="workato-connector.import_workato_package",
    effects=["workato.package.imported"],
)
async def import_workato_package(ctx, params: ImportPackageParams) -> ActionResult:
    """Chat function: import workato package."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.import_package(ctx, dc, tok, params.folder_id, params.package_file_url,
                                        params.restart_recipes)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        WorkatoPackage(id=str(data.get("id", "")), title="Package",
                        status=data.get("status", "") or ""),
        summary="Package import started.", refresh_panels=["workato_folders"])


@chat.function(
    "get_workato_package",
    "Read one Workato package's status and metadata by id.",
    action_type="read", chain_callable=True, data_model=WorkatoPackage,
    event="workato-connector.get_workato_package",
)
async def get_workato_package(ctx, params: PackageIdParams) -> ActionResult:
    """Chat function: get workato package."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.get_package(ctx, dc, tok, params.package_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        WorkatoPackage(id=params.package_id, title="Package", status=data.get("status", "") or ""),
        summary="Package read.")


@chat.function(
    "get_workato_package_download_url",
    "Get the signed download URL for a completed Workato package export.",
    action_type="read", chain_callable=True, data_model=PackageDownloadUrl,
    event="workato-connector.get_workato_package_download_url",
)
async def get_workato_package_download_url(ctx, params: PackageIdParams) -> ActionResult:
    """Chat function: get workato package download url."""
    try:
        tok, dc = await _creds(ctx)
        data = await wc.get_package_download_url(ctx, dc, tok, params.package_id)
    except wc.ProviderError as exc:
        return _err(exc)
    return ActionResult.success(
        PackageDownloadUrl(id=params.package_id, title="Package download URL",
                            download_url=data.get("url", "") or data.get("download_url", "") or ""),
        summary="Download URL read.")


