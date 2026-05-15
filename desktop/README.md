# Manpower Desktop App

This folder contains the desktop delivery layer for the Manpower Optimization tool.

The desktop app uses:

- React + TypeScript + Vite for the UI.
- Tauri for the native desktop shell.
- A local FastAPI sidecar that reuses the Python model in `../manpower_app`.

## User Experience

The UI is organized as a client-facing workforce scenario planning cockpit: upload and validate the workbook, review data health, tune assumptions, calculate the target split (or rely on the implicit policy pass when you run the final scenario), run the final optimized scenario, review executive analytics, and export Excel results.

The upload screen is a dedicated launchpad: assumptions and optimization actions stay locked until a workbook is loaded. After upload, the app moves into a guided scenario builder with baseline readiness, a posture summary strip plus accordion sections for Saudization, cost and risk, and workforce protection, target-split checks, and final-scenario execution. Results emphasize a single baseline-vs-optimized payroll comparison and headcount mix on the Overview tab, with job families, target split, and audit available as supporting tabs. On first launch, the app quietly treats missing previous results as an empty restore state. The desktop UI also uses the CPC logo from the repo root; Vite is configured to allow that shared asset during development.

## Development Mode

Run the Python API from the repo root:

```bash
python3 -m uvicorn manpower_api.app:app --host 127.0.0.1 --port 8765 --reload
```

Then run the React UI:

```bash
cd desktop
npm install
npm run dev
```

Open `http://127.0.0.1:5174`.

The local FastAPI backend allows local browser origins on any Vite port (`http://127.0.0.1:*` and `http://localhost:*`), plus the Tauri local origins used by the desktop shell.

**Browser dev:** `vite.config.ts` proxies API paths to `http://127.0.0.1:8765`, so you can run the API and `npm run dev` without changing `VITE_API_BASE`. Production Docker builds set `VITE_API_BASE` to empty for same-origin calls against the bundled server. Packaged desktop builds ignore the fixed dev port and ask Tauri for the sidecar URL selected at runtime.

The sidebar logo is served from `public/cpc-logo.svg` in this folder (see `npm run build` output). Optional `CPC logo.png` at the repository root remains documented for Streamlit and legacy Tauri icon configuration.

To launch the full Tauri desktop shell in development mode:

```bash
cd desktop
npm run tauri:dev
```

## Tauri Desktop Build

From the repo root:

```bash
bash scripts/build_desktop_pilot.sh
```

This script:

1. Installs Python desktop packaging dependencies.
2. Builds the FastAPI backend as a PyInstaller sidecar.
3. Copies the sidecar to `desktop/src-tauri/binaries/` with a Tauri-compatible platform suffix.
4. Installs frontend dependencies.
5. Builds the React frontend.
6. Runs `tauri build`.

Icons live under `src-tauri/icons/` (`icon.icns`, `icon.ico`, `icon.png`, and fixed-size PNGs). They were generated from the CPC sidebar artwork (`public/cpc-logo.svg`) using macOS Quick Look rasterization plus `npx @tauri-apps/cli icon` so every platform target has the assets Tauri expects.

**Tauri compile:** `tauri-build` requires the platform-named sidecar file under `src-tauri/binaries/` (created by `bash scripts/build_api_sidecar.sh` from the repo root). Without it, `cargo check` / `tauri build` fail with a missing external binary path.

Unsigned desktop artifacts are written under:

```text
desktop/src-tauri/target/release/bundle
```

## Sidecar lifecycle

The FastAPI sidecar is started from Rust during Tauri `setup`. On application exit, the shell tears down that child process so installers and updates are not blocked by a stray `manpower-api` still listening on the API port. Spawning only from the JavaScript shell API would register children in the plugin store automatically; the Rust `setup` path requires this explicit exit cleanup on every desktop platform.

Packaged desktop instances choose an available `127.0.0.1` port independently and pass it to the sidecar with `MANPOWER_API_PORT`. The React UI resolves its API origin from Tauri at startup, so multiple desktop app processes can run side by side as separate UI ↔ sidecar pairs. Development and browser builds continue to use the Vite proxy / `8765` flow described above.

## Production Notes

Production distribution should add code signing, checksum generation, release notes, and client IT allowlisting or managed software distribution.
