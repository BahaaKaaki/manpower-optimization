# Networking: manpower pilot vs Edwin (deploy / SCM path)

Azure CLI output from subscription **`pzi-gxx1-sw5t3-dev001`** (same subscription context used by both apps).

## Side-by-side (current)

| Aspect | **Edwin** `app-edwin-slides` (`rg-edwin-slides`) | **Manpower pilot** `manpower-studio-3d85d5` (`rg-manpower-pilot`) |
|--------|---------------------------------------------------|---------------------------------------------------------------------|
| **Public network access** | **`Disabled`** | **`Disabled`** |
| **Regional VNet integration** | **Yes** — `.../pzi-sw5t3-dev001-we-vnt-001/subnets/pzi-sw5t3-dev001-we-snt-003` | **Same** subnet as Edwin |
| **Private endpoint** | **Yes** — `pe-app-edwin-slides` (NIC in `...-we-snt-004`) | **Yes** — `pe-manpower-studio` (same `...-we-snt-004` pattern) |
| **Private DNS zone group** | **Yes** — `default` on the PE, zone `privatelink.azurewebsites.net` (cross-subscription ID in `pzi-gxus-p-rgp-eddi-p003`) | **Yes** — `default` on `pe-manpower-studio`, same shared zone |
| **Access path** | Main + SCM hostnames resolve via **Private DNS** when on the corporate path | **Same** — use VPN / internal DNS so `manpower-studio-3d85d5.scm` resolves to the private IP |

Edwin’s own docs reference **private endpoint** and **Private DNS** (`privatelink.azurewebsites.net`) for internal resolution — manpower now uses the **same** shared zone and subnet pattern.

## What this means for you

1. **`*.scm.azurewebsites.net` (Kudu / ZipDeploy / `az webapp deploy`)**  
   With **`publicNetworkAccess: Disabled`**, you must be on a path where DNS resolves the SCM host to the **private** address (typically **corporate network / VPN** and tenant Private DNS). Deploy from the same kind of session where Edwin’s `./deploy.sh` already succeeds.

2. **504 / timeouts on long uploads**  
   Prefer the **private** path above; proxies on **public** routes no longer apply once ingress is private-only.

3. **SSL errors in some environments**  
   If Azure CLI still reports **certificate verify failed**, use **`AZURE_CLI_CA_BUNDLE`** (see root [`deploy.sh`](../../deploy.sh)) so Python trusts your organization’s CA on the **same** machine you use for deploy.

## If you need to re-provision another app

1. **Private endpoint** in `...-we-snt-004` (or an approved PE subnet), `group-id` **`sites`**, connection to the Web App.
2. **Private DNS zone group** on the PE to the shared **`privatelink.azurewebsites.net`** zone (Edwin and manpower use the cross-subscription zone in `pzi-gxus-p-rgp-eddi-p003`).
3. **Regional VNet integration** on the Web App to **`...-we-snt-003`** (or the approved integration subnet).
4. Set **`publicNetworkAccess`** to **`Disabled`** only **after** PE + DNS are healthy.

## Commands used (for re-check)

```bash
az webapp show -g rg-edwin-slides -n app-edwin-slides \
  --query "{publicNetworkAccess:publicNetworkAccess,virtualNetworkSubnetId:virtualNetworkSubnetId}"

az webapp show -g rg-manpower-pilot -n manpower-studio-3d85d5 \
  --query "{publicNetworkAccess:publicNetworkAccess,virtualNetworkSubnetId:virtualNetworkSubnetId}"

az network private-endpoint list -g rg-edwin-slides -o table
az network private-endpoint list -g rg-manpower-pilot -o table
```
