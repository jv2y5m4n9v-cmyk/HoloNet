$ErrorActionPreference = "Stop"
$Venv = Join-Path $PSScriptRoot "venv"
$Python = Join-Path $Venv "Scripts\python.exe"

if (-not (Test-Path $Python)) {
    $BasePython = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $BasePython) { throw "Python 3 is required to create the project venv." }
    & $BasePython.Source -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
    if ($LASTEXITCODE -ne 0) { throw "Python 3.12 or newer is required." }
    & $BasePython.Source -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create venv." }
}

& $Python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
if ($LASTEXITCODE -ne 0) { throw "The existing venv must use Python 3.12 or newer." }

& $Python (Join-Path $PSScriptRoot "runtime_setup.py")
if ($LASTEXITCODE -ne 0) { throw "Cross-platform runtime setup failed. See HoloNet setup output." }

$Pythonw = Join-Path $Venv "Scripts\pythonw.exe"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "HoloNet.lnk"
$Shell = New-Object -ComObject WScript.Shell
$OldShortcutPath = Join-Path $Desktop "Zigbee Desk.lnk"
if (Test-Path $OldShortcutPath) {
    $OldShortcut = $Shell.CreateShortcut($OldShortcutPath)
    if ($OldShortcut.TargetPath -eq $Pythonw -and $OldShortcut.Arguments -match "app\.py") {
        Remove-Item $OldShortcutPath -Force
    }
}
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Executable = Join-Path $PSScriptRoot "dist\HoloNet.exe"
if (Test-Path $Executable) {
    $Shortcut.TargetPath = $Executable
    $Shortcut.Arguments = ""
} else {
    $Shortcut.TargetPath = $Pythonw
    $Shortcut.Arguments = "`"$(Join-Path $PSScriptRoot 'app.py')`""
}
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.Description = "Manage your local Zigbee network"
$Shortcut.Save()
Write-Host "Setup complete. Desktop shortcut: $ShortcutPath" -ForegroundColor Green
