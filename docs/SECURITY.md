# Safety and Security Boundaries

## Local authorization model

The Twin exposes distinct Brain, Guardian, Operator, and Evaluator roles through its configured interfaces. The shared `TwinFacade` applies permissions, input validation, privacy projections, quarantine checks, and request idempotency before simulated effects are committed.

- Brain-role callers may request supported simulated actuator actions.
- Guardian-role callers may isolate or restore devices.
- Operator actions use the private dashboard session.
- Evaluator projections may expose designated private diagnostic information; ordinary reported views do not expose sensor ground truth.

The dashboard is intended for local demonstration. Use loopback access and real, distinct secrets for any deployment configuration. Do not commit `.env` files or credentials. `--dev` is for local development only.

## Safety semantics

- Unsupported devices and invalid commands are rejected; they are not silently mapped to another device.
- Quarantine blocks later commands to the quarantined device.
- Guardian behavior is a veto/quarantine boundary, not a positive approval service. Pending status is not approval.
- Successful command records refer to simulated CityCore effects. They are not hardware acknowledgements.

See [Known Limitations](KNOWN_LIMITATIONS.md) for unverified external and physical boundaries. This summary is not a security certification or deployment hardening assessment.
