# Manpower Optimization Tool

Source repository (private): https://github.com/pwc-me-adv-strategyand/manpower-optimization

This project is a manpower planning and payroll optimization tool. It reads workforce data from Excel, maps employees into configured job families, applies outsourceability and Saudization rules, runs an integer optimization model, shows analytics, and exports the recommended allocation with audit detail to Excel.

## Current Delivery Model

The repo now supports two working interfaces:

- `Manpower Tool.py` remains the Streamlit interface for quick local review and logic validation.
- `desktop/` contains the Tauri + React desktop experience with an upload-first launchpad, guided scenario builder (posture summary plus accordion policy areas), target-split review, executive savings analytics, baseline-vs-optimized payroll overview (no intermediate model layers in the client UI), job-family drilldowns, optimization audit tables, and Excel export. Running the final scenario automatically computes the target split when it has not been run yet so the workflow step for policy review stays honest in the sidebar. The Ready-stage optimization bar can stay pinned while you review inputs, and the scenario builder plus results dashboard share refreshed layout and styling with the rest of the shell. Results donuts place slice callouts on the chart, job-family headcount bars print counts inside segments when there is room, savings KPI titles stay short while values carry the units, and the shell navigation drops the extra subtitle line under each step label.

## Requirements

Use Python 3.11 or newer where possible. Install dependencies with:

```bash
python -m pip install -r requirements.txt
```

## Quick local testing

