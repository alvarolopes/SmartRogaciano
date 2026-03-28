$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$envLocalPath = Join-Path $projectRoot '.env.local'
if (-not (Test-Path $envLocalPath)) {
    throw ".env.local nao encontrado. Copie .env.example para .env.local antes de subir os containers."
}

$dockerReady = $false

for ($attempt = 1; $attempt -le 24; $attempt++) {
    docker version *> $null
    if ($LASTEXITCODE -eq 0) {
        $dockerReady = $true
        break
    }

    Start-Sleep -Seconds 5
}

if (-not $dockerReady) {
    throw "Docker Desktop nao ficou pronto a tempo para iniciar o Home Assistant."
}

$networkRuntimeScript = Join-Path $PSScriptRoot 'Update-CastwallNetworkState.ps1'
if (Test-Path $networkRuntimeScript) {
    & $networkRuntimeScript
}


docker compose up -d


