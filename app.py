"""Extension declaration, secrets, lifecycle hooks.

WHY BYOK, SAME REASONING AS n8n Connector / Make.com Connector.

Workato is a platform the USER runs their own paid workspace on -- not
something Imperal can broker centrally. The user pastes their own API
Client Bearer token once, Vault-encrypted via `ctx.secrets`, and every
call runs against their own Workato workspace.

WHY ONE SECRET (api_token) PLUS A DISCOVERED data_center, NOT TWO USER-
ENTERED SECRETS THE WAY n8n Connector ASKS FOR base_url DIRECTLY.

Workato has a small FIXED set of data-center hosts (US/EU/JP/SG/AU/IL/
CN/KR/UK/trial -- docs.workato.com/workato-api, "Base URL" section) --
the same shape as Make.com's zone list (eu1/eu2/us1/us2), not the
unbounded, self-hosted-anywhere shape of n8n's base_url. So this
connector follows Make.com Connector's pattern: probe the known hosts
with the cheap, side-effect-free `GET /api/users/me` call, persist the
winning host as a second (system-written) secret, and only ask the user
for the one thing they actually hold -- their own token.

WHY `Authorization: Bearer <api_token>`, NOT the legacy full-access key.

Workato's own docs recommend API Clients (Bearer token, role + project
scoped) over the legacy full-access API key + email scheme.

WHY `write_mode="both"`, SAME REASONING AS n8n Connector / Make.com
Connector.

Declaring `write_mode="user"` would mean only the platform's generic
Secrets screen could write these -- leaving a first-time user with no
in-app screen explaining what a Workato API Client token even is or
whether what they pasted actually works. `write_mode="both"` keeps the
platform Secrets screen working AND lets this extension's own
`connect_workato` validate the token against the user's own workspace
*before* writing it.
"""

from imperal_sdk import Extension, ChatExtension

ext = Extension(
    "workato-connector",
    version="0.1.0",
    display_name="Workato",
    description=(
        "Connect your own Workato workspace to see and manage your "
        "recipes from Imperal -- list/create/update/copy/delete recipes, "
        "start/stop them, force a run, inspect their jobs, manage "
        "connections, folders/projects, tags, lookup tables (full "
        "row-level CRUD), environment properties, and recipe lifecycle "
        "packages. Your Workato API Client token is verified against "
        "your own workspace before it's saved."
    ),
    icon="icon.svg",
    actions_explicit=True,
    capabilities=["workato:read", "workato:write"],
)

chat = ChatExtension(
    ext,
    tool_name="workato-connector",
    description="View and manage your Workato recipes, connections, jobs and lookup tables",
)

ext.secret(
    name="workato_api_token",
    description=(
        "Workato API Client Bearer token -- create it in your workspace: "
        "Workspace admin -> API clients -> Create API client, assign it a "
        "role and project scope, then copy its token. Verified against "
        "your workspace before saving."
    ),
    write_mode="both",
)
ext.secret(
    name="workato_data_center",
    description=(
        "Workato data-center host this token was verified against "
        "(e.g. app.eu.workato.com). Discovered automatically by "
        "connect_workato -- you never need to set this yourself."
    ),
    write_mode="both",
)


@ext.health_check
async def health_check(ctx) -> bool:
    """Basic liveness check -- confirms the store surface is reachable."""
    await ctx.store.query("workato_app_settings", limit=1)
    return True
