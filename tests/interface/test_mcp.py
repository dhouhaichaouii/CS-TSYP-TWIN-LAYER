"""Test suite for FastMCP server, middleware, and REST fallback router.

Verifies that external LLM agents and HTTP REST clients can discover tools,
authenticate, query telemetry, and dispatch actuator commands through the TwinFacade.
"""
import asyncio
import unittest

from city_live.runtime import LiveCity
from twin_interface.auth import DEFAULT_TOKENS, Role
from twin_interface.envelope import ErrorCode
from twin_interface.facade import TwinFacade
from twin_interface.mcp_server.middleware import extract_bearer_token, resolve_header_role
from twin_interface.mcp_server.server import create_mcp_server
from twin_interface.rest.router import handle_rest_request


class MCPServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.city = LiveCity("test-mcp-01")
        self.facade = TwinFacade(self.city)
        self.mcp = create_mcp_server(self.facade)

        self.brain_token = DEFAULT_TOKENS[Role.BRAIN]
        self.guardian_token = DEFAULT_TOKENS[Role.GUARDIAN]

    async def asyncTearDown(self):
        self.city.close()

    async def test_tool_discovery_and_docstrings(self):
        """Verify all core tools are registered with detailed descriptions for LLMs."""
        tools = await self.mcp.list_tools()
        tool_names = {t.name for t in tools}

        expected_tools = {
            "get_sensor_readings",
            "get_city_state",
            "get_events_since",
            "send_actuator_command",
            "isolate_device",
            "restore_device",
        }
        self.assertTrue(expected_tools.issubset(tool_names), f"Missing tools: {expected_tools - tool_names}")

        # Check that every tool has a descriptive docstring
        for tool in tools:
            self.assertTrue(tool.description and len(tool.description) > 20, f"Tool {tool.name} lacks rich docstring")

    async def test_mcp_get_sensor_readings(self):
        """Verify invoking get_sensor_readings via MCP call_tool."""
        content, meta = await self.mcp.call_tool("get_sensor_readings", {"zone_id": "PRT"})
        resp = meta.get("result", meta)
        self.assertTrue(resp["ok"])
        self.assertIn("readings", resp["data"])

    async def test_mcp_actuator_and_quarantine_lifecycle(self):
        """Verify end-to-end command dispatch, isolation, and quarantine blocking over MCP."""
        device = "V-12"

        # 1. Brain sends command to valve V-12
        _, meta1 = await self.mcp.call_tool(
            "send_actuator_command",
            {
                "device_id": device,
                "command": "set_opening",
                "params": {"open_pct": 75.0},
                "request_id": "req-mcp-01",
                "token": self.brain_token,
            },
        )
        resp1 = meta1.get("result", meta1)
        self.assertTrue(resp1["ok"])
        self.assertEqual(resp1["data"]["status"], "APPLIED")

        # 2. Guardian isolates valve V-12
        _, meta2 = await self.mcp.call_tool(
            "isolate_device",
            {
                "device_id": device,
                "reason": "Suspected cyber manipulation",
                "token": self.guardian_token,
            },
        )
        resp2 = meta2.get("result", meta2)
        self.assertTrue(resp2["ok"])
        self.assertEqual(resp2["data"]["status"], "ISOLATED")

        # 3. Brain attempts command on quarantined valve -> Rejected with GUARDIAN_RESTRICTED
        _, meta3 = await self.mcp.call_tool(
            "send_actuator_command",
            {
                "device_id": device,
                "command": "set_opening",
                "params": {"open_pct": 20.0},
                "request_id": "req-mcp-02",
                "token": self.brain_token,
            },
        )
        resp3 = meta3.get("result", meta3)
        self.assertFalse(resp3["ok"])
        self.assertEqual(resp3["error"]["code"], ErrorCode.GUARDIAN_RESTRICTED)

        # 4. Guardian restores valve V-12
        _, meta4 = await self.mcp.call_tool(
            "restore_device",
            {
                "device_id": device,
                "token": self.guardian_token,
            },
        )
        resp4 = meta4.get("result", meta4)
        self.assertTrue(resp4["ok"])
        self.assertEqual(resp4["data"]["status"], "RESTORED")


