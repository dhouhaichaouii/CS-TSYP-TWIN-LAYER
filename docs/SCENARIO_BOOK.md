# Scenario Results

The scenarios exercise local Twin behavior with declared fixtures and controlled test callers. They are not live city incidents and do not establish partner-service participation.

| Scenario | Local behavior exercised | Verified outcome | Boundary |
| --- | --- | --- | --- |
| T5 / SCN-01 | Port sensor spoof and safety handling | Unsafe command held while Guardian review is pending | Local Twin test call; no partner response |
| SCN-02 | Seeded port reading and supported pump command path | Campaign checks pass | Controlled local caller; simulated CityCore effect only |
| SCN-03 | Frozen traffic reading, dead temperature sensor, seeded industrial backup | `DTN-TLT-01` command rejected with `SCENARIO_GUARDIAN_PENDING`; CityCore revision 10 before and after | The industrial backup is unrelated to `DTN-TRF-01`; no fallback or valve command is invented |
| SCN-04 | Quarantine and command safety checks | Unsafe command rejected; `PRT-PMP-02` cannot serve as independent backup | Both pump IDs map to CityCore target `P-03` |
| SCN-05 | Seeded traffic input and labeled air fixture | Local scenario checks pass; fixture is not registered hardware | No autonomous Brain or Guardian response is claimed |
| SCN-06 | Controlled Brain/Guardian availability flags and fail-closed handling | Local checks pass; campaign partner outage cases remain blocked | No network outage, service recovery, or Kafka interruption is tested |

## Latest campaign

The campaign completed at `2026-11-08T07:43:07.712530+00:00`. All six individual scenarios, sequential execution, and cross-scenario checks are **PASS**. Local process-restart and idempotency checks are **PASS**. The campaign overall is **BLOCKED** because real Brain and Guardian services are absent. Kafka is not integrated and is **NOT TESTED**.

Evidence: [`campaign.json`](../test-evidence/scenario-campaign-20261108T074306.489418Z-f1e94dce/campaign.json). SCN-03 event and audit files are linked from [Status](STATUS.md).

## SCN-03 interpretation

`DTN-TLT-01` is the supported signal linked to frozen traffic sensor `DTN-TRF-01`. That sensor has no registered backup. The scenario also provides `IND-TMP-02`, but it is an industrial temperature sensor and does not satisfy the traffic sensor relationship. Both requests are rejected safely. `IND-VLV-01` remains unsupported. This is the verified behavior; the older SCN-03 valve-success claim is superseded.

Run the campaign with Python 3.12 or newer:

```powershell
\.venv\Scripts\python.exe -X utf8 tools\run_scenario_campaign.py --evidence-root test-evidence
```

The overall process may return a nonzero exit code because external partner checks are blocked. Read the JSON statuses instead of treating that result as a local scenario failure.
