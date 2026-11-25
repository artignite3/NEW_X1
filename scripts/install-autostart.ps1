# Starts the NEW_X1 backend (API, models and tunnel) in the background every
# time you sign in to Windows. Status and the tunnel address go to
# outputs\launcher.log, server request logs to outputs\launcher.err.log
# (both start fresh at each sign-in).
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
$ErrLog = Join-Path $Outputs "launcher.err.log"
$Launcher = Join-Path $Repo "run_all.py"

# Start-Process writes the launcher's output byte for byte (plain UTF-8; PowerShell
# 5.1 redirection would produce UTF-16 and wrap every server log line as an error),
# and the exit code is passed on so the task's restart-on-failure applies.
$Command = "`$p = Start-Process -FilePath '$Python' -ArgumentList '-X utf8 -u `"$Launcher`"' " +
    "-WorkingDirectory '$Repo' -WindowStyle Hidden -RedirectStandardOutput '$Log' " +
    "-RedirectStandardError '$ErrLog' -PassThru -Wait; exit `$p.ExitCode"
$Encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($Command))
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -WorkingDirectory $Repo `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -EncodedCommand $Encoded"
$Trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 2) -MultipleInstances IgnoreNew
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings `
    -Principal $Principal -Description "Runs the NEW_X1 inference API and public tunnel at sign-in." -Force | Out-Null

Write-Host "Installed '$TaskName'. It starts at every sign-in."
Write-Host "Start it now:  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Status and tunnel address: Get-Content '$Log' -Wait -Tail 20"
Write-Host "Server request log:       Get-Content '$ErrLog' -Wait -Tail 20"