Use the **repository root** as the working directory so `Manpower Tool.py` resolves and optional companion files (`Ratio.xlsx`, `CPC logo.png`) load from the same folder as documented in [Local companion files](#local-companion-files).

### Streamlit only

```bash
cd /path/to/manpower-optimization
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python3 -m pip install -r requirements.txt
streamlit run "Manpower Tool.py"
```

Streamlit listens on **8501** by default (check the terminal URL). Thin entrypoint: `Manpower Tool.py` calls `manpower_app.ui_streamlit.run_app()`.

Shell shortcut (same steps as above, from repo root):

```bash
bash scripts/dev_streamlit.sh
```

### Desktop (FastAPI + Tauri)

In development, the React UI uses same-origin API paths and Vite proxies them to **http://127.0.0.1:8765**. Vite serves the frontend on **5174** by default (`desktop/vite.config.ts`). Packaged desktop builds ask Tauri for the per-instance sidecar URL selected at runtime, so multiple installed desktop instances do not share one hardcoded API port. The API allows browser origins matching **`http://127.0.0.1:*`** and **`http://localhost:*`** via `CORSMiddleware` in `manpower_api/app.py` (regex), plus Tauri schemes — restart **`uvicorn`** after changing CORS code.

**Terminal A — API**

```bash
cd /path/to/manpower-optimization
source .venv/bin/activate   # if you use a venv
bash scripts/dev_api.sh
```

Equivalent manual command:

```bash
python3 -m uvicorn manpower_api.app:app --host 127.0.0.1 --port 8765 --reload
```

**Terminal B — Tauri desktop shell**

```bash
cd /path/to/manpower-optimization/desktop
npm install
npm run tauri:dev
```

Shortcut from repo root (installs npm dependencies on first run if `node_modules` is missing):

```bash
bash scripts/dev_desktop.sh
```

**Browser-only UI (no Tauri window):** with the API running, `cd desktop && npm run dev` opens the Vite app at `http://127.0.0.1:5174` (or `npm run dev -- --port 5175` for another port; restart the API after adding a new CORS origin if needed). Vite proxies `/health`, `/workbooks`, `/model`, `/optimization`, and `/exports` to the API on **8765**, so the React client can use same-origin relative URLs in development.

### Deploying the web UI (Docker / Azure)

Build a **single container** that serves the optimized React app and FastAPI on one origin (consultants open one HTTPS URL; no Streamlit):

```bash
docker build -t manpower-web:latest .
docker run --rm -p 8080:8000 manpower-web:latest
```

Then open `http://127.0.0.1:8080`. Azure Container Apps / Web App for Containers steps, ports, and **what to delete after consultant pilots** are in [packaging/deploy/azure-container-app.md](packaging/deploy/azure-container-app.md). If your tenant **blocks creating a container registry** (Premium / private network policies), use **Linux App Service + ZIP** instead: run **`./deploy.sh`** from the repo root (same pattern as `edwin-slides-creator/deploy.sh`; details in [packaging/azure/README.md](packaging/azure/README.md)). The ZIP stages **`pyproject.toml`** plus a **slim** [`requirements-azure.txt`](packaging/azure/requirements-azure.txt) as `requirements.txt` so Oryx runs **`pip install .`** (non-editable) and copies **`manpower_api` / `manpower_app`** into **`antenv`** — editable installs break after Oryx extracts the build under **`/tmp`**. Streamlit/Plotly stay only in root [`requirements.txt`](requirements.txt) for local use. After building the ZIP, **`./scripts/verify-azure-package.sh`** reproduces Oryx-style **`pip install`** and confirms **`manpower_api`** imports. The pilot Web App uses **private endpoint + Private DNS** and **`publicNetworkAccess: Disabled`** (aligned with Edwin); run deploy and open the site from a session where **corporate VPN / internal DNS** resolves `*.privatelink.azurewebsites.net` — see [packaging/azure/NETWORKING_VS_EDWIN.md](packaging/azure/NETWORKING_VS_EDWIN.md). Client-facing **packaged Tauri handoff** (installer, checksums, release notes) is described in [packaging/signing_and_release.md](packaging/signing_and_release.md).

### Savings % alignment

Use the same Excel workbook as in the desktop app. To compare **savings %** between Streamlit and the desktop app, align scenario inputs with the desktop defaults (`desktop/src/App.tsx`, `defaultSettings`) or whatever you set in the Scenario panel: Saudization on/off and rate, risk factor, negotiated rates, tenure protection and threshold, profession-specific Saudization rates, and “allow reducing current Saudi headcount.” Savings are reported for the **Final Optimized Scenario**: `(current_payroll_cost - optimized_payroll) / current_payroll_cost`, where `current_payroll_cost` is current outsourced plus in-house using fully loaded in-house averages from the aggregated model input table.

## Matching Streamlit vs Desktop (Tauri)

- **Shared core:** `POST /optimization/run` in `manpower_api` calls `manpower_app.service.run_optimization`, which prepares one model input table, solves the final optimized scenario, and returns compatibility fields for older `payroll_v5` consumers.
- **Defaults:** API request body defaults (`manpower_api/app.py`, `OptimizationSettingsRequest`) match `OptimizationSettings` in `manpower_app/service.py` and the desktop `defaultSettings` in `desktop/src/App.tsx` (e.g. overall Saudization 0.30, risk factor 0.25, engineer/sales/management rates 0.25 / 0.60 / 0.35). Streamlit widgets use the same numeric defaults on first load (`manpower_app/ui_streamlit.py`).
- **If percentages still differ:** Confirm identical workbook upload and the same scenario controls on both sides (Streamlit stores inputs in session state; the desktop sends them as JSON). The maintained desktop/API path now uses the consultant risk-factor formula for partially outsourceable rows.

## Optimization Formula Notes

For partially outsourceable job families, the consultant-derived risk factor is applied as a capacity haircut on outsourced employees:

```text
O = outsourced employees
I = in-house employees
T = total count
M = minimum count
R = risk factor

O + I = T
O * (1 - R) + I >= M
```

The equivalent outsource cap is `O <= (T - M) / R` when `R > 0`. When `R == 0` the haircut is disabled — the constraint degenerates to `O + I >= M`, which the LP can satisfy as long as `T >= M`. The API and desktop UI accept `0 <= R <= 1`; the rearranged closed-form `(T - M) / R` is only consulted when `R > 0`. The Excel export includes an **Optimization Audit** sheet with the final outsourced/in-house counts, `O * (1 - R) + I`, and pass/fail checks for each constraint.

## Input Workbook

Upload a workbook named or shaped like `Manpower.xlsx` with these required sheets:

- `Inhouse`
- `Subcontractor`

The app expects workforce columns such as employee number, location or working area, profession, nationality, and payroll cost fields. Column names are stripped for whitespace during loading. Rows that cannot be mapped to a configured job family are shown in the UI and processing stops so the mapping can be corrected.

## Local Companion Files

Place these files next to `Manpower Tool.py` when available:

- `Ratio.xlsx`: optional ratio and outsourceability research input. If missing, the app falls back to embedded rules.
- `CPC logo.png`: optional logo used in the Streamlit header. If missing, a text placeholder is shown.

## Code Layout

- `Manpower Tool.py`: thin Streamlit launcher.
- `manpower_app/ui_streamlit.py`: Streamlit screens and presentation flow.
- `manpower_app/mappings.py`: pactivity, profession, and job-family mappings.
- `manpower_app/rules.py`: outsourceability and maximum ratio rules.
- `manpower_app/pipeline.py`: workbook loading helpers.
- `manpower_app/costs.py`: in-house and outsourced cost calculations.
- `manpower_app/tenure.py`: tenure detection and tenure protection helpers.
- `manpower_app/ratios.py`: ratio loading, driver values, and minimum in-house calculations.
- `manpower_app/optimization.py`: final optimization solver and legacy stage compatibility helpers.
- `manpower_app/results.py`: optimization result shaping and summary metrics.
- `manpower_app/export.py`: reusable Excel workbook generation helper.

## Desktop App

The Tauri + React desktop app lives in `desktop/`. It calls the local FastAPI wrapper in `manpower_api/`, which reuses the same `manpower_app` model used by Streamlit. Local run commands are in [Quick local testing](#quick-local-testing) (API on **8765**, Vite on **5174** in dev). Cargo writes build output under `desktop/src-tauri/target/`; that directory is ignored and must not be committed. Tauri-generated files under `desktop/src-tauri/gen/` and the PyInstaller sidecar binaries under `desktop/src-tauri/binaries/` are also build outputs (from `cargo tauri` and `scripts/build_api_sidecar.sh` respectively) and are not tracked in git. Packaged runs start one API sidecar per app process, assign a free local port per instance, and stop that sidecar when its window exits so upgrades, uninstalls, and parallel desktop sessions are not blocked; details are in `desktop/README.md` under **Sidecar lifecycle**.

Build desktop artifacts:

```bash
bash scripts/build_desktop_pilot.sh
```

Signing and release guidance is documented in `packaging/signing_and_release.md`.