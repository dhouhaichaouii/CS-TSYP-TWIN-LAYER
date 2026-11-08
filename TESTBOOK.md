# Phase 1 Test Book

## Shared scenario pipeline

All six existing JSON scenarios use `LiveCity`'s `ScenarioRunner`. The runner
injects only explicitly seeded sensor inputs and declared sensor faults, then
observes the normal Twin sampling path. It does not fabricate Guardian verdicts
or Brain decisions. A Brain response is recorded only when an authenticated
Brain caller uses the existing Twin actuator interface; an isolation or restore
is recorded only when an authenticated Guardian caller uses the existing
Guardian interface.

Guardian integration is currently veto-only: there is no request-bound positive
approval API. `GUARDIAN_PENDING` means that no real verdict has arrived;
`GUARDIAN_REJECTED` records a real inbound isolation action. Twin permissions,
device quarantine, command validation, idempotency, and CityCore checks still
apply before any effect. Successful actuator receipts identify the committed
CityCore effect. Partner services are not launched by this repository, so a
scenario can remain pending until the Brain or Guardian team calls the existing
interfaces. The local scenario selector is available after authenticating the
operator dashboard.

The Residential `RES-AIR-TEST-01` observation in SCN-05 is a scenario-local
fixture, not a sensor in the Twin registry. It appears as a clearly labeled
scenario event and is never registered or sampled as hardware. SCN-04's listed
backup pump `PRT-PMP-02` explicitly shares the CityCore target `P-03` with
`PRT-PMP-01`; it is not an independent fallback. The runner does not bypass
that quarantine or invent another device.

| ID | Existing scenario data | Shared Twin behavior | Partner behavior and command outcome |
|---|---|---|---|
| T5 / SCN-01 | Port flood spoof: PRT-WLV-01 actual input 40 cm, reported value 180 cm from the declared false-reading fault. | Samples through SensorBank; exposes the actual/reported mismatch in private Twin diagnostics and lifecycle events. Unsafe Brain commands linked to the untrusted sensor are rejected unless a validated registered backup reading is supplied. | Guardian is pending until it actually isolates the sensor. Brain is pending until an actual command or response arrives. No automatic flood action is fabricated. |
| SCN-02 | Port level seeded to 110 cm from the existing scenario definition. | Forces a real Twin sensor sample of the seeded value and publishes it through the ordinary reading path. | The dashboard and MCP/REST consumers can observe it. A Brain command is applied only after existing permission, idempotency, quarantine, and CityCore validation. |
| SCN-03 | Existing traffic and temperature sensor faults, plus seeded IND-TMP-02 backup input. | DTN-TRF-01 holds reported 48 (private fixture actual 55); IND-TMP-01 reports null/FAILED; backup IND-TMP-02 reports 70. | Scenario command targets supported linked signal DTN-TLT-01. Both the no-backup call and call citing unrelated IND-TMP-02 were rejected as `SCENARIO_GUARDIAN_PENDING`, because DTN-TRF-01 has no registered backup. CityCore revision stayed 10. Focused test and latest campaign passed; calls are local TwinFacade checks, not real Brain/Guardian responses. |
| SCN-04 | Guardian containment of PRT-PMP-01; existing scenario data lists PRT-PMP-02 as backup. | Waits for real Guardian isolation before treating the target as quarantined. Twin rejects a Brain request while isolation is pending and rejects it through the normal quarantine gate after isolation. | PRT-PMP-02 is not an eligible fallback in the current device catalog because it maps to the same physical pump target as PRT-PMP-01. |
| SCN-05 | Seeded Downtown traffic value and scenario-local Residential air fixture at the same tick. | Publishes the traffic event through SensorBank. Emits the air fixture as a labeled fixture event only; it is not inserted into the hardware registry. | Only an actual Brain command to an existing eligible signal can change CityCore. No Guardian or Brain response is synthesized for the air fixture. |
| SCN-06 | Controlled, deterministic availability transitions for Brain-facing and Guardian-facing inbound Twin interfaces. | Emits explicit baseline, unavailable, and recovered lifecycle records. Injected failures block Brain commands and Guardian isolate/restore calls; an unavailable Guardian also blocks Brain and operator actuator commands. Quarantine is preserved. | This is local `ScenarioRunner` failure injection, not a network outage or service probe. No Brain decision or Guardian verdict is fabricated. Outage requests are rejected, not queued; delayed requests are evaluated again against current revision and safety gates. |

## Launch and inspect

Start one shared Twin process with an existing scenario. This starts the
dashboard and FastMCP server against the same `LiveCity`; scenario events are
written to the normal observability log:

```text
python scenarios/run.py --scenario t5
python scenarios/run.py --scenario scn-02
python scenarios/run.py --scenario scn-03
python scenarios/run.py --scenario scn-04
python scenarios/run.py --scenario scn-05
python scenarios/run.py --scenario scn-06
```

The command prompts for a one-launch operator passphrase. The dashboard and MCP
are loopback-only by default; the dashboard defaults to `http://127.0.0.1:8765`
and MCP to port 8000. Optional `--dashboard-port`, `--mcp-port`,
`--mcp-transport`, `--run-id`, and `--dev` arguments are forwarded to
`tools/run_twin.py`. Do not enable `--dev` outside local development.

