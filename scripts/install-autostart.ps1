# Starts the NEW_X1 backend (API, models and tunnel) in the background every
# time you sign in to Windows. Output goes to outputs\launcher.log.
#   Install:   powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
#   Remove:    powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1 -Remove
#   Start now: Start-ScheduledTask -TaskName "NEW_X1 backend"
param([switch]$Remove)

$ErrorActionPreference = "Stop"
$TaskName = "NEW_X1 backend"

if ($Remove) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed '$TaskName'."
    } else {
        Write-Host "'$TaskName' is not installed."
    }
    return
}

$Repo = Split-Path -Parent $PSScriptRoot
$Candidates = @(
    (Join-Path (Split-Path -Parent $Repo) "NEW_X1\env\Scripts\python.exe"),
    (Join-Path $Repo "env\Scripts\python.exe")
)
$Python = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Python) { throw "No Python environment found. Expected one of: $($Candidates -join ', ')" }

$Outputs = Join-Path $Repo "outputs"
New-Item -ItemType Directory -Force -Path $Outputs | Out-Null
$Log = Join-Path $Outputs "launcher.log"
$Launcher = Join-Path $Repo "run_all.py"

$Command = "& '$Python' '$Launcher' *>> '$Log'"
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -WorkingDirectory $Repo `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command `"$Command`""
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
    -Principal $Principal -Description "Runs the NEW_X1 inference API and public tunnel at sign-in." -Force | Out-Null

Write-Host "Installed '$TaskName'. It starts at every sign-in."
Write-Host "Start it now:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Watch the log: Get-Content '$Log' -Wait -Tail 20"
