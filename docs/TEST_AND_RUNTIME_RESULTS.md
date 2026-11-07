# Causal Twin test and runtime results

**Run date:** 7 November 2026  
**Runtime:** Python 3.12.16 on Windows  
**Scope:** Software-only Twin simulation. No physical equipment, IoT devices,
or real-world actuation was used.

This is the causal-feedback implementation's validation record. The existing
root-level `TEST_AND_RUNTIME_RESULTS.md` is a separate historical audit and is
left unchanged.

## Architecture outcome

Before this change, the Twin exposed command and sensor paths but lacked a
consistent, evidence-based actor-to-state/sensor registry and truthful
execution details at the Brain-facing façade. Pump speed already had a
fractional CityCore representation in the user-modified baseline, but the
command receipt/correlation path and ambiguous actor mappings still needed
alignment.

After this change, supported commands resolve through the generated actor
catalog, validate before effect application, and return a committed execution
receipt with requested/effective values and correlation ID. Later simulation
ticks sample the updated CityCore or sensor-model state; reported sensor
faults remain downstream. Brain observations remain pull-based through the
existing REST/MCP façade. See [CAUSAL_SIMULATION.md](./CAUSAL_SIMULATION.md)
for the complete lifecycle, actor/sensor catalog, equations, and boundaries.

## Actor-to-state summary

| Actor(s) | Canonical state affected | Sensor relationship |
|---|---|---|
| `PRT-PMP-01`, `PRT-PMP-02`, `P-03` | CityCore `P-03` speed fraction and water balance. Both PRT IDs explicitly share one target; neither is an independent backup. | No registered PRT sensor measures the CityCore basin. |
| `V-12` | CityCore valve opening fraction and inlet flow. | No registered sensor measures this CityCore basin path. |
| `IND-VLV-01`, `DTN-VLV-01`, `RES-VLV-01` | Unsupported cross-zone mappings; no state change. | None. |
| `DTN-TLT-01` / `J-D1` | Road capacities on `R-LOW` and `R-IND`, then completed departures. | `DTN-TRF-01` (`R-LOW`). |
| `DTN-TLT-02` / `J-D2` | Road capacities on `R-DOWN` and `R-LINK`, then completed departures. | `DTN-TRF-02` (`R-DOWN`) and `RES-TRF-01` (`R-LINK`). |
| `RES-TLT-01` | Unsupported; no CityCore target. | None. |
| `F-URBAN`, `F-IND`, `F-ESS` | Their explicitly bound feeder power states. | `F-URBAN` affects its mapped model sensors; `F-IND` affects Industrial model sensors; `F-ESS` has no linked sensor. |
| `AMB-01`, `AMB-02`, `POL-01` | Responder mission, destination, route, progress, blocked/arrived status, and release state. | No registered sensor measures responder status. |

## Sensor sources and causal rules

Sensors project canonical simulation state and are sampled after a simulation
tick when their configured interval is due. Sensor faults transform reported
measurements only; they do not edit the underlying CityCore or model state.
The full per-sensor mapping, units, intervals, and equations are in
[CAUSAL_SIMULATION.md](./CAUSAL_SIMULATION.md).

Implemented rules verified here:

- Pump requested speed is `speed_pct / 100`; pump discharge capacity is
  `1.2 m^3/s * speed_fraction`, subject to existing CityCore water-balance
  constraints.
- Valve inlet flow is `0.6 m^3/s * opening_fraction`.
- Road capacity is base capacity times remaining unblocked fraction times the
  signal multiplier: normal `1.0`, priority `1.5`, stop/unpowered `0`.
  Completed departures drive the registered traffic counters.
- Responder dispatch reserves an available unit and validates the route.
  Travel progress uses the existing CityCore rule
  `road_length / free_speed + queue / capacity`, advanced by at most one
  second per tick; blocked roads pause progress.
- No equation connects the separate PDF Harbour sensors to CityCore pump or
  valve state, so no such response is claimed.

## Command and integration lifecycle

`LiveCity` validates actor, action, parameters, run/revision, quarantine, and
idempotency before applying an effect. A duplicate command ID replays the
original result; a changed payload is rejected. Accepted, executed, rejected,
and failed outcomes remain distinct. The façade reports `EXECUTED` only after
the CityCore effect commits and includes requested/effective effects,
correlation ID, revision, and commit status. Rejections are audited and report
`city_core_updated: false`.

The deterministic SCN-05 causal test exercises an initial sensor observation,
a Brain-role read, sequential signal interventions, CityCore state changes,
and later sensor reads. Brain and Guardian in this repository are in-process
mocks; the Twin does not launch or push to external Brain services. Real
service-to-service integration remains unverified. Scenario inputs and fault
triggers continue to come from existing scenario definitions.

## Verification results

| Suite / check | Result |
|---|---|
| Focused command, idempotency, sensor, scenario, interface, and causal tests | **77 passed**, 0 failures/errors |
| Full live runner (`tools/run_live_checks.py`) | **125 passed**, 0 failures/errors/skips; configured executable-line coverage gate passed |
| Full dashboard runner (`tools/run_dashboard_checks.py`) | **43 passed**, 0 failures/errors/skips; configured executable-line coverage gate passed |
| Full core runner (`tools/run_checks.py`) | **252 tests**; 3 failures and 1 error; CityCore executable-line coverage gate passed |
| Standalone mock-backed run | **PASS**; Guardian isolated `PRT-WLV-01`, Brain mock dispatched `PRT-PMP-02`; 4 events and 42 JSONL lines recorded |

The core-runner failures are in existing ASGI contract expectations:
`test_openapi_describes_rest_query_and_json_body_parameters` errors because
the OpenAPI sensor path lacks the expected `parameters` key; three
`test_asgi_app` cases expect dashboard/login routes to return HTTP 200 but get
404. These routes were not changed for this task. The durable-idempotency
fixture and stale cross-zone valve expectation exposed during the run were
updated to match the current correlation-ID and unsupported-mapping contracts.

The command catalog was regenerated from the checked-in YAML/JSON sources
using the existing Python 3.12 virtual environment. The test runner evidence
is under the ignored `tmp/causal-validation/` directory.

### Standalone command

The successful run used a fresh run ID to avoid appending to prior user logs:

```powershell
tmp/twin-audit-venv/Scripts/python.exe -X utf8 tools/run_standalone.py --ticks 1150 --run-id causal-validation-20261107
```

Its JSONL record is `logs/standalone_causal-validation-20261107.jsonl`.
This verifies the local mock-backed demonstration, not external Brain or
Guardian integration.

## Remaining unsupported behavior

- The cross-zone logical valves have no approved mapping to the single PRT
  `V-12` target and are rejected.
- `RES-TLT-01` has no supported CityCore signal target.
- The two PRT pump IDs share `P-03`; the second is not an independent backup.
- PRT Harbour PDF sensors use a separate deterministic model, not CityCore's
  River basin; pump/valve-to-PRT-sensor causality is therefore unsupported.
- No registered sensor measures responder progress.
- No external Brain/Guardian endpoint, physical gateway, or hardware was
  configured or tested.
