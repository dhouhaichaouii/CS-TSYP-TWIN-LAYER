# City Brain Convergence — Twin Layer

The Twin Layer is a local software simulation and interface boundary for the Phase 1 city. It owns simulated city state, sensor reporting, declared scenarios, command validation, and Twin-side event records.

> **Status, 8 November 2026:** local scenario checks have evidence. The latest campaign is **BLOCKED overall** because real Brain and Guardian outage checks cannot run without those partner services. Real partner integration is **NOT VERIFIED**. The current dashboard redesign and event trace are not browser-verified.

## Start here

- [Jury documentation index](docs/README.md)
- [Final report](FINAL_REPORT.md)
- [Test Book](TESTBOOK.md)
- [Scenario outcomes](docs/SCENARIO_BOOK.md)
- [Current status and evidence paths](docs/STATUS.md)
- [Known limitations](docs/KNOWN_LIMITATIONS.md)

## Local demo

Python 3.12 or newer is required. Setup and run instructions are in the [Demo Guide](docs/DEMO_GUIDE.md). The dashboard displays Twin records and simulated state; it is not a verified three-service partner dashboard.

## System boundary

The standalone Brain and Guardian demonstration uses in-process mocks. They do not establish external service connectivity. Sensor models are illustrative and uncalibrated. Simulated actuator effects are not physical acknowledgements. See the [architecture](docs/ARCHITECTURE.md), [sensor verification](docs/SENSOR_VERIFICATION.md), and [security boundary](docs/SECURITY.md).

## Repository map

| Path | Purpose |
| --- | --- |
| `src/city_core/` | Simulated city state and effects |
| `src/city_live/` | Runtime, sensor path, scenarios, operator lifecycle |
| `src/twin_interface/` | Shared facade, role checks, REST and MCP interfaces |
| `src/city_dashboard/` | Local operator dashboard |
| `mocks/` | In-process demo clients |
| `scenarios/` | Scenario definitions |
| `test-evidence/` | Dated campaign and validation results |
| `docs/` | Jury-facing documentation |