Alternatively, start the shared runtime using `python tools/run_twin.py` and
launch the scenario from the authenticated dashboard's **Existing scenario**
selector. Brain and Guardian integrations must use their existing authenticated
MCP/REST contracts; scenario launch alone does not claim their participation.

Verify:

1. Authenticate to the private operator dashboard and start the chosen
   scenario, or start it with the command above.
2. Observe the scenario correlation ID and lifecycle timeline. Sensor events
   appear in the normal readings and dashboard frame; SCN-05's fixture remains
   explicitly labeled.
3. Use the existing Brain/Guardian credentials and interfaces to issue real
   inbound commands or isolation actions. A pending status is not a service
   response.
4. Confirm a successful actuator result has `city_core_updated: true` and a
   committed effect/revision. A rejected or pending command is not execution.
5. Replay a successful request ID to verify the existing idempotent receipt is
   returned without a second physical effect.

Targeted orchestration tests:

```text
python -m unittest live_tests.test_b_scenario_adapter live_tests.test_scenario_orchestration
python -m unittest dashboard_tests.test_bridge
```

Run the full integration campaign and create a unique evidence directory (the
campaign will not overwrite an existing run):

```text
python tools/run_scenario_campaign.py
```

The campaign's overall result may be `FAIL` or `BLOCKED` when it detects
current durability defects or requires unavailable Brain/Guardian services.
Read `campaign.json` for per-check `PASS`, `FAIL`, `BLOCKED`, `SKIPPED`, and
`NOT TESTED` results and the exact evidence paths.

Run the dedicated communication failure/recovery campaign:

```text
python tools/run_scn06_campaign.py
```

The campaign creates a unique `test-evidence/scn06-*` directory with a JSON
report, Twin events, EventStore export, dashboard frame, and sanitized audit
log. A passing run validates controlled local failure injection only; no
external Brain or Guardian service is involved. There is no durable pending
command queue or process-restart recovery in this architecture.

## Verification record — 7 November 2026

| Command | Exit | Result |
|---|---:|---|
| `$env:PYTHONPATH='src'; tmp/twin-audit-venv/Scripts/python.exe -X utf8 -m unittest live_tests.test_scenario_orchestration.ScenarioOrchestrationTests.test_scn03_rejects_ambiguous_valve_even_with_valid_backup_sensor` | 0 | Isolated SCN-03 test: 1 passed. Both expected rejections were asserted; CityCore revision did not change. |
| `tmp/twin-audit-venv/Scripts/python.exe -X utf8 tools/run_scenario_campaign.py --evidence-root test-evidence` | 1 | All six individual scenarios PASS; sequential and cross-scenario checks PASS. Overall **BLOCKED** because real Brain/Guardian outage cases require absent partner services. Latest campaign completed `2026-11-07T17:55:50.889053Z`; see [campaign JSON](test-evidence/scenario-campaign-20261107T175549.588643Z-6c9f9858/campaign.json). |
| `$env:PYTHONPATH='src'; tmp/twin-audit-venv/Scripts/python.exe -X utf8 -m unittest discover -s tests/security -t .` | 0 | 10 security tests passed. |
| `$env:PYTHONPATH='src'; tmp/twin-audit-venv/Scripts/python.exe -X utf8 -m unittest tests.interface.test_facade tests.interface.test_command_integration` | 0 | 15 interface tests passed. |
| `$env:PYTHONPATH='src'; tmp/twin-audit-venv/Scripts/python.exe -X utf8 -m unittest tests.interface.test_asgi_app.UnifiedAsgiAppTests.test_rest_header_auth_permissions_and_credential_rejection` | 0 | 1 interface test passed; malformed JSON/non-object inputs returned 400, missing auth 401, and role denials 403. |

The new campaign evidence is in
[`campaign.json`](test-evidence/scenario-campaign-20261107T175549.588643Z-6c9f9858/campaign.json),
with SCN-03 Twin events, dashboard frame, and audit log in that folder's
`individual/` and `audit/` subfolders. Campaign calls are controlled local
TwinFacade calls. Real Brain/Guardian integration is **NOT VERIFIED**;
`IND-VLV-01` is unsupported and no actuator or post-action physical feedback is
claimed.

## Verification record — 8 November 2026

| Command | Exit | Result |
|---|---:|---|
| `$env:PYTHONPATH='src'; .\tmp\twin-audit-venv\Scripts\python.exe -X utf8 -m unittest live_tests.test_scenario_orchestration.ScenarioOrchestrationTests.test_scn03_rejects_signal_command_without_linked_traffic_backup` | 0 | Updated SCN-03 focused test passed. Both commands to `DTN-TLT-01` were rejected with `SCENARIO_GUARDIAN_PENDING`; CityCore revision did not change. |
| ` .\tmp\twin-audit-venv\Scripts\python.exe -X utf8 tools/run_scenario_campaign.py --evidence-root test-evidence` | 1 | All six scenarios, sequential run, cross-scenario checks, and local process-restart checks passed. Overall **BLOCKED** because real Brain/Guardian outage checks cannot run without partner services. Evidence: [campaign JSON](test-evidence/scenario-campaign-20261108T074306.489418Z-f1e94dce/campaign.json), SCN-03 [events](test-evidence/scenario-campaign-20261108T074306.489418Z-f1e94dce/individual/individual-scn-03-city-events.json), and [audit](test-evidence/scenario-campaign-20261108T074306.489418Z-f1e94dce/audit/individual-scn-03_campaign-3-ff347598eee5.jsonl). |
