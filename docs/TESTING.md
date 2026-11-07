# Testing and evidence

Use Python 3.12 or newer and install the locked dependencies as shown in the root [README](../README.md). In PowerShell, set the source path before direct unittest discovery:

```powershell
$env:PYTHONPATH = "src"
```

## Test groups

```powershell
python -m unittest discover -s tests/unit -t .
python -m unittest discover -s tests/integration -t .
python -m unittest discover -s tests/interface -t .
python -m unittest discover -s tests/security -t .
```

The interface group includes ASGI, REST/MCP, dashboard/security, and command contract tests. A test failure is a real failure even if related targeted tests pass.

## Project runners

Each runner requires a new evidence destination; do not reuse or overwrite a previous report:

```powershell
python tools/run_checks.py --evidence tmp/validation/core
python tools/run_live_checks.py --evidence tmp/validation/live
python tools/run_dashboard_checks.py --evidence tmp/validation/dashboard
python tools/run_scenario_campaign.py --evidence-root test-evidence
```

The test runners write `tests.txt`, `coverage.txt`, and `checks.json` under their evidence path. The scenario campaign makes a unique timestamped folder containing `campaign.json`, scenario event histories, dashboard frames, event-store exports, and audit logs. A blocked real-partner check is not a pass.

## Mock demonstration

```powershell
python -X utf8 tools/run_standalone.py --ticks 1150 --run-id jury-demo-<unique-id>
```

The standalone launcher writes a JSONL file in `logs/`. Use a new run ID to avoid colliding with existing evidence. It uses local Brain and Guardian mocks; it does not validate real services or network transport.

## Evidence handling

- Keep generated evidence in `test-evidence/` and retain the exact timestamped path in the index/report.
- Runtime logs in `logs/` are ignored by Git; copy any submission evidence that must travel with the repository into a dated `test-evidence/` folder.
- Never overwrite an existing evidence folder. Campaign output names include a timestamp and random suffix.
- See [current status](STATUS.md), [scenario results](../TESTBOOK.md), and [test/runtime results](TEST_AND_RUNTIME_RESULTS.md) for interpretation and known failures.
- The latest captured outputs are indexed in [test-evidence/README.md](../test-evidence/README.md).
