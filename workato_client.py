"""Workato Developer API client -- Bearer token auth, data-center discovery,
and thin wrappers around every resource this connector exposes: recipes,
connections, jobs, folders/projects, tags, lookup tables, environment
properties, recipe lifecycle management, and workspace details.

WHY DATA-CENTER DISCOVERY, SAME REASONING AS make_client.py's ZONE DISCOVERY.

Workato's own docs (docs.workato.com/workato-api) list a small fixed set of
data-center base URLs (US/EU/JP/SG/AU/IL/CN/KR/UK/trial) -- there is no
single global host, and a token from one data center is rejected outright
by another's host. Same shape as Make.com's zone discovery: probe the
known hosts with the cheap, side-effect-free `GET /api/users/me` call
until one accepts the token, then the caller persists the winning host.

WHY `Authorization: Bearer <api_token>`, NOT the legacy full-access key.

Workato's docs explicitly recommend API Clients (Bearer token) over the
legacy full-access API key + email scheme, which they call out as
deprecated-in-spirit even though still technically supported.
"""
from __future__ import annotations

import json

KNOWN_DATA_CENTERS: list[str] = [
    "www.workato.com",
    "app.eu.workato.com",
    "app.jp.workato.com",
    "app.sg.workato.com",
    "app.au.workato.com",
    "app.il.workato.com",
    "app.workatoapp.cn",
    "app.kr.workato.com",
    "app.uk.workato.com",
    "app.trial.workato.com",
]


class ProviderError(Exception):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.message = message
        self.status = status


def _headers(api_token: str) -> dict:
    return {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }


def _api(data_center: str, path: str) -> str:
    return f"https://{data_center}/api{path}"


def _check_status(resp, action: str):
    if resp.status_code == 401:
        raise ProviderError(
            f"Could not {action}: this data center/token pair was not recognised "
            "(wrong data center, wrong/expired token, or workspace unreachable).",
            401,
        )
    if resp.status_code == 403:
        raise ProviderError(
            f"Could not {action}: the token is recognised but its API client "
            "role lacks the privilege for this endpoint. Check Workspace admin "
            "-> API clients -> Client roles.",
            403,
        )
    if resp.status_code == 404:
        raise ProviderError(f"Could not {action}: not found.", 404)
    if resp.status_code == 429:
        raise ProviderError(
            f"Could not {action}: rate limited by Workato. Wait and retry.", 429
        )
    if resp.status_code >= 400:
        raise ProviderError(f"Could not {action}: HTTP {resp.status_code}.", resp.status_code)
    if resp.status_code == 204 or not resp.content:
        return {}
    try:
        return resp.json()
    except Exception:
        return {}


async def discover_data_center(ctx, api_token: str) -> str:
    """Probe each known data-center host with GET /api/users/me until one
    accepts the token. Returns the winning host. Raises ProviderError if
    none accept it."""
    last_err = None
    for host in KNOWN_DATA_CENTERS:
        try:
            resp = await ctx.http.get(_api(host, "/users/me"), headers=_headers(api_token))
            if resp.status_code == 200:
                return host
            if resp.status_code in (401, 403):
                last_err = resp.status_code
                continue
        except Exception as e:
            last_err = str(e)
            continue
    raise ProviderError(
        "Could not verify this API token against any known Workato data center "
        "(US/EU/JP/SG/AU/IL/CN/KR/UK/trial). Double-check the token was copied "
        "in full from Workspace admin -> API clients."
    )


async def get_workspace_details(ctx, data_center: str, api_token: str) -> dict:
    resp = await ctx.http.get(_api(data_center, "/users/me"), headers=_headers(api_token))
    return _check_status(resp, "get workspace details")


# ──────────────────────────────────────────────────────────────────────────
# Recipes (Workato's term for what n8n/Make.com call workflows/scenarios)
# ──────────────────────────────────────────────────────────────────────────


async def list_recipes(ctx, dc, tok, folder_id="", project_id="", running=None,
                        page=1, per_page=100) -> dict:
    params = {"page": page, "per_page": per_page}
    if folder_id:
        params["folder_id"] = folder_id
    if project_id:
        params["project_id"] = project_id
    if running is not None:
        params["running"] = "true" if running else "false"
    resp = await ctx.http.get(_api(dc, "/recipes"), headers=_headers(tok), params=params)
    return _check_status(resp, "list recipes")


async def get_recipe(ctx, dc, tok, recipe_id: str, include_tags=False) -> dict:
    params = {"includes[]": "tags"} if include_tags else {}
    resp = await ctx.http.get(_api(dc, f"/recipes/{recipe_id}"), headers=_headers(tok), params=params)
    return _check_status(resp, "get recipe")


