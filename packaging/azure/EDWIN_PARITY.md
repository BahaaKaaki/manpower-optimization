# Edwin vs Manpower Azure deploy (same pattern)

[Edwin Slides Creator](../../../edwin-slides-creator/deploy.sh) and this repo’s root [`deploy.sh`](../../deploy.sh) follow the **same deploy sequence** (Edwin’s script is the reference):

1. Build frontend (`npm run build` in `desktop/` — Edwin uses `slide-generator/`).
2. Stage backend + static assets into one folder (Edwin runs `npm install --omit=dev` into `deploy-temp`; Manpower ships Python sources and lets **Oryx** run `pip install -r requirements.txt` on Azure because Linux wheels cannot be built reliably from macOS the way npm can).
3. Zip the folder.
4. **`az account set`** → **`BUILD_ID`** app setting → **`az webapp deploy --type zip --restart true`**.

Manpower’s **`deploy.sh`** inserts **`az webapp config set --startup-file 'bash manpower_start.sh'`** immediately before deploy — Edwin does **not** need this because Node’s startup command is configured in the Portal (`node dist/index.js`). Use **`manpower_start.sh`** (not **`startup.sh`**) to avoid colliding with Oryx’s **`/opt/startup/startup.sh`**.

## Configuration alignment

| Setting | Edwin (`app-edwin-slides`) | Manpower (`manpower-studio-3d85d5`) |
|--------|-----------------------------|-------------------------------------|
| Plan / RG | `asp-edwin-slides`, `rg-edwin-slides` | `asp-manpower-pilot`, `rg-manpower-pilot` |
| Stack | `NODE|20-lts` | `PYTHON|3.11` |
| Startup | `node dist/index.js` (Portal) | **`bash manpower_start.sh`** (set in **`deploy.sh`** before zip deploy) → **`uvicorn`** — see [`manpower_start.sh`](manpower_start.sh) |
| HTTPS only | Yes (policy) | Yes |
| Always On | Yes | Yes |
| App logs | Filesystem + detailed errors | Matched via `az webapp log config` |

Edwin’s Node zip **includes** production `node_modules` produced locally. Manpower’s zip **does not** include a cross-platform Python venv from macOS; **Oryx** installs dependencies on Azure Linux after zip deploy (`SCM_DO_BUILD_DURING_DEPLOYMENT`, `ENABLE_ORYX_BUILD`).

## TLS / `az webapp deploy` failures

Both apps hit **`https://<app>.scm.azurewebsites.net`** for Kudu. If the Azure CLI reports **certificate verify failed**, the fix is the same for Edwin and Manpower: trust your organization’s intercept CA (see root [`deploy.sh`](../../deploy.sh) env **`AZURE_CLI_CA_BUNDLE`**) or merge it with Certifi:

```bash
python3 -c "import certifi, pathlib; print(certifi.where())"
# Merge certifi PEM + your CorporateRoot.pem → ~/combined-azure-ca.pem
export AZURE_CLI_CA_BUNDLE="$HOME/combined-azure-ca.pem"
./deploy.sh
```

Deploying from **CI (Ubuntu GitHub Actions)** often avoids the laptop proxy entirely.

## Private networking (important)

Edwin’s Web App uses **`publicNetworkAccess: Disabled`**, **regional VNet integration** (subnet `pzi-sw5t3-dev001-we-snt-003`), a **private endpoint** (`pe-app-edwin-slides` in `...-we-snt-004`), and **Private DNS** for `privatelink.azurewebsites.net`. The manpower pilot app **`manpower-studio-3d85d5`** now matches that pattern: **`pe-manpower-studio`**, the same VNet integration subnet, the same shared Private DNS zone group, and **`publicNetworkAccess: Disabled`**. Deploy and browse from a context where **private** resolution works (typically VPN). Details and verification commands: [NETWORKING_VS_EDWIN.md](NETWORKING_VS_EDWIN.md).
