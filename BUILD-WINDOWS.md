# Build the Manpower Optimization desktop app on Windows

This produces `Manpower Optimization_0.1.0_x64-setup.exe` — an installer you
can run on any Windows 10/11 machine.

The app is **unsigned**, so the first launch shows a Microsoft SmartScreen
warning ("Windows protected your PC"). Click **More info** → **Run anyway**.
After the first run, Windows trusts it.

---

## 1. Install prerequisites (one time, ~15 min)

Install in this order, accepting defaults unless noted:

1. **Node.js 20 LTS** — <https://nodejs.org/>
2. **Rust** — <https://rustup.rs/> (the `rustup-init.exe` from the page).
   Pick the default `stable-x86_64-pc-windows-msvc` toolchain.
3. **Python 3.11** — <https://www.python.org/downloads/release/python-3119/>.
   **Check "Add Python to PATH"** on the first installer screen.
4. **Visual Studio Build Tools 2022** — <https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022>.
   In the installer, on the **Workloads** tab, tick **"Desktop development with C++"**.
   This brings in the MSVC compiler, Windows SDK, and the linker that Rust uses.
5. **Git** — <https://git-scm.com/download/win>. The default install includes
   **Git Bash**, which the build script needs.
6. **WebView2 Runtime** — already installed on Windows 11 and on most up-to-date
   Windows 10 boxes. If not, install the
   [Evergreen Standalone Installer](https://developer.microsoft.com/en-us/microsoft-edge/webview2/).

Reboot after Visual Studio Build Tools finishes — the new linker only shows up
in PATH after a restart.

---

## 2. Clone the repo

In Git Bash:

```bash
git clone https://github.com/pwc-me-adv-strategyand/manpower-optimization.git
cd manpower-optimization
```

---

## 3. Build the installer (one command, ~10 min first time)

Still in Git Bash, from the repo root:

```bash
bash scripts/build_desktop_pilot.sh
```

This script does, in order:

1. `pip install -r requirements-desktop.txt` — Python deps.
2. PyInstaller bundles the FastAPI backend into
   `desktop/src-tauri/binaries/manpower-api-x86_64-pc-windows-msvc.exe`
   (the "sidecar" Tauri ships alongside the GUI).
3. `npm install` in `desktop/`.
4. Vite builds the React frontend into `desktop/dist/`.
5. Rust compiles the Tauri shell and wraps everything into an installer.

First run is the slow one — Rust pulls down ~360 crates and compiles them.
Subsequent builds are incremental and finish in 1-2 minutes.

---

## 4. Find the installer

After the build finishes, the installer is at:

```
desktop/src-tauri/target/release/bundle/nsis/Manpower Optimization_0.1.0_x64-setup.exe
```

(There is also a `.msi` next to it under `bundle/msi/` — either works. NSIS is
smaller and installs per-user without admin rights; MSI installs system-wide
and asks for admin.)

Double-click to install. The app appears in the Start menu as **Manpower
Optimization**.

---

## Troubleshooting

**"link.exe not found" or "MSVC link error" during Rust compile**
You skipped the C++ workload in Visual Studio Build Tools, or you didn't
reboot. Open the Visual Studio Installer, click **Modify**, tick
**Desktop development with C++**, finish, then reboot.

**`npm` or `cargo` command not found in Git Bash**
Close and reopen Git Bash so it picks up the updated PATH.

**Python errors about missing `pulp` / `pandas` / `openpyxl`**
Run `python -m pip install -r requirements-desktop.txt` manually, then re-run
the build script.

**SmartScreen still blocks the .exe after "Run anyway"**
Right-click the .exe → **Properties** → at the bottom, tick **Unblock** → OK.

**Sidecar fails to start after install**
Open `%LOCALAPPDATA%\com.pwc.manpower.optimization\logs\` and look at the
most recent log. The sidecar is the FastAPI server — if it crashes, the GUI
will sit on "Starting engine..." indefinitely.