async def create_recipe(ctx, dc, tok, name: str, folder_id: str = "", code: dict | None = None) -> dict:
    payload = {"name": name}
    if folder_id:
        payload["folder_id"] = folder_id
    if code:
        payload["code"] = json.dumps(code)
    resp = await ctx.http.post(_api(dc, "/recipes"), headers=_headers(tok), json=payload)
    return _check_status(resp, "create recipe")


async def update_recipe(ctx, dc, tok, recipe_id: str, name: str = "", code: dict | None = None) -> dict:
    payload = {}
    if name:
        payload["name"] = name
    if code:
        payload["code"] = json.dumps(code)
    resp = await ctx.http.put(_api(dc, f"/recipes/{recipe_id}"), headers=_headers(tok), json=payload)
    return _check_status(resp, "update recipe")


async def copy_recipe(ctx, dc, tok, recipe_id: str, folder_id: str = "") -> dict:
    payload = {"folder_id": folder_id} if folder_id else {}
    resp = await ctx.http.post(_api(dc, f"/recipes/{recipe_id}/copy"), headers=_headers(tok), json=payload)
    return _check_status(resp, "copy recipe")


async def delete_recipe(ctx, dc, tok, recipe_id: str) -> dict:
    resp = await ctx.http.delete(_api(dc, f"/recipes/{recipe_id}"), headers=_headers(tok))
    return _check_status(resp, "delete recipe")


async def start_recipe(ctx, dc, tok, recipe_id: str) -> dict:
    resp = await ctx.http.put(_api(dc, f"/recipes/{recipe_id}/start"), headers=_headers(tok))
    return _check_status(resp, "start recipe")


async def stop_recipe(ctx, dc, tok, recipe_id: str) -> dict:
    resp = await ctx.http.put(_api(dc, f"/recipes/{recipe_id}/stop"), headers=_headers(tok))
    return _check_status(resp, "stop recipe")


async def reset_recipe_trigger(ctx, dc, tok, recipe_id: str) -> dict:
    resp = await ctx.http.post(_api(dc, f"/recipes/{recipe_id}/reset_trigger"), headers=_headers(tok))
    return _check_status(resp, "reset recipe trigger")


async def force_run_recipe(ctx, dc, tok, recipe_id: str) -> dict:
    resp = await ctx.http.post(_api(dc, f"/recipes/{recipe_id}/force_run"), headers=_headers(tok))
    return _check_status(resp, "force run recipe")


async def poll_now_recipe(ctx, dc, tok, recipe_id: str) -> dict:
    resp = await ctx.http.post(_api(dc, f"/recipes/{recipe_id}/poll_now"), headers=_headers(tok))
    return _check_status(resp, "activate recipe polling trigger")


async def reconnect_recipe_application(ctx, dc, tok, recipe_id: str, connection_id: str) -> dict:
    """PUT /recipes/:id/connect -- update the connection used by a
    stopped recipe for a given application, without editing recipe code."""
    resp = await ctx.http.put(
        _api(dc, f"/recipes/{recipe_id}/connect"),
        headers=_headers(tok), json={"connection_id": connection_id},
    )
    return _check_status(resp, "update recipe connection")


async def list_recipe_versions(ctx, dc, tok, recipe_id: str) -> dict:
    resp = await ctx.http.get(_api(dc, f"/recipes/{recipe_id}/versions"), headers=_headers(tok))
    return _check_status(resp, "list recipe versions")


async def get_recipe_version(ctx, dc, tok, recipe_id: str, version_id: str) -> dict:
    resp = await ctx.http.get(_api(dc, f"/recipes/{recipe_id}/versions/{version_id}"), headers=_headers(tok))
    return _check_status(resp, "get recipe version")


async def get_recipe_health(ctx, dc, tok, recipe_id: str) -> dict:
    resp = await ctx.http.get(_api(dc, f"/recipes/{recipe_id}/health"), headers=_headers(tok))
    return _check_status(resp, "get recipe health")


# ──────────────────────────────────────────────────────────────────────────
# Connections
# ──────────────────────────────────────────────────────────────────────────


async def list_connections(ctx, dc, tok, folder_id="", project_id="",
                            include_tags=False) -> dict:
    params = {}
    if folder_id:
        params["folder_id"] = folder_id
    if project_id:
        params["project_id"] = project_id
    if include_tags:
        params["includes[]"] = "tags"
    resp = await ctx.http.get(_api(dc, "/connections"), headers=_headers(tok), params=params)
    return _check_status(resp, "list connections")


