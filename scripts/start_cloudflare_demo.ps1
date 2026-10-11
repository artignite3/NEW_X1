param(
    [Parameter(Mandatory = $true)][string]$ArtifactsRoot,
    [Parameter(Mandatory = $true)][string]$SiteOrigin,
    [ValidateSet('Cloudflare', 'LocalhostRun')][string]$TunnelProvider = 'Cloudflare',
    [switch]$LocalOnly,
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$artifacts = (Resolve-Path -LiteralPath $ArtifactsRoot).Path
$python = Join-Path $artifacts 'env\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw "Python environment missing: $python" }
if (-not (Test-Path -LiteralPath (Join-Path $artifacts 'model_artifacts'))) { throw 'Model artifacts are missing.' }
if (-not (Test-Path -LiteralPath (Join-Path $artifacts 'data\processed'))) { throw 'Processed data is missing.' }
if (-not $LocalOnly -and $TunnelProvider -eq 'Cloudflare') {
    $cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
    $cloudflaredPath = if ($cloudflared) { $cloudflared.Source } else { 'C:\Program Files (x86)\cloudflared\cloudflared.exe' }
    if (-not (Test-Path -LiteralPath $cloudflaredPath)) { throw 'Install cloudflared before starting this demo.' }
} elseif (-not $LocalOnly -and -not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    throw 'OpenSSH is required for the localhost.run tunnel.'
}
$siteUri = [Uri]$SiteOrigin
if ($siteUri.Scheme -ne 'https' -or $siteUri.AbsoluteUri.TrimEnd('/') -ne $siteUri.GetLeftPart([System.UriPartial]::Authority)) {
    throw 'SiteOrigin must be an HTTPS origin with no path, query or fragment.'
}

$env:APP_ENV = 'staging'
$env:CORS_ORIGINS = "$($siteUri.GetLeftPart([System.UriPartial]::Authority)),http://localhost:3000,http://127.0.0.1:3000"
$env:NEW_X1_DATA_ROOT = Join-Path $artifacts 'data'
$env:NEW_X1_MODEL_ROOT = Join-Path $artifacts 'model_artifacts'
$envFile = Join-Path $artifacts '.env'
$arguments = '-m uvicorn model.model_fastapi:app --host 127.0.0.1 --port ' + $Port
if (Test-Path -LiteralPath $envFile) { $arguments += ' --env-file "' + $envFile + '"' }
if ($LocalOnly) {
    Write-Host "Starting local API on http://127.0.0.1:$Port (Ctrl+C to stop)."
    if (Test-Path -LiteralPath $envFile) {
        & $python -m uvicorn model.model_fastapi:app --host 127.0.0.1 --port $Port --env-file $envFile
    } else {
        & $python -m uvicorn model.model_fastapi:app --host 127.0.0.1 --port $Port
    }
    exit $LASTEXITCODE
}
$logDir = Join-Path $projectRoot 'outputs'
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$api = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $projectRoot `
    -RedirectStandardOutput (Join-Path $logDir 'cloudflare_api.out.log') `
    -RedirectStandardError (Join-Path $logDir 'cloudflare_api.err.log') `
    -WindowStyle Hidden -PassThru

try {
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        if ($api.HasExited) { throw 'API exited during startup. Check outputs/cloudflare_api.err.log.' }
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/live" -TimeoutSec 2
            if ($response.StatusCode -eq 200) { $ready = $true; break }
        } catch { Start-Sleep -Seconds 1 }
    }
    if (-not $ready) { throw 'API did not start within 30 seconds. Check outputs/cloudflare_api.err.log.' }
    Write-Host "API ready on http://127.0.0.1:$Port"
    Write-Host 'The tunnel will print a temporary HTTPS URL. Paste it into the website Settings page.'
    if ($TunnelProvider -eq 'Cloudflare') {
        & $cloudflaredPath tunnel --url "http://127.0.0.1:$Port"
    } else {
        & ssh -T -o StrictHostKeyChecking=accept-new -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 `
            -R "80:127.0.0.1:$Port" nokey@localhost.run
    }
    if ($LASTEXITCODE -ne 0) { throw "$TunnelProvider tunnel failed with exit code $LASTEXITCODE." }
} finally {
    if (-not $api.HasExited) { Stop-Process -Id $api.Id -ErrorAction SilentlyContinue }
}
