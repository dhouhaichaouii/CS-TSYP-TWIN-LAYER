"""Translate Person B scenario JSON into LiveCity actions.

B's standalone runner is deliberately not imported: its fixture logic is kept
as scenario data, and the effects are applied to the real city core here.
"""
from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re

from .records import LiveError

SCENARIO_DIR = Path(__file__).resolve().parents[2] / "scenarios"


@dataclass(frozen=True, slots=True)
class Trigger:
    sim_tick: int
    action: str
    target: str
    fault_type: str | None
    parameters: dict
    reason: str
    after_scenario: bool
    scenario_local_fixture: bool


@dataclass(frozen=True, slots=True)
class Scenario:
    scenario_id: str
    name: str
    duration_ticks: int
    triggers: tuple
    fixture: dict


def _aliases(scenario_id, path):
    values = {scenario_id.lower(), scenario_id.lower().replace("_", "-"),
              path.stem.lower(), path.stem.lower().replace("_", "-")}
    match = re.match(r"scn[_-]?0*(\d+)", path.stem.lower())
    if match:
        number = match.group(1)
        values.update({f"scn-{number}", f"scn_{number}", f"scn-0{number}",
                       f"scn_0{number}"})
    if scenario_id.upper() == "T5":
        values.add("t5")
    return values