async def create_connection(ctx, dc, tok, name: str, provider: str,
                             folder_id: str = "", input_dict: dict | None = None) -> dict:
    payload = {"name": name, "provider": provider}
    if folder_id:
        payload["folder_id"] = folder_id
    if input_dict:
        payload["input"] = input_dict
    resp = await ctx.http.post(_api(dc, "/connections"), headers=_headers(tok), json=payload)
    return _check_status(resp, "create connection")


async def update_connection(ctx, dc, tok, connection_id: str, name: str = "",
                             input_dict: dict | None = None) -> dict:
    payload = {}
    if name:
        payload["name"] = name
    if input_dict:
        payload["input"] = input_dict
    resp = await ctx.http.put(_api(dc, f"/connections/{connection_id}"), headers=_headers(tok), json=payload)
    return _check_status(resp, "update connection")


async def disconnect_connection(ctx, dc, tok, connection_id: str) -> dict:
    resp = await ctx.http.post(_api(dc, f"/connections/{connection_id}/disconnect"), headers=_headers(tok))
    return _check_status(resp, "disconnect connection")


async def delete_connection(ctx, dc, tok, connection_id: str) -> dict:
    resp = await ctx.http.delete(_api(dc, f"/connections/{connection_id}"), headers=_headers(tok))
    return _check_status(resp, "delete connection")


async def get_connection_picklist(ctx, dc, tok, connection_id: str, picklist_name: str,
                                   extra: dict | None = None) -> dict:
    payload = {"picklist_name": picklist_name}
    if extra:
        payload.update(extra)
    resp = await ctx.http.post(_api(dc, f"/connections/{connection_id}/pick_list"),
                                headers=_headers(tok), json=payload)
    return _check_status(resp, "get connection picklist")


# ──────────────────────────────────────────────────────────────────────────
# Jobs
# ──────────────────────────────────────────────────────────────────────────


async def list_recipe_jobs(ctx, dc, tok, recipe_id: str, since="", until="",
                            status="", page=1, per_page=100) -> dict:
    params = {"page": page, "per_page": per_page}
    if since:
        params["since"] = since
    if until:
        params["until"] = until
    if status:
        params["status"] = status
    resp = await ctx.http.get(_api(dc, f"/recipes/{recipe_id}/jobs"), headers=_headers(tok), params=params)
    return _check_status(resp, "list recipe jobs")


async def get_job(ctx, dc, tok, job_id: str, include_var=False) -> dict:
    params = {"include_var": "true"} if include_var else {}
    resp = await ctx.http.get(_api(dc, f"/jobs/{job_id}"), headers=_headers(tok), params=params)
    return _check_status(resp, "get job")


async def repeat_jobs(ctx, dc, tok, job_ids: list[str]) -> dict:
    resp = await ctx.http.post(_api(dc, "/jobs/repeat"), headers=_headers(tok),
                                json={"job_ids": job_ids})
    return _check_status(resp, "repeat jobs")


# ──────────────────────────────────────────────────────────────────────────
# Folders / Projects
# ──────────────────────────────────────────────────────────────────────────


async def list_folders(ctx, dc, tok, parent_id="") -> dict:
    params = {"parent_id": parent_id} if parent_id else {}
    resp = await ctx.http.get(_api(dc, "/folders"), headers=_headers(tok), params=params)
    return _check_status(resp, "list folders")


async def get_folder(ctx, dc, tok, folder_id: str) -> dict:
    resp = await ctx.http.get(_api(dc, f"/folders/{folder_id}"), headers=_headers(tok))
    return _check_status(resp, "get folder")


async def create_folder(ctx, dc, tok, name: str, parent_id: str = "") -> dict:
    payload = {"name": name}
    if parent_id:
        payload["parent_id"] = parent_id
    resp = await ctx.http.post(_api(dc, "/folders"), headers=_headers(tok), json=payload)
    return _check_status(resp, "create folder")


async def update_folder(ctx, dc, tok, folder_id: str, name: str) -> dict:
    resp = await ctx.http.put(_api(dc, f"/folders/{folder_id}"), headers=_headers(tok),
                               json={"name": name})
    return _check_status(resp, "update folder")


async def delete_folder(ctx, dc, tok, folder_id: str) -> dict:
    resp = await ctx.http.delete(_api(dc, f"/folders/{folder_id}"), headers=_headers(tok))
    return _check_status(resp, "delete folder")


async def list_projects(ctx, dc, tok) -> dict:
    resp = await ctx.http.get(_api(dc, "/projects"), headers=_headers(tok))
    return _check_status(resp, "list projects")


