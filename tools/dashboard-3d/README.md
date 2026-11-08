# Twin-hosted 3D city view

This package builds the React and Three.js primary view for the Python Twin dashboard. The 3D city model is paired with live sensor, actuator, scenario, and event summaries. The existing Twin operations suite remains available in a collapsed “More Twin tools” section. Authentication, frame access, and private-versus-reported visibility continue to use the existing dashboard server; the React view listens for `twin-dashboard-frame` events and does not call a separate data API.

The supplied GLB is served from `src/city_dashboard/web/3d/models/city-cs-challenge.glb`. The displayed `S-WATER-01` sensor and `DTN-VLV-01` actuator marker positions are illustrative; the model has not been georeferenced to the Twin's asset catalog. The sensor summary uses the reported value and unit in the current Twin frame; operator-only physical water diagnostics are shown separately. The Brain/Guardian card explicitly says their status is not reported by this Twin frame; it does not infer a partner response.

Build the static bundle from the repository root:

```powershell
Set-Location tools/dashboard-3d
npm ci
npm run build
```

The build writes the bundled JavaScript and CSS to `src/city_dashboard/web/3d/assets`. The dashboard loads the Three.js viewer when the operations page opens, and the server streams the GLB model rather than loading the full file into memory.

To run the integrated dashboard, return to the repository root and launch `Start Dashboard.cmd`. The local server prompts for a one-launch operator passphrase; the reported view is read-only and does not require sign-in.
