<#
.SYNOPSIS
Builds the Windows desktop release packages for Manpower Optimization.

.DESCRIPTION
This script is intentionally Windows-only. It builds the Python FastAPI sidecar
with PyInstaller, packages the React/Tauri desktop app as an NSIS installer,
creates a portable ZIP, and writes SHA-256 checksum files next to the outputs.

It supports two release modes:

- Unsigned: no Authenticode signing is applied to the sidecar, app executable,
  NSIS installer, NSIS helper DLLs, or portable ZIP contents.
- Signed: signs the sidecar and lets Tauri sign the app executable, NSIS helper
  DLLs, uninstaller, and final installer using DigiCert KeyLocker via smctl.

This script must be run on Windows because it depends on Windows-only tooling:
PowerShell, PyInstaller producing a Windows .exe, Rust MSVC/Cargo, Tauri Windows
bundling, NSIS, signtool, and optional DigiCert KeyLocker smctl.

.PREREQUISITES
- Windows 10/11.
- Python available as `python`.
- Node.js/npm.
- Rust MSVC toolchain (`cargo`).
- Tauri dependencies already installed by `npm install`.
- NSIS tool cache available at `%LOCALAPPDATA%\tauri\NSIS`.
  If missing, place `nsis-3.11.zip` at `%TEMP%\nsis-3.11.zip`; the script will
  verify and extract it.
- For signed builds only: DigiCert KeyLocker user environment variables must be
  configured, especially `SM_HOST`, `SM_CLIENT_CERT_FILE`, and PATH entries for
  DigiCert KeyLocker Tools and Windows SDK signtool.

.EXAMPLES
Build unsigned NSIS installer and unsigned portable ZIP:

    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_desktop_windows.ps1 -Mode Unsigned

Build signed NSIS installer and signed portable ZIP:

    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_desktop_windows.ps1 -Mode Signed

Rebuild only Tauri packaging using the existing sidecar:

    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_desktop_windows.ps1 -Mode Unsigned -SkipSidecarBuild

.OUTPUTS
NSIS installer and portable ZIP names use productName and version from
desktop\src-tauri\tauri.conf.json, for example:

    ...\bundle\nsis\<ProductName>_<version>_x64-setup-<signed|unsigned>.exe
    ...\bundle\portable\<ProductName>_<version>_x64-portable-<signed|unsigned>.zip

Checksum files:

    *.sha256

.NOTES
Do not use `-SkipSidecarBuild` unless the existing sidecar already matches the
requested mode. A signed sidecar inside an unsigned installer, or an unsigned
sidecar inside a signed installer, can create confusing release artifacts.
#>

param(
    # Controls whether the sidecar and desktop bundle are signed.
    [ValidateSet("Signed", "Unsigned")]
    [string]$Mode = "Unsigned",

    # DigiCert code-signing certificate fingerprint used only for signed builds.
    [string]$Fingerprint = "014cab87a4b3b30f2862bb4ea18c268a95552532",

    # Skips PyInstaller sidecar rebuild. Use only when the existing sidecar is already correct for Mode.
    [switch]$SkipSidecarBuild
)

$ErrorActionPreference = "Stop"

# Read productName and version without ConvertFrom-Json so "$schema" in tauri.conf.json
# does not break Windows PowerShell 5.1 property access.
function Read-TauriBundleNaming {
    param([Parameter(Mandatory)][string]$TauriConfPath)
    if (-not (Test-Path -LiteralPath $TauriConfPath)) {
        throw "Tauri config not found: $TauriConfPath"
    }
    $raw = Get-Content -LiteralPath $TauriConfPath -Raw -Encoding UTF8
    if ($raw -notmatch '"productName"\s*:\s*"([^"]+)"') {
        throw "Could not parse productName from $TauriConfPath"
    }
    $productName = $Matches[1]
    if ($raw -notmatch '"version"\s*:\s*"([^"]+)"') {
        throw "Could not parse version from $TauriConfPath"
    }
    $version = $Matches[1]
    return @{
        ProductName = $productName
        Version       = $version
    }
}

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DesktopDir = Join-Path $RootDir "desktop"
$TauriDir = Join-Path $DesktopDir "src-tauri"
$TauriConfPath = Join-Path $TauriDir "tauri.conf.json"
$tauriBundle = Read-TauriBundleNaming $TauriConfPath
$ProductName = $tauriBundle.ProductName
$AppVersion = $tauriBundle.Version
Write-Host "Tauri bundle: productName='$ProductName' version='$AppVersion' (from tauri.conf.json)"

