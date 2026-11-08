# Testing and Evidence

## Latest scenario campaign

The machine-readable campaign at [`campaign.json`](../test-evidence/scenario-campaign-20261108T074306.489418Z-f1e94dce/campaign.json) completed at `2026-11-08T07:43:07.712530+00:00`.

| Check | Recorded result |
| --- | --- |
| SCN-01 to SCN-06 individual runs | PASS |
| Sequential run | PASS |
| Cross-scenario checks | PASS |
| Local process-restart and durable idempotency checks | PASS |
| Real Brain/Guardian outage checks | BLOCKED; partner services absent |
| Kafka interruption | NOT TESTED; Kafka is not integrated |
| Campaign overall | BLOCKED |

SCN-03 event, dashboard-frame, and audit evidence is retained under the same campaign directory. Exact paths are listed in [Status](STATUS.md).

## Dated validation snapshot

The validation package [`validation-20261107T175933Z`](../test-evidence/validation-20261107T175933Z/README.md) records these results on Python 3.12:

| Suite/check | Result | Evidence |
| --- | --- | --- |
| Unit | 77 passed; exit 0 | [`unit.txt`](../test-evidence/validation-20261107T175933Z/unit.txt) |
| Integration | 42 passed; exit 0 | [`integration.txt`](../test-evidence/validation-20261107T175933Z/integration.txt) |
| Security | 10 passed; exit 0 | [`security.txt`](../test-evidence/validation-20261107T175933Z/security.txt) |
| Interface | 61 run; 3 failures and 1 error; exit 1 | [`interface.txt`](../test-evidence/validation-20261107T175933Z/interface.txt) |
| Focused SCN-03 test | 1 passed; exit 0 | [`scn03-focused.txt`](../test-evidence/validation-20261107T175933Z/scn03-focused.txt) |
| Standalone Twin plus local mocks | PASS; exit 0 | [`standalone.txt`](../test-evidence/validation-20261107T175933Z/standalone.txt) and [`standalone.jsonl`](../test-evidence/validation-20261107T175933Z/standalone.jsonl) |
| Compose configuration | PASS; exit 0 | [`compose-config.txt`](../test-evidence/validation-20261107T175933Z/compose-config.txt) |
| Full current dashboard browser rendering | NOT VERIFIED | No browser result for the current redesign and event trace |

The interface failures are preserved in the evidence output; they must not be described as a passing full interface suite. A separate older report records dashboard checks, but it does not verify the current dashboard redesign or its browser rendering.

## Reproduction commands

From PowerShell at the repository root, with the Python 3.12 virtual environment installed:

```powershell
$env:PYTHONPATH = "src"
\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests\unit -t .
\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests\integration -t .
\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests\interface -t .
\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests\security -t .
\.venv\Scripts\python.exe -X utf8 tools\run_scenario_campaign.py --evidence-root test-evidence
```

Use a new evidence directory for each validation run. Report individual `PASS`, `FAIL`, `BLOCKED`, `SKIPPED`, and `NOT TESTED` outcomes separately.
