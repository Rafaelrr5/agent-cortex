# Windows: making the gateway survive boot and mid-day death

Companion to *"The channel is only as alive as the gateway"* in `SKILL.md`.
Measured on a real machine (Windows 11, desktop install, non-admin user), not
inferred.

## The failure

What the user said: *"every time I turn the PC on, Telegram should just work."*

What was happening:

| Evidence | Reading |
|---|---|
| `hermes gateway status` → login item installed | a file exists; says nothing about execution |
| boot at 18:55, gateway process started 13:12 the next day | **delta 1096 min**: the login item did not fire |
| two boots that day, no gateway start logged near either | confirmed twice |
| last heartbeat five days before, followed by an unclean-exit record | dead for five days, silently |

The gateway that *was* alive had been started by opening the Hermes desktop app.
That is why the failure is so easy to miss: whenever the user looks, the app is
open and the gateway is up.

Hermes logs one start line per launch, plus unclean-exit records, under
`HERMES_HOME/logs/`. Boot days with no start line near them mean the launcher is
not running.

## Rule out the cheap causes once, then move on

```powershell
# .vbs still associated with Windows Script Host?
(Get-ItemProperty 'Registry::HKEY_CLASSES_ROOT\.vbs').'(default)'                # VBSFile
# Script Host disabled by policy? (0 = disabled)
(Get-ItemProperty 'HKLM:\Software\Microsoft\Windows Script Host\Settings' -EA SilentlyContinue).Enabled
(Get-ItemProperty 'HKCU:\Software\Microsoft\Windows Script Host\Settings' -EA SilentlyContinue).Enabled
# Startup entry switched off in Task Manager?
$k='HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\StartupFolder'
if (Test-Path $k) { (Get-Item $k).Property } else { 'nothing disabled here' }
# Defender attack-surface rules blocking script launchers?
(Get-MpPreference).AttackSurfaceReductionRules_Ids
```

In the measured case all of these came back clean, and the launcher worked when run
by hand, yet it never fired at logon. The cause was never isolated. That is the
point to stop investigating and change mechanism. A scheduler entry beats a
repaired one-shot launcher whatever the root cause, because it brings retry and
repetition with it.

## Register with XML, not the cmdlets

The PowerShell cmdlets cannot express an indefinite repetition cleanly:
`RepetitionDuration = [TimeSpan]::MaxValue` serialises to `P99999999DT23H59M59S`,
and `Register-ScheduledTask` rejects it as out of range. In the XML, leaving
`<Duration>` out of `<Repetition>` means "forever".

```bat
schtasks /Create /TN "HermesGateway" /XML "C:\path\to\HermesGateway.task.xml" /F
```

Template: `../templates/windows-gateway-task.xml`. Substitute the user id and the
paths. Keep the filled-in XML next to your Hermes files so the task can be
recreated after a reinstall.

Design points in the template:

- **Logon trigger with a 45 s delay**: lets the network come up first.
- **15-minute repetition with no duration**: the watchdog. This is what fixes the
  five-day silent death, not the logon trigger.
- **`IgnoreNew` for multiple instances**, plus the gateway's own instance lock.
- **`ExecutionTimeLimit PT0S`**: zero means no limit. The default limit would have
  Task Scheduler kill a long-lived gateway.
- **`LeastPrivilege` with an interactive token**: no admin, no UAC prompt, runs in
  the user's session.
- **`RestartOnFailure`**: three retries, two minutes apart.

Point the action at the launcher Hermes itself installed for the gateway service
(under `HERMES_HOME`), not at a hand-written one. It already sets the environment
the gateway needs.

## A verification that proves it

```bat
:: 1) destructive: stop the gateway, then confirm status reports none
:: 2) fire the trigger the way Windows will
schtasks /Run /TN "HermesGateway"
:: 3) wait ~50 s, then the two things that count:
::    hermes gateway status  -> running, NEW pid
::    gateway_state.json     -> the platform's state is connected
powershell -NoProfile -Command "Get-ScheduledTaskInfo -TaskName 'HermesGateway' | Select LastRunTime,LastTaskResult"
:: 4) idempotency: fire again WITHOUT stopping -> same pid, still connected
schtasks /Run /TN "HermesGateway"
```

Wait 40-50 s before judging step 3. Channel startup includes connection checks, so
looking at 10 s reads as failure when it is only mid-connect.

### Counting processes

- One healthy gateway can show as **two** `python.exe` processes with `gateway` in
  the command line: a small detached launcher that is the parent of the large real
  gateway. Check parent pid and memory before concluding you started a duplicate.

  ```powershell
  Get-CimInstance Win32_Process -Filter 'Name="python.exe"' |
    ?{$_.CommandLine -like '*gateway*'} |
    %{ "PID $($_.ProcessId) parent $($_.ParentProcessId) mem $([math]::Round($_.WorkingSetSize/1MB))MB" }
  ```

- The command line may show a uv-managed interpreter instead of the venv's
  `python.exe`. That is normal. Do not "fix" it.

### A test harness that fakes a failure

Running the Startup-folder launcher from a shell without quoting its spaces
(`...\Start Menu\Programs\Startup\...`) makes a working launcher look dead. Quote
first, conclude second.

## Leave the old Startup item alone

The gateway refuses to double-start, so the old login item costs nothing and is
free redundancy if it ever starts working. Removing it is churn with no upside.
