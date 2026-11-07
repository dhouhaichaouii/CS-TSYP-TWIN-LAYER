# Validation run

Started UTC: 2026-11-07T17:59:33.3721341Z
Python: $python -X utf8


## unit

- Started UTC: 2026-11-07T17:59:33.3808844Z
- Command: `tmp/twin-audit-venv/Scripts/python.exe -X utf8 -m unittest discover -s tests/unit -t .` 
- Exit: 0
- Output: [unit.txt](unit.txt)

## integration

- Started UTC: 2026-11-07T17:59:35.3486838Z
- Command: `tmp/twin-audit-venv/Scripts/python.exe -X utf8 -m unittest discover -s tests/integration -t .` 
- Exit: 0
- Output: [integration.txt](integration.txt)

## interface

- Started UTC: 2026-11-07T17:59:36.7707714Z
- Command: `tmp/twin-audit-venv/Scripts/python.exe -X utf8 -m unittest discover -s tests/interface -t .` 
- Exit: 1
- Output: [interface.txt](interface.txt)

## security

- Started UTC: 2026-11-07T17:59:40.0713508Z
- Command: `tmp/twin-audit-venv/Scripts/python.exe -X utf8 -m unittest discover -s tests/security -t .` 
- Exit: 0
- Output: [security.txt](security.txt)

## scn03-focused

- Started UTC: 2026-11-07T17:59:40.2153324Z
- Command: `tmp/twin-audit-venv/Scripts/python.exe -X utf8 -m unittest live_tests.test_scenario_orchestration.ScenarioOrchestrationTests.test_scn03_rejects_ambiguous_valve_even_with_valid_backup_sensor` 
- Exit: 0
- Output: [scn03-focused.txt](scn03-focused.txt)

## asgi-malformed-auth

- Started UTC: 2026-11-07T17:59:40.5725285Z
- Command: `tmp/twin-audit-venv/Scripts/python.exe -X utf8 -m unittest tests.interface.test_asgi_app.UnifiedAsgiAppTests.test_rest_header_auth_permissions_and_credential_rejection` 
- Exit: 0
- Output: [asgi-malformed-auth.txt](asgi-malformed-auth.txt)

## standalone-mocks

- Started UTC: 2026-11-07T17:59:41.9933008Z
- Command: `tmp/twin-audit-venv/Scripts/python.exe -X utf8 tools/run_standalone.py --ticks 1150 --run-id jury-demo-20261107-evidence-20261107T175933Z` 
- Exit: 0
- Output: [standalone.txt](standalone.txt)
- JSONL: [standalone.jsonl](standalone.jsonl)

## compose-config

- Started UTC: 2026-11-07T17:59:45.2784921Z
- Command: `TWIN_ENV_FILE=.env.example; docker compose --env-file .env.example config --quiet` 
- Exit: 0
- Output: [compose-config.txt](compose-config.txt)
- Note: Docker CLI emitted a user-config access warning; config validation succeeded.

## live-suite

- Command: `tmp/twin-audit-venv/Scripts/python.exe -X utf8 tools/run_live_checks.py --evidence tmp/final_validation/live` 
- Result: PASS; 127 tests, 0 failures, 0 errors, 0 skipped; coverage gate passed.
- Runner evidence copied from ignored temporary output: [checks.json](checks.json), [tests.txt](tests.txt), [coverage.txt](coverage.txt).

Validation evidence directory: `test-evidence\validation-20261107T175933Z`

## interface-core targeted

- Started UTC: 2026-11-07T18:00:18.9020688Z
- Command: `tmp/twin-audit-venv/Scripts/python.exe -X utf8 -m unittest tests.interface.test_facade tests.interface.test_command_integration` (with `PYTHONPATH=src`)
- Exit: 0
- Result: 15 focused interface tests passed.
- Output: [interface-core.txt](interface-core.txt)
