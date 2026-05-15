# Desktop Delivery Notes

## Recommended Delivery Position

For immediate use, keep the Streamlit app and package the Python environment clearly. For a more polished client laptop delivery, move toward a Tauri desktop shell with a React UI and a local Python/FastAPI sidecar that calls the same `manpower_app` modules.

## Distribution Options

- **Local Streamlit package**: fastest path for a controlled pilot. Users run the app locally with Python dependencies installed or managed by a launcher.
- **Portable ZIP**: practical for pilots, but many corporate devices block unknown executables or scripts. Include checksums and a clear installation guide.
- **Signed installer**: preferred for client trust, Windows SmartScreen reduction, and IT allowlisting.
- **Client IT distribution**: best long-term route through Intune, Company Portal, SCCM, Software Center, or an approved internal download portal.

## Security And IP Reality

If logic runs on the client machine, the package can be inspected. Packaging, minification, PyInstaller, and obfuscation only raise the effort required to inspect the implementation. Do not embed secrets, API keys, or confidential credentials in the package.

For highly sensitive logic, use a client-hosted backend or a controlled hosted service. If the app must remain fully local, document the residual reverse-engineering risk and keep especially sensitive logic out of frontend JavaScript and plain Python where feasible.

## Signing Considerations

Unsigned Windows builds can trigger SmartScreen and endpoint security warnings. A production client release should use a recognized code-signing certificate or Azure Trusted Signing. macOS releases require Developer ID signing and notarization if distributed outside the App Store.

## Client Download Guidance

A download link is acceptable for pilots only if it is hosted on an approved secure channel and accompanied by version number, checksum, release notes, and installation instructions. For broader rollout, coordinate with client IT and ask them to distribute or allowlist the installer.