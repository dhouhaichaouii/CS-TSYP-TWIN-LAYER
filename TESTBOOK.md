# Phase 1 Test Book

**Evidence reviewed:** 8 November 2026
**Classification:** software-only Twin checks; partner integration is not verified

## Campaign result

The latest campaign completed at `2026-11-08T07:43:07.712530+00:00`.

| Campaign part | Result |
| --- | --- |
| Six individual scenarios | PASS |
| Sequential scenario run | PASS |
| Cross-scenario checks | PASS |
| Local process restart and idempotency | PASS |
| Real Brain/Guardian outage cases | BLOCKED; partner services are absent |
| Kafka interruption | NOT TESTED; Kafka is absent |
| Overall campaign | BLOCKED |

The campaign command may exit nonzero because blocked external checks are included in the overall result. The exact per-check statuses are in [`campaign.json`](test-evidence/scenario-campaign-20261108T074306.489418Z-f1e94dce/campaign.json).

## SCN-03 result

SCN-03 exercises a frozen traffic sensor, a dead industrial temperature sensor, and a seeded industrial backup reading. The command targets supported signal `DTN-TLT-01`, which is linked to `DTN-TRF-01`. Because the traffic source has no registered backup, both the no-backup and unrelated-temperature-backup calls are rejected with `SCENARIO_GUARDIAN_PENDING`. CityCore remains at revision 10. The call results are local TwinFacade checks, not real Brain or Guardian responses. `IND-VLV-01` remains unsupported.

Evidence: [`SCN-03 events`](test-evidence/scenario-campaign-20261108T074306.489418Z-f1e94dce/individual/individual-scn-03-city-events.json), [`SCN-03 audit`](test-evidence/scenario-campaign-20261108T074306.489418Z-f1e94dce/audit/individual-scn-03_campaign-3-ff347598eee5.jsonl), and [focused validation output](test-evidence/validation-20261107T175933Z/scn03-focused.txt).

## Dated test suite results

The 7 November validation package records:

| Suite | Result | Exit |
| --- | --- | ---: |
| Unit | 77 passed | 0 |
| Integration | 42 passed | 0 |
| Security | 10 passed | 0 |
| Interface | 61 tests; 3 failures and 1 error | 1 |
| Focused SCN-03 | 1 passed | 0 |
| Standalone Twin + local mocks | PASS | 0 |
| Compose configuration | PASS | 0 |

Raw output and run timestamps: [`test-evidence/validation-20261107T175933Z/README.md`](test-evidence/validation-20261107T175933Z/README.md). The interface failures are disclosed, not treated as passing. Full current browser rendering of the dashboard redesign and event trace is **NOT VERIFIED**.

See the [Scenario Book](docs/SCENARIO_BOOK.md), [Testing and Evidence](docs/TESTING.md), and [Current Status](docs/STATUS.md) for the scope and interpretation of these results.
