<#
.SYNOPSIS
  Read-only. Finds out WHICH process owns a visible window, and optionally watches for
  newly-spawned processes so you can catch a flashing console in the act.

.DESCRIPTION
  Counting processes does not answer "who opened that window" -- most console-mode
  interpreters have no window at all. This lists PIDs that actually own a visible window,
  with their full command line, and in -Watch mode logs every new process (with parent and
  command line) so the spawn chain becomes visible.

  Changes nothing. Safe to run at any time.

.EXAMPLE
  powershell -NoProfile -File window_owners.ps1
  # snapshot: every PID owning a visible window

.EXAMPLE
  powershell -NoProfile -File window_owners.ps1 -Watch 150
  # watch 150s: log new processes (default names) AND any newly visible window

.EXAMPLE
  powershell -NoProfile -File window_owners.ps1 -Watch 90 -Match 'cc_stop_hook|sync-brain'
  # only report new processes whose command line matches the regex
#>
param(
    [int]      $Watch      = 0,
    [string[]] $Name       = @('python', 'pythonw', 'conhost', 'cmd', 'bash', 'powershell'),
    [string]   $Match      = '',
    [int]      $IntervalMs = 500
)

$ErrorActionPreference = 'Continue'

function Get-CmdLine {
    param([int] $ProcId)
    try {
        $p = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcId" -ErrorAction SilentlyContinue
        if ($null -eq $p) { return '' }
        $c = $p.CommandLine
        if ([string]::IsNullOrWhiteSpace($c)) { return '' }
        return ($c -replace '\s+', ' ')
    } catch { return '' }
}

function Get-Parent {
    param([int] $ProcId)
    try {
        $p = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcId" -ErrorAction SilentlyContinue
        if ($null -eq $p) { return @{ Pid = 0; Name = '?' } }
        $pp = Get-CimInstance Win32_Process -Filter "ProcessId=$($p.ParentProcessId)" -ErrorAction SilentlyContinue
        return @{ Pid = [int]$p.ParentProcessId; Name = if ($pp) { $pp.Name } else { '(gone)' } }
    } catch { return @{ Pid = 0; Name = '?' } }
}

function Trunc {
    param([string] $Text, [int] $Max = 170)
    if ([string]::IsNullOrEmpty($Text)) { return '' }
    if ($Text.Length -le $Max) { return $Text }
    return $Text.Substring(0, $Max) + ' ...'
}

# --- who owns a VISIBLE window right now -------------------------------------
function Get-WindowOwners {
    Get-Process | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle } |
        ForEach-Object {
            [pscustomobject]@{
                Id      = $_.Id
                Proc    = $_.ProcessName
                Title   = $_.MainWindowTitle
                CmdLine = Trunc (Get-CmdLine $_.Id)
            }
        }
}

Write-Output '=== processes owning a VISIBLE window ==='
$owners = Get-WindowOwners
if (-not $owners) {
    Write-Output '(none)'
} else {
    foreach ($o in $owners) {
        Write-Output ("pid={0,-7} {1,-16} title='{2}'" -f $o.Id, $o.Proc, $o.Title)
        if ($o.CmdLine) { Write-Output ("        cmd= {0}" -f $o.CmdLine) }
    }
}

if ($Watch -le 0) { return }

# --- watch mode ---------------------------------------------------------------
Write-Output ''
Write-Output ("=== watching {0}s for new processes / new windows (Ctrl+C to stop) ===" -f $Watch)
if ($Match) { Write-Output ("    filter: command line matches /{0}/" -f $Match) }
else        { Write-Output ("    names : {0}" -f ($Name -join ', ')) }

$seenProc = @{}
$seenWin  = @{}
foreach ($p in Get-Process) { $seenProc[$p.Id] = $true }
foreach ($o in $owners)     { $seenWin["$($o.Id)|$($o.Title)"] = $true }

$nameRegex = '(' + (($Name | ForEach-Object { [regex]::Escape($_) }) -join '|') + ')'
$deadline  = (Get-Date).AddSeconds($Watch)

while ((Get-Date) -lt $deadline) {

    foreach ($p in Get-Process) {
        if ($seenProc.ContainsKey($p.Id)) { continue }
        $seenProc[$p.Id] = $true

        $cmd = Get-CmdLine $p.Id
        if ($Match) {
            if ($cmd -notmatch $Match) { continue }
        } elseif ($p.ProcessName -notmatch $nameRegex) {
            continue
        }

        $par = Get-Parent $p.Id
        Write-Output ("{0} NEW  pid={1,-7} {2,-14} parent={3}({4})" -f `
            (Get-Date -Format HH:mm:ss), $p.Id, $p.ProcessName, $par.Name, $par.Pid)
        if ($cmd) { Write-Output ("                cmd= {0}" -f (Trunc $cmd)) }
    }

    foreach ($o in Get-WindowOwners) {
        $k = "$($o.Id)|$($o.Title)"
        if ($seenWin.ContainsKey($k)) { continue }
        $seenWin[$k] = $true
        Write-Output ("{0} WINDOW pid={1,-7} {2,-14} title='{3}'" -f `
            (Get-Date -Format HH:mm:ss), $o.Id, $o.Proc, $o.Title)
        if ($o.CmdLine) { Write-Output ("                cmd= {0}" -f $o.CmdLine) }
    }

    Start-Sleep -Milliseconds $IntervalMs
}

Write-Output ''
Write-Output '=== done. A clean run reports NO new WINDOW lines. ==='
