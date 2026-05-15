# Deploy React + API as one container (Azure)

This image serves **FastAPI** and the **built Vite app** from one URL (same origin). Streamlit is not included.

## Alternative: App Service ZIP (no container registry)

Many enterprises **deny** new Azure Container Registry SKUs (Premium-only policies). In that case deploy **FastAPI + static UI** as a **Linux Python Web App** using a ZIP package and **`manpower_start.sh`**; see [packaging/azure/README.md](../azure/README.md).

## Build locally

From the repository root (Docker required):

```bash
docker build -t manpower-web:latest .
docker run --rm -p 8080:8000 -e PORT=8000 manpower-web:latest
```

Open `http://127.0.0.1:8080`. The UI loads from `/`; API routes stay at `/health`, `/workbooks/upload`, `/optimization/*`, `/exports/*`.

## Azure Container Apps or Web App for Containers

1. Create a container registry (ACR), build and push the image (Azure Portal **Containers** > **Quick deploy**, or `az acr build`).
2. Create **Container Apps** or **Web App for Containers** pointing at that image.
3. **Ingress**: HTTPS enabled, target port **8000** (the container listens on `PORT`, default 8000 via `/entrypoint.sh`).
4. **Environment variables** (optional):
   - `CORS_ALLOW_ORIGINS` — comma-separated extra origins if you ever split frontend and API onto different hostnames.
   - Leave `STATIC_ROOT` unset only if you customize the image; the default image sets `/app/static` internally.

## Pilot teardown — what to delete later

Keep every **temporary cloud pilot** inside a dedicated **resource group** (for example `rg-manpower-consultant-pilot`) so teardown is one action. Before deleting, export anything you must retain (cost logs, access logs, runbooks).

When the consultant testing phase ends, remove or verify the following so billing and exposure stop:

| Item | Notes |
|------|--------|
| **Container App or Web App for Containers** | Stops the public URL and compute for the Docker image. |
| **Container registry** | Delete only if created solely for this pilot; if the registry is shared, delete **only the repository/tag** for `manpower-web` (or your image name). |
| **Resource group** | **Delete the whole pilot RG** once nothing inside is shared—this is the usual clean teardown. |
| **Application Insights / Log Analytics** | If attached to the pilot RG, they go away with the RG; if linked cross-RG, delete or detach manually. |
| **Managed identities / Key Vault references** | Remove app registrations or secrets created only for this pilot. |
| **DNS / custom domain bindings** | Remove CNAME or TXT records if you pointed a hostname at the pilot app. |
| **Dashboards or alerts** | Delete pilot-specific monitors so they do not page the team after the app is gone. |

**Do not delete** subscription-wide shared resources (central ACR, hub networking, shared Key Vault) unless your cloud owner agrees.

After deletion, confirm in **Cost Management** that no orphaned charges remain from retained disks, stopped-but-not-deleted apps, or registry storage.

## Client handoff (desktop) vs cloud pilot

The **browser pilot** above is for short consultant testing. The **long-term client delivery** for the installed experience is the **packaged Tauri desktop app** (React UI + local Python API sidecar), handed off separately—see [Signing and release](../signing_and_release.md) and **Client handoff** in that document.

## Security notes for consultants

- Workforce uploads are sensitive; prefer **Microsoft Entra ID (Easy Auth)** on the web app or IP restrictions.
- Session state lives **in memory** on the API process; scaling out to multiple replicas requires a sticky session or external store (not implemented)—use **one instance** for short pilots.

## Costs

Use the smallest suitable SKU for two testers; enable scale-to-zero on Container Apps where applicable for idle periods.
