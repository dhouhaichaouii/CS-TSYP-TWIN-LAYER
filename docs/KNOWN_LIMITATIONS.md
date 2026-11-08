# Known Limitations

These limits apply to the current repository and should be stated during a demonstration.

## Integration

- Real Brain and Guardian services, outbound clients, credentials, and network connections are absent. Integration, protocol compatibility, latency, and real outage recovery are **NOT VERIFIED**.
- The standalone demonstration uses in-process mocks. Twin event source/role labels do not independently attest which process made a request.
- Guardian behavior is veto/quarantine-based. A request-bound positive Guardian approval is not implemented.
- SCN-06 changes local availability flags. It does not probe or disconnect partner networks. Requests during simulated unavailability are rejected, not queued for automatic replay.

## Devices and simulation

- `IND-VLV-01` is unsupported. SCN-03 uses supported signal `DTN-TLT-01` and safely rejects the request when its linked traffic source has no registered backup.
- `PRT-PMP-01` and `PRT-PMP-02` share CityCore target `P-03`; they are not independent redundant pumps.
- Sensor-side physics are illustrative and uncalibrated. Some sensor models are not causally connected to similarly named CityCore assets or actuators. Sensor readings are not field telemetry.
- The dashboard can show Twin records and simulated state. It does not show verified physical actuator feedback or a verified live three-service workflow.

## Runtime and testing

- The current dashboard redesign and Operational trace have not been browser-verified.
- The dated interface test run has 3 failures and 1 error. See [Testing](TESTING.md) and its linked raw output.
- Persistence checks cover selected CityCore state and actuator receipts. They do not prove full restoration of scenario timing, sensor adapters, event history, or pending partner work.
- Kafka is not integrated. Its interruption and recovery behavior are **NOT TESTED**.
