# Twin Layer Specification Summary

## Scope

The Twin Layer is a software simulation and interface boundary for the Phase 1 city. It owns CityCore's simulated state, the local sensor reporting path, scenario inputs, command validation, and Twin-side event records.

## Inputs and outputs

**Inputs:** declared scenario seeds and faults; authenticated role requests through configured local interfaces; operator actions through the private dashboard.

**Outputs:** role-projected observations, scenario and command events, audit records, and simulated CityCore effects after validation.

## Safety and trust rules

- Requests are role-checked and validated at the Twin boundary.
- Unsupported device IDs are rejected; the Twin does not infer replacements.
- Quarantine and existing command safety checks apply before effects.
- Sensor ground truth is private and separated from reported readings.
- Simulated effects are not physical acknowledgements.
- Local Brain/Guardian mocks are not external services. Real partner integration is **NOT VERIFIED**.

For evidence and limits, see [Status](STATUS.md), [Testing](TESTING.md), and [Known Limitations](KNOWN_LIMITATIONS.md).
