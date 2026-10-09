$ErrorActionPreference = "Stop"
$Inf = Join-Path $PSScriptRoot "downloads\cp210x-driver\silabser.inf"
if (-not (Test-Path $Inf)) {
    throw "CP210x driver INF not found at $Inf. Run setup and download the signed Microsoft Catalog package first."
}

$PnPUtil = Join-Path $env:WINDIR "System32\pnputil.exe"
$Identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$Principal = [Security.Principal.WindowsPrincipal]::new($Identity)
$IsAdministrator = $Principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($IsAdministrator) {
    & $PnPUtil /add-driver $Inf /install
    if ($LASTEXITCODE -ne 0) { throw "Windows driver installation failed with exit code $LASTEXITCODE." }
} else {
    $Arguments = "/add-driver `"$Inf`" /install"
    Write-Host "Requesting administrator approval to install the signed Silicon Labs CP210x driver..."
    $Installer = Start-Process -FilePath $PnPUtil -ArgumentList $Arguments -Verb RunAs -Wait -PassThru
    if ($Installer.ExitCode -ne 0) {
        throw "Windows driver installation failed with exit code $($Installer.ExitCode)."
    }
}

Write-Host "Driver installed. Reconnect the SONOFF dongle and refresh ports in HoloNet." -ForegroundColor Green
Read-Host "Press Enter to close"
