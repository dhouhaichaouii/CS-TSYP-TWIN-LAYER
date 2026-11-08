# Sensor Verification

## What the repository verifies

The Twin keeps private model truth separate from reported sensor values. Declared faults such as stuck or dead readings affect the report path; they do not establish that a real sensor was installed or that the modeled physical process is calibrated.

The latest campaign verifies the SCN-03 sensor inputs and safety result:

- `DTN-TRF-01` reports its frozen value while its private scenario input differs.
- `IND-TMP-01` reports unavailable under the declared dead-sensor fault.
- `IND-TMP-02` reports the seeded industrial temperature value.
- The traffic sensor has no registered backup. The industrial temperature reading is not a valid traffic backup, so the command to linked signal `DTN-TLT-01` is rejected and CityCore revision remains unchanged.

Evidence is in [`campaign.json`](../test-evidence/scenario-campaign-20261108T074306.489418Z-f1e94dce/campaign.json) and its SCN-03 event/audit files linked from [Status](STATUS.md).

## What this does not verify

- Field sensor connectivity, calibration, accuracy, or deployment.
- Automatic backup selection or failover.
- Complete physical causality between every sensor and similarly named actuator.
- Industrial valve operation; `IND-VLV-01` is unsupported.

Sensor models are illustrative. Do not present simulated readings as measured city telemetry. The source inventory is [Twin-Layer-Sensor-Specification.pdf](sources/Twin-Layer-Sensor-Specification.pdf).
