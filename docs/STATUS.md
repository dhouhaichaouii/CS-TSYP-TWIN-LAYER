# Twin Layer status

**Last reviewed:** 8 November 2026. This is a local Twin prototype; status below distinguishes in-process evidence from external integration.

## Current demonstrated status

- **Standalone demo with local mocks:** previously passed at 1,150 configured ticks. The mock Guardian isolated the injected sensor and mock Brain dispatched a pump. This is an in-process demonstration, not partner connectivity.
- **Scenario campaign:** latest campaign completed at `2026-11-08T07:43:07.712530Z`. All six individual scenarios, sequential execution, and cross-scenario checks passed. Overall campaign status is **BLOCKED** because real Brain/Guardian outage cases cannot run without partner services. The real process restart and local failure checks passed. See the [latest campaign JSON](../test-evidence/scenario-campaign-20261108T074306.489418Z-f1e94dce/campaign.json).
- **SCN-03:** the scenario targets supported `DTN-TLT-01`, linked to frozen `DTN-TRF-01`. Both missing-backup and unrelated industrial-backup requests were rejected with `SCENARIO_GUARDIAN_PENDING`; CityCore revision remained 10. The focused test and latest campaign passed. `IND-VLV-01` remains unsupported and unchanged. See the [Test Book](../TESTBOOK.md) and [current campaign evidence](../test-evidence/scenario-campaign-20261108T074306.489418Z-f1e94dce/campaign.json).
- **Real Brain/Guardian services:** **NOT VERIFIED**. There are no outbound partner clients or partner service processes in this repository.
- **Validation snapshot:** 7 Nov 2026, Python 3.12.16. Unit 77/77, integration 42/42, security 10/10, live suite 127/127, standalone demo, and Compose syntax pass. Full interface suite has 3 failures and 1 error in dashboard/OpenAPI assertions; 15 targeted façade/command tests and the malformed-input/auth probe pass. Core and dashboard traced runners were interrupted before reporting results. Details and output files are in the [dated validation index](../test-evidence/README.md).

## Integration and deployment status

- Guardian enforcement is quarantine/veto-based; request-bound positive approval is not implemented.
- Sensor-side models are illustrative and uncalibrated. Several sensor readings are not coupled to similarly named CityCore actuators.
- `PRT-PMP-01` and `PRT-PMP-02` share CityCore target `P-03`; they are not independent redundant pumps.
- Docker Compose requires real role credentials, an allowed host, and a private env file. The template contains invalid `REPLACE_ME` placeholders only.
- A browser dashboard is available for the Twin operator. A live, real three-layer timeline has not been verified.

## Evidence sources

- [Dated test and runtime results](TEST_AND_RUNTIME_RESULTS.md)
- [Jury technical report](JURY_TECHNICAL_REPORT.md)
- [Partner connection guide](PARTNER_TESTING.md)
- [Scenario verification matrix](SCENARIO_VERIFICATION_MATRIX.md)
- [Sensor verification](SENSOR_VERIFICATION.md)
