# Dated validation evidence index

Validation run: **7 November 2026**, Windows, Python 3.12.16. The captured test batch started at **2026-11-07T17:59:33.3721341Z**. Per-command start timestamps, exact commands, exit codes, and console output are in [validation-20261107T175933Z/README.md](validation-20261107T175933Z/README.md).

## Results

| Check | Result | Evidence |
|---|---|---|
| Unit tests | **PASS** — 77 tests | [output](validation-20261107T175933Z/unit.txt) |
| Integration tests | **PASS** — 42 tests | [output](validation-20261107T175933Z/integration.txt) |
| Interface tests | **FAIL** — 61 tests, 3 failures, 1 error | [output](validation-20261107T175933Z/interface.txt). Failures are dashboard paths returning 404; OpenAPI test errors because the expected `parameters` field is absent. |
| Security tests | **PASS** — 10 tests | [output](validation-20261107T175933Z/security.txt) |
| Focused SCN-03 test | **PASS** — 1 test | [output](validation-20261107T175933Z/scn03-focused.txt) |
| Targeted façade/command interface tests | **PASS** — 15 tests | [output](validation-20261107T175933Z/interface-core.txt) |
| Malformed input/auth ASGI test | **PASS** — malformed/non-object JSON 400, missing auth 401, role denial 403 | [output](validation-20261107T175933Z/asgi-malformed-auth.txt) |
| Live suite runner | **PASS** — 127 tests, 0 failures/errors/skips; coverage gate passed | [checks](validation-20261107T175933Z/checks.json), [test output](validation-20261107T175933Z/tests.txt), [coverage](validation-20261107T175933Z/coverage.txt) |
| Standalone mock demo | **PASS** — Guardian isolated `PRT-WLV-01`; Brain mock dispatched `PRT-PMP-02`; 42 JSONL lines | [console](validation-20261107T175933Z/standalone.txt), [JSONL](validation-20261107T175933Z/standalone.jsonl) |
| Scenario campaign | **BLOCKED overall** — all six individual scenarios, sequential, and cross-scenario checks pass; real partner outage cases unavailable | [campaign report](scenario-campaign-20261107T175549.588643Z-6c9f9858/campaign.json), completed `2026-11-07T17:55:50.889053Z` |
| Docker Compose config | **PASS** — config parsed with placeholder template; Docker CLI warned it could not read the user Docker config. No container was started. | [output](validation-20261107T175933Z/compose-config.txt) |
| Traced core runner | **NOT COMPLETED** — interrupted after prolonged no-output run; no result inferred | Command: `tmp/twin-audit-venv/Scripts/python.exe -X utf8 tools/run_checks.py --evidence tmp/final_validation/core` |
| Dashboard runner | **NOT COMPLETED** — interrupted after prolonged no-output run; no result inferred | Command: `tmp/twin-audit-venv/Scripts/python.exe -X utf8 tools/run_dashboard_checks.py --evidence tmp/final_validation/dashboard` |

The campaign and standalone use local mocks/controlled façade calls. They do not establish real Brain or Guardian integration. The campaign's nonzero exit is due to **BLOCKED** real-partner checks, not a failing individual scenario.
