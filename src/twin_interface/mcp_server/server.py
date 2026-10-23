"""FastMCP Tool Server for City Brain Convergence Twin Layer.

Exposes semantic tools for external LLM agents (Brain, Guardian, Evaluator)
over the standard Model Context Protocol (MCP).
All tools pass through the TwinFacade to ensure strict security, permissions,
quarantine checks, and anti-leak projections.
"""
from typing import Any
from mcp.server.fastmcp import FastMCP

from twin_interface.auth import DEFAULT_TOKENS, Role
from twin_interface.facade import TwinFacade


def create_mcp_server(facade: TwinFacade | None = None) -> FastMCP:
    """Create and configure the FastMCP tool server instance bound to the TwinFacade.

    Args:
        facade: Optional initialized TwinFacade instance. If None, a new one is created.

    Returns:
        Configured FastMCP application instance with all tools registered.
    """
    fac = facade if facade is not None else TwinFacade()
    mcp = FastMCP("City-Brain-Twin")

    # --------------------------------------------------------------------------
    # 1. OBSERVATION TOOLS (Read Telemetry & State)
    # --------------------------------------------------------------------------

    @mcp.tool()
    def get_sensor_readings(
        zone_id: str | None = None,
        sensor_id: str | None = None,
        sensor_type: str | None = None,
        token: str = DEFAULT_TOKENS[Role.BRAIN],
    ) -> dict[str, Any]:
        """Retrieve public sensor telemetry and operational status across the city.

        Returns only public/projected observations. Secret Ground Truth variables
        (actual_value, delta, fault models) are strictly filtered and omitted.

        Args:
            zone_id: Optional zone filter ('PRT', 'DTN', 'IND', 'RES', 'HSP').
                     Omit to retrieve sensors across the entire city.
            sensor_id: Optional filter for a specific equipment ID (e.g. 'PRT-WLV-01').
            sensor_type: Optional filter by measurement type:
                         - 'water_level' (cm)
                         - 'traffic_counter' (veh/min)
                         - 'air_quality' (ug/m3 PM2.5)
                         - 'power_load' (kW)
            token: Bearer authentication token. Defaults to authorized Brain token.

        Returns:
            Envelope containing sim_tick, count, and array of public sensor readings:
            {
                "ok": true,
                "run_id": "live-001",
                "data": {
                    "sim_tick": 45,
                    "count": 4,
                    "readings": [
                        {
                            "sensor_id": "PRT-WLV-01",
                            "zone_id": "PRT",
                            "type": "water_level",
                            "unit": "cm",
                            "reported_value": 78.5,
                            "status": "OK",
                            "backup_ids": ["PRT-WLV-02"],
                            "timestamp": "2026-10-23T12:00:00Z"
                        }
                    ]
                }
            }
        """
        return fac.get_sensor_readings(
            token=token,
            zone_id=zone_id,
            sensor_id=sensor_id,
            sensor_type=sensor_type,
        )

    @mcp.tool()
    def get_city_state(
        zone_id: str | None = None,
        token: str = DEFAULT_TOKENS[Role.BRAIN],
    ) -> dict[str, Any]:
        """Retrieve high-level macro situational awareness of urban infrastructure and alerts.

        Use this tool to get an overarching operational picture before planning actuator dispatches.
        Provides pump operation states, valve positions, traffic light phases, electrical grid status,
        and active incident alerts.

        Args:
            zone_id: Optional zone filter ('PRT', 'DTN', 'IND', 'RES', 'HSP').
                     Omit to receive high-level status for all zones.
            token: Bearer authentication token. Defaults to authorized Brain token.

        Returns:
            Envelope containing active alerts, simulation speed, and zone equipment breakdowns.
        """
        return fac.get_city_state(token=token, zone_id=zone_id)

    @mcp.tool()
    def get_events_since(
        seq: int = 0,
        token: str = DEFAULT_TOKENS[Role.BRAIN],
    ) -> dict[str, Any]:
        """Retrieve timeline events that occurred after a given sequence number.

        Use this tool to poll for newly triggered alarms, completed actions, or status changes
        without re-downloading the full sensor catalog.

        Args:
            seq: Sequence number cursor. Only events with event_seq > seq will be returned.
            token: Bearer authentication token. Defaults to authorized Brain token.

        Returns:
            Envelope containing from_seq, count, and array of chronological event objects.
        """
        return fac.get_events_since(token=token, seq=seq)

    # --------------------------------------------------------------------------
    # 2. CONTROL TOOLS (Actuator Commands — Brain & Operator Only)
    # --------------------------------------------------------------------------

    @mcp.tool()
    def send_actuator_command(
        device_id: str,
        command: str,
        params: dict[str, Any],
        request_id: str,
        context: dict[str, Any] | None = None,
        token: str = DEFAULT_TOKENS[Role.BRAIN],
    ) -> dict[str, Any]:
        """Dispatch a physical action to an urban actuator (pump, valve, signal, grid, dispatch).

        Permission: Restricted to Role 'brain' and 'operator'. Guardian calls are rejected.
        Idempotency: Re-transmitting the same request_id returns the cached outcome safely.
        Quarantine: If the device is isolated by the Guardian, the command will be rejected
                    with error code GUARDIAN_RESTRICTED.

        Supported equipment & commands:
        - Water Pumps ('PRT-PMP-01', 'PRT-PMP-02', 'P-01'):
            * command='start', params={'speed_pct': 0-100}
            * command='stop', params={}
            * command='set_speed', params={'speed_pct': 0-100}
        - Water Valves ('V-12', 'IND-VLV-01', 'DTN-VLV-01'):
            * command='set_opening', params={'open_pct': 0.0-100.0}
        - Traffic Signals ('DTN-TLT-01', 'TLT'):
            * command='set_phase', params={'phase': 'green_ns'|'green_ew'|'all_red'|'flashing'}
        - Electrical Feeder Switches ('F-ESS', 'F-URBAN', 'F-IND', 'GRD'):
            * command='open' (disconnect power), params={}
            * command='close' (energize power), params={}
        - Emergency Dispatch ('AMB-01', 'POL-01', 'DSP'):
            * command='dispatch', params={'zone_id': 'DTN'|'PRT'|'IND'|'RES'}
            * command='release', params={}

        Args:
            device_id: Target equipment ID.
            command: Action verb matching equipment type.
            params: Dictionary of parameters required by the command.
            request_id: Unique client UUID for idempotent execution.
            context: Optional metadata dictionary (e.g. Guardian verdict ID).
            token: Bearer authentication token.

        Returns:
            Envelope with command outcome:
            {
                "ok": true,
                "data": {
                    "request_id": "req-123",
                    "device_id": "PRT-PMP-02",
                    "command": "start",
                    "status": "APPLIED",
                    "effective_revision": 16
                }
            }
        """
        return fac.send_actuator_command(
            token=token,
            device_id=device_id,
            command=command,
            params=params,
            request_id=request_id,
            context=context,
        )

    # --------------------------------------------------------------------------
    # 3. SECURITY & QUARANTINE TOOLS (Guardian & Operator Only)
    # --------------------------------------------------------------------------

    @mcp.tool()
    def isolate_device(
        device_id: str,
        reason: str = "",
        token: str = DEFAULT_TOKENS[Role.GUARDIAN],
    ) -> dict[str, Any]:
        """Place a suspected compromised, drifting, or attacked device into quarantine.

        Permission: Restricted to Role 'guardian' and 'operator'. Brain calls are rejected.
        Effect: The device is marked OFFLINE. All future actuator commands sent to this device
                will be rejected with error GUARDIAN_RESTRICTED until it is restored.

        Args:
            device_id: Equipment ID to quarantine (e.g. 'PRT-WLV-01', 'V-12').
            reason: Diagnostic explanation (e.g. 'Sensor drift > 50cm compared to backup').
            token: Bearer authentication token. Defaults to authorized Guardian token.

        Returns:
            Envelope confirming isolation:
            {
                "ok": true,
                "data": {
                    "device_id": "PRT-WLV-01",
                    "status": "ISOLATED",
                    "isolated_by": "guardian",
                    "reason": "..."
                }
            }
        """
        return fac.isolate_device(
            token=token,
            device_id=device_id,
            reason=reason,
        )

    @mcp.tool()
    def restore_device(
        device_id: str,
        token: str = DEFAULT_TOKENS[Role.GUARDIAN],
    ) -> dict[str, Any]:
        """Restore a quarantined device back to active operational status.

        Permission: Restricted to Role 'guardian' and 'operator'.

        Args:
            device_id: Equipment ID to remove from quarantine.
            token: Bearer authentication token. Defaults to authorized Guardian token.

        Returns:
            Envelope confirming restoration:
            {
                "ok": true,
                "data": {
                    "device_id": "PRT-WLV-01",
                    "status": "RESTORED"
                }
            }
        """
        return fac.restore_device(
            token=token,
            device_id=device_id,
        )

    return mcp
