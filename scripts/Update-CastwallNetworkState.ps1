param(
    [string[]]$TargetHosts,
    [string]$OutputPath,
    [string]$ComposePath,
    [string]$EnvPath
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputPath) {
    $OutputPath = Join-Path $projectRoot 'config\www\castwall\runtime\network.json'
}
if (-not $ComposePath) {
    $ComposePath = Join-Path $projectRoot 'docker-compose.yml'
}
if (-not $EnvPath) {
    $EnvPath = Join-Path $projectRoot '.env.local'
}

function Get-EnvFileValues {
    param([string]$Path)

    $values = @{}
    if (-not (Test-Path $Path)) {
        return $values
    }

    foreach ($rawLine in Get-Content $Path) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith('#')) {
            continue
        }

        $separatorIndex = $line.IndexOf('=')
        if ($separatorIndex -lt 1) {
            continue
        }

        $key = $line.Substring(0, $separatorIndex).Trim()
        $value = $line.Substring($separatorIndex + 1).Trim()
        if ($value.Length -ge 2) {
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        $values[$key] = $value
    }

    return $values
}

function Get-ComposeTargetHosts {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return @()
    }

    $content = Get-Content $Path -Raw
    $targetKeys = @(
        'CHROMECAST_KNOWN_HOSTS',
        'CHROMECAST_IP',
        'CAMERA_RUA_RTSP',
        'CAMERA_VARANDA_RTSP'
    )

    $ips = New-Object System.Collections.Generic.List[string]
    foreach ($key in $targetKeys) {
        $pattern = '(?m)^\s*' + [regex]::Escape($key) + ':\s*(.+)$'
        $match = [regex]::Match($content, $pattern)
        if (-not $match.Success) {
            continue
        }

        foreach ($ipMatch in [regex]::Matches($match.Groups[1].Value, '(?:\d{1,3}\.){3}\d{1,3}')) {
            $ip = $ipMatch.Value
            if (-not $ips.Contains($ip)) {
                [void]$ips.Add($ip)
            }
        }
    }

    return $ips.ToArray()
}

function Get-ConfiguredTargetHosts {
    param(
        [string]$ComposePath,
        [string]$EnvPath
    )

    $targetKeys = @(
        'CHROMECAST_KNOWN_HOSTS',
        'CHROMECAST_IP',
        'CAMERA_RUA_RTSP',
        'CAMERA_VARANDA_RTSP'
    )

    $ips = New-Object System.Collections.Generic.List[string]
    $envValues = Get-EnvFileValues -Path $EnvPath
    foreach ($key in $targetKeys) {
        if (-not $envValues.ContainsKey($key)) {
            continue
        }

        foreach ($ipMatch in [regex]::Matches([string]$envValues[$key], '(?:\d{1,3}\.){3}\d{1,3}')) {
            $ip = $ipMatch.Value
            if (-not $ips.Contains($ip)) {
                [void]$ips.Add($ip)
            }
        }
    }

    foreach ($ip in (Get-ComposeTargetHosts -Path $ComposePath)) {
        if (-not $ips.Contains($ip)) {
            [void]$ips.Add($ip)
        }
    }

    return $ips.ToArray()
}

function Get-IPv4Prefix {
    param([string]$Address)

    if ([string]::IsNullOrWhiteSpace($Address)) {
        return $null
    }

    $parts = $Address.Split('.')
    if ($parts.Count -lt 3) {
        return $null
    }

    return ($parts[0..2] -join '.')
}

function Test-SameSubnet24 {
    param(
        [string]$A,
        [string]$B
    )

    $prefixA = Get-IPv4Prefix $A
    $prefixB = Get-IPv4Prefix $B
    return $prefixA -and $prefixB -and ($prefixA -eq $prefixB)
}