class MiddlewareAndRESTTests(unittest.TestCase):
    def setUp(self):
        self.city = LiveCity("test-rest-01")
        self.facade = TwinFacade(self.city)
        self.brain_token = DEFAULT_TOKENS[Role.BRAIN]
        self.guardian_token = DEFAULT_TOKENS[Role.GUARDIAN]

    def tearDown(self):
        self.city.close()

    def test_middleware_token_extraction(self):
        """Verify token extraction from various HTTP header formats."""
        self.assertEqual(extract_bearer_token({"Authorization": "Bearer secret-123"}), "secret-123")
        self.assertEqual(extract_bearer_token({"authorization": "secret-456"}), "secret-456")
        self.assertIsNone(extract_bearer_token({}))
        self.assertIsNone(extract_bearer_token({"Other": "val"}))

        # Role resolution
        headers = {"Authorization": f"Bearer {self.brain_token}"}
        self.assertEqual(resolve_header_role(headers), Role.BRAIN)

    def test_rest_health_endpoint(self):
        """Verify unauthenticated GET /health returns 200 UP."""
        status_code, resp = handle_rest_request(self.facade, "GET", "/health")
        self.assertEqual(status_code, 200)
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["data"]["status"], "UP")

    def test_rest_sensors_with_auth(self):
        """Verify GET /api/v1/sensors with Bearer header."""
        headers = {"Authorization": f"Bearer {self.brain_token}"}
        status_code, resp = handle_rest_request(self.facade, "GET", "/api/v1/sensors?zone_id=PRT", headers=headers)
        self.assertEqual(status_code, 200)
        self.assertTrue(resp["ok"])
        self.assertIn("readings", resp["data"])

    def test_rest_sensors_unauthorized(self):
        """Verify GET /api/v1/sensors without token returns 401."""
        status_code, resp = handle_rest_request(self.facade, "GET", "/api/v1/sensors")
        self.assertEqual(status_code, 401)
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], ErrorCode.NOT_AUTHORIZED)

    def test_rest_command_and_quarantine(self):
        """Verify POST /api/v1/commands and POST /api/v1/isolate via REST."""
        brain_headers = {"Authorization": f"Bearer {self.brain_token}"}
        guardian_headers = {"Authorization": f"Bearer {self.guardian_token}"}

        # 1. Send command
        body = {
            "device_id": "V-12",
            "command": "set_opening",
            "params": {"open_pct": 50.0},
            "request_id": "req-rest-01",
        }
        status, resp = handle_rest_request(self.facade, "POST", "/api/v1/commands", headers=brain_headers, body=body)
        self.assertEqual(status, 200)
        self.assertTrue(resp["ok"])

        # 2. Guardian isolates device
        iso_body = {"device_id": "V-12", "reason": "REST Anomaly"}
        status_iso, resp_iso = handle_rest_request(self.facade, "POST", "/api/v1/isolate", headers=guardian_headers, body=iso_body)
        self.assertEqual(status_iso, 200)
        self.assertTrue(resp_iso["ok"])

        # 3. Brain command rejected on quarantined device -> 403 GUARDIAN_RESTRICTED
        body2 = {**body, "request_id": "req-rest-02"}
        status_cmd2, resp_cmd2 = handle_rest_request(self.facade, "POST", "/api/v1/commands", headers=brain_headers, body=body2)
        self.assertEqual(status_cmd2, 403)
        self.assertFalse(resp_cmd2["ok"])
        self.assertEqual(resp_cmd2["error"]["code"], ErrorCode.GUARDIAN_RESTRICTED)

        # 4. Guardian restores device via REST
        res_body = {"device_id": "V-12"}
        status_res, resp_res = handle_rest_request(self.facade, "POST", "/api/v1/restore", headers=guardian_headers, body=res_body)
        self.assertEqual(status_res, 200)
        self.assertTrue(resp_res["ok"])

    def test_rest_state_and_events_endpoints(self):
        """Verify GET /api/v1/state and GET /api/v1/events."""
        headers = {"Authorization": f"Bearer {self.brain_token}"}
        
        # State
        status, resp = handle_rest_request(self.facade, "GET", "/api/v1/state?zone_id=PRT", headers=headers)
        self.assertEqual(status, 200)
        self.assertTrue(resp["ok"])

        # Events
        status_ev, resp_ev = handle_rest_request(self.facade, "GET", "/api/v1/events?seq=0", headers=headers)
        self.assertEqual(status_ev, 200)
        self.assertTrue(resp_ev["ok"])

    def test_rest_validation_and_error_branches(self):
        """Verify error branches, missing fields, 404s, and token fallbacks."""
        headers = {"Authorization": f"Bearer {self.brain_token}"}

        # 404 Not Found
        status, resp = handle_rest_request(self.facade, "GET", "/unknown/route")
        self.assertEqual(status, 404)
        self.assertFalse(resp["ok"])

        # POST /commands missing fields -> 400
        status_cmd, resp_cmd = handle_rest_request(self.facade, "POST", "/api/v1/commands", headers=headers, body={})
        self.assertEqual(status_cmd, 400)

        # POST /isolate missing device_id -> 400
        status_iso, resp_iso = handle_rest_request(self.facade, "POST", "/api/v1/isolate", headers=headers, body={})
        self.assertEqual(status_iso, 400)

        # POST /restore missing device_id -> 400
        status_rst, resp_rst = handle_rest_request(self.facade, "POST", "/api/v1/restore", headers=headers, body={})
        self.assertEqual(status_rst, 400)

        # Token via query param
        status_q, resp_q = handle_rest_request(self.facade, "GET", f"/api/v1/sensors?token={self.brain_token}")
        self.assertEqual(status_q, 200)

        # Token via body
        body_with_token = {
            "token": self.brain_token,
            "device_id": "V-12",
            "command": "set_opening",
            "params": {"open_pct": 10.0},
            "request_id": "req-token-body-01",
        }
        status_b, resp_b = handle_rest_request(self.facade, "POST", "/api/v1/commands", body=body_with_token)
        self.assertEqual(status_b, 200)


if __name__ == "__main__":
    unittest.main()
