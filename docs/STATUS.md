# Current Status

**Reviewed:** 8 November 2026
**Classification:** software prototype; local simulation only

## Verified locally

- The 8 November scenario campaign reports all six individual scenarios, the sequential run, cross-scenario checks, and local process-restart checks as **PASS**.
- SCN-03 uses supported signal `DTN-TLT-01`. Because its source `DTN-TRF-01` is frozen and has no registered backup, both the missing-backup and unrelated-backup requests are safely rejected with `SCENARIO_GUARDIAN_PENDING`; CityCore remains at revision 10.
- A standalone demonstration using in-process Brain and Guardian mocks has a recorded **PASS**.

## Not verified or blocked

- The campaign overall is **BLOCKED**: no real Brain or Guardian service is present to test partner outage behavior. Kafka is also absent and not tested.
- The current dashboard redesign and Operational trace have not been verified in a browser. Dashboard rendering must not be presented as a tested live three-layer timeline.
- Full interface validation has known failures. See [Testing](TESTING.md) for the dated counts and evidence.
- Physical sensor calibration and complete sensor-to-actuator feedback are not established.

## Latest campaign evidence

- Completed: `2026-11-08T07:43:07.712530+00:00` (UTC)
- Campaign JSON: [`test-evidence/scenario-campaign-20261108T074306.489418Z-f1e94dce/campaign.json`](../test-evidence/scenario-campaign-20261108T074306.489418Z-f1e94dce/campaign.json)
- SCN-03 events: [`individual-scn-03-city-events.json`](../test-evidence/scenario-campaign-20261108T074306.489418Z-f1e94dce/individual/individual-scn-03-city-events.json)
- SCN-03 audit: [`individual-scn-03_campaign-3-ff347598eee5.jsonl`](../test-evidence/scenario-campaign-20261108T074306.489418Z-f1e94dce/audit/individual-scn-03_campaign-3-ff347598eee5.jsonl)

The campaign JSON records its reproduction commands and per-check statuses. Its nonzero overall result reflects **BLOCKED** partner checks; it does not turn the local scenario checks into partner integration evidence.
