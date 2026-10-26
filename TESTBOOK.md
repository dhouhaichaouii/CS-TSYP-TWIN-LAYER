# Phase 1 Test Book

The commands below each launch exactly one scenario. Each run creates a new,
append-only JSON Lines timeline under `logs/`; event records include a run ID,
sequence number, simulated tick, layer, event type, and correlation ID.

**Integration boundary:** This repository contains the Twin registry, sensor,
and actuator engines, but no Guardian or City Brain service implementation.
`scenarios/run.py` therefore exercises the real Twin code and emits explicitly
labeled deterministic scenario-adapter events for Guardian and City Brain.
Those adapter verdicts and decisions are test fixtures, not evidence that
external Guardian/Brain services ran. The air-quality feed in SCN-05 is also a
scenario-local fixture because no Residential air-quality sensor is present in
the immutable device seed. Completed actuator effects are logged as returned
data; the runner does not apply them to `city_core`.

| ID | Name | Layers involved | Description | Trigger | Expected: Twin | Expected: Guardian | Expected: Brain | How to verify |
|---|---|---|---|---|---|---|---|---|
| T5 (SCN-01) | Fake flood at the port | Twin, Guardian, City Brain | At tick 5, PRT-WLV-01 reports 180 cm while its physical input remains 40 cm. | `python scenarios/run.py --scenario t5` | The real SensorEngine emits `actual_value: 40.0`, `reported_value: 180.0`, and the sensor is marked RESTRICTED after quarantine. No actuator command is sent. | The deterministic adapter marks the reading UNTRUSTED at the same simulation tick (within the stated 10-second target) and quarantines PRT-WLV-01. | The deterministic adapter refuses the flood response because the only reading is untrusted. | Follow the `correlation_id` from Twin `reading` to Guardian `verdict`, City Brain `decision`, and Twin `actuator_action` (`NOT_DISPATCHED`) in the terminal and `logs/t5-*.log`. |
| SCN-02 | Harbor basin surge and emergency valve dispatch | Twin, Guardian, City Brain | Authentic rain accumulation raises port basin level from 40 cm to 110 cm. | `python scenarios/run.py --scenario scn-02` | The real SensorEngine reports matching actual/reported 110 cm. The runner records a PENDING timeline marker before dispatch; the real ActuatorEngine advances PRT-PMP-01 from RUNNING to COMPLETED. Completion effects are recorded but not applied to `city_core`. | The deterministic adapter returns TRUSTED after checking dual-state equality. | The deterministic adapter recognizes the >100 cm threshold and dispatches START to PRT-PMP-01. | Follow the reading → TRUSTED → OPEN_DISCHARGE → actuator state events in `logs/scn-02-*.log`; the effect event documents that city_core integration is absent. |
| SCN-03 | Sensor death and frozen traffic telemetry | Twin, Guardian, City Brain | DTN-TRF-01 freezes at its pre-fault value while IND-TMP-01 dies during the same test step. | `python scenarios/run.py --scenario scn-03` | The real SensorEngine returns the frozen traffic value with the current STUCK contract status (`OK`), and the dead temperature reading is `null` with status FAILED. | The deterministic adapter detects lack of variance and missing telemetry, marks both streams UNTRUSTED, and quarantines both devices. | The deterministic adapter ignores the quarantined feeds and samples compatible backup IND-TMP-02. | Inspect both reading events, Guardian isolation events, and City Brain `fallback_feed` in `logs/scn-03-*.log`. |
| SCN-04 | Guardian containment prevents unsafe Brain dispatch | Brain, Guardian, Twin | PRT-PMP-01 is quarantined before City Brain requests an operational start. | `python scenarios/run.py --scenario scn-04` | The real ActuatorEngine rejects the primary command with FAILED / GUARDIAN_RESTRICTED, then runs the available backup PRT-PMP-02 command. | The deterministic adapter quarantines PRT-PMP-01 before dispatch. | The deterministic adapter observes rejection, queries the registry's compatible backup, and routes to PRT-PMP-02. | Verify quarantine → rejected command → compatible-device lookup → backup completion in `logs/scn-04-*.log`. |
| SCN-05 | Concurrent real emergency and spoofing attack | Twin, Guardian, City Brain | An authentic Downtown accident and a spoofed Residential air-quality fixture occur at the same simulation tick. | `python scenarios/run.py --scenario scn-05` | The real traffic SensorEngine reports 105 vehicles/min. The air-quality spoof is an explicitly marked scenario-local fixture (`RES-AIR-TEST-01`), not a seeded device. | The deterministic adapter trusts the traffic reading and quarantines the inconsistent air fixture. | The deterministic adapter dispatches the Downtown priority signal and suppresses the response to the untrusted air fixture. | Compare the separate traffic and air `correlation_id` chains in `logs/scn-05-*.log`; confirm signal completion and no air-response dispatch. |

## Run and inspect

Run any one scenario from the repository root:

```text
python scenarios/run.py --scenario t5
python scenarios/run.py --scenario scn-02
python scenarios/run.py --scenario scn-03
python scenarios/run.py --scenario scn-04
python scenarios/run.py --scenario scn-05
```

Each invocation creates its own `logs/<scenario-id>-<UTC timestamp>.log` file.
Files are opened with exclusive creation and are never overwritten. Every JSON
line is flushed as it is emitted, so a failed run retains its preceding audit
events and includes a `scenario_failed` record.
