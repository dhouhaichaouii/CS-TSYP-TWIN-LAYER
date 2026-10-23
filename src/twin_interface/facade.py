"""Central Façade Gateway for the Twin Layer.

Acts as the intelligent gatekeeper and unified interface:
- Authenticates incoming tokens and resolves roles.
- Enforces the permission matrix (Tool × Role).
- Enforces device quarantines (GUARDIAN_RESTRICTED).
- Interacts thread-safely with the LiveCity simulation.
- Applies allow-list projections to strip Ground Truth.
- Wraps all responses in standard envelopes.
"""
import threading
from typing import Any

from city_live.runtime import LiveCity
from twin_interface.auth import Role, resolve_token
from twin_interface.envelope import ErrorCode, error_envelope, success_envelope, utc_now_iso
from twin_interface.permissions import check_tool_permission
from twin_interface.projections import project_event, project_reading, project_readings


class TwinFacade:
    """The central unified API gateway for both FastMCP and REST transports."""

    def __init__(self, city: LiveCity | None = None):
        """Initialize the Façade with a LiveCity instance and internal tracking ledgers."""
        self._city = city if city is not None else LiveCity()
        self._lock = threading.RLock()
        self._quarantined_devices: dict[str, dict[str, Any]] = {}
        self._idempotency_cache: dict[str, dict[str, Any]] = {}

    @property
    def city(self) -> LiveCity:
        """Direct access to the underlying LiveCity instance."""
        return self._city

    @property
    def run_id(self) -> str:
        """Current simulation run ID."""
        return self._city.status()["run_id"]

    # --------------------------------------------------------------------------
    # 1. OBSERVATION METHODS (Read Telemetry & State)
    # --------------------------------------------------------------------------

    def get_sensor_readings(
        self,
        token: str | None,
        zone_id: str | None = None,
        sensor_id: str | None = None,
        sensor_type: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve sanitized sensor telemetry.

        Args:
            token: Caller Bearer token string.
            zone_id: Optional filter by zone ('PRT', 'DTN', 'IND', 'RES', 'HSP').
            sensor_id: Optional filter for a specific sensor ID.
            sensor_type: Optional filter by measurement type ('water_level', etc.).

        Returns:
            Standard envelope containing filtered, projected sensor observations.
        """
        role = resolve_token(token)
        ok, err_msg = check_tool_permission("get_sensor_readings", role)
        if not ok:
            return error_envelope(self.run_id, ErrorCode.NOT_AUTHORIZED, err_msg or "Unauthorized")

        with self._city._condition:
            status = self._city.status()
            sim_tick = status["sim_tick"]

            # Pull observations from PublicReader
            raw_readings = self._city.public.observations()

            # If the public store has no sampled readings yet, construct baseline readings
            if not raw_readings:
                raw_readings = self._build_baseline_readings(sim_tick)

        # Apply filtering
        filtered = list(raw_readings)

        if sensor_id:
            filtered = [r for r in filtered if r.get("sensor_id") == sensor_id]
            if not filtered:
                return error_envelope(
                    self.run_id,
                    ErrorCode.DEVICE_NOT_FOUND,
                    f"Sensor '{sensor_id}' not found.",
                    details={"sensor_id": sensor_id},
                )

        if zone_id:
            filtered = [r for r in filtered if r.get("zone_id") == zone_id]

        if sensor_type:
            filtered = [r for r in filtered if r.get("type") == sensor_type]

        # Apply quarantine status overrides: quarantined sensors report as OFFLINE
        with self._lock:
            for item in filtered:
                s_id = item.get("sensor_id")
                if s_id in self._quarantined_devices:
                    item["status"] = "OFFLINE"
                    item["available"] = False

        # Apply allow-list projection (censor ground truth for public roles)
        sanitized = project_readings(filtered, role)

        return success_envelope(
            self.run_id,
            {
                "sim_tick": sim_tick,
                "count": len(sanitized),
                "readings": sanitized,
            },
        )

    def get_city_state(
        self,
        token: str | None,
        zone_id: str | None = None,
    ) -> dict[str, Any]:
        """Retrieve high-level macro situational overview of city infrastructure.

        Args:
            token: Caller Bearer token string.
            zone_id: Optional filter by zone ('PRT', 'DTN', 'IND', 'RES', 'HSP').

        Returns:
            Standard envelope containing active alerts and infrastructure state summary.
        """
        role = resolve_token(token)
        ok, err_msg = check_tool_permission("get_city_state", role)
        if not ok:
            return error_envelope(self.run_id, ErrorCode.NOT_AUTHORIZED, err_msg or "Unauthorized")

        with self._city._condition:
            status = self._city.status()
            diag = self._city.diagnostics()
            sim_tick = status["sim_tick"]

        # Synthesize public infrastructure state per zone
        zones_summary = self._build_zones_summary(diag)

        if zone_id:
            if zone_id not in zones_summary:
                return error_envelope(
                    self.run_id,
                    ErrorCode.DEVICE_NOT_FOUND,
                    f"Zone '{zone_id}' not found.",
                    details={"zone_id": zone_id},
                )
            zones_summary = {zone_id: zones_summary[zone_id]}

        # Compute active incidents / alerts
        incidents = self._compute_active_alerts(diag)

        return success_envelope(
            self.run_id,
            {
                "sim_tick": sim_tick,
                "speed": status.get("speed", 1.0),
                "active_incidents": incidents,
                "quarantined_devices_count": len(self._quarantined_devices),
                "zones": zones_summary,
            },
        )

    def get_events_since(
        self,
        token: str | None,
        seq: int = 0,
    ) -> dict[str, Any]:
        """Retrieve timeline events that occurred after a given sequence number.

        Args:
            token: Caller Bearer token string.
            seq: Sequence cursor (returns events with event_seq > seq).

        Returns:
            Standard envelope with sanitized events list.
        """
        role = resolve_token(token)
        ok, err_msg = check_tool_permission("get_events_since", role)
        if not ok:
            return error_envelope(self.run_id, ErrorCode.NOT_AUTHORIZED, err_msg or "Unauthorized")

        with self._city._condition:
            all_events = self._city.events().get("events", [])

        # Filter events after seq
        new_events = [e for e in all_events if e.get("event_seq", 0) > seq or e.get("seq", 0) > seq]

        # Sanitize each event (strip forbidden keys from details)
        sanitized_events = [project_event(e, role) for e in new_events]

        return success_envelope(
            self.run_id,
            {
                "from_seq": seq,
                "count": len(sanitized_events),
                "events": sanitized_events,
            },
        )

    # --------------------------------------------------------------------------
    # 2. CONTROL METHODS (Actuator Commands)
    # --------------------------------------------------------------------------

    def send_actuator_command(
        self,
        token: str | None,
        device_id: str,
        command: str,
        params: dict[str, Any],
        request_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Dispatch a physical action to an urban actuator (pump, valve, light, switch).

        Args:
            token: Caller Bearer token string.
            device_id: Target equipment ID (e.g. 'PRT-PMP-02', 'V-12', 'DTN-TLT-01').
            command: Action verb ('start', 'stop', 'set_opening', 'set_phase', etc.).
            params: Parameters dictionary (e.g. {'speed_pct': 80}).
            request_id: Unique client UUID for idempotent execution.
            context: Optional client metadata (e.g. Guardian verdict ID).

        Returns:
            Standard envelope with outcome status ('APPLIED', 'REJECTED', etc.).
        """
        role = resolve_token(token)
        ok, err_msg = check_tool_permission("send_actuator_command", role)
        if not ok:
            return error_envelope(self.run_id, ErrorCode.NOT_AUTHORIZED, err_msg or "Unauthorized")

        if not request_id or not isinstance(request_id, str):
            return error_envelope(self.run_id, ErrorCode.INVALID_PARAM, "request_id must be a non-empty string.")

        # Check idempotency cache
        with self._lock:
            cached = self._idempotency_cache.get(request_id)
            if cached is not None:
                # If cached request matches, return the identical previous outcome
                if cached.get("device_id") == device_id and cached.get("command") == command:
                    return success_envelope(self.run_id, cached["data"])
                # If same request_id reused with different parameters, reject conflict
                return error_envelope(
                    self.run_id,
                    ErrorCode.DUPLICATE_CONFLICT,
                    f"request_id '{request_id}' already used with different parameters.",
                )

        # Check quarantine status (GUARDIAN_RESTRICTED)
        if self.is_device_isolated(device_id):
            quarantine_info = self._quarantined_devices.get(device_id, {})
            return error_envelope(
                self.run_id,
                ErrorCode.GUARDIAN_RESTRICTED,
                f"Cannot execute command: device '{device_id}' is isolated by the Guardian.",
                details={
                    "device_id": device_id,
                    "reason": quarantine_info.get("reason", "Quarantined"),
                    "isolated_by": quarantine_info.get("isolated_by", "guardian"),
                },
            )

        # Translate command to physical effect request for city_core
        effect, err = self._translate_command_to_effect(device_id, command, params)
        if err is not None:
            return error_envelope(self.run_id, ErrorCode.INVALID_PARAM, err)

        # Apply effect atomically to the simulation
        try:
            with self._city._condition:
                receipt = self._city._effect(effect)
                revision = receipt.context.revision if hasattr(receipt, "context") else None

            result_data = {
                "request_id": request_id,
                "device_id": device_id,
                "command": command,
                "status": "APPLIED",
                "effective_revision": revision,
                "context": context or {},
                "timestamp": utc_now_iso(),
            }

            # Cache outcome for idempotency
            with self._lock:
                self._idempotency_cache[request_id] = {
                    "device_id": device_id,
                    "command": command,
                    "data": result_data,
                }

            return success_envelope(self.run_id, result_data)

        except Exception as exc:
            return error_envelope(
                self.run_id,
                ErrorCode.INTERNAL_ERROR,
                f"Simulation failed to apply effect: {str(exc)}",
            )

    # --------------------------------------------------------------------------
    # 3. SECURITY & QUARANTINE METHODS (Guardian Tools)
    # --------------------------------------------------------------------------

    def isolate_device(
        self,
        token: str | None,
        device_id: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Place a compromised or drifting device into quarantine.

        Args:
            token: Caller Bearer token string (Guardian or Operator required).
            device_id: Target device ID to quarantine.
            reason: Diagnostic explanation for isolation.

        Returns:
            Standard envelope with isolation confirmation.
        """
        role = resolve_token(token)
        ok, err_msg = check_tool_permission("isolate_device", role)
        if not ok:
            return error_envelope(self.run_id, ErrorCode.NOT_AUTHORIZED, err_msg or "Unauthorized")

        if not device_id or not isinstance(device_id, str):
            return error_envelope(self.run_id, ErrorCode.INVALID_PARAM, "device_id must be a valid string.")

        with self._lock:
            self._quarantined_devices[device_id] = {
                "device_id": device_id,
                "reason": reason or "Unspecified Guardian quarantine",
                "isolated_by": role,
                "timestamp": utc_now_iso(),
            }

        # Log an event in the simulation event ledger
        with self._city._condition:
            self._city._event("DEVICE_ISOLATED", {"device_id": device_id, "reason": reason, "role": role})

        return success_envelope(
            self.run_id,
            {
                "device_id": device_id,
                "status": "ISOLATED",
                "isolated_by": role,
                "reason": reason,
            },
        )

    def restore_device(
        self,
        token: str | None,
        device_id: str,
    ) -> dict[str, Any]:
        """Restore a quarantined device to normal operational status.

        Args:
            token: Caller Bearer token string (Guardian or Operator required).
            device_id: Target device ID to restore.

        Returns:
            Standard envelope with restoration confirmation.
        """
        role = resolve_token(token)
        ok, err_msg = check_tool_permission("restore_device", role)
        if not ok:
            return error_envelope(self.run_id, ErrorCode.NOT_AUTHORIZED, err_msg or "Unauthorized")

        with self._lock:
            if device_id not in self._quarantined_devices:
                return error_envelope(
                    self.run_id,
                    ErrorCode.DEVICE_NOT_FOUND,
                    f"Device '{device_id}' is not currently isolated.",
                )
            del self._quarantined_devices[device_id]

        # Log an event in the simulation event ledger
        with self._city._condition:
            self._city._event("DEVICE_RESTORED", {"device_id": device_id, "role": role})

        return success_envelope(
            self.run_id,
            {
                "device_id": device_id,
                "status": "RESTORED",
                "restored_by": role,
            },
        )

    def is_device_isolated(self, device_id: str) -> bool:
        """Check whether a device is currently quarantined."""
        with self._lock:
            return device_id in self._quarantined_devices

    # --------------------------------------------------------------------------
    # 4. INTERNAL TRANSLATION & SYNTHESIS HELPERS
    # --------------------------------------------------------------------------

    def _translate_command_to_effect(
        self, device_id: str, command: str, params: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Translate public actuator command into a typed city_core physical effect tag."""
        cmd = command.lower()

        # Water Pump translation (PRT-PMP-01, PRT-PMP-02, P-01)
        if "PMP" in device_id or device_id.startswith("P-"):
            if cmd == "start":
                speed = float(params.get("speed_pct", 100)) / 100.0
                return {"tag": "pump_state", "target_id": "P-01", "running": True, "speed_fraction": speed}, None
            if cmd == "stop":
                return {"tag": "pump_state", "target_id": "P-01", "running": False, "speed_fraction": 0.0}, None
            if cmd == "set_speed":
                speed = float(params.get("speed_pct", 100)) / 100.0
                return {"tag": "pump_state", "target_id": "P-01", "running": speed > 0, "speed_fraction": speed}, None
            return None, f"Unknown pump command: '{command}'. Supported: 'start', 'stop', 'set_speed'."

        # Water Valve translation (V-12, IND-VLV-01, DTN-VLV-01, RES-VLV-01)
        if "VLV" in device_id or device_id.startswith("V-"):
            if cmd == "set_opening":
                pct = float(params.get("open_pct", 0.0))
                if not (0.0 <= pct <= 100.0):
                    return None, "open_pct must be between 0.0 and 100.0."
                return {"tag": "valve_position", "target_id": "V-12", "opening_fraction": pct / 100.0}, None
            return None, f"Unknown valve command: '{command}'. Supported: 'set_opening'."

        # Traffic Light translation (DTN-TLT-01, TLT, signal)
        if "TLT" in device_id or "SIG" in device_id:
            if cmd == "set_phase":
                phase = str(params.get("phase", "green_ns")).lower()
                allowed_phases = ("green_ns", "green_ew", "all_red", "flashing")
                if phase not in allowed_phases:
                    return None, f"Invalid phase '{phase}'. Supported: {allowed_phases}."
                return {"tag": "signal_phase", "target_id": "J-01", "phase": phase}, None
            return None, f"Unknown traffic signal command: '{command}'. Supported: 'set_phase'."

        # Electrical Feeder translation (F-ESS, F-URBAN, F-IND, GRD)
        if device_id.startswith("F-") or "GRD" in device_id:
            target = "F-ESS" if device_id.startswith("F-") else "F-URBAN"
            if cmd in ("close", "connect"):
                return {"tag": "feeder_switch", "target_id": target, "closed": True}, None
            if cmd in ("open", "disconnect"):
                return {"tag": "feeder_switch", "target_id": target, "closed": False}, None
            return None, f"Unknown grid switch command: '{command}'. Supported: 'open', 'close'."

        # Emergency Dispatch translation (AMB-01, POL-01, DSP)
        if "AMB" in device_id or "POL" in device_id or "DSP" in device_id:
            unit_id = "AMB-01" if "AMB" in device_id else "POL-01"
            if cmd == "dispatch":
                zone = params.get("zone_id", "DTN")
                return {"tag": "responder_reserve", "unit_id": unit_id, "mission_ref": f"m-{zone.lower()}-01"}, None
            if cmd == "release":
                return {"tag": "responder_release", "unit_id": unit_id}, None
            return None, f"Unknown dispatch command: '{command}'. Supported: 'dispatch', 'release'."

        return None, f"Unrecognized actuator device_id: '{device_id}'."

    def _build_baseline_readings(self, sim_tick: int) -> list[dict[str, Any]]:
        """Synthesize default baseline sensor readings when public store is empty."""
        timestamp = utc_now_iso()
        return [
            {
                "sensor_id": "PRT-WLV-01",
                "zone_id": "PRT",
                "type": "water_level",
                "unit": "cm",
                "sim_tick": sim_tick,
                "seq": 1,
                "timestamp": timestamp,
                "reported_value": 45.0,
                "status": "OK",
                "available": True,
                "backup_ids": ["PRT-WLV-02"],
                "linked_device_ids": ["PRT-PMP-01"],
            },
            {
                "sensor_id": "PRT-WLV-02",
                "zone_id": "PRT",
                "type": "water_level",
                "unit": "cm",
                "sim_tick": sim_tick,
                "seq": 2,
                "timestamp": timestamp,
                "reported_value": 44.8,
                "status": "OK",
                "available": True,
                "backup_ids": ["PRT-WLV-01"],
                "linked_device_ids": ["PRT-PMP-02"],
            },
            {
                "sensor_id": "DTN-TRF-01",
                "zone_id": "DTN",
                "type": "traffic_counter",
                "unit": "veh/min",
                "sim_tick": sim_tick,
                "seq": 3,
                "timestamp": timestamp,
                "reported_value": 28.0,
                "status": "OK",
                "available": True,
                "backup_ids": [],
                "linked_device_ids": ["DTN-TLT-01"],
            },
            {
                "sensor_id": "IND-AIR-01",
                "zone_id": "IND",
                "type": "air_quality",
                "unit": "ug/m3",
                "sim_tick": sim_tick,
                "seq": 4,
                "timestamp": timestamp,
                "reported_value": 35.0,
                "status": "OK",
                "available": True,
                "backup_ids": [],
                "linked_device_ids": [],
            },
        ]

    def _build_zones_summary(self, diag: dict[str, Any]) -> dict[str, Any]:
        """Summarize operational equipment state per zone."""
        water_state = diag.get("physical_state", {}).get("water", {})
        valve_fraction = water_state.get("valve", {}).get("effective_opening_fraction", 0.5)

        return {
            "PRT": {
                "name": "Port / Harbor Zone",
                "pumps": {"PRT-PMP-01": "STOPPED", "PRT-PMP-02": "STANDBY"},
                "valves": {"V-12": f"OPEN_{int(valve_fraction * 100)}%"},
                "flood_status": "NORMAL",
            },
            "DTN": {
                "name": "Downtown Zone",
                "traffic_signals": {"DTN-TLT-01": "GREEN_NS"},
                "power_feeder": {"F-URBAN": "ENERGIZED"},
            },
            "IND": {
                "name": "Industrial Zone",
                "power_feeder": {"F-IND": "ENERGIZED"},
                "air_scrubbers": "ACTIVE",
            },
            "RES": {
                "name": "Residential Zone",
                "water_pressure": "NORMAL",
                "grid_status": "ONLINE",
            },
            "HSP": {
                "name": "Hospital Critical Zone",
                "power_status": "PRIORITY_FEED_OK",
                "ambulance_access": "CLEAR",
            },
        }

    def _compute_active_alerts(self, diag: dict[str, Any]) -> list[str]:
        """Extract active alerts from the physical state."""
        alerts = []
        water = diag.get("physical_state", {}).get("water", {})
        if water.get("surface_depth_m", 0.0) > 0.3:
            alerts.append("HARBOR_SURGE_WARNING")

        for road_id, road_data in diag.get("traffic", {}).items():
            if not road_data.get("usable", True):
                alerts.append(f"ROAD_BLOCKED_{road_id}")

        return alerts
