# Known limitations

These limitations describe the current implementation and should be stated during jury review.

## Partner integration and trust

- Real Brain and Guardian clients and service processes are absent. Connectivity, protocol compatibility, authentication, latency, and outage recovery are **NOT VERIFIED**.
- Guardian enforcement is veto/quarantine-based. The Twin does not require a request-bound positive Guardian approval before a Brain command.
- SCN-06 uses local channel-availability injection, not a real service outage. Unavailable work is rejected rather than queued for automatic retry.

## Simulation and devices

- Sensor faults change reported values/status independently of CityCore state. Some sensor-side physical models are illustrative, uncalibrated, and independent from similarly named CityCore assets.
- Pump and valve consequences do not feed every related sensor. Only specific pathways, such as supported traffic signal/departure readings, have verified feedback.
- `IND-VLV-01` is catalogued as unsupported. SCN-03 no longer targets it; the scenario command targets linked signal `DTN-TLT-01` and is rejected because frozen traffic sensor `DTN-TRF-01` has no registered backup. This local behavior passed the 8 November focused test and campaign; no industrial valve actuation is claimed.
- `PRT-PMP-01` and `PRT-PMP-02` map to the same target (`P-03`), so the second ID is not independent redundancy.
- The model does not establish calibrated hydraulic behavior or field-device telemetry.

## Runtime, evidence, and deployment

- Event history, sensor adapters, and portions of runtime state are process-local; SQLite persistence does not prove complete whole-runtime restoration.
- Docker/hosted deployment requires valid distinct role tokens, exact allowed hostnames, and suitable persistent storage. Local tests are not deployment availability evidence.
- The dashboard can display Twin/operator events. Browser-rendered end-to-end interaction across three independently running layers is **NOT VERIFIED**.
- The full interface suite currently has known dashboard/OpenAPI failures. See the [current status](STATUS.md), [validation index](../test-evidence/README.md), and [test results](TEST_AND_RUNTIME_RESULTS.md).