$BundleDir = Join-Path $TauriDir "target\release\bundle"
$NsisDir = Join-Path $BundleDir "nsis"
$PortableDir = Join-Path $BundleDir "portable"
$SidecarName = "manpower-api-x86_64-pc-windows-msvc.exe"
$SidecarPath = Join-Path $TauriDir "binaries\$SidecarName"
$ReleaseSidecarPath = Join-Path $TauriDir "target\release\manpower-api.exe"
$ReleaseAppPath = Join-Path $TauriDir "target\release\manpower-desktop.exe"
$NsisSetupFileName = "${ProductName}_${AppVersion}_x64-setup.exe"
$InstallerPath = Join-Path $NsisDir $NsisSetupFileName

# Rebuild PATH from persisted Machine/User environment scopes because shells
# launched by IDEs do not always inherit newly installed tools like Cargo/smctl.
function Restore-ToolPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $cargoPath = Join-Path $env:USERPROFILE ".cargo\bin"
    $env:Path = "$machinePath;$userPath;$cargoPath"

    # KeyLocker settings are only needed when this run is expected to sign files.
    if ($Mode -eq "Signed") {
        $env:SM_HOST = [Environment]::GetEnvironmentVariable("SM_HOST", "User")
        $env:SM_CLIENT_CERT_FILE = [Environment]::GetEnvironmentVariable("SM_CLIENT_CERT_FILE", "User")
    }
}

# Fail early with a clear message if any required build/signing tool is missing.
function Test-RequiredCommand([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found in PATH."
    }
}

# Print a visible stage marker so long-running build logs are easier to follow.
function Invoke-Step([string]$Name, [scriptblock]$ScriptBlock) {
    Write-Host ""
    Write-Host "==> $Name"
    & $ScriptBlock
}

# Write a checksum next to each distributable for release verification.
function Write-Checksum([string]$Path) {
    $hash = Get-FileHash -Algorithm SHA256 $Path
    $checksumPath = "$Path.sha256"
    "$($hash.Hash)  $([System.IO.Path]::GetFileName($Path))" | Set-Content -Path $checksumPath -Encoding ASCII
    Write-Host "SHA256 $([System.IO.Path]::GetFileName($Path)): $($hash.Hash)"
}

# Returns true only when Windows Authenticode sees a valid signature chain.
function Test-Signed([string]$Path) {
    $signature = Get-AuthenticodeSignature $Path
    return $signature.Status -eq "Valid"
}

# Guardrail: signed builds must contain signed binaries, unsigned builds must not.
# This prevents accidentally shipping a mixed release.
function Assert-SignatureState([string]$Path) {
    $signature = Get-AuthenticodeSignature $Path
    if ($Mode -eq "Signed") {
        if ($signature.Status -ne "Valid") {
            throw "Expected signed file but got '$($signature.Status)': $Path"
        }
    }
    else {
        if ($signature.Status -ne "NotSigned") {
            throw "Expected unsigned file but got '$($signature.Status)': $Path"
        }
    }
    Write-Host "$Mode signature state confirmed: $Path"
}

# Sign a single file through DigiCert KeyLocker and verify the result with signtool.
function Invoke-KeyLockerSign([string]$Path) {
    Test-RequiredCommand "smctl"
    Test-RequiredCommand "signtool"

    smctl sign `
        --fingerprint $Fingerprint `
        --input $Path `
        --tool=signtool `
        --digalg=SHA256 `
        --timestamp `
        --verbose

    if ($LASTEXITCODE -ne 0) {
        throw "smctl failed for $Path"
    }

    signtool verify /pa /v $Path
    if ($LASTEXITCODE -ne 0) {
        throw "signtool verification failed for $Path"
    }
}

