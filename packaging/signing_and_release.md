# Signing And Release Plan

## Release Channels

Use a staged release process:

1. **Internal smoke build**: local unsigned build for development only.
2. **Client pilot build**: zipped artifact or installer shared through an approved secure link with checksum and release notes.
3. **Production build**: signed installer distributed through client IT tooling.

## Windows Signing

Unsigned Windows apps can trigger SmartScreen and endpoint security warnings. For production:

- Use a company code-signing certificate or Azure Trusted Signing.
- Timestamp signatures so releases remain valid after certificate expiry.
- Sign the installer and, where practical, the sidecar executable.
- Provide SHA-256 checksums to client IT.

Potential distribution channels:

- Intune
- Company Portal
- SCCM
- Software Center
- Client-approved secure download portal

## macOS Signing

If macOS delivery is required:

- Use Apple Developer ID signing.
- Notarize the `.app` or `.dmg`.
- Staple notarization tickets before distribution.

## ZIP Versus Installer

A ZIP can work for a narrow pilot, but it is not ideal for broad rollout. Many corporate endpoints block unknown binaries or quarantine downloaded ZIP contents. A signed installer distributed by client IT is the more reliable production path.

## Secrets And IP

Do not embed secrets, API keys, or client credentials in the desktop package. Any logic shipped locally can be inspected by a motivated user. If the business logic becomes too sensitive to distribute, move that logic to client-hosted infrastructure or a controlled backend.

## Release Checklist

- Version number updated.
- React frontend built.
- Python sidecar built for target OS/architecture.
- Tauri bundle created.
- Installer and sidecar signed for production.
- SHA-256 checksum generated.
- Release notes prepared.
- Installation guide prepared.
- Client IT allowlisting/distribution path confirmed.

## Client handoff (packaged Tauri app)

After consultant testing on the **temporary Azure URL** is finished and resources are torn down (see [Azure pilot teardown](deploy/azure-container-app.md#pilot-teardown--what-to-delete-later)), the **primary delivery** to the client is the **desktop application**: the Tauri shell wraps the same React UI and bundles or couples it with the **local FastAPI sidecar** built for Windows/macOS per `scripts/build_desktop_pilot.sh` and `desktop/` packaging.

**Goal:** hand off a **single, client-ready package** that feels intentional, not a loose folder of binaries.

Recommended contents of the handoff bundle:

1. **Installer or signed archive** produced by the official build pipeline (`.msi`/`.exe`/`.dmg` or approved ZIP per client IT policy).
2. **SHA-256 checksum** file next to the artifact for verification.
3. **Release notes** — version, date, fixed issues, known limitations.
4. **Installation and first-run guide** — install steps, that the **Python API runs locally** with the app, firewall prompts if any, and where logs appear.
5. **Support boundary** — what is in scope for pilot vs production (e.g. workbook format, minimum OS version).

Optional polish:

- Branded **README PDF** or one-pager summarizing launch steps for business users.
- **Version label** visible in the app or About dialog aligned with the package version.

The **cloud pilot** (Docker on Azure) is **not** the long-term product unless the client explicitly chooses a hosted model; plan to **delete** pilot Azure resources once validation ends and rely on this packaged handoff for ongoing client use unless agreed otherwise.
