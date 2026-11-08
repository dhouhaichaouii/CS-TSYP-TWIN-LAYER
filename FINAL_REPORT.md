# Final Report — Twin Layer

**Submission snapshot:** 8 November 2026
**Project:** City Brain Convergence, Phase 1
**Classification:** software prototype; local simulation only

## Summary

The Twin Layer models city state and provides a boundary for scenario inputs, sensor observations, simulated actuator requests, and event records. Its shared facade applies role checks, validation, quarantine, and idempotency before a simulated CityCore effect is committed.

## Evidence

The latest campaign completed at `2026-11-08T07:43:07.712530+00:00`. Its six individual scenarios, sequential run, cross-scenario checks, and local process-restart checks report **PASS**. The campaign overall is **BLOCKED** because the real Brain and Guardian partner outage checks cannot run without those services. Kafka is not integrated and is **NOT TESTED**.

The campaign report and SCN-03 event/audit evidence are linked from [Current Status](docs/STATUS.md). Dated suite results, including known interface failures, are in the [Test Book](TESTBOOK.md).

## Integration boundary

Brain and Guardian are not implemented as external services in this repository. Standalone mock calls are in-process demonstrations. The Twin dashboard records Twin events; its role labels do not attest the identity of a remote process. Real partner connectivity, a live three-layer workflow, physical sensors, and physical actuator feedback are **NOT VERIFIED**.

## Important limitations

- Guardian behavior is veto/quarantine-based; request-bound positive approval is not implemented.
- SCN-03 uses supported signal `DTN-TLT-01`. The linked traffic source `DTN-TRF-01` has no registered backup, so its command is safely rejected. `IND-VLV-01` is unsupported.
- `PRT-PMP-01` and `PRT-PMP-02` share CityCore target `P-03`; they are not redundant independent pumps.
- Sensor models are illustrative and uncalibrated; complete sensor-to-actuator feedback is not established.
- The current dashboard redesign and event trace have not been browser-verified.

## Jury reading path

Start with the [documentation index](docs/README.md), then review the [Scenario Book](docs/SCENARIO_BOOK.md), [Testing and Evidence](docs/TESTING.md), and [Known Limitations](docs/KNOWN_LIMITATIONS.md).
