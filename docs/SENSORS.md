# Sensor Scope

The repository includes a local sensor registry and deterministic simulated sensor models. The supplied [sensor specification](sources/Twin-Layer-Sensor-Specification.pdf) is the reference for the selected sensor inventory.

## Interpretation

- A Twin reading is a software-generated observation, not proof of a field device or live telemetry.
- The Twin stores model truth separately from the value reported to callers. Fault injection changes the reported path.
- Model parameters are illustrative and uncalibrated. Similar asset names do not prove a physical feedback connection.
- No automatic backup policy is claimed. A backup is usable only when the existing registry and safety checks establish the relevant relationship.
- `IND-VLV-01` is unsupported and must not be presented as an available actuator.

For the latest concrete sensor case, see [SCN-03](SCENARIO_BOOK.md#scn-03-interpretation) and [Sensor Verification](SENSOR_VERIFICATION.md).
