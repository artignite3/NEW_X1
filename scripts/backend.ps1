# Turn the NEW_X1 analysis backend on or off, or check it.
#   .\scripts\backend.ps1 start     start now (it also starts at every sign-in)
#   .\scripts\backend.ps1 stop      stop the API and tunnel; the website shows "offline"
#   .\scripts\backend.ps1 status    task state, local health and the published address
#   .\scripts\backend.ps1 restart
# Requires the sign-in task from scripts\install-autostart.ps1.
param([Parameter(Position = 0)][ValidateSet("start", "stop", "status", "restart")][string]$Action = "status")

$ErrorActionPreference = "Stop"
$TaskName = "NEW_X1 backend"
$Repo = Split-Path -Parent $PSScriptRoot
$Log = Join-Path $Repo "outputs\launcher.log"

function Find-Python {
    $candidates = @((Join-Path $Repo "env\Scripts\python.exe"),
                    (Join-Path (Split-Path -Parent $Repo) "NEW_X1\env\Scripts\python.exe"))
    $found = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $found) { throw "No Python environment found next to $Repo" }
    return $found
}

function Get-BackendProcesses {
    # This checkout's launcher, the API on port 8000 and the tunnels it opened.
    $launcher = [regex]::Escape((Join-Path $Repo "run_all.py"))
    Get-CimInstance Win32_Process | Where-Object {
        $_.CommandLine -and (
            $_.CommandLine -match $launcher -or
            $_.CommandLine -match 'model\.model_fastapi:app --host 127\.0\.0\.1 --port 8000' -or
            $_.CommandLine -match 'cloudflared.*--url http://127\.0\.0\.1:8000' -or
            $_.CommandLine -match 'nokey@localhost\.run')
    }
}

function Stop-Backend {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $TaskName   # first, so the task does not restart it
    }
    $procs = @(Get-BackendProcesses)
    foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    Write-Host "Stopped $($procs.Count) backend process(es)."
    & (Find-Python) (Join-Path $Repo "run_all.py") --unpublish
}

function Show-Status {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Write-Host ("Sign-in task : " + $(if ($task) { $task.State } else { "not installed" }))
    $running = @(Get-BackendProcesses).Count
    Write-Host ("Processes    : " + $running)
    if (-not $running) { Write-Host "Status       : stopped; the website shows analysis as offline"; return }
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 5
        $ready = ($health.models.PSObject.Properties | Where-Object { $_.Value }).Name -join ", "
        Write-Host "Local API    : $($health.status), models ready: $ready"
    } catch { Write-Host "Local API    : not responding" }
    if (Test-Path $Log) {
        $address = Select-String -Path $Log -Pattern "PUBLIC API: (\S+)" | Select-Object -Last 1
        if ($address) { Write-Host "Last address : $($address.Matches[0].Groups[1].Value)" }
        $published = Select-String -Path $Log -Pattern "Published to the website" -Quiet
        Write-Host ("Published    : " + $(if ($published) { "yes, the website connects automatically" } else { "not yet (see $Log)" }))
    }
}

switch ($Action) {
    "start" {
        if (-not (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue)) {
            throw "Install the sign-in task first: powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1"
        }
        if (@(Get-BackendProcesses).Count) { Write-Host "Already running."; Show-Status; return }
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "Starting. Models load in about a minute; the tunnel needs up to two more."
        Write-Host "Check with: .\scripts\backend.ps1 status"
    }
    "stop" { Stop-Backend }
    "restart" { Stop-Backend; Start-Sleep -Seconds 3; Start-ScheduledTask -TaskName $TaskName; Write-Host "Restarting." }
    "status" { Show-Status }
}
