"""Run a deterministic Phase 1 scenario and write an append-only JSONL timeline."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import sys
import time
import traceback
import types
from typing import Any
import uuid


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_DIR = Path(__file__).resolve().parent
SEED_PATH = ROOT / "config" / "devices.seed.yaml"
LOG_DIR = ROOT / "logs"
SCENARIO_FILES = {
    "t5": "scn_01_fake_flood.json",
    "scn-01": "scn_01_fake_flood.json",
    "scn_01": "scn_01_fake_flood.json",
    "scn-02": "scn_02_real_flash_flood.json",
    "scn_02": "scn_02_real_flash_flood.json",
    "scn-03": "scn_03_sensor_malfunction.json",
    "scn_03": "scn_03_sensor_malfunction.json",
    "scn-04": "scn_04_quarantined_actuator.json",
    "scn_04": "scn_04_quarantined_actuator.json",
    "scn-05": "scn_05_full_city_stress.json",
    "scn_05": "scn_05_full_city_stress.json",
}


class Timeline:
    def __init__(self, scenario_id: str, path: Path) -> None:
        self.scenario_id = scenario_id
        self.run_id = str(uuid.uuid4())
        self.path = path
        self.sequence = 0
        self.started = time.monotonic()
        self.correlation_started: dict[str, float] = {}
        self._file = path.open("x", encoding="utf-8", newline="\n")

    def emit(
        self,
        layer: str,
        event_type: str,
        sim_tick: int,
        details: dict[str, Any],
        correlation_id: str,
    ) -> dict[str, Any]:
        self.sequence += 1
        now = time.monotonic()
        correlation_started = self.correlation_started.setdefault(
            correlation_id, now
        )
        event = {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "event_seq": self.sequence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sim_tick": sim_tick,
            "layer": layer,
            "event_type": event_type,
            "correlation_id": correlation_id,
            "correlation_elapsed_ms": round(
                (now - correlation_started) * 1000, 3
            ),
            "details": details,
        }
        self._file.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        self._file.flush()
        elapsed_ms = (now - self.started) * 1000
        print(
            f"[tick {sim_tick:>2}] {layer:<11} {event_type:<22} "
            f"{correlation_id} {json.dumps(details, sort_keys=True)} "
            f"({elapsed_ms:.1f} ms)"
        )
        return event

    def correlation_elapsed_ms(self, correlation_id: str) -> float:
        started = self.correlation_started.get(correlation_id)
        if started is None:
            raise KeyError(f"Unknown correlation ID: {correlation_id}")
        return round((time.monotonic() - started) * 1000, 3)

    def close(self) -> None:
        self._file.close()


def load_twin_modules() -> tuple[Any, Any, Any]:
    """Import local modules even if another installed package uses this name."""
    source_dir = ROOT / "src" / "twin_devices"
    source_path = str(source_dir)
    package = types.ModuleType("twin_devices")
    package.__path__ = [source_path]
    package.__package__ = "twin_devices"
    sys.modules["twin_devices"] = package
    for module_name in ("registry", "faults", "sensors", "actuators"):
        sys.modules.pop(f"twin_devices.{module_name}", None)
    registry_module = importlib.import_module("twin_devices.registry")
    sensors_module = importlib.import_module("twin_devices.sensors")
    actuators_module = importlib.import_module("twin_devices.actuators")
    return (
        registry_module.DeviceRegistry,
        sensors_module.SensorEngine,
        actuators_module.ActuatorEngine,
    )


def load_scenario(name: str) -> dict[str, Any]:
    filename = SCENARIO_FILES.get(name.lower())
    if filename is None:
        choices = ", ".join(sorted(set(SCENARIO_FILES)))
        raise ValueError(f"Unknown scenario {name!r}. Supported IDs: {choices}")
    with (SCENARIOS_DIR / filename).open("r", encoding="utf-8") as scenario_file:
        scenario = json.load(scenario_file)
    required = {
        "ID",
        "Name",
        "Layers involved",
        "Description",
        "Trigger",
        "Expected: Twin",
        "Expected: Guardian",
        "Expected: Brain",
        "How to verify",
        "triggers",
        "fixture",
    }
    missing = required.difference(scenario)
    if missing:
        raise ValueError(f"Scenario {filename} missing fields: {sorted(missing)}")
    return scenario


def correlation(*parts: str) -> str:
    return "-".join(parts)


def emit_reading(
    timeline: Timeline,
    reading: dict[str, Any],
    correlation_id: str,
) -> None:
    timeline.emit("Twin", "reading", reading["sim_tick"], reading, correlation_id)


def guardian_verdict(
    timeline: Timeline,
    sim_tick: int,
    correlation_id: str,
    verdict: str,
    reason: str,
    device_ids: list[str],
    registry: Any,
) -> None:
    for device_id in device_ids:
        if verdict == "UNTRUSTED":
            registry.set_restricted(device_id, True, reason)
            timeline.emit(
                "Guardian",
                "isolate_device",
                sim_tick,
                {
                    "device_id": device_id,
                    "action": "quarantine",
                    "status": registry.get_device(device_id)["status"],
                    "adapter": "scenario_fixture",
                },
                correlation_id,
            )
    timeline.emit(
        "Guardian",
        "verdict",
        sim_tick,
        {
            "verdict": verdict,
            "reason": reason,
            "device_ids": device_ids,
            "latency_target_seconds": 10,
            "latency_ms": timeline.correlation_elapsed_ms(correlation_id),
            "adapter": "scenario_fixture",
        },
        correlation_id,
    )


def run_t5(s: dict[str, Any], timeline: Timeline, registry: Any, sensors: Any, actuators: Any) -> None:
    fixture = s["fixture"]
    sensor_id = fixture["sensor_id"]
    trigger = next(t for t in s["triggers"] if t["action"] == "INJECT_FAULT")
    sensors.sample_sensor(sensor_id, fixture["ground_truth_value"], 4, 1)
    sensors.inject_fault(sensor_id, trigger["fault_type"], trigger["parameters"])
    tick = trigger["sim_tick"]
    corr = correlation(timeline.run_id[:8], sensor_id, str(tick))
    reading = sensors.sample_sensor(sensor_id, fixture["ground_truth_value"], tick, 2)
    emit_reading(timeline, reading, corr)
    trusted = (
        reading["reported_value"] == reading["actual_value"]
        and reading["status"] == "OK"
    )
    verdict = "TRUSTED" if trusted else "UNTRUSTED"
    guardian_verdict(
        timeline,
        tick,
        corr,
        verdict,
        "reported_value differs from physical ground truth",
        [sensor_id] if not trusted else [],
        registry,
    )
    decision = "OPEN_DISCHARGE" if trusted else "REFUSE_FLOOD_RESPONSE"
    timeline.emit(
        "City Brain",
        "decision",
        tick,
        {
            "decision": decision,
            "trust_verdict": verdict,
            "reason": "untrusted sensor; no actuator dispatch" if not trusted else "trusted",
        },
        corr,
    )
    if trusted:
        result = actuators.dispatch_command(
            fixture["actuator_id"], "START", {"duration_ticks": 1}, corr
        )
        timeline.emit("Twin", "actuator_action", tick, result, corr)
    else:
        timeline.emit(
            "Twin",
            "actuator_action",
            tick,
            {
                "status": "NOT_DISPATCHED",
                "error": "UNTRUSTED_SENSOR",
                "device_id": fixture["actuator_id"],
            },
            corr,
        )
    sensors.clear_fault(sensor_id)


def run_scn_02(s: dict[str, Any], timeline: Timeline, registry: Any, sensors: Any, actuators: Any) -> None:
    fixture = s["fixture"]
    tick = s["triggers"][0]["sim_tick"]
    sensor_id = fixture["sensor_id"]
    corr = correlation(timeline.run_id[:8], "real-flood", sensor_id)
    reading = sensors.sample_sensor(sensor_id, fixture["ground_truth_value"], tick, 1)
    emit_reading(timeline, reading, corr)
    trusted = reading["actual_value"] == reading["reported_value"]
    verdict = "TRUSTED" if trusted else "UNTRUSTED"
    guardian_verdict(timeline, tick, corr, verdict, "dual-state consistency check", [], registry)
    decision = "OPEN_DISCHARGE" if trusted else "REFUSE_FLOOD_RESPONSE"
    timeline.emit(
        "City Brain",
        "decision",
        tick,
        {"decision": decision, "trust_verdict": verdict, "threshold_cm": 100.0},
        corr,
    )
    if not trusted:
        timeline.emit(
            "Twin",
            "actuator_action",
            tick,
            {"status": "NOT_DISPATCHED", "error": "UNTRUSTED_SENSOR"},
            corr,
        )
        return
    command_id = corr
    timeline.emit(
        "Runner",
        "actuator_state",
        tick,
        {
            "command_id": command_id,
            "device_id": fixture["actuator_id"],
            "status": "PENDING",
            "note": "pre-dispatch timeline marker; not an ActuatorEngine state",
        },
        corr,
    )
    result = actuators.dispatch_command(
        fixture["actuator_id"],
        fixture["command"],
        fixture["params"],
        command_id,
    )
    timeline.emit("Twin", "actuator_state", tick, result, corr)
    if result["status"] != "RUNNING":
        return
    for progress_tick in range(1, fixture["params"]["duration_ticks"] + 1):
        effects = actuators.tick_progress()
        status = actuators.get_status(command_id)
        timeline.emit("Twin", "actuator_state", tick + progress_tick, status, corr)
        if effects:
            timeline.emit(
                "Twin",
                "effect_returned",
                tick + progress_tick,
                {
                    "effects": effects,
                    "applied_to_city_core": False,
                    "note": "Scenario runner records effects; city_core integration is not present.",
                },
                corr,
            )


def run_scn_03(s: dict[str, Any], timeline: Timeline, registry: Any, sensors: Any, actuators: Any) -> None:
    f = s["fixture"]
    tick = s["triggers"][0]["sim_tick"]
    traffic_corr = correlation(timeline.run_id[:8], "traffic-stuck")
    sensors.sample_sensor(f["traffic_sensor_id"], f["traffic_before_fault"], tick - 1, 1)
    sensors.inject_fault("DTN-TRF-01", "STUCK", {})
    traffic = sensors.sample_sensor(
        f["traffic_sensor_id"], f["traffic_actual_during_fault"], tick, 2
    )
    emit_reading(timeline, traffic, traffic_corr)
    guardian_verdict(
        timeline, tick, traffic_corr, "UNTRUSTED",
        "traffic telemetry repeated its pre-fault value (no variance)",
        [f["traffic_sensor_id"]], registry,
    )
    dead_corr = correlation(timeline.run_id[:8], "temperature-dead")
    sensors.inject_fault(f["dead_sensor_id"], "DEAD", {})
    dead = sensors.sample_sensor(
        f["dead_sensor_id"], f["dead_sensor_actual"], tick, 1
    )
    emit_reading(timeline, dead, dead_corr)
    guardian_verdict(
        timeline, tick, dead_corr, "UNTRUSTED",
        "temperature sensor stopped producing values",
        [f["dead_sensor_id"]], registry,
    )
    backup = sensors.sample_sensor(
        f["backup_sensor_id"], f["backup_actual"], tick + 1, 1
    )
    timeline.emit(
        "City Brain",
        "fallback_feed",
        tick + 1,
        {
            "ignored_sensor_ids": [f["traffic_sensor_id"], f["dead_sensor_id"]],
            "backup_reading": backup,
            "decision": "use_compatible_temperature_backup",
            "adapter": "scenario_fixture",
        },
        dead_corr,
    )


def run_scn_04(s: dict[str, Any], timeline: Timeline, registry: Any, sensors: Any, actuators: Any) -> None:
    f = s["fixture"]
    tick = s["triggers"][0]["sim_tick"]
    target = f["actuator_id"]
    backup_id = f["backup_actuator_id"]
    corr = correlation(timeline.run_id[:8], "quarantined-actuator", target)
    registry.set_restricted(target, True, s["triggers"][0]["reason"])
    timeline.emit(
        "Guardian",
        "isolate_device",
        tick,
        {
            "device_id": target,
            "action": "quarantine",
            "status": registry.get_device(target)["status"],
            "adapter": "scenario_fixture",
        },
        corr,
    )
    timeline.emit(
        "City Brain",
        "trust_query",
        tick,
        {"device_id": target, "query": "is this actuator trusted and dispatchable?"},
        corr,
    )
    timeline.emit(
        "Guardian",
        "trust_response",
        tick,
        {
            "device_id": target,
            "verdict": "UNTRUSTED",
            "restriction_reason": registry.get_device(target)["restriction_reason"],
        },
        corr,
    )
    timeline.emit(
        "City Brain",
        "decision",
        tick,
        {
            "decision": "dispatch_requested_with_failover",
            "device_id": target,
            "trust_verdict": "UNTRUSTED",
        },
        corr,
    )
    rejected = actuators.dispatch_command(target, f["command"], {}, corr)
    timeline.emit("Twin", "actuator_action", tick, rejected, corr)
    compatible = registry.get_compatible_devices(target)
    timeline.emit(
        "City Brain",
        "failover_lookup",
        tick,
        {
            "source_device_id": target,
            "compatible_device_ids": [device["device_id"] for device in compatible],
        },
        corr,
    )
    if not any(device["device_id"] == backup_id for device in compatible):
        timeline.emit(
            "City Brain",
            "failover_failed",
            tick,
            {"device_id": backup_id, "reason": "no available compatible backup"},
            corr,
        )
        return
    failover_corr = correlation(corr, "failover", backup_id)
    dispatched = actuators.dispatch_command(
        backup_id, f["command"], {"duration_ticks": 1}, failover_corr
    )
    timeline.emit("Twin", "actuator_action", tick, dispatched, failover_corr)
    if dispatched["status"] == "RUNNING":
        for _ in range(1):
            effects = actuators.tick_progress()
        timeline.emit(
            "Twin",
            "actuator_state",
            tick + 1,
            actuators.get_status(failover_corr),
            failover_corr,
        )
        if effects:
            timeline.emit(
                "Twin",
                "effect_returned",
                tick + 1,
                {"effects": effects, "applied_to_city_core": False},
                failover_corr,
            )


def run_scn_05(s: dict[str, Any], timeline: Timeline, registry: Any, sensors: Any, actuators: Any) -> None:
    f = s["fixture"]
    tick = s["triggers"][0]["sim_tick"]
    traffic_corr = correlation(timeline.run_id[:8], "accident", f["traffic_sensor_id"])
    traffic = sensors.sample_sensor(
        f["traffic_sensor_id"], f["traffic_actual"], tick, 1
    )
    emit_reading(timeline, traffic, traffic_corr)
    guardian_verdict(
        timeline, tick, traffic_corr, "TRUSTED",
        "authentic traffic ground truth and reported value match", [], registry,
    )
    timeline.emit(
        "City Brain",
        "decision",
        tick,
        {"decision": "ROUTE_EMERGENCY", "trust_verdict": "TRUSTED"},
        traffic_corr,
    )
    traffic_command = actuators.dispatch_command(
        f["actuator_id"],
        f["command"],
        {"duration_ticks": 1, "corridor": "DTN-PRIORITY"},
        traffic_corr,
    )
    timeline.emit("Twin", "actuator_action", tick, traffic_command, traffic_corr)
    if traffic_command["status"] == "RUNNING":
        effects = actuators.tick_progress()
        timeline.emit(
            "Twin",
            "actuator_state",
            tick + 1,
            actuators.get_status(traffic_corr),
            traffic_corr,
        )
        if effects:
            timeline.emit(
                "Twin",
                "effect_returned",
                tick + 1,
                {"effects": effects, "applied_to_city_core": False},
                traffic_corr,
            )

    air_corr = correlation(timeline.run_id[:8], "spoofed-air", f["air_sensor_id"])
    air_reading = {
        "sensor_id": f["air_sensor_id"],
        "zone_id": "RES",
        "type": "air_quality",
        "unit": "AQI",
        "sim_tick": tick,
        "seq": 1,
        "actual_value": f["air_actual"],
        "reported_value": f["air_reported"],
        "delta": round(f["air_reported"] - f["air_actual"], 2),
        "status": "OK",
        "fault": "FALSE_READING",
        "available": True,
        "scenario_local_fixture": True,
    }
    timeline.emit("Twin", "fixture_reading", tick, air_reading, air_corr)
    guardian_verdict(
        timeline, tick, air_corr, "UNTRUSTED",
        "scenario-local air fixture reported a value inconsistent with ground truth",
        [], registry,
    )
    timeline.emit(
        "Guardian",
        "isolate_device",
        tick,
        {
            "device_id": f["air_sensor_id"],
            "action": "quarantine_fixture",
            "adapter": "scenario_fixture",
        },
        air_corr,
    )
    timeline.emit(
        "City Brain",
        "decision",
        tick,
        {
            "decision": "SUPPRESS_AIR_ALARM",
            "trust_verdict": "UNTRUSTED",
            "reason": "scenario-local test feed quarantined",
        },
        air_corr,
    )
    timeline.emit(
        "Twin",
        "actuator_action",
        tick,
        {"status": "NOT_DISPATCHED", "reason": "untrusted air-quality fixture"},
        air_corr,
    )


RUNNERS = {
    "T5": run_t5,
    "SCN-02": run_scn_02,
    "SCN-03": run_scn_03,
    "SCN-04": run_scn_04,
    "SCN-05": run_scn_05,
}


def create_log_path(scenario_id: str) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return LOG_DIR / f"{scenario_id.lower()}-{stamp}.log"


def execute(scenario: dict[str, Any]) -> Path:
    DeviceRegistry, SensorEngine, ActuatorEngine = load_twin_modules()
    registry = DeviceRegistry(str(SEED_PATH))
    sensor_engine = SensorEngine(registry, seed=int(scenario["fixture"]["seed"]))
    actuator_engine = ActuatorEngine(registry)
    log_path = create_log_path(scenario["ID"])
    timeline = Timeline(scenario["ID"], log_path)
    try:
        timeline.emit(
            "Runner",
            "scenario_started",
            0,
            {
                "name": scenario["Name"],
                "run_id": timeline.run_id,
                "guardian_brain_mode": "deterministic scenario adapters",
                "layers_involved": scenario["Layers involved"],
            },
            timeline.run_id,
        )
        runner = RUNNERS.get(scenario["ID"])
        if runner is None:
            raise ValueError(f"No scenario implementation for {scenario['ID']}")
        runner(scenario, timeline, registry, sensor_engine, actuator_engine)
        timeline.emit(
            "Runner",
            "scenario_completed",
            int(scenario.get("duration_ticks", 1)),
            {"log_file": str(log_path.relative_to(ROOT))},
            timeline.run_id,
        )
    except Exception as error:
        timeline.emit(
            "Runner",
            "scenario_failed",
            0,
            {
                "error_type": type(error).__name__,
                "error": str(error),
                "traceback": traceback.format_exc(),
            },
            timeline.run_id,
        )
        raise
    finally:
        timeline.close()
    return log_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        required=True,
        help="Scenario ID: t5, scn-02, scn-03, scn-04, or scn-05",
    )
    args = parser.parse_args()
    try:
        scenario = load_scenario(args.scenario)
        path = execute(scenario)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(f"Append-only timeline log: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