@lru_cache(maxsize=1)
def load_scenarios():
    result = {}
    for path in sorted(SCENARIO_DIR.glob("scn_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        triggers = tuple(
            Trigger(
                int(row["sim_tick"]), row["action"], row["target_device_id"],
                row.get("fault_type"), dict(row.get("parameters", {})),
                row.get("reason", ""), bool(row.get("after_scenario", False)),
                bool(row.get("scenario_local_fixture", False)),
            )
            for row in data["triggers"]
        )
        scenario = Scenario(data["ID"], data["Name"],
                            int(data.get("duration_ticks", 1)), triggers,
                            dict(data.get("fixture", {})))
        for alias in _aliases(scenario.scenario_id, path):
            result[alias] = scenario
    return result


def scenario(name):
    found = load_scenarios().get(str(name).lower().replace("_", "-"))
    if found is None:
        raise LiveError("UNSUPPORTED_SCENARIO")
    return found


def _fault_params(kind, params):
    if kind == "FALSE_READING":
        if "fixed_value" in params:
            return {"value": params["fixed_value"]}
        if "offset" in params:
            return {"offset": params["offset"]}
    if kind == "DRIFT" and "rate_per_tick" in params:
        return {"rate": params["rate_per_tick"]}
    if kind == "NOISE" and "amplitude" in params:
        return {"amplitude": params["amplitude"]}
    if kind == "DELAYED" and "lag_ticks" in params:
        return {"lag_ticks": params["lag_ticks"]}
    if kind == "DROPOUT" and "duration_ticks" in params:
        return {"duration_ticks": params["duration_ticks"]}
    return dict(params)


class ScenarioRunner:
    def __init__(self, city):
        self.city = city
        self.reset()

    def reset(self):
        self.scenario = None
        self.start_tick = None
        self.processed = set()
        self.done = False
        self.commands_sent = False
        self.truth_ids = set()

    def start(self, name):
        self.scenario = scenario(name)
        self.start_tick = self.city._snapshot().context.tick
        self.processed = set()
        self.done = False
        self.commands_sent = False
        self.truth_ids = set()
        self._setup()
        return self.scenario

    def _setup(self):
        s = self.scenario
        sensors = self.city._sensors
        if s.scenario_id == "T5":
            self._truth("PRT-WLV-01", 40.0)
            sensors.force_sample("PRT-WLV-01", self.start_tick + 5)
        elif s.scenario_id == "SCN-02":
            self._truth("PRT-WLV-01", 110.0)
            sensors.force_sample("PRT-WLV-01", self.start_tick + 1)
        elif s.scenario_id == "SCN-03":
            self._truth("DTN-TRF-01", 55.0)
            self._truth("IND-TMP-01", 71.0)
            self._truth("IND-TMP-02", 70.0)
            sensors.seed_last_valid("DTN-TRF-01", 48.0)
            sensors.force_sample("IND-TMP-02", self.start_tick + 3)
        elif s.scenario_id == "SCN-05":
            sensors.add_scenario_sensor(
                "RES-AIR-TEST-01", zone_id="RES", type="air_quality",
                unit="ug/m3", description="Scenario-local air-quality fixture",
                normal_limits=(0, 100), hard_limits=(0, 1000), interval=1,
            )
            self._truth("DTN-TRF-01", 105.0)
            self._truth("RES-AIR-TEST-01", 18.0)
            sensors.force_sample("DTN-TRF-01", self.start_tick + 5)
            sensors.force_sample("RES-AIR-TEST-01", self.start_tick + 5)

    def _truth(self, sensor_id, value):
        self.city._sensors.set_truth(sensor_id, float(value))
        self.truth_ids.add(sensor_id)

    def advance(self, tick):
        if self.scenario is None or self.done:
            return
        for index, trigger in enumerate(self.scenario.triggers):
            if index in self.processed or trigger.after_scenario:
                continue
            absolute = self.start_tick + trigger.sim_tick
            if absolute != tick:
                continue
            self.processed.add(index)
            if trigger.action == "SET_GROUND_TRUTH":
                value = trigger.parameters.get("value", trigger.parameters.get("to_cm"))
                if value is not None:
                    self._truth(trigger.target, float(value))
                    self.city._sensors.force_sample(trigger.target, tick)
            elif trigger.action == "INJECT_FAULT":
                if trigger.scenario_local_fixture and self.city._sensors.sensor_row(
                        trigger.target) is None:
                    self.city._sensors.add_scenario_sensor(
                        trigger.target, zone_id="RES", type="air_quality",
                        unit="ug/m3", description="Scenario-local fixture",
                        normal_limits=(0, 100), hard_limits=(0, 1000), interval=1,
                    )
                try:
                    self.city._sensors.inject(
                        trigger.target, trigger.fault_type,
                        _fault_params(trigger.fault_type, trigger.parameters),
                        tick, allow_unbound=True,
                    )
                    self.city._sensors.force_sample(trigger.target, tick)
                    if trigger.scenario_local_fixture:
                        self.city.quarantine_device(trigger.target, "scenario_local_fixture")
                except LiveError as error:
                    if error.code != "FAULT_ALREADY_ACTIVE":
                        raise
            elif trigger.action == "CLEAR_FAULT":
                self.city._sensors.clear(trigger.target, repair=True)
            elif trigger.action == "QUARANTINE":
                self.city.quarantine_device(trigger.target, trigger.reason or "scenario")
            else:
                raise LiveError("UNSUPPORTED_OPERATION")
        self._fixture_commands(tick)

    def _fixture_commands(self, tick):
        s = self.scenario
        if self.commands_sent or tick != self.start_tick + s.triggers[0].sim_tick:
            return
        self.commands_sent = True
        fixture = s.fixture
        device = fixture.get("actuator_id")
        command = fixture.get("command")
        if not device or not command:
            return
        requested = {"START": True, "STOP": False, "SET_PRIORITY_CORRIDOR": "priority",
                     "OPEN": False, "CLOSE": True}.get(command.upper(), command)
        try:
            self.city.command(device, requested,
                              command_id=f"b-{s.scenario_id}-{tick}-{device}")
        except LiveError:
            pass
        if s.scenario_id == "SCN-04":
            backup = fixture.get("backup_actuator_id")
            if backup:
                try:
                    self.city.command(backup, True,
                                      command_id=f"b-{s.scenario_id}-{tick}-{backup}")
                except LiveError:
                    pass

    def finish(self, tick):
        if self.scenario is None or self.done:
            return
        last_trigger = max(trigger.sim_tick for trigger in self.scenario.triggers)
        end = self.start_tick + last_trigger + self.scenario.duration_ticks
        if tick < end:
            return
        self.done = True
        for index, trigger in enumerate(self.scenario.triggers):
            if index in self.processed or not trigger.after_scenario:
                continue
            self.processed.add(index)
            if trigger.action == "CLEAR_FAULT":
                self.city._sensors.clear(trigger.target, repair=True)
        for sensor_id in self.truth_ids:
            self.city._sensors.clear_truth(sensor_id)
