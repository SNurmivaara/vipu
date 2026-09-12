# OAuth for ChatGPT and Claude

Vipu is an OAuth resource server. Both web clients connect to the same HTTPS
`/mcp` URL and authenticate through an external authorization server. Authelia
handles login, consent, authorization code + PKCE S256, and rotating refresh
tokens. Vipu verifies RFC 9068 JWT access tokens using the provider's public keys.

This is independent of Authelia's Traefik forward-auth middleware. Do not put
that middleware in front of `/mcp` or OAuth discovery/token endpoints. A request
without an access token must receive a JSON `401` and `WWW-Authenticate`
discovery challenge. Browser login redirects belong to the authorization flow.
Keep the ordinary Vipu website and the rest of the homelab behind their
existing authentication.

## Configure Authelia

Use a current supported Authelia release. The example requires **4.39.23 or
later** for resource-indicator fixes. Back up its configuration and storage
before upgrading through your usual image-update process. If WUD watches a
mutable tag such as `latest`, enable `wud.watch.digest=true` on the service;
watching tag names alone will miss new releases with the same name.

Start with [the provider example](../deploy/authelia-oidc.example.yml). Merge
its `identity_providers.oidc` settings into your configuration, preserving any
existing provider keys and clients. Replace the sample domain and username,
generate an RSA signing key and HMAC secret, and generate a different client
secret for each client using
[Authelia's credential-generation instructions](https://www.authelia.com/integration/openid-connect/frequently-asked-questions/).
Store the **hash** in Authelia and the original secret in the corresponding
client's connector form. Keep all real credentials outside Git.

The example uses the `vipu` scope, restricted to these two clients and to the
specified user. Its claims policy includes `preferred_username` in the signed
access token. Vipu checks that claim against its own allowlist, in addition to
checking the client ID, issuer, audience, expiry, `openid` and `vipu` scopes.
Treat an allowlisted username as an access-control identity: remove it from
Vipu before deleting or reassigning the provider account. This remains a
single-dataset application; every allowed user can access the same finances.

Access tokens last ten minutes; refresh tokens last thirty days. Revoking a
refresh token prevents renewal; an already issued JWT can remain usable until
it expires. Removing a user or client from Vipu's allowlist and recreating the
service revokes their access immediately.

Validate the completed configuration with Authelia before applying it. Then
verify these public endpoints, using the issuer's actual discovery values:

```text
https://auth.example.com/.well-known/openid-configuration
https://auth.example.com/.well-known/oauth-authorization-server
https://auth.example.com/jwks.json
```

The metadata must advertise PKCE `S256`, authorization and token endpoints,
and the exact issuer. Enable all advertised OIDC scopes for the ChatGPT client;
ChatGPT requests them by default. The example enables Authelia's standard
OIDC scopes plus `vipu`. Both clients support pre-registered client IDs and
secrets, so Authelia does not need dynamic client registration.

## Configure Vipu

Set these environment variables on the MCP service through your deployment
configuration:

```dotenv
MCP_OAUTH_ISSUER=https://auth.example.com
MCP_OAUTH_RESOURCE_URL=https://vipu-mcp.example.com/mcp
MCP_OAUTH_JWKS_URL=https://auth.example.com/jwks.json
MCP_OAUTH_ALLOWED_CLIENTS=vipu-chatgpt,vipu-claude
MCP_OAUTH_ALLOWED_USERS=your-authelia-username
```

Copy the issuer and JWKS URL from discovery. The resource URL must be the
canonical public MCP URL, including `/mcp` and no trailing slash. Set the same
resource as the audience for both Authelia clients. Both clients send it in
the OAuth `resource` parameter; Vipu rejects tokens for any other audience.
All URLs must use HTTPS. User and client allowlists are comma-separated and
case-sensitive. Any partial OAuth configuration is a startup error.

Vipu never forwards access tokens to the financial backend. It accepts only
RS256 access tokens with the `at+jwt` type (also `application/at+jwt`); ID tokens,
unsigned tokens and tokens signed by another issuer fail authentication.
Signing keys are cached for five minutes with bounded refresh on rotation.
Expired key caches fail closed if the provider cannot be reached.

Release code through a PR and a published GitHub release. The release workflow
publishes the MCP image to GHCR, and WUD can update the deployed `latest` image.
Apply the environment settings with your normal Compose configuration process.
Do not copy edited Python into a running container or build a replacement
production image outside that workflow.

During migration, keep the existing `MCP_AUTH_TOKEN` configured. It will still
work alongside OAuth at the same `/mcp` URL. After both clients are connected
and verified with OAuth, remove it and recreate the MCP service. With neither
OAuth nor a legacy token configured, Vipu refuses to start.

## Connect ChatGPT web

Enable developer mode in ChatGPT's settings, then create a custom app/plugin
with MCP support (the setting names depend on your account). Enter:

| Field | Value |
| --- | --- |
| MCP server URL | `https://vipu-mcp.example.com/mcp` |
| Authentication | OAuth |
| OAuth client ID | `vipu-chatgpt` |
| OAuth client secret | Original ChatGPT client secret, not its hash |

Register the **exact callback URI shown by ChatGPT** in Authelia. Providers
advertising `authorization_response_iss_parameter_supported: true` and
returning the correct `iss` in authorization responses can use
`https://chatgpt.com/connector_platform_oauth_redirect`. Otherwise ChatGPT uses
a callback such as `https://chatgpt.com/connector/oauth/{callback_id}`. Never
substitute a wildcard. Save the connector, connect, sign in to Authelia, and
grant consent. Enable Vipu in a chat and ask for your financial summary.

The target here is ChatGPT web. Availability of custom developer apps on
mobile depends on the client and account; check separately after web works.

## Connect Claude web

In Settings → Connectors → Add custom connector, enter the same MCP server
URL. In the advanced OAuth fields enter `vipu-claude` and its original secret.
Register `https://claude.ai/api/mcp/auth_callback` in Authelia. Connect, sign in,
grant consent, then enable Vipu in a chat and ask for your financial summary.
The hosted Claude connector also serves Desktop and mobile. A local
`mcp-remote` bridge using the old token can remain in place during migration.

## Verify before removing the old token

```bash
curl -i https://vipu-mcp.example.com/health
curl -i -X POST https://vipu-mcp.example.com/mcp
curl -s https://vipu-mcp.example.com/.well-known/oauth-protected-resource/mcp
```

Expect health `200`, unauthenticated MCP `401` with `resource_metadata` in the
challenge, and public JSON metadata with the exact issuer/resource values.
Each client should initialize, list tools and call `get_financial_summary`
after browser consent. Verify token refresh after the ten-minute access-token
lifetime too. Use this read-only tool for production verification; `get_budget`
performs housekeeping and is not a read-only check.

An `insufficient_scope` response is `403`. Invalid or expired tokens produce
`401` so clients can refresh or reconnect. Discovery and signing-key requests
must be reachable from the clients' cloud servers without browser challenges.
If discovery works but linking fails, check the callback, issuer (including
trailing slash), `resource` audience, client authentication method, scopes and
PKCE configuration. Do not work around errors by disabling audience checks.

## References

- [OpenAI: OAuth authentication](https://developers.openai.com/plugins/build/auth)
- [OpenAI: developer mode](https://developers.openai.com/api/docs/guides/developer-mode)
- [Claude: connector authentication](https://claude.com/docs/connectors/building/authentication)
- [Authelia: OAuth client configuration](https://www.authelia.com/configuration/identity-providers/openid-connect/clients/)
- [Authelia: provider configuration](https://www.authelia.com/configuration/identity-providers/openid-connect/provider/)
