"""The MCP server: registration, transport and the ASGI app.

Transport is stateless streamable HTTP with JSON responses. Stateless removes
session affinity concerns behind the tunnel, and JSON responses avoid streaming
SSE through Cloudflare entirely.
"""

from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from vipu_mcp import config, prompts, resources
from vipu_mcp.auth import BearerTokenMiddleware
from vipu_mcp.client import VipuClient
from vipu_mcp.oauth import REQUIRED_SCOPES, OAuthTokenVerifier
from vipu_mcp.tools import manage, plan, read, record

INSTRUCTIONS = """\
Vipu is a balance-based personal finance tracker: it follows account balances \
and recurring obligations rather than individual transactions. There is no \
"log a spend" tool, because there are no transactions to log; the equivalent is \
updating a balance and taking a snapshot.

Start with get_financial_summary for anything open-ended. It frames every \
figure the other tools return.\
"""


def build_server(
    client: VipuClient,
    read_only: bool | None = None,
    *,
    oauth: config.OAuthConfig | None = None,
    token_verifier: TokenVerifier | None = None,
) -> MCPServer:
    """An MCPServer with every tool this deployment should expose.

    ``read_only`` defaults to the VIPU_MCP_READ_ONLY flag. When set, the write
    tools are not registered at all rather than registered and refused: a tool
    the model cannot see is one it cannot plan around.
    """
    if read_only is None:
        read_only = config.VIPU_MCP_READ_ONLY

    server = MCPServer(
        name="vipu",
        title="Vipu",
        version="0.1.0",
        instructions=INSTRUCTIONS,
        auth=(
            AuthSettings.model_validate(
                {
                    # Let AuthSettings preserve the issuer's exact spelling;
                    # constructing AnyHttpUrl first adds a spurious slash.
                    "issuer_url": oauth.issuer,
                    "resource_server_url": oauth.resource_url,
                    "required_scopes": REQUIRED_SCOPES,
                    "validate_token_resource": True,
                }
            )
            if oauth
            else None
        ),
        token_verifier=token_verifier,
    )

    @server.custom_route("/health", methods=["GET"], include_in_schema=False)
    async def health(_request: Request) -> JSONResponse:
        """Unauthenticated liveness probe for the compose healthcheck."""
        return JSONResponse({"status": "ok"})

    read.register(server, client)
    # project_fire and forecast_net_worth compute and store nothing, so they
    # belong on the read side of the flag; the two update_* tools do not.
    plan.register(server, client, read_only=read_only)
    if not read_only:
        record.register(server, client)
        manage.register(server, client)

    resources.register(server, client)
    prompts.register(server, read_only=read_only)
    return server


def build_app(server: MCPServer, token: str = "") -> ASGIApp:
    """The ASGI app: public health/discovery, authenticated MCP requests."""
    if server.settings.auth is None and not token:
        raise ValueError("Configure OAuth or a non-empty MCP_AUTH_TOKEN")
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        # DNS rebinding protection off, explicitly rather than by omission:
        # passing None here would auto-enable it for the default 127.0.0.1 host
        # and reject every request, since the Cloudflare tunnel forwards the
        # public hostname as Host and this container cannot enumerate it. The
        # access token is the gate that actually matters.
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )
    if server.settings.auth is not None:
        return app
    return BearerTokenMiddleware(app, token)


def create_app() -> ASGIApp:
    """Entry point for uvicorn: uvicorn vipu_mcp.server:create_app --factory."""
    oauth = config.oauth_config()
    if oauth is not None:
        verifier = OAuthTokenVerifier(oauth, legacy_token=config.MCP_AUTH_TOKEN)
        return build_app(
            build_server(VipuClient(), oauth=oauth, token_verifier=verifier)
        )
    token = config.require_auth_token()
    return build_app(build_server(VipuClient()), token)
