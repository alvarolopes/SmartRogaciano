$ErrorActionPreference = "Stop"

param(
    [string]$TaskName = "HomeAssistant Docker"
)

$startScript = Join-Path $PSScriptRoot "Start-HomeAssistant.ps1"
$currentUser = "{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME

$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Sobe o Docker Compose do Home Assistant no logon do Windows." `
    -Force
