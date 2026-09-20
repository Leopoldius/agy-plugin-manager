$ErrorActionPreference = "Stop"

$InstallRoot = Join-Path $env:LOCALAPPDATA "agy-plugin-manager"
$BinDir = Join-Path $InstallRoot "bin"

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath) {
    $Filtered = @(
        $UserPath -split ";" |
        Where-Object {
            $_ -and ($_.TrimEnd([char]92) -ine $BinDir.TrimEnd([char]92))
        }
    )
    [Environment]::SetEnvironmentVariable(
        "Path",
        ($Filtered -join ";"),
        "User"
    )
}

if (Test-Path $InstallRoot) {
    Remove-Item -Recurse -Force $InstallRoot
}

Write-Host "Removed agy-plugin-manager standalone installation."
