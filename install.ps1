param(
    [string]$Ref = "main"
)

$ErrorActionPreference = "Stop"

$SourceUrl = if ($env:AGY_PLUGIN_MANAGER_SOURCE_URL) {
    $env:AGY_PLUGIN_MANAGER_SOURCE_URL
} else {
    "https://github.com/Leopoldius/agy-plugin-manager/archive/refs/heads/$Ref.zip"
}

$InstallRoot = Join-Path $env:LOCALAPPDATA "agy-plugin-manager"
$VenvDir = Join-Path $InstallRoot "venv"
$BinDir = Join-Path $InstallRoot "bin"
$Launcher = Join-Path $BinDir "agy-plugins.cmd"

$PythonExe = $null
$PythonPrefix = @()

$Py = Get-Command py.exe -ErrorAction SilentlyContinue
if ($Py) {
    $PythonExe = $Py.Source
    $PythonPrefix = @("-3")
} else {
    $Python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($Python) {
        $PythonExe = $Python.Source
    }
}

if (-not $PythonExe) {
    throw "Python 3.10 or newer is required."
}

& $PythonExe @PythonPrefix -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.10 or newer is required."
}

New-Item -ItemType Directory -Force -Path $InstallRoot, $BinDir | Out-Null

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    & $PythonExe @PythonPrefix -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create Python virtual environment."
    }
}

& $VenvPython -m pip install --disable-pip-version-check --upgrade --force-reinstall $SourceUrl
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install agy-plugin-manager."
}

$EntryPoint = Join-Path $VenvDir "Scripts\agy-plugins.exe"
$Cmd = "@echo off`r`n`"$EntryPoint`" %*`r`n"
Set-Content -Path $Launcher -Value $Cmd -Encoding ASCII

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$Entries = @()
if ($UserPath) {
    $Entries = @($UserPath -split ";" | Where-Object { $_ })
}

$AlreadyPresent = $false
foreach ($Entry in $Entries) {
    if ($Entry.TrimEnd("\") -ieq $BinDir.TrimEnd("\")) {
        $AlreadyPresent = $true
        break
    }
}

if (-not $AlreadyPresent) {
    $NewUserPath = if ($UserPath) {
        "$UserPath;$BinDir"
    } else {
        $BinDir
    }
    [Environment]::SetEnvironmentVariable("Path", $NewUserPath, "User")
}

$CurrentEntries = @($env:Path -split ";")
if (-not ($CurrentEntries | Where-Object { $_.TrimEnd("\") -ieq $BinDir.TrimEnd("\") })) {
    $env:Path = "$BinDir;$env:Path"
}

Write-Host ""
Write-Host "Installed agy-plugin-manager."
Write-Host "Launcher: $Launcher"
Write-Host ""
& $EntryPoint self-info