async def update_project(ctx, dc, tok, project_id: str, name: str) -> dict:
    resp = await ctx.http.put(_api(dc, f"/projects/{project_id}"), headers=_headers(tok),
                               json={"name": name})
    return _check_status(resp, "update project")


async def delete_project(ctx, dc, tok, project_id: str) -> dict:
    resp = await ctx.http.delete(_api(dc, f"/projects/{project_id}"), headers=_headers(tok))
    return _check_status(resp, "delete project")


# ──────────────────────────────────────────────────────────────────────────
# Tags + Tag assignments
# ──────────────────────────────────────────────────────────────────────────


async def list_tags(ctx, dc, tok, page=1, per_page=100) -> dict:
    resp = await ctx.http.get(_api(dc, "/tags"), headers=_headers(tok),
                               params={"page": page, "per_page": per_page})
    return _check_status(resp, "list tags")


async def create_tag(ctx, dc, tok, name: str) -> dict:
    resp = await ctx.http.post(_api(dc, "/tags"), headers=_headers(tok), json={"name": name})
    return _check_status(resp, "create tag")


async def update_tag(ctx, dc, tok, tag_id: str, name: str) -> dict:
    resp = await ctx.http.put(_api(dc, f"/tags/{tag_id}"), headers=_headers(tok), json={"name": name})
    return _check_status(resp, "update tag")


async def delete_tag(ctx, dc, tok, tag_id: str) -> dict:
    resp = await ctx.http.delete(_api(dc, f"/tags/{tag_id}"), headers=_headers(tok))
    return _check_status(resp, "delete tag")


async def add_tag_assignment(ctx, dc, tok, taggable_type: str, taggable_id: str, tag_ids: list[str]) -> dict:
    payload = {"taggable_type": taggable_type, "taggable_id": taggable_id, "tag_ids": tag_ids}
    resp = await ctx.http.post(_api(dc, "/tag_assignments"), headers=_headers(tok), json=payload)
    return _check_status(resp, "add tag assignment")


async def remove_tag_assignment(ctx, dc, tok, taggable_type: str, taggable_id: str, tag_ids: list[str]) -> dict:
    payload = {"taggable_type": taggable_type, "taggable_id": taggable_id, "tag_ids": tag_ids}
    resp = await ctx.http.delete(_api(dc, "/tag_assignments"), headers=_headers(tok), json=payload)
    return _check_status(resp, "remove tag assignment")


# ──────────────────────────────────────────────────────────────────────────
# Lookup tables (full CRUD, including rows)
# ──────────────────────────────────────────────────────────────────────────


async def list_lookup_tables(ctx, dc, tok, page=1, per_page=100) -> dict:
    resp = await ctx.http.get(_api(dc, "/lookup_tables"), headers=_headers(tok),
                               params={"page": page, "per_page": per_page})
    return _check_status(resp, "list lookup tables")


async def create_lookup_table(ctx, dc, tok, name: str, schema: list, folder_id: str = "") -> dict:
    payload = {"name": name, "schema": schema}
    if folder_id:
        payload["folder_id"] = folder_id
    resp = await ctx.http.post(_api(dc, "/lookup_tables"), headers=_headers(tok), json=payload)
    return _check_status(resp, "create lookup table")


async def batch_delete_lookup_tables(ctx, dc, tok, lookup_table_ids: list[str]) -> dict:
    resp = await ctx.http.post(_api(dc, "/lookup_tables/batch_delete"), headers=_headers(tok),
                                json={"lookup_table_ids": lookup_table_ids})
    return _check_status(resp, "batch delete lookup tables")


async def list_lookup_table_rows(ctx, dc, tok, lookup_table_id: str, page=1, per_page=100) -> dict:
    resp = await ctx.http.get(_api(dc, f"/lookup_tables/{lookup_table_id}/rows"),
                               headers=_headers(tok), params={"page": page, "per_page": per_page})
    return _check_status(resp, "list lookup table rows")


async def lookup_row(ctx, dc, tok, lookup_table_id: str, filters: dict) -> dict:
    resp = await ctx.http.get(_api(dc, f"/lookup_tables/{lookup_table_id}/lookup"),
                               headers=_headers(tok), params=filters)
    return _check_status(resp, "look up a row")


async def get_lookup_table_row(ctx, dc, tok, lookup_table_id: str, row_id: str) -> dict:
    resp = await ctx.http.get(_api(dc, f"/lookup_tables/{lookup_table_id}/rows/{row_id}"),
                               headers=_headers(tok))
    return _check_status(resp, "get lookup table row")