# Prepare the NSIS toolchain cache expected by Tauri.
# Tauri downloads these tools automatically, but corporate networks may block
# GitHub downloads, so this function also supports a manually copied ZIP.
function Initialize-NsisTools {
    $toolsRoot = Join-Path $env:LOCALAPPDATA "tauri"
    $nsisCache = Join-Path $toolsRoot "NSIS"
    $makensis = Join-Path $nsisCache "makensis.exe"
    $plugin = Join-Path $nsisCache "Plugins\x86-unicode\additional\nsis_tauri_utils.dll"

    if (-not (Test-Path $makensis)) {
        # The official Tauri NSIS ZIP can be downloaded manually and dropped
        # into %TEMP% when automated download fails.
        $zipPath = Join-Path $env:TEMP "nsis-3.11.zip"
        if (-not (Test-Path $zipPath)) {
            throw "NSIS cache is missing. Download nsis-3.11.zip to $zipPath from https://github.com/tauri-apps/binary-releases/releases/download/nsis-3.11/nsis-3.11.zip"
        }

        # Verify the exact Tauri-supported NSIS package before extracting it.
        $zipHash = (Get-FileHash -Algorithm SHA1 $zipPath).Hash
        if ($zipHash -ne "EF7FF767E5CBD9EDD22ADD3A32C9B8F4500BB10D") {
            throw "Invalid nsis-3.11.zip hash. Expected EF7FF767E5CBD9EDD22ADD3A32C9B8F4500BB10D, got $zipHash"
        }

        $extractRoot = Join-Path $env:TEMP "tauri-nsis-extract"
        if (Test-Path $extractRoot) {
            Remove-Item -Recurse -Force $extractRoot
        }
        New-Item -ItemType Directory -Force $extractRoot | Out-Null
        Expand-Archive -Path $zipPath -DestinationPath $extractRoot -Force

        New-Item -ItemType Directory -Force $toolsRoot | Out-Null
        if (Test-Path $nsisCache) {
            Remove-Item -Recurse -Force $nsisCache
        }
        Move-Item -Force (Join-Path $extractRoot "nsis-3.11") $nsisCache
    }

    if (-not (Test-Path $plugin)) {
        # Tauri adds this NSIS plugin for sidecar/process handling in generated installers.
        New-Item -ItemType Directory -Force (Split-Path $plugin) | Out-Null
        curl.exe --ssl-no-revoke -L --retry 5 --retry-all-errors --retry-delay 5 `
            -o $plugin `
            "https://github.com/tauri-apps/nsis-tauri-utils/releases/download/nsis_tauri_utils-v0.5.3/nsis_tauri_utils.dll"
    }

    # Keep this hash check even when the plugin already exists in cache.
    $pluginHash = (Get-FileHash -Algorithm SHA1 $plugin).Hash
    if ($pluginHash -ne "75197FEE3C6A814FE035788D1C34EAD39349B860") {
        throw "Invalid nsis_tauri_utils.dll hash. Expected 75197FEE3C6A814FE035788D1C34EAD39349B860, got $pluginHash"
    }
}

