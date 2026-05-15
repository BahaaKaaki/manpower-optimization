# Azure App Service deployment (ZIP / Python)

Same pattern as **Edwin Slides Creator**: pre-install all dependencies locally, ship a ready-to-run ZIP, no server-side build.

## One-command deploy

```bash
./deploy.sh
```

Options: `--skip-build` (deploy existing zip), `--skip-deploy` (build zip only).

Override defaults with env vars:

```text
AZURE_SUBSCRIPTION   default: pzi-gxx1-sw5t3-dev001
AZURE_RESOURCE_GROUP default: rg-manpower-pilot
AZURE_WEBAPP_NAME    default: manpower-studio-3d85d5
DEPLOY_ZIP_PATH      default: <repo>/manpower-deploy.zip
```

## How it works

The deploy mirrors Edwin exactly:

| Step | Edwin | Manpower |
|------|-------|----------|
| Build frontend | `npm run build` | `npm run build` (Vite) |
| Install deps | `npm install --omit=dev` | `pip install --platform manylinux2014_x86_64 --target packages/` |
| Create ZIP | zip everything | zip everything |
| Deploy | `az webapp deploy --type zip` | `az webapp deploy --type zip --async true` |
| Server-side build | None (`SCM_DO_BUILD_DURING_DEPLOYMENT=false`) | None (`SCM_DO_BUILD_DURING_DEPLOYMENT=false`) |

The `--async true` flag is needed because Python Linux containers don't implement the `/deploymentStatus` polling endpoint that the Azure CLI expects. The upload succeeds regardless.

## What's in the ZIP (~50MB)

```
manpower_api/        Python API source
manpower_app/        Optimization engine source
packages/            Pre-installed Linux Python packages (pandas, fastapi, uvicorn, etc.)
static/              Vite-built frontend (from desktop/dist)
manpower_start.sh    Startup script
```

## App settings (already configured)

| Setting | Value | Purpose |
|---------|-------|---------|
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `false` | No server-side build (deps are in the zip) |
| `ENABLE_ORYX_BUILD` | `false` | Same — skip Oryx |
| `WEBSITES_PORT` | `8000` | Uvicorn listens here |
| `startup-file` | `bash manpower_start.sh` | App entry point |

## Azure resources

| Resource | Name |
|----------|------|
| Subscription | `pzi-gxx1-sw5t3-dev001` |
| Resource group | `rg-manpower-pilot` |
| App Service plan | `asp-manpower-pilot` (Linux, Premium V3 P1v3) |
| Web app | `manpower-studio-3d85d5` |
| URL | https://manpower-studio-3d85d5.azurewebsites.net |
| Network | Private endpoint only (same VNet as Edwin, requires VPN) |

## Verify after deploy

```bash
curl https://manpower-studio-3d85d5.azurewebsites.net/health
# → {"status":"ok"}
```

Browser: same URL loads the React app (requires VPN since `publicNetworkAccess` is disabled).

## Troubleshooting

### App shows "Application Error" (503)

The container hasn't started yet. Wait 1-2 minutes after deploy, then check:

```bash
az webapp log tail --resource-group rg-manpower-pilot --name manpower-studio-3d85d5
```

### `ModuleNotFoundError`

The `packages/` directory is missing or was built for the wrong platform. Rebuild:

```bash
./deploy.sh  # rebuilds from scratch
```

### SSL/TLS error from `az webapp deploy`

Corporate proxy intercepting TLS:

```bash
export REQUESTS_CA_BUNDLE=/path/to/your/org-ca-bundle.pem
./deploy.sh --skip-build
```

## Build ZIP only (no deploy)

```bash
bash packaging/azure/build-deploy-zip.sh
# Creates /tmp/manpower-app.zip (or set OUTPUT_ZIP)
```

## Teardown

Delete resource group `rg-manpower-pilot` when the pilot ends.
