# City Brain Convergence — Phase 1 Final Report

## Part 4 — Test Scenarios

The five scenarios below cover Twin-to-Brain, Twin-to-Guardian, Brain-to-Guardian,
and simultaneous three-layer interactions. Each scenario is launched by one
command and writes its own ordered JSON Lines audit trail under `logs/`.

**Implementation boundary:** The repository provides the Twin device registry,
sensor engine, and actuator engine, but does not include Guardian or City Brain
services. The runner invokes real Twin modules and labels the Guardian/Brain
events as deterministic scenario adapters; it does not claim to execute the
missing services. SCN-05's Residential air-quality signal is a scenario-local
test fixture because that sensor is absent from the device seed. Actuator
effects are logged as returned data and are not applied to `city_core`.

| ID | Name | Layers involved | Description | Trigger | Expected: Twin | Expected: Guardian | Expected: Brain | How to verify |
|---|---|---|---|---|---|---|---|---|
| T5 (SCN-01) | Fake flood at the port | Twin, Guardian, City Brain | At tick 5, PRT-WLV-01 reports 180 cm while its physical input remains 40 cm. | `python scenarios/run.py --scenario t5` | The SensorEngine emits `actual_value: 40.0`, `reported_value: 180.0`, and the sensor is marked RESTRICTED after quarantine. No actuator command is sent. | The deterministic adapter marks the reading UNTRUSTED at the same simulation tick (within the stated 10-second target) and quarantines PRT-WLV-01. | The deterministic adapter refuses the flood response because the only reading is untrusted. | Follow the `correlation_id` from Twin `reading` to Guardian `verdict`, City Brain `decision`, and Twin `actuator_action` (`NOT_DISPATCHED`) in the terminal and `logs/t5-*.log`. |
| SCN-02 | Harbor basin surge and emergency valve dispatch | Twin, Guardian, City Brain | Authentic rain accumulation raises port basin level from 40 cm to 110 cm. | `python scenarios/run.py --scenario scn-02` | The SensorEngine reports matching actual/reported 110 cm. The runner records a PENDING timeline marker before dispatch; the ActuatorEngine advances PRT-PMP-01 from RUNNING to COMPLETED. Completion effects are recorded but not applied to `city_core`. | The deterministic adapter returns TRUSTED after checking dual-state equality. | The deterministic adapter recognizes the >100 cm threshold and dispatches START to PRT-PMP-01. | Follow the reading → TRUSTED → OPEN_DISCHARGE → actuator state events in `logs/scn-02-*.log`; the effect event documents that city_core integration is absent. |
| SCN-03 | Sensor death and frozen traffic telemetry | Twin, Guardian, City Brain | DTN-TRF-01 freezes at its pre-fault value while IND-TMP-01 dies during the same test step. | `python scenarios/run.py --scenario scn-03` | The SensorEngine returns the frozen traffic value with the current STUCK contract status (`OK`), and the dead temperature reading is `null` with status FAILED. | The deterministic adapter detects lack of variance and missing telemetry, marks both streams UNTRUSTED, and quarantines both devices. | The deterministic adapter ignores the quarantined feeds and samples compatible backup IND-TMP-02. | Inspect both reading events, Guardian isolation events, and City Brain `fallback_feed` in `logs/scn-03-*.log`. |
| SCN-04 | Guardian containment prevents unsafe Brain dispatch | Brain, Guardian, Twin | PRT-PMP-01 is quarantined before City Brain requests an operational start. | `python scenarios/run.py --scenario scn-04` | The ActuatorEngine rejects the primary command with FAILED / GUARDIAN_RESTRICTED, then runs the available backup PRT-PMP-02 command. | The deterministic adapter quarantines PRT-PMP-01 before dispatch and answers the Brain trust query. | The deterministic adapter observes rejection, queries Guardian, checks the registry's compatible backup, and routes to PRT-PMP-02. | Verify quarantine → Brain trust query → Guardian trust response → rejected command → compatible-device lookup → backup completion in `logs/scn-04-*.log`. |
| SCN-05 | Concurrent real emergency and spoofing attack | Twin, Guardian, City Brain | An authentic Downtown accident and a spoofed Residential air-quality fixture occur at the same simulation tick. | `python scenarios/run.py --scenario scn-05` | The traffic SensorEngine reports 105 vehicles/min. The air-quality spoof is an explicitly marked scenario-local fixture (`RES-AIR-TEST-01`), not a seeded device. | The deterministic adapter trusts the traffic reading and quarantines the inconsistent air fixture. | The deterministic adapter dispatches the Downtown priority signal and suppresses the response to the untrusted air fixture. | Compare the separate traffic and air `correlation_id` chains in `logs/scn-05-*.log`; confirm signal completion and no air-response dispatch. |

All executions are reproducible from the seed stored in each scenario fixture.
Each run receives a unique ID; its audit events include UTC timestamps,
simulation ticks, sequence numbers, layer names, correlation IDs, and measured
correlation latency.