# Build the local FastAPI backend as a Windows sidecar executable.
# The sidecar is what Tauri launches automatically when the desktop app starts.
function Build-Sidecar {
    if ($SkipSidecarBuild) {
        Write-Host "Skipping sidecar build."
        return
    }

    Push-Location $RootDir
    try {
        python -m pip install -r "requirements-desktop.txt"
        if ($LASTEXITCODE -ne 0) {
            throw "pip install failed"
        }

        # Collect the Python packages that PyInstaller otherwise commonly misses.
        python -m PyInstaller `
            --clean `
            --onefile `
            --name manpower-api `
            --collect-all pulp `
            --collect-all pandas `
            --collect-all openpyxl `
            "manpower_api/run.py"

        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller failed"
        }

        New-Item -ItemType Directory -Force (Split-Path $SidecarPath) | Out-Null
        Copy-Item -Force (Join-Path $RootDir "dist\manpower-api.exe") $SidecarPath
    }
    finally {
        Pop-Location
    }

    # Signed mode signs the sidecar before Tauri bundles it; unsigned mode asserts it stayed unsigned.
    if ($Mode -eq "Signed") {
        Invoke-KeyLockerSign $SidecarPath
    }
    else {
        Assert-SignatureState $SidecarPath
    }
}

# Build the React frontend and package the Tauri Windows app as an NSIS installer.
function Build-TauriNsis {
    Push-Location $DesktopDir
    try {
        npm install
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed"
        }

        Remove-Item -Force $ReleaseAppPath -ErrorAction SilentlyContinue
        Remove-Item -Force $InstallerPath -ErrorAction SilentlyContinue

        # --no-sign disables all Tauri signing points: app exe, NSIS plugins,
        # uninstaller, and final setup executable.
        $tauriArgs = @("build", "--bundles", "nsis", "--ci")
        if ($Mode -eq "Unsigned") {
            $tauriArgs += "--no-sign"
        }

        & ".\node_modules\.bin\tauri.cmd" @tauriArgs
        if ($LASTEXITCODE -ne 0) {
            throw "Tauri build failed"
        }
    }
    finally {
        Pop-Location
    }
}

# Create a ZIP distribution containing the app executable and sidecar.
# This is not an installer; users extract the folder and run the app directly.
function Build-PortableZip {
    $portableName = if ($Mode -eq "Signed") { "$ProductName signed" } else { "$ProductName unsigned" }
    $portableFolder = Join-Path $PortableDir $portableName
    $zipSuffix = if ($Mode -eq "Signed") { "signed" } else { "unsigned" }
    $zipPath = Join-Path $PortableDir "${ProductName}_${AppVersion}_x64-portable-$zipSuffix.zip"

    if (Test-Path $portableFolder) {
        Remove-Item -Recurse -Force $portableFolder
    }
    New-Item -ItemType Directory -Force $portableFolder | Out-Null

    # Ensure the portable ZIP uses the sidecar that matches the selected mode.
    Copy-Item -Force $SidecarPath $ReleaseSidecarPath

    Copy-Item -Force $ReleaseAppPath (Join-Path $portableFolder "$ProductName.exe")
    Copy-Item -Force $ReleaseSidecarPath (Join-Path $portableFolder "manpower-api.exe")

    if (Test-Path $zipPath) {
        Remove-Item -Force $zipPath
    }
    Compress-Archive -Path $portableFolder -DestinationPath $zipPath -Force
    Write-Checksum $zipPath
    return $zipPath
}

# Validate the host before doing expensive build work.
Restore-ToolPath
Test-RequiredCommand "python"
Test-RequiredCommand "node"
Test-RequiredCommand "npm"
Test-RequiredCommand "cargo"
Test-RequiredCommand "curl.exe"

if ($Mode -eq "Signed") {
    # Signed builds require both the KeyLocker CLI and the Windows SDK verification tool.
    Test-RequiredCommand "smctl"
    Test-RequiredCommand "signtool"
    if (-not $env:SM_HOST -or -not $env:SM_CLIENT_CERT_FILE) {
        throw "SM_HOST and SM_CLIENT_CERT_FILE must be set in the user environment for signed builds."
    }
}

Invoke-Step "Ensure NSIS tools" { Initialize-NsisTools }
Invoke-Step "Build $Mode sidecar" { Build-Sidecar }
Invoke-Step "Build $Mode NSIS installer" { Build-TauriNsis }

# Tauri signs the patched executable that is embedded into the NSIS installer,
# but the standalone target\release executable can remain unsigned afterwards.
# Sign it explicitly so the portable ZIP also contains a valid signed app exe.
if ($Mode -eq "Signed" -and -not (Test-Signed $ReleaseAppPath)) {
    Invoke-Step "Sign standalone app executable" { Invoke-KeyLockerSign $ReleaseAppPath }
}

# Keep the canonical Tauri output and also create an explicit signed/unsigned copy.
$modeSuffix = if ($Mode -eq "Signed") { "signed" } else { "unsigned" }
$modeInstaller = Join-Path $NsisDir "${ProductName}_${AppVersion}_x64-setup-$modeSuffix.exe"
Copy-Item -Force $InstallerPath $modeInstaller
Write-Checksum $modeInstaller

# Verify release artifacts after packaging so failures are caught before handoff.
Assert-SignatureState $modeInstaller
Assert-SignatureState $ReleaseAppPath
Assert-SignatureState $SidecarPath

Invoke-Step "Build $Mode portable ZIP" { Build-PortableZip | Out-Host }

Write-Host ""
Write-Host "Build complete."
Write-Host "NSIS: $modeInstaller"
Write-Host "Portable: $(Join-Path $PortableDir "${ProductName}_${AppVersion}_x64-portable-$modeSuffix.zip")"
