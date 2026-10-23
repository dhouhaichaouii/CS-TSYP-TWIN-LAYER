"""REST API Fallback Router for City Brain Convergence Twin Layer.

Provides a standard HTTP JSON REST interface backed by the exact same TwinFacade.
Acts as the failover safety net on stage if partner laptops encounter MCP client issues.
"""
import json
from typing import Any
from urllib.parse import parse_qs, urlparse

from twin_interface.envelope import ErrorCode, error_envelope, success_envelope
from twin_interface.facade import TwinFacade
from twin_interface.mcp_server.middleware import extract_bearer_token


def handle_rest_request(
    facade: TwinFacade,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Dispatch an inbound HTTP REST request through the TwinFacade.

    Args:
        facade: Active TwinFacade instance.
        method: HTTP method ('GET', 'POST').
        path: URL path with optional query string (e.g. '/api/v1/sensors?zone_id=PRT').
        headers: Inbound HTTP headers mapping.
        body: Optional parsed JSON request body dictionary.

    Returns:
        Tuple of (http_status_code: int, response_envelope_dict: dict).
    """
    parsed_url = urlparse(path)
    clean_path = parsed_url.path.rstrip("/")
    query_params = parse_qs(parsed_url.query)

    # 1. Health check (No auth required)
    if clean_path in ("", "/", "/health"):
        return 200, success_envelope(
            facade.run_id,
            {"status": "UP", "service": "Convergence City Twin Layer REST Gateway"},
        )

    # 2. Extract Bearer Token (Headers first, then query/body fallback)
    token = extract_bearer_token(headers or {})
    if not token and body:
        token = body.get("token")
    if not token and "token" in query_params:
        token = query_params["token"][0]

    # Helper to get first query param or None
    def get_query(key: str) -> str | None:
        val = query_params.get(key)
        return val[0] if val else None

    method_upper = method.upper()

    # --------------------------------------------------------------------------
    # GET /api/v1/sensors
    # --------------------------------------------------------------------------
    if method_upper == "GET" and clean_path == "/api/v1/sensors":
        zone_id = get_query("zone_id")
        sensor_id = get_query("sensor_id")
        sensor_type = get_query("sensor_type")
        resp = facade.get_sensor_readings(
            token=token,
            zone_id=zone_id,
            sensor_id=sensor_id,
            sensor_type=sensor_type,
        )
        status_code = 200 if resp["ok"] else (401 if resp["error"]["code"] == ErrorCode.NOT_AUTHORIZED else 400)
        return status_code, resp

    # --------------------------------------------------------------------------
    # GET /api/v1/state
    # --------------------------------------------------------------------------
    if method_upper == "GET" and clean_path == "/api/v1/state":
        zone_id = get_query("zone_id")
        resp = facade.get_city_state(token=token, zone_id=zone_id)
        status_code = 200 if resp["ok"] else (401 if resp["error"]["code"] == ErrorCode.NOT_AUTHORIZED else 400)
        return status_code, resp

    # --------------------------------------------------------------------------
    # GET /api/v1/events
    # --------------------------------------------------------------------------
    if method_upper == "GET" and clean_path == "/api/v1/events":
        seq_str = get_query("seq") or "0"
        try:
            seq = int(seq_str)
        except ValueError:
            seq = 0
        resp = facade.get_events_since(token=token, seq=seq)
        status_code = 200 if resp["ok"] else (401 if resp["error"]["code"] == ErrorCode.NOT_AUTHORIZED else 400)
        return status_code, resp

    # --------------------------------------------------------------------------
    # POST /api/v1/commands
    # --------------------------------------------------------------------------
    if method_upper == "POST" and clean_path == "/api/v1/commands":
        payload = body or {}
        device_id = payload.get("device_id")
        command = payload.get("command")
        params = payload.get("params", {})
        request_id = payload.get("request_id")
        context = payload.get("context")

        if not device_id or not command or not request_id:
            return 400, error_envelope(
                facade.run_id,
                ErrorCode.INVALID_PARAM,
                "Missing required fields: device_id, command, and request_id are mandatory.",
            )

        resp = facade.send_actuator_command(
            token=token,
            device_id=device_id,
            command=command,
            params=params,
            request_id=request_id,
            context=context,
        )
        status_code = 200 if resp["ok"] else (
            401 if resp["error"]["code"] == ErrorCode.NOT_AUTHORIZED
            else (403 if resp["error"]["code"] == ErrorCode.GUARDIAN_RESTRICTED else 400)
        )
        return status_code, resp

    # --------------------------------------------------------------------------
    # POST /api/v1/isolate
    # --------------------------------------------------------------------------
    if method_upper == "POST" and clean_path == "/api/v1/isolate":
        payload = body or {}
        device_id = payload.get("device_id")
        reason = payload.get("reason", "")

        if not device_id:
            return 400, error_envelope(
                facade.run_id,
                ErrorCode.INVALID_PARAM,
                "Missing required field: device_id is mandatory.",
            )

        resp = facade.isolate_device(token=token, device_id=device_id, reason=reason)
        status_code = 200 if resp["ok"] else (401 if resp["error"]["code"] == ErrorCode.NOT_AUTHORIZED else 400)
        return status_code, resp

    # --------------------------------------------------------------------------
    # POST /api/v1/restore
    # --------------------------------------------------------------------------
    if method_upper == "POST" and clean_path == "/api/v1/restore":
        payload = body or {}
        device_id = payload.get("device_id")

        if not device_id:
            return 400, error_envelope(
                facade.run_id,
                ErrorCode.INVALID_PARAM,
                "Missing required field: device_id is mandatory.",
            )

        resp = facade.restore_device(token=token, device_id=device_id)
        status_code = 200 if resp["ok"] else (401 if resp["error"]["code"] == ErrorCode.NOT_AUTHORIZED else 400)
        return status_code, resp

    # Endpoint not found
    return 404, error_envelope(
        facade.run_id,
        "ROUTE_NOT_FOUND",
        f"Path '{clean_path}' with method '{method_upper}' not recognized.",
    )