function Get-NetworkCandidates {
    $candidates = @()
    $interfaces = [System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces()

    foreach ($nic in $interfaces) {
        if ($nic.OperationalStatus -ne [System.Net.NetworkInformation.OperationalStatus]::Up) {
            continue
        }

        if ($nic.NetworkInterfaceType -in @(
            [System.Net.NetworkInformation.NetworkInterfaceType]::Loopback,
            [System.Net.NetworkInformation.NetworkInterfaceType]::Tunnel
        )) {
            continue
        }

        $name = $nic.Name
        $description = $nic.Description
        if ($name -match 'vEthernet|Hyper-V|Bluetooth|VirtualBox|VMware|WSL' -or $description -match 'Hyper-V|VirtualBox|VMware|WSL|Bluetooth') {
            continue
        }

        $props = $nic.GetIPProperties()
        $ipv4Addresses = @(
            $props.UnicastAddresses |
                Where-Object {
                    $_.Address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and
                    $_.Address.ToString() -notlike '169.254.*'
                } |
                ForEach-Object { $_.Address.ToString() }
        )

        if (-not $ipv4Addresses) {
            continue
        }

        $gateways = @(
            $props.GatewayAddresses |
                Where-Object { $_.Address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork } |
                ForEach-Object { $_.Address.ToString() }
        )

        $dnsServers = @(
            $props.DnsAddresses |
                Where-Object { $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork } |
                ForEach-Object { $_.ToString() }
        )

        $isWifi = $nic.NetworkInterfaceType -eq [System.Net.NetworkInformation.NetworkInterfaceType]::Wireless80211 -or $name -match 'Wi-Fi|Wireless'

        $candidates += [pscustomobject]@{
            interface_alias       = $name
            interface_description = $description
            interface_type        = $nic.NetworkInterfaceType.ToString()
            status                = $nic.OperationalStatus.ToString()
            is_wifi               = [bool]$isWifi
            ipv4_addresses        = $ipv4Addresses
            gateways              = $gateways
            dns_suffix            = $props.DnsSuffix
            dns_servers           = $dnsServers
            speed_mbps            = [math]::Round($nic.Speed / 1MB * 8, 0)
        }
    }

    return $candidates
}

if (-not $TargetHosts -or $TargetHosts.Count -eq 0) {
    $TargetHosts = Get-ConfiguredTargetHosts -ComposePath $ComposePath -EnvPath $EnvPath
}

$TargetHosts = @($TargetHosts | Where-Object { $_ } | Select-Object -Unique)
$candidates = Get-NetworkCandidates
if (-not $candidates) {
    throw 'Nao encontrei interfaces IPv4 ativas elegiveis para o castwall.'
}

$scored = foreach ($candidate in $candidates) {
    $address = $candidate.ipv4_addresses | Select-Object -First 1
    $reasons = New-Object System.Collections.Generic.List[string]
    $score = 0

    if ($candidate.is_wifi) {
        $score += 200
        [void]$reasons.Add('wifi')
    }

    if ($candidate.gateways.Count -gt 0) {
        $score += 20
        [void]$reasons.Add('gateway')
    }

    if ($address) {
        $sameSubnetTargets = @($TargetHosts | Where-Object { Test-SameSubnet24 -A $address -B $_ })
        if ($sameSubnetTargets.Count -gt 0) {
            $score += 500
            [void]$reasons.Add('same-subnet-as-target')
        }
    }

    if ($candidate.interface_alias -match '^Wi-Fi$') {
        $score += 25
        [void]$reasons.Add('wifi-alias')
    }

    [pscustomobject]@{
        interface_alias       = $candidate.interface_alias
        interface_description = $candidate.interface_description
        interface_type        = $candidate.interface_type
        status                = $candidate.status
        is_wifi               = $candidate.is_wifi
        selected_ip           = $address
        gateways              = $candidate.gateways
        dns_suffix            = $candidate.dns_suffix
        dns_servers           = $candidate.dns_servers
        speed_mbps            = $candidate.speed_mbps
        score                 = $score
        reasons               = @($reasons)
    }
}

$selected = $scored |
    Sort-Object @{ Expression = 'score'; Descending = $true }, @{ Expression = 'is_wifi'; Descending = $true }, @{ Expression = 'speed_mbps'; Descending = $true } |
    Select-Object -First 1

if (-not $selected -or -not $selected.selected_ip) {
    throw 'Nao consegui selecionar um IPv4 valido para o castwall.'
}

$output = [pscustomobject]@{
    selected_ip              = $selected.selected_ip
    selected_interface_alias = $selected.interface_alias
    selected_interface_type  = $selected.interface_type
    selected_reason          = ($selected.reasons -join ',')
    updated_at               = (Get-Date).ToString('o')
    target_hosts             = @($TargetHosts)
    candidates               = @($scored)
}

$outputDir = Split-Path -Parent $OutputPath
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

$output | ConvertTo-Json -Depth 6 | Set-Content -Path $OutputPath -Encoding UTF8
Write-Host "Castwall network runtime atualizado: $($selected.selected_ip) via $($selected.interface_alias) [$($selected.reasons -join ', ')]"
Write-Host "Arquivo: $OutputPath"
