param(
    [Parameter(Mandatory = $true)]
    [string]$Name,

    [Parameter(Mandatory = $true)]
    [string]$Username,

    [Parameter(Mandatory = $true)]
    [string]$Password,

    [string]$BaseUrl = "http://localhost:8123",
    [string]$Language = "pt-BR"
)

$ErrorActionPreference = "Stop"

$clientId = $BaseUrl.TrimEnd("/")
$redirectUri = "$clientId/"

function Invoke-HaJsonPost {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri,

        [Parameter(Mandatory = $true)]
        [hashtable]$Body,

        [hashtable]$Headers
    )

    $params = @{
        Uri         = $Uri
        Method      = "Post"
        ContentType = "application/json"
        Body        = ($Body | ConvertTo-Json -Compress)
    }

    if ($Headers) {
        $params.Headers = $Headers
    }

    Invoke-RestMethod @params
}

function Invoke-HaFormPost {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Uri,

        [Parameter(Mandatory = $true)]
        [hashtable]$Body
    )

    Invoke-RestMethod `
        -Uri $Uri `
        -Method Post `
        -ContentType "application/x-www-form-urlencoded" `
        -Body $Body
}

$status = Invoke-RestMethod -Uri "$clientId/api/onboarding" -Method Get

if ($status.done -contains $null) {
    throw "Resposta inesperada do endpoint de onboarding."
}

$userStep = $status | Where-Object { $_.step -eq "user" }
if ($null -eq $userStep) {
    throw "Nao consegui localizar a etapa de onboarding 'user'."
}

if ($userStep.done) {
    Write-Host "O onboarding ja foi concluido nesta instancia."
    exit 0
}

$userResponse = Invoke-HaJsonPost `
    -Uri "$clientId/api/onboarding/users" `
    -Body @{
        name      = $Name
        username  = $Username
        password  = $Password
        client_id = $clientId
        language  = $Language
    }

$tokenResponse = Invoke-HaFormPost `
    -Uri "$clientId/auth/token" `
    -Body @{
        grant_type = "authorization_code"
        code       = $userResponse.auth_code
        client_id  = $clientId
    }

$headers = @{
    Authorization = "Bearer $($tokenResponse.access_token)"
}

Invoke-HaJsonPost `
    -Uri "$clientId/api/onboarding/core_config" `
    -Body @{} `
    -Headers $headers | Out-Null

Invoke-HaJsonPost `
    -Uri "$clientId/api/onboarding/analytics" `
    -Body @{} `
    -Headers $headers | Out-Null

Invoke-HaJsonPost `
    -Uri "$clientId/api/onboarding/integration" `
    -Body @{
        client_id    = $clientId
        redirect_uri = $redirectUri
    } `
    -Headers $headers | Out-Null

Write-Host "Onboarding concluido com sucesso em $clientId"
