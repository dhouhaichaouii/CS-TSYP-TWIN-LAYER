# Jury demonstration guide

This is a local Twin demonstration with in-process mocks. It is not a live connection to real Brain or Guardian services.

## 1. Prepare

Use Python 3.12+, install dependencies using the root README, and run commands from the repository root. Keep the project terminal open so the JSONL log is flushed and the launcher can be stopped cleanly.

## 2. Run the standalone proof

Choose a run ID not already used:

```powershell
python -X utf8 tools/run_standalone.py --ticks 1150 --run-id jury-demo-20261107-a1
```

Expected terminal observations:

1. The launcher injects a `FALSE_READING` fault into `PRT-WLV-01` and starts heavy rain.
2. The local Guardian mock isolates `PRT-WLV-01` against `PRT-WLV-02` at a 100 cm discrepancy.
3. The local Brain mock dispatches `PRT-PMP-02` when the simulated level reaches its configured threshold.
4. The launcher prints `[PASS]` and reports the final tick and JSONL line count.

Inspect `logs/standalone_jury-demo-20261107-a1.jsonl`. This log is mock-backed and does not prove a physical pump response or external service participation.

## 3. Inspect a scenario

For the shared operator dashboard/MCP runtime and one scenario, run:

```powershell
python -X utf8 scenarios/run.py --scenario scn-03
```

Authenticate to the local operator dashboard using the passphrase requested by the launcher. SCN-03 shows the stuck traffic reading, the failed temperature sensor, and the seeded backup reading. It targets supported signal `DTN-TLT-01`, linked to the frozen traffic sensor. Because that traffic sensor has no registered backup, both no-backup and unrelated industrial-backup contexts are held with `SCENARIO_GUARDIAN_PENDING`, leaving CityCore unchanged. The focused test and 8 November campaign verified this local behavior.

Run the dated campaign for saved scenario evidence:

```powershell
python -X utf8 tools/run_scenario_campaign.py --evidence-root test-evidence
```

Individual local scenario results can pass while the overall campaign is **BLOCKED** for absent real partner services. Read `campaign.json` and report each status accurately.

## 4. What to say

- The Twin owns simulated city state and the sensor/actuator boundary.
- Sensor truth and reported values are separate; injected faults alter the report path.
- The mocks call TwinFacade in-process. Real Brain/Guardian integration is **NOT VERIFIED**.
- Guardian approval is veto/quarantine-based, not a request-bound positive verdict.
- Several physical sensor/actuator feedback paths are not modeled; `IND-VLV-01` is unsupported and the two named Port pumps share one target.
- The UI is an operator dashboard, not a verified three-service live timeline.

See [current evidence/status](STATUS.md) and [known limitations](KNOWN_LIMITATIONS.md).
