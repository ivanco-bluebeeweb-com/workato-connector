"""Pydantic params models + SDL entity contracts for Workato Connector.

All params models are module-scope (V17 federal invariant, same rule as
n8n Connector's / Make.com Connector's schemas.py).
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from imperal_sdk import sdl


class NoParams(BaseModel):
    """Explicit empty params model -- V17 disallows untyped handlers."""
    pass


# ──────────────────────────────────────────────────────────────────────────
# Connection
# ──────────────────────────────────────────────────────────────────────────


class ConnectWorkatoParams(BaseModel):
    api_token: str = Field(
        "",
        description=(
            "Workato API Client Bearer token -- create it in your workspace: "
            "Workspace admin -> API clients -> Create API client, assign it a "
            "role and project scope, then copy its token."
        ),
    )


class ProviderConnection(sdl.Entity):
    id: str = ""
    title: str = ""
    connected: bool = False
    data_center: str = ""
    detail: str = ""


class DeleteResult(sdl.Entity):
    id: str = ""
    title: str = ""
    deleted: bool = False


# ──────────────────────────────────────────────────────────────────────────
# Recipes
# ──────────────────────────────────────────────────────────────────────────


class ListRecipesParams(BaseModel):
    folder_id: str = Field("", description="Filter to one folder. Empty for all reachable folders.")
    project_id: str = Field("", description="Filter to one project. Empty for all.")
    running: bool | None = Field(None, description="Filter by running/stopped state. Omit for all.")
    page: int = Field(1, ge=1, description="Page number.")
    per_page: int = Field(100, ge=1, le=100, description="Page size, max 100.")


class WorkatoRecipe(sdl.Entity):
    id: str = ""
    title: str = ""
    name: str = ""
    running: bool = False
    folder_id: str = ""
    project_id: str = ""
    trigger_application: str = ""
    action_applications: list[str] = Field(default_factory=list)
    job_succeeded_count: int = 0
    job_failed_count: int = 0
    lifetime_task_count: int = 0
    last_run_at: str = ""
    webhook_url: str = ""


class WorkatoRecipeList(sdl.EntityList[WorkatoRecipe]):
    pass


class GetRecipeParams(BaseModel):
    recipe_id: str = Field(..., description="Workato recipe id (see list_workato_recipes).")
    include_tags: bool = Field(False, description="Include the recipe's tags in the response.")


class CreateRecipeParams(BaseModel):
    name: str = Field(..., description="Recipe name.")
    folder_id: str = Field("", description="Folder to create the recipe in. Empty for root.")


class UpdateRecipeParams(BaseModel):
    recipe_id: str = Field(..., description="Workato recipe id to update.")
    name: str = Field("", description="New recipe name. Leave empty to keep unchanged.")


class CopyRecipeParams(BaseModel):
    recipe_id: str = Field(..., description="Workato recipe id to copy.")
    folder_id: str = Field("", description="Folder to place the copy in. Empty keeps the source's folder.")


class RecipeIdParams(BaseModel):
    recipe_id: str = Field(..., description="Workato recipe id.")


class RecipeActionResult(sdl.Entity):
    id: str = ""
    title: str = ""
    recipe_id: str = ""
    running: bool = False
    status: str = ""


class ReconnectRecipeParams(BaseModel):
    recipe_id: str = Field(..., description="Workato recipe id (must be stopped).")
    connection_id: str = Field(..., description="New connection id to use for this recipe's application.")


class ListRecipeVersionsParams(BaseModel):
    recipe_id: str = Field(..., description="Workato recipe id.")


class WorkatoRecipeVersion(sdl.Entity):
    id: str = ""
    title: str = ""
    version_id: str = ""
    recipe_id: str = ""
    comment: str = ""
    created_at: str = ""


class WorkatoRecipeVersionList(sdl.EntityList[WorkatoRecipeVersion]):
    pass


class GetRecipeVersionParams(BaseModel):
    recipe_id: str = Field(..., description="Workato recipe id.")
    version_id: str = Field(..., description="Recipe version id (see list_workato_recipe_versions).")


class RecipeHealthReport(sdl.Entity):
    id: str = ""
    title: str = ""
    recipe_id: str = ""
    summary: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Connections
# ──────────────────────────────────────────────────────────────────────────


class ListConnectionsParams(BaseModel):
    folder_id: str = Field("", description="Filter to one folder. Empty for all.")
    project_id: str = Field("", description="Filter to one project. Empty for all.")
    include_tags: bool = Field(False, description="Include each connection's tags in the response.")


class WorkatoConnection(sdl.Entity):
    id: str = ""
    title: str = ""
    name: str = ""
    provider: str = ""
    folder_id: str = ""
    authorized: bool = False
    external_id: str = ""


class WorkatoConnectionList(sdl.EntityList[WorkatoConnection]):
    pass


class CreateConnectionParams(BaseModel):
    name: str = Field(..., description="Connection display name.")
    provider: str = Field(..., description="Workato provider/adapter slug, e.g. 'salesforce', 'slack'.")
    folder_id: str = Field("", description="Folder to create the connection in. Empty for root.")
    input_json: str = Field("{}", description="JSON object of provider-specific connection input fields.")


class UpdateConnectionParams(BaseModel):
    connection_id: str = Field(..., description="Workato connection id to update.")
    name: str = Field("", description="New connection name. Leave empty to keep unchanged.")
    input_json: str = Field("", description="JSON object of provider-specific fields to change. Leave empty to keep unchanged.")


class ConnectionIdParams(BaseModel):
    connection_id: str = Field(..., description="Workato connection id.")


class ConnectionActionResult(sdl.Entity):
    id: str = ""
    title: str = ""
    connection_id: str = ""
    authorized: bool = False


class GetConnectionPicklistParams(BaseModel):
    connection_id: str = Field(..., description="Workato connection id.")
    picklist_name: str = Field(..., description="Name of the picklist to fetch, as defined by the connection's provider adapter.")
    extra_json: str = Field("{}", description="JSON object of extra picklist-dependent parameters, if the picklist needs them.")


class PicklistValue(sdl.Entity):
    id: str = ""
    title: str = ""
    label: str = ""
    value: str = ""


class PicklistValueList(sdl.EntityList[PicklistValue]):
    pass


# ──────────────────────────────────────────────────────────────────────────
# Jobs
# ──────────────────────────────────────────────────────────────────────────


class ListRecipeJobsParams(BaseModel):
    recipe_id: str = Field(..., description="Workato recipe id whose jobs to list.")
    since: str = Field("", description="ISO8601 -- only jobs completed after this time.")
    until: str = Field("", description="ISO8601 -- only jobs completed before this time.")
    status: str = Field("", description="Filter: succeeded, failed. Empty for all.")
    page: int = Field(1, ge=1, description="Page number.")
    per_page: int = Field(100, ge=1, le=100, description="Page size, max 100.")


class WorkatoJob(sdl.Entity):
    id: str = ""
    title: str = ""
    job_id: str = ""
    recipe_id: str = ""
    status: str = ""
    started_at: str = ""
    completed_at: str = ""
    is_error: bool = False
    error: str = ""


class WorkatoJobList(sdl.EntityList[WorkatoJob]):
    pass


class GetJobParams(BaseModel):
    job_id: str = Field(..., description="Workato job id (see list_workato_recipe_jobs).")
    include_var: bool = Field(False, description="Include run-time input/output variable data (larger response).")


class RepeatJobsParams(BaseModel):
    job_ids: list[str] = Field(..., description="Job ids to re-run with their original trigger input.")


class RepeatJobsResult(sdl.Entity):
    id: str = ""
    title: str = ""
    requested_count: int = 0
    repeated_count: int = 0


# ──────────────────────────────────────────────────────────────────────────
# Folders / Projects
# ──────────────────────────────────────────────────────────────────────────


class ListFoldersParams(BaseModel):
    parent_id: str = Field("", description="List only children of this folder. Empty for the root folder's children.")


class WorkatoFolder(sdl.Entity):
    id: str = ""
    title: str = ""
    name: str = ""
    parent_id: str = ""
    is_project: bool = False
    project_id: str = ""


class WorkatoFolderList(sdl.EntityList[WorkatoFolder]):
    pass


class FolderIdParams(BaseModel):
    folder_id: str = Field(..., description="Workato folder id.")


class CreateFolderParams(BaseModel):
    name: str = Field(..., description="Folder (or project, if parent_id is empty and this becomes top-level) name.")
    parent_id: str = Field("", description="Parent folder id. Empty creates a top-level project.")
    is_project: bool = Field(False, description="True to create this as a top-level project (only meaningful when parent_id is empty).")


class UpdateFolderParams(BaseModel):
    folder_id: str = Field(..., description="Workato folder id to rename.")
    name: str = Field(..., description="New folder name.")


class ListProjectsParams(BaseModel):
    pass


class WorkatoProject(sdl.Entity):
    id: str = ""
    title: str = ""
    name: str = ""


class WorkatoProjectList(sdl.EntityList[WorkatoProject]):
    pass


class UpdateProjectParams(BaseModel):
    project_id: str = Field(..., description="Workato project id (a top-level folder) to rename.")
    name: str = Field(..., description="New project name.")


class ProjectIdParams(BaseModel):
    project_id: str = Field(..., description="Workato project id.")


# ──────────────────────────────────────────────────────────────────────────
# Tags + Tag assignments
# ──────────────────────────────────────────────────────────────────────────


class ListTagsParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number.")
    per_page: int = Field(100, ge=1, le=100, description="Page size, max 100.")


class WorkatoTag(sdl.Entity):
    id: str = ""
    title: str = ""
    name: str = ""


class WorkatoTagList(sdl.EntityList[WorkatoTag]):
    pass


class CreateTagParams(BaseModel):
    name: str = Field(..., description="Tag name.")


class UpdateTagParams(BaseModel):
    tag_id: str = Field(..., description="Workato tag id to rename.")
    name: str = Field(..., description="New tag name.")


class TagIdParams(BaseModel):
    tag_id: str = Field(..., description="Workato tag id.")


class TagAssignmentParams(BaseModel):
    taggable_type: str = Field(..., description="Asset type to tag/untag, e.g. 'Recipe', 'Connection', 'LookupTable'.")
    taggable_id: str = Field(..., description="Id of the asset to tag/untag.")
    tag_ids: list[str] = Field(..., description="Tag ids to add or remove.")


class TagAssignmentResult(sdl.Entity):
    id: str = ""
    title: str = ""
    taggable_id: str = ""
    tag_count: int = 0


# ──────────────────────────────────────────────────────────────────────────
# Lookup tables (full CRUD, including rows)
# ──────────────────────────────────────────────────────────────────────────


class ListLookupTablesParams(BaseModel):
    page: int = Field(1, ge=1, description="Page number.")
    per_page: int = Field(100, ge=1, le=100, description="Page size, max 100.")


class WorkatoLookupTable(sdl.Entity):
    id: str = ""
    title: str = ""
    name: str = ""
    project_id: str = ""
    table_schema: str = ""


class WorkatoLookupTableList(sdl.EntityList[WorkatoLookupTable]):
    pass


class CreateLookupTableParams(BaseModel):
    name: str = Field(..., description="Lookup table name.")
    table_schema: str = Field(..., description="JSON array of column definitions, e.g. "
                              '[{"control_type":"text","label":"code","name":"col1","type":"string","sticky":true}].')
    folder_id: str = Field("", description="Folder to create the table in. Empty for root.")


class BatchDeleteLookupTablesParams(BaseModel):
    lookup_table_ids: list[str] = Field(..., description="Lookup table ids to delete.")


class BatchDeleteResult(sdl.Entity):
    id: str = ""
    title: str = ""
    requested_count: int = 0
    deleted_count: int = 0


class ListLookupTableRowsParams(BaseModel):
    lookup_table_id: str = Field(..., description="Workato lookup table id.")
    page: int = Field(1, ge=1, description="Page number.")
    per_page: int = Field(100, ge=1, le=100, description="Page size, max 100.")


class WorkatoLookupTableRow(sdl.Entity):
    id: str = ""
    title: str = ""
    row_id: str = ""
    data_json: str = ""


class WorkatoLookupTableRowList(sdl.EntityList[WorkatoLookupTableRow]):
    pass


class LookupRowParams(BaseModel):
    lookup_table_id: str = Field(..., description="Workato lookup table id.")
    filters_json: str = Field(..., description='JSON object of column->value filters, e.g. {"col1":"US"}.')


class GetLookupTableRowParams(BaseModel):
    lookup_table_id: str = Field(..., description="Workato lookup table id.")
    row_id: str = Field(..., description="Row id (see list_workato_lookup_table_rows).")


class AddLookupTableRowParams(BaseModel):
    lookup_table_id: str = Field(..., description="Workato lookup table id.")
    row_json: str = Field(..., description='JSON object of column->value pairs for the new row, e.g. {"col1":"US","col2":"United States"}.')


class UpdateLookupTableRowParams(BaseModel):
    lookup_table_id: str = Field(..., description="Workato lookup table id.")
    row_id: str = Field(..., description="Row id to update.")
    row_json: str = Field(..., description="JSON object of column->value pairs to set on this row.")


class DeleteLookupTableRowParams(BaseModel):
    lookup_table_id: str = Field(..., description="Workato lookup table id.")
    row_id: str = Field(..., description="Row id to delete.")


# ──────────────────────────────────────────────────────────────────────────
# Environment properties
# ──────────────────────────────────────────────────────────────────────────


class ListPropertiesByPrefixParams(BaseModel):
    prefix: str = Field(..., description="Property name prefix, e.g. 'salesforce_sync.'.")


class WorkatoProperty(sdl.Entity):
    id: str = ""
    title: str = ""
    key: str = ""
    value: str = ""


class WorkatoPropertyList(sdl.EntityList[WorkatoProperty]):
    pass


class UpsertPropertiesParams(BaseModel):
    properties_json: str = Field(..., description='JSON object of property_key->value pairs to create or update, e.g. {"my.prop":"value"}.')


class UpsertPropertiesResult(sdl.Entity):
    id: str = ""
    title: str = ""
    success: bool = False


class ClearSecretsCacheResult(sdl.Entity):
    id: str = ""
    title: str = ""
    success: bool = False


# ──────────────────────────────────────────────────────────────────────────
# Recipe lifecycle management: export manifests + packages
# ──────────────────────────────────────────────────────────────────────────


class ViewFolderAssetsParams(BaseModel):
    folder_id: str = Field("", description="Folder to inspect assets in. Empty for the root folder.")


class WorkatoAsset(sdl.Entity):
    id: str = ""
    title: str = ""
    name: str = ""
    asset_type: str = ""
    version: int = 0
    absolute_path: str = ""


class WorkatoAssetList(sdl.EntityList[WorkatoAsset]):
    pass


class CreateExportManifestParams(BaseModel):
    name: str = Field(..., description="Export manifest name.")
    folder_id: str = Field(..., description="Folder the manifest's assets live in.")
    asset_ids_json: str = Field(..., description='JSON array of {"id": ..., "type": ...} asset references (see view_workato_folder_assets).')


class UpdateExportManifestParams(BaseModel):
    manifest_id: str = Field(..., description="Export manifest id to update.")
    asset_ids_json: str = Field(..., description="JSON array of asset references replacing the manifest's current asset list.")


class ManifestIdParams(BaseModel):
    manifest_id: str = Field(..., description="Workato export manifest id.")


class WorkatoManifest(sdl.Entity):
    id: str = ""
    title: str = ""
    name: str = ""
    folder_id: str = ""


class ExportPackageParams(BaseModel):
    manifest_id: str = Field(..., description="Export manifest id to build a package from.")


class WorkatoPackage(sdl.Entity):
    id: str = ""
    title: str = ""
    status: str = ""
    manifest_id: str = ""


class ImportPackageParams(BaseModel):
    folder_id: str = Field(..., description="Destination folder id to import the package into.")
    package_file_url: str = Field(..., description="URL of a previously downloaded package file (see get_workato_package_download_url).")
    restart_recipes: bool = Field(False, description="Restart any running recipes affected by the import.")


class PackageIdParams(BaseModel):
    package_id: str = Field(..., description="Workato package id (see export_workato_package).")


class PackageDownloadUrl(sdl.Entity):
    id: str = ""
    title: str = ""
    download_url: str = ""

