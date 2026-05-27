param(
    [Parameter(Mandatory = $true)]
    [string]$Board,

    [string]$AppName = "SmartStretchCoach",

    [switch]$CleanCache
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $repoRoot "app_lab\SmartStretchCoach"
$remoteAppDir = "/home/arduino/ArduinoApps/$AppName"
$remote = "arduino@$Board"

if (-not (Test-Path -LiteralPath $source)) {
    throw "App Lab source folder not found: $source"
}

Write-Host "Ensuring App Lab app exists on $remote..."
ssh $remote "if [ ! -d '$remoteAppDir' ]; then arduino-app-cli app new '$AppName'; fi; mkdir -p '$remoteAppDir'"

Write-Host "Copying App Lab files to ${remote}:$remoteAppDir ..."
scp -r "$source/." "${remote}:$remoteAppDir/"

if ($CleanCache) {
    Write-Host "Removing generated App Lab Python cache so dependencies reinstall cleanly..."
    ssh $remote "rm -rf '$remoteAppDir/.cache'"
}

Write-Host "Done."
Write-Host "Start it with:"
Write-Host "  ssh $remote"
Write-Host "  arduino-app-cli app start `"$remoteAppDir`""
Write-Host "  arduino-app-cli app logs `"$remoteAppDir`" --all"