async def add_lookup_table_row(ctx, dc, tok, lookup_table_id: str, row: dict) -> dict:
    resp = await ctx.http.post(_api(dc, f"/lookup_tables/{lookup_table_id}/rows"),
                                headers=_headers(tok), json={"row": row})
    return _check_status(resp, "add lookup table row")


async def update_lookup_table_row(ctx, dc, tok, lookup_table_id: str, row_id: str, row: dict) -> dict:
    resp = await ctx.http.put(_api(dc, f"/lookup_tables/{lookup_table_id}/rows/{row_id}"),
                               headers=_headers(tok), json={"row": row})
    return _check_status(resp, "update lookup table row")


async def delete_lookup_table_row(ctx, dc, tok, lookup_table_id: str, row_id: str) -> dict:
    resp = await ctx.http.delete(_api(dc, f"/lookup_tables/{lookup_table_id}/rows/{row_id}"),
                                  headers=_headers(tok))
    return _check_status(resp, "delete lookup table row")


# ──────────────────────────────────────────────────────────────────────────
# Environment properties
# ──────────────────────────────────────────────────────────────────────────


async def list_properties_by_prefix(ctx, dc, tok, prefix: str) -> dict:
    resp = await ctx.http.get(_api(dc, "/properties"), headers=_headers(tok),
                               params={"prefix": prefix})
    return _check_status(resp, "list properties by prefix")


async def upsert_properties(ctx, dc, tok, properties: dict) -> dict:
    resp = await ctx.http.post(_api(dc, "/properties"), headers=_headers(tok),
                                json={"properties": properties})
    return _check_status(resp, "upsert properties")


# ──────────────────────────────────────────────────────────────────────────
# Environment management: secrets cache
# ──────────────────────────────────────────────────────────────────────────


async def clear_secrets_cache(ctx, dc, tok) -> dict:
    resp = await ctx.http.post(_api(dc, "/secrets_management/clear_cache"), headers=_headers(tok))
    return _check_status(resp, "clear secrets management cache")


# ──────────────────────────────────────────────────────────────────────────
# Recipe lifecycle management: export manifests + packages
# ──────────────────────────────────────────────────────────────────────────


async def view_folder_assets(ctx, dc, tok, folder_id: str = "") -> dict:
    params = {"folder_id": folder_id} if folder_id else {}
    resp = await ctx.http.get(_api(dc, "/export_manifests/folder_assets"), headers=_headers(tok), params=params)
    return _check_status(resp, "view folder assets")


async def create_export_manifest(ctx, dc, tok, name: str, folder_id: str, asset_ids: list[dict]) -> dict:
    payload = {"name": name, "folder_id": folder_id, "assets": asset_ids}
    resp = await ctx.http.post(_api(dc, "/export_manifests"), headers=_headers(tok), json=payload)
    return _check_status(resp, "create export manifest")


async def update_export_manifest(ctx, dc, tok, manifest_id: str, asset_ids: list[dict]) -> dict:
    resp = await ctx.http.put(_api(dc, f"/export_manifests/{manifest_id}"), headers=_headers(tok),
                               json={"assets": asset_ids})
    return _check_status(resp, "update export manifest")


async def get_export_manifest(ctx, dc, tok, manifest_id: str) -> dict:
    resp = await ctx.http.get(_api(dc, f"/export_manifests/{manifest_id}"), headers=_headers(tok))
    return _check_status(resp, "get export manifest")


async def delete_export_manifest(ctx, dc, tok, manifest_id: str) -> dict:
    resp = await ctx.http.delete(_api(dc, f"/export_manifests/{manifest_id}"), headers=_headers(tok))
    return _check_status(resp, "delete export manifest")


async def export_package(ctx, dc, tok, manifest_id: str) -> dict:
    resp = await ctx.http.post(_api(dc, f"/packages/export/{manifest_id}"), headers=_headers(tok))
    return _check_status(resp, "export package")


async def import_package(ctx, dc, tok, folder_id: str, package_file_url: str,
                          restart_recipes: bool = False) -> dict:
    payload = {"package_file_url": package_file_url, "restart_recipes": restart_recipes}
    resp = await ctx.http.post(_api(dc, f"/packages/import/{folder_id}"), headers=_headers(tok), json=payload)
    return _check_status(resp, "import package")


async def get_package(ctx, dc, tok, package_id: str) -> dict:
    resp = await ctx.http.get(_api(dc, f"/packages/{package_id}"), headers=_headers(tok))
    return _check_status(resp, "get package")


async def get_package_download_url(ctx, dc, tok, package_id: str) -> dict:
    resp = await ctx.http.get(_api(dc, f"/packages/{package_id}/download"), headers=_headers(tok))
    return _check_status(resp, "download package")
