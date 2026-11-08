# Local Demo Guide

This demo runs the Twin on one machine. It is a local software demonstration; it does not connect to real Brain or Guardian services or physical devices.

## Requirements

Use Python **3.12 or newer**. Check `python --version` before creating the virtual environment. From PowerShell at the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.lock
```

If `python` points to Python 3.11, install/select Python 3.12 first and use its executable to create `.venv`. The project declares Python `>=3.12`.

## Start the operator dashboard

```powershell
.\.venv\Scripts\python.exe -X utf8 tools\run_dashboard.py --open
```

Choose a one-launch passphrase when prompted. Sign in at the local URL printed by the launcher. Keep the terminal open while using the dashboard; stop it with `Ctrl+C`.

## Show scenario events

1. Sign in to the private operator view.
2. Open **More Twin tools**, select **SCN-03**, and start it.
3. Open **History & event timeline** and inspect **Operational trace**.

The trace should show Twin-recorded sensor updates and pending markers. SCN-03 does not call a real Brain or Guardian service. A local scenario start alone does not produce a partner decision or a physical actuator response. The browser rendering of the current dashboard trace is **NOT VERIFIED** in the saved evidence.

For the recorded standalone mock demo and scenario outcomes, see [Testing](TESTING.md) and [Scenario Book](SCENARIO_BOOK.md).
