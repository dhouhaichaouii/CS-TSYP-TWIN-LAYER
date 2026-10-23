"""Interface and Façade test suite.

Verifies end-to-end integration between the TwinFacade, authentication,
permissions, quarantine enforcement, and simulation engine.
"""
import unittest

from city_live.runtime import LiveCity
from twin_interface.auth import DEFAULT_TOKENS, Role
from twin_interface.envelope import ErrorCode
from twin_interface.facade import TwinFacade


class TwinFacadeTests(unittest.TestCase):
    def setUp(self):
        # Create a fresh LiveCity simulation and Façade gateway
        self.city = LiveCity("test-facade-01")
        self.facade = TwinFacade(self.city)

        # Standard test tokens
        self.brain_token = DEFAULT_TOKENS[Role.BRAIN]
        self.guardian_token = DEFAULT_TOKENS[Role.GUARDIAN]
        self.evaluator_token = DEFAULT_TOKENS[Role.EVALUATOR]
        self.operator_token = DEFAULT_TOKENS[Role.OPERATOR]

    def tearDown(self):
        self.city.close()

    # --------------------------------------------------------------------------
    # 1. Tests for get_sensor_readings
    # --------------------------------------------------------------------------

    def test_get_sensor_readings_unauthorized(self):
        """Reject reading sensors when token is missing or invalid."""
        resp = self.facade.get_sensor_readings(token="bad-token")
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], ErrorCode.NOT_AUTHORIZED)

    def test_get_sensor_readings_brain_censorship(self):
        """Verify Brain receives clean telemetry with 0 ground-truth leakage."""
        resp = self.facade.get_sensor_readings(token=self.brain_token)
        self.assertTrue(resp["ok"])
        data = resp["data"]
        self.assertGreater(data["count"], 0)

        # Ensure no forbidden ground truth fields exist in readings
        for r in data["readings"]:
            self.assertIn("sensor_id", r)
            self.assertIn("reported_value", r)
            self.assertNotIn("actual_value", r)
            self.assertNotIn("delta", r)
            self.assertNotIn("fault", r)

    def test_get_sensor_readings_filtering(self):
        """Verify filtering by zone and specific sensor ID."""
        # 1. Filter by zone PRT
        resp_zone = self.facade.get_sensor_readings(token=self.brain_token, zone_id="PRT")
        self.assertTrue(resp_zone["ok"])
        for r in resp_zone["data"]["readings"]:
            self.assertEqual(r["zone_id"], "PRT")

        # 2. Filter by specific sensor
        resp_sensor = self.facade.get_sensor_readings(token=self.brain_token, sensor_id="PRT-WLV-01")
        self.assertTrue(resp_sensor["ok"])
        self.assertEqual(len(resp_sensor["data"]["readings"]), 1)
        self.assertEqual(resp_sensor["data"]["readings"][0]["sensor_id"], "PRT-WLV-01")

        # 3. Non-existent sensor returns DEVICE_NOT_FOUND
        resp_unknown = self.facade.get_sensor_readings(token=self.brain_token, sensor_id="UNKNOWN-999")
        self.assertFalse(resp_unknown["ok"])
        self.assertEqual(resp_unknown["error"]["code"], ErrorCode.DEVICE_NOT_FOUND)

    # --------------------------------------------------------------------------
    # 2. Tests for get_city_state
    # --------------------------------------------------------------------------

    def test_get_city_state(self):
        """Verify macro situational state retrieval."""
        resp = self.facade.get_city_state(token=self.brain_token)
        self.assertTrue(resp["ok"])
        data = resp["data"]
        self.assertIn("sim_tick", data)
        self.assertIn("zones", data)
        self.assertIn("PRT", data["zones"])
        self.assertIn("DTN", data["zones"])

        # Filter by single zone
        resp_prt = self.facade.get_city_state(token=self.brain_token, zone_id="PRT")
        self.assertTrue(resp_prt["ok"])
        self.assertEqual(list(resp_prt["data"]["zones"].keys()), ["PRT"])

    # --------------------------------------------------------------------------
    # 3. Tests for Quarantine Enforcement (isolate & restore)
    # --------------------------------------------------------------------------

    def test_guardian_isolation_and_quarantine_enforcement(self):
        """Verify that an isolated device rejects commands with GUARDIAN_RESTRICTED."""
        device = "V-12"

        # 1. Guardian isolates valve V-12
        iso_resp = self.facade.isolate_device(
            token=self.guardian_token,
            device_id=device,
            reason="Suspected physical valve obstruction",
        )
        self.assertTrue(iso_resp["ok"])
        self.assertTrue(self.facade.is_device_isolated(device))

        # 2. Brain attempts to actuate the isolated valve -> MUST BE REJECTED
        cmd_resp = self.facade.send_actuator_command(
            token=self.brain_token,
            device_id=device,
            command="set_opening",
            params={"open_pct": 80.0},
            request_id="req-cmd-iso-01",
        )
        self.assertFalse(cmd_resp["ok"])
        self.assertEqual(cmd_resp["error"]["code"], ErrorCode.GUARDIAN_RESTRICTED)
        self.assertIn("isolated by the Guardian", cmd_resp["error"]["message"])

        # 3. Guardian restores the valve
        res_resp = self.facade.restore_device(token=self.guardian_token, device_id=device)
        self.assertTrue(res_resp["ok"])
        self.assertFalse(self.facade.is_device_isolated(device))

        # 4. Brain attempts command again -> MUST SUCCEED
        cmd_ok_resp = self.facade.send_actuator_command(
            token=self.brain_token,
            device_id=device,
            command="set_opening",
            params={"open_pct": 50.0},
            request_id="req-cmd-iso-02",
        )
        self.assertTrue(cmd_ok_resp["ok"])
        self.assertEqual(cmd_ok_resp["data"]["status"], "APPLIED")

    # --------------------------------------------------------------------------
    # 4. Tests for Permissions Separation
    # --------------------------------------------------------------------------

    def test_permission_separation(self):
        """Verify role separation: Brain cannot isolate; Guardian cannot actuate."""
        # Brain tries to isolate -> NOT_AUTHORIZED
        resp = self.facade.isolate_device(token=self.brain_token, device_id="V-12")
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], ErrorCode.NOT_AUTHORIZED)

        # Guardian tries to send actuator command -> NOT_AUTHORIZED
        resp2 = self.facade.send_actuator_command(
            token=self.guardian_token,
            device_id="V-12",
            command="set_opening",
            params={"open_pct": 20.0},
            request_id="req-guard-01",
        )
        self.assertFalse(resp2["ok"])
        self.assertEqual(resp2["error"]["code"], ErrorCode.NOT_AUTHORIZED)

    # --------------------------------------------------------------------------
    # 5. Tests for Idempotency
    # --------------------------------------------------------------------------

    def test_actuator_command_idempotency(self):
        """Verify that duplicate request_ids return cached results; changed params return conflict."""
        req_id = "req-idemp-01"

        # 1. First invocation
        resp1 = self.facade.send_actuator_command(
            token=self.brain_token,
            device_id="V-12",
            command="set_opening",
            params={"open_pct": 30.0},
            request_id=req_id,
        )
        self.assertTrue(resp1["ok"])

        # 2. Duplicate invocation (same request_id, same command) -> returns identical success
        resp2 = self.facade.send_actuator_command(
            token=self.brain_token,
            device_id="V-12",
            command="set_opening",
            params={"open_pct": 30.0},
            request_id=req_id,
        )
        self.assertTrue(resp2["ok"])
        self.assertEqual(resp1["data"], resp2["data"])

        # 3. Conflicting invocation (same request_id, different command) -> DUPLICATE_CONFLICT
        resp3 = self.facade.send_actuator_command(
            token=self.brain_token,
            device_id="PRT-PMP-01",
            command="start",
            params={"speed_pct": 80.0},
            request_id=req_id,
        )
        self.assertFalse(resp3["ok"])
        self.assertEqual(resp3["error"]["code"], ErrorCode.DUPLICATE_CONFLICT)

    # --------------------------------------------------------------------------
    # 6. Tests for get_events_since
    # --------------------------------------------------------------------------

    def test_get_events_since(self):
        """Verify events retrieval cursor."""
        resp = self.facade.get_events_since(token=self.brain_token, seq=0)
        self.assertTrue(resp["ok"])
        self.assertIn("events", resp["data"])


if __name__ == "__main__":
    unittest.main()
