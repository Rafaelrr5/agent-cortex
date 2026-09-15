# latency_audit.ps1 - read-only snapshot of the Windows latency chain.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File latency_audit.ps1
#
# Reads only. Changes nothing. Runs fine as a standard (non-admin) user;
# reading HKLM does not require elevation, only writing does.
#
# Assembled from probes verified individually on Windows 11 build 26200.
# Read the output and judge it - do not treat any single line as a verdict.

$ErrorActionPreference = 'SilentlyContinue'

function Section($t) { Write-Output ''; Write-Output "=== $t ===" }

Section 'ADMIN'
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()`
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Output "IsAdmin: $isAdmin"
if (-not $isAdmin) {
    Write-Output '  -> HKLM writes will FAIL (and reg.exe still exits 0). VBS/MMCSS/HAGS are off-limits.'
    Write-Output '  -> powercfg on your own schemes and all HKCU tweaks still work.'
}

Section 'MACHINE'
$cs = Get-CimInstance Win32_ComputerSystem
Write-Output "$($cs.Manufacturer) $($cs.Model)"
Get-CimInstance Win32_Processor | ForEach-Object {
    Write-Output "CPU: $($_.Name)"
    Write-Output "     $($_.NumberOfCores) cores / $($_.NumberOfLogicalProcessors) threads, base $($_.MaxClockSpeed) MHz"
}
Write-Output "RAM: $([math]::Round($cs.TotalPhysicalMemory/1GB,1)) GB"
Get-CimInstance Win32_PhysicalMemory | ForEach-Object {
    Write-Output "     DIMM $($_.Capacity/1GB) GB @ $($_.ConfiguredClockSpeed) MHz"
}
$os = Get-CimInstance Win32_OperatingSystem
Write-Output "OS:  $($os.Caption) build $($os.BuildNumber)"
$batt = @(Get-CimInstance Win32_Battery).Count
Write-Output "Battery present: $($batt -gt 0)   (if true: thermals and DC/AC split matter)"

Section 'DISPLAY / GPU  (link 2 + 4)'
Get-CimInstance Win32_VideoController | ForEach-Object {
    Write-Output "GPU: $($_.Name)  | driver $($_.DriverVersion)  | $($_.DriverDate)"
    if ($_.CurrentRefreshRate) {
        Write-Output "     ACTIVE PANEL: $($_.CurrentHorizontalResolution)x$($_.CurrentVerticalResolution) @ $($_.CurrentRefreshRate) Hz (max $($_.MaxRefreshRate))"
        Write-Output "     >> compare this Hz against the game's frame cap <<"
    }
}
if ((Get-CimInstance Win32_VideoController | Measure-Object).Count -gt 1) {
    Write-Output 'NOTE: hybrid/Optimus - the panel is usually driven by the iGPU.'
}

Section 'PER-APP GPU PREFERENCE (HKCU)'
$gk = 'HKCU:\SOFTWARE\Microsoft\DirectX\UserGpuPreferences'
if (Test-Path $gk) {
    $p = Get-ItemProperty $gk
    $p.PSObject.Properties |
        Where-Object { $_.Name -notlike 'PS*' } |
        ForEach-Object { Write-Output "  $($_.Name) => $($_.Value)" }
    Write-Output '  (GpuPreference=2 is high performance / dGPU)'
} else {
    Write-Output '  none set'
}

Section 'POWER PLAN + CORE PARKING  (link 7)'
$sk = 'HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes'
$active = (Get-ItemProperty $sk).ActivePowerScheme
Write-Output "Active scheme GUID: $active"
& powercfg /getactivescheme 2>&1 | ForEach-Object { Write-Output "  $_" }

$sub = '54533251-82be-4824-96c1-47b60b740d00'   # SUB_PROCESSOR
$settings = [ordered]@{
    'CPMINCORES      (class0/P, 100=parking OFF)' = '0cc5b647-c1df-4637-891a-dec35c318583'
    'CPMINCORES      (class1/E, 100=parking OFF)' = '0cc5b647-c1df-4637-891a-dec35c318584'
    'CPMAXCORES      (class0)'                    = 'ea062031-0e34-4ff1-9b6d-eb1059334028'
    'PROCTHROTTLEMIN (freq floor %)'              = '893dee8e-2bef-41e0-89c6-b55d0929964c'
    'PROCTHROTTLEMAX (freq ceiling %)'            = 'bc5038f7-23e0-4960-96da-33abaf5935ec'
    'PERFBOOSTMODE   (2=aggressive)'              = 'be337238-0d82-4146-a960-4f3749d470c7'
}
Write-Output ''
Write-Output ('{0,-46} {1,>6} {2,>6}' -f 'setting', 'AC', 'DC')
foreach ($k in $settings.Keys) {
    $path = Join-Path $sk "$active\$sub\$($settings[$k])"
    if (Test-Path $path) {
        $v = Get-ItemProperty $path
        Write-Output ('{0,-46} {1,>6} {2,>6}' -f $k, $v.ACSettingIndex, $v.DCSettingIndex)
    } else {
        Write-Output ('{0,-46} {1,>6} {2,>6}' -f $k, '(unset)', '(unset)')
    }
}
Write-Output '(unset) = never customised on this scheme; powercfg /q SCHEME_CURRENT SUB_PROCESSOR is authoritative.'

Section 'VBS / HVCI  (link 6 - admin to change)'
$dg = Get-CimInstance -Namespace root\Microsoft\Windows\DeviceGuard -ClassName Win32_DeviceGuard
if ($dg) {
    Write-Output "VirtualizationBasedSecurityStatus: $($dg.VirtualizationBasedSecurityStatus)  (2 = RUNNING)"
    Write-Output "SecurityServicesRunning:           $($dg.SecurityServicesRunning -join ',')  (2 = HVCI/memory integrity)"
    if ($dg.VirtualizationBasedSecurityStatus -eq 2) {
        Write-Output '  -> costs roughly 5-15% CPU in games. Disabling needs admin AND lowers security.'
        Write-Output '  -> present as the user''s decision, with the tradeoff stated.'
    }
} else {
    Write-Output 'DeviceGuard class unavailable.'
}
Write-Output "HypervisorPresent: $($cs.HypervisorPresent)"

Section 'GAME CAPTURE (HKCU)'
foreach ($pair in @(
    @('HKCU:\System\GameConfigStore', 'GameDVR_Enabled'),
    @('HKCU:\Software\Microsoft\Windows\CurrentVersion\GameDVR', 'AppCaptureEnabled')
)) {
    $val = (Get-ItemProperty $pair[0]).$($pair[1])
    Write-Output "  $($pair[1]) = $val   (0 = off, good)"
}

Section 'NETWORK  (link 8)'
Get-NetAdapter | Sort-Object Status | ForEach-Object {
    Write-Output "  [$($_.Status)] $($_.Name) - $($_.InterfaceDescription) - $($_.LinkSpeed)"
}
if (Get-NetAdapter | Where-Object { $_.Status -eq 'Disconnected' -and $_.InterfaceDescription -match 'Ethernet|GbE' }) {
    Write-Output '  >> An Ethernet port exists but is UNPLUGGED. For online games, a cable beats every tweak here. <<'
}
Write-Output ''
& netsh wlan show interfaces 2>&1 |
    Select-String -Pattern 'SSID|Channel|Canal|Signal|Sinal|Rssi|Banda|Band|Receive|Transmit|Recep|Transmis' |
    ForEach-Object { Write-Output "  $($_.Line.Trim())" }

# DFS warning - 5 GHz channels 52-144 are radar-shared and can stall for up to 60s
$chLine = (& netsh wlan show interfaces 2>&1 | Select-String -Pattern 'Channel|Canal' | Select-Object -First 1)
if ($chLine -and $chLine.Line -match '(\d+)\s*$') {
    $ch = [int]$Matches[1]
    if ($ch -ge 52 -and $ch -le 144) {
        Write-Output ''
        Write-Output "  >> Wi-Fi channel $ch is a DFS channel (radar-shared)."
        Write-Output '     The AP must go silent on radar detection - a classic cause of INTERMITTENT'
        Write-Output '     online lag that a calm-period ping test will completely miss.'
        Write-Output '     Move the router to 36-48 or 149-161, or use a cable.'
    }
}

Section 'OEM SOFTWARE THAT MAY OVERWRITE YOUR TUNING'
$svc = Get-Service | Where-Object { $_.Name -match 'Alienware|AWCC|Dell|Lenovo|Vantage|Armoury|Asus|Killer|SmartByte|NvContainer' }
if ($svc) { $svc | ForEach-Object { Write-Output "  $($_.Name) = $($_.Status)" } }
else { Write-Output '  none detected' }

Write-Output ''
Write-Output '=== END. Nothing was modified. ==='
