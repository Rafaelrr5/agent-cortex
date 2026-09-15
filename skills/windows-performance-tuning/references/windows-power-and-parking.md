# powercfg: power plans, hidden attributes, core parking

All commands below were run and verified on Windows 11 build 26200, **as a standard (non-admin) user**, on an Intel i5-12500H. `powercfg` operating on the user's own schemes does not need elevation.

## Create and activate the hidden High Performance plan

Windows 11 hides High Performance from `powercfg.cpl` in favour of the slider. Duplicate it from its well-known GUID:

```bash
powercfg -duplicatescheme 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
powercfg /setactive 62ee0894-ca94-4ec7-94a9-c56500ead606
powercfg /getactivescheme   # authoritative
```

Well-known scheme GUIDs:

| Plan | GUID |
|---|---|
| Balanced | `381b4222-f694-41f0-9685-ff5bb260df2e` |
| High performance | `8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c` |
| Power saver | `a1841308-3541-4fab-bc81-f71556f20b4a` |
| Ultimate performance | `e9a42b02-d5df-448d-aa00-03f14749eb61` |

**Gotcha:** `-duplicatescheme` for High Performance prints/reuses `62ee0894-...` and `powercfg /list` may not show the new plan on the very next call. `/setactive` works anyway. Verify with `/getactivescheme`, not `/list`.

## Unhiding processor settings

Most of the interesting processor knobs are hidden from the GUI. Unhide before setting:

```bash
powercfg -attributes SUB_PROCESSOR <setting-guid> -ATTRIB_HIDE
```

Once unhidden, `powercfg /q SCHEME_CURRENT SUB_PROCESSOR` lists them with aliases.

## Processor subgroup (`SUB_PROCESSOR` = `54533251-82be-4824-96c1-47b60b740d00`)

| Alias | GUID (class 0) | What it does |
|---|---|---|
| `CPMINCORES` | `0cc5b647-c1df-4637-891a-dec35c318583` | Min % of cores kept unparked. **100 = parking off.** |
| `CPMAXCORES` | `ea062031-0e34-4ff1-9b6d-eb1059334028` | Max % of cores available |
| `PROCTHROTTLEMIN` | `893dee8e-2bef-41e0-89c6-b55d0929964c` | Minimum processor state (%) |
| `PROCTHROTTLEMAX` | `bc5038f7-23e0-4960-96da-33abaf5935ec` | Maximum processor state (%) |
| `PERFBOOSTMODE` | `be337238-0d82-4146-a960-4f3749d470c7` | Turbo boost mode (2 = aggressive) |
| `IDLEDISABLE` | `5d76a2ca-e8c0-402f-a133-2158492d58ad` | 1 = disable C-states (heat! last resort) |
| `SCHEDPOLICY` | `4b92d758-5a24-4851-a470-815d78aee119` | Core parking scheduler policy |

## THE BIG ONE: heterogeneous CPUs have TWO parking classes

On Intel 12th-gen and newer (P-cores + E-cores), Windows exposes **per-class** copies of the parking settings. **The class-1 GUID is the class-0 GUID with the last hex digit incremented.**

```
CPMINCORES  class 0 (P-cores): 0cc5b647-c1df-4637-891a-dec35c318583
CPMINCORES  class 1 (E-cores): 0cc5b647-c1df-4637-891a-dec35c31858 4   <-- note the 4

CPMAXCORES  class 0:           ea062031-0e34-4ff1-9b6d-eb1059334028
CPMAXCORES  class 1:           ea062031-0e34-4ff1-9b6d-eb10593340 29
```

**ParkControl and the Windows power panel only touch class 0.** Set only that and the E-cores keep parking — you get half the fix and a confusing result. Verified: the class-1 GUID accepts `-setacvalueindex` and reads back correctly on an i5-12500H.

The class-1 settings need unhiding separately.

## Verified working sequence (non-admin)

```bash
# unhide both parking classes
powercfg -attributes SUB_PROCESSOR 0cc5b647-c1df-4637-891a-dec35c318583 -ATTRIB_HIDE
powercfg -attributes SUB_PROCESSOR 0cc5b647-c1df-4637-891a-dec35c318584 -ATTRIB_HIDE

# AC: parking off on BOTH classes, clock pinned, turbo aggressive
powercfg -setacvalueindex SCHEME_CURRENT SUB_PROCESSOR CPMINCORES 100
powercfg -setacvalueindex SCHEME_CURRENT SUB_PROCESSOR 0cc5b647-c1df-4637-891a-dec35c318584 100
powercfg -setacvalueindex SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMIN 100
powercfg -setacvalueindex SCHEME_CURRENT SUB_PROCESSOR PROCTHROTTLEMAX 100
powercfg -setacvalueindex SCHEME_CURRENT SUB_PROCESSOR PERFBOOSTMODE 2

# DC (battery): parking off, but leave frequency free
powercfg -setdcvalueindex SCHEME_CURRENT SUB_PROCESSOR CPMINCORES 100
powercfg -setdcvalueindex SCHEME_CURRENT SUB_PROCESSOR 0cc5b647-c1df-4637-891a-dec35c318584 100

# REQUIRED - values do not take effect until the scheme is re-applied
powercfg /setactive SCHEME_CURRENT
```

**Split AC/DC deliberately on laptops.** Parking-off is cheap and helps latency on both. A 100% frequency *floor* on battery just burns charge and generates heat for nothing — leave `PROCTHROTTLEMIN` low on DC unless the user explicitly asks otherwise, and tell them you made that call.

## Reading values back

Localized Windows makes `powercfg /q` output painful to parse. Two options:

```bash
# 1. strip control chars, grep the current-index lines
export LC_ALL=C
powercfg /q SCHEME_CURRENT SUB_PROCESSOR CPMINCORES 2>&1 \
  | tr -d '\r' | tr -cd '\11\12\15\40-\176' | grep -iE 'Atuais|Current'
```

```powershell
# 2. locale-proof: read the registry directly (READING HKLM needs no admin)
$s = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes').ActivePowerScheme
Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes\$s\54533251-82be-4824-96c1-47b60b740d00\0cc5b647-c1df-4637-891a-dec35c318583"
# -> ACSettingIndex / DCSettingIndex
```

Values are hex in `powercfg` output: `0x64` = 100, `0x04` = 4%.

## Reverting

```bash
powercfg /setactive 381b4222-f694-41f0-9685-ff5bb260df2e   # back to Balanced
powercfg -delete 62ee0894-ca94-4ec7-94a9-c56500ead606      # remove the duplicated plan
```

All of this is per-scheme, so switching plans already reverts the behaviour without deleting anything.
