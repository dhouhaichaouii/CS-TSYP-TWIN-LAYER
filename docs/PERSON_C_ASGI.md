# Person C unified ASGI application

`src/twin_app.py` is the network-facing application entry point. Its FastAPI
lifespan creates one `LiveCity`, one `TwinFacade`, one FastMCP server, one
in-memory event store, and one JSONL logger. The REST routes and the mounted
MCP server share that same facade and runtime.

## Local startup

Install the declared project dependencies, set the required environment
variables, then run from the repository root:

```text
python src/twin_app.py
```

The process binds to `0.0.0.0` and uses `PORT` (default `8000`). It runs one
Uvicorn process. Do not set `TWIN_ALLOW_INSECURE_DEV_TOKENS`; startup rejects
development-token mode.

Required environment variables:

| Variable | Purpose |
|---|---|
| `TWIN_TOKEN_BRAIN` | Brain role credential; unique, at least 32 characters, and 16 distinct characters |
| `TWIN_TOKEN_GUARDIAN` | Guardian role credential; unique, at least 32 characters, and 16 distinct characters |
| `TWIN_TOKEN_OPERATOR` | Operator role credential; unique, at least 32 characters, and 16 distinct characters |
| `TWIN_TOKEN_EVALUATOR` | Evaluator role credential; unique, at least 32 characters, and 16 distinct characters |
| `TWIN_ALLOWED_HOSTS` | Comma-separated exact HTTP hostnames accepted by the app and MCP |

Optional variables:

| Variable | Purpose |
|---|---|
| `PORT` | Public HTTP port; defaults to `8000` |
| `TWIN_ALLOWED_ORIGINS` | Comma-separated exact HTTP(S) origins for browser clients |
| `TWIN_RUN_ID` | Explicit simulation run ID; otherwise generated at startup |
| `TWIN_LOG_DIR` | JSONL log directory; defaults to `logs` |
| `TWIN_TRUSTED_PROXY_IPS` | Uvicorn trusted reverse-proxy IPs/CIDRs; defaults to `127.0.0.1` |

Generate independent credentials from cryptographically secure randomness
(for example, `secrets.token_urlsafe(32)`) and store each in the host's secret
manager. The startup length/diversity checks reject obvious weak values but
cannot measure a token's actual randomness. Never reuse a role's credential
for another role.

Hostnames are exact entries, without schemes, ports, or paths. Include the
Railway-provided public domain (for example, `service-name.up.railway.app`) in
`TWIN_ALLOWED_HOSTS`; do not use `*`. The FastAPI TrustedHost middleware and
MCP DNS-rebinding protection both enforce this list. MCP accepts requests with
no `Origin` header; if `Origin` is supplied, it must exactly match
`TWIN_ALLOWED_ORIGINS`. Configure origins only for browser-based clients. CORS
is enabled only when that list is non-empty.

REST and MCP require `Authorization: Bearer <role-token>`. MCP authentication
happens before the Streamable HTTP app or any tool runs. Tokens are not MCP
tool arguments. REST rejects credentials in URLs and JSON bodies. Missing or
invalid credentials return HTTP 401; authenticated roles lacking permission
receive HTTP 403. The built-in development tokens and development-token mode
are rejected at startup.

Public HTTPS is terminated by Railway's proxy; the app validates the original
`Host` header and uses Uvicorn proxy headers for scheme/client metadata. Set
`TWIN_TRUSTED_PROXY_IPS` only to the actual ingress proxy IPs/CIDRs for the
deployment; do not trust arbitrary forwarded headers. The app does not use
`X-Forwarded-Host` to bypass its Host allowlist. Uvicorn access logging is
disabled so credential-bearing URLs cannot be copied to access logs.

REST example (use HTTPS on the public deployment):

```text
curl https://service-name.up.railway.app/api/v1/sensors -H "Authorization: Bearer ${TWIN_TOKEN_BRAIN}"
```

Independent MCP clients must send the credential as an HTTP header, not a tool
argument:

```python
async with streamablehttp_client(
    "https://service-name.up.railway.app/mcp/",
    headers={"Authorization": f"Bearer {brain_token}"},
) as (read_stream, write_stream, _):
    async with ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        readings = await session.call_tool("get_sensor_readings", {})
```

## Routes

| Interface | Endpoint |
|---|---|
| MCP Streamable HTTP | `POST /mcp/` (Bearer header required for all MCP requests) |
| REST sensors | `GET /api/v1/sensors` |
| REST city state | `GET /api/v1/state` |
| REST events / timeline | `GET /api/v1/events`, `GET /api/v1/timeline` |
| REST command / isolation | `POST /api/v1/commands`, `/api/v1/isolate`, `/api/v1/restore` |
| Readiness / liveness | `GET /health/ready`, `/health/live` |
| OpenAPI UI / schema | `/docs`, `/openapi.json` |

The REST layer adapts HTTP requests to the existing `handle_rest_request`
dispatcher; authorization and domain actions remain in `TwinFacade`. MCP tools
read the authenticated request header through FastMCP context and then invoke
the same facade checks.

The event store and simulation are process-local. JSONL files are local
filesystem output; persistence across container replacement requires an
external volume and configuring `TWIN_LOG_DIR` to its mount path. The app uses
one Uvicorn worker; keep one replica until shared simulation state is
implemented.
