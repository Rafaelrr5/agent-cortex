---
name: windows-performance-tuning
description: Windows slow or laggy? Tune the whole latency chain.
version: 1.0.0
author: Rafael Rocha Ribeiro (github.com/Rafaelrr5)
license: MIT
metadata:
  agent:
    tags: [windows, performance, latency, gaming, powercfg, cpu, gpu, input-lag]
    related_skills: []
---

# Windows performance & latency tuning

## When to Use

- "My PC feels slow / stuttery / laggy."
- **Input lag in a game** — especially online/competitive modes.
- The user arrives asking for **one specific tweak someone recommended** ("put it on High Performance", "disable core parking", "use ParkControl", "debloat Windows", some registry tweak from a forum).
- Frametime spikes, stutter, fans screaming, thermal throttling.

## The one principle

**Latency is a chain. The tweak the user was told about is rarely the biggest link.**

When someone asks for a named tweak, they are reporting a *symptom* and repeating a *guess*. Do the tweak they asked for — it's cheap, reversible, and they asked. Then **keep going and measure every other link**, because the real cost is usually somewhere they didn't look.

Real example (this skill's origin session): user asked for High Performance + ParkControl to fix input lag in EA FC 26 Pro Clubs. Both were applied. But the game's own config had `TARGET_FRAME_RATE = 60` on a **120 Hz panel** — that alone is ~8 ms of added latency per frame, arithmetic, not opinion. Plus 1.2x supersampling on a 4 GB GPU and borderless-window compositing. Core parking was real but third-order. Stopping at the requested tweak would have "completed the task" and left the actual problem untouched.

## Third-party tools are usually a GUI over something native

Before installing anything (ParkControl, Process Lasso, "debloat" scripts, latency tweakers), check whether it is just a front-end for a native knob you can drive directly:

| Tool | What it actually drives |
|---|---|
| ParkControl / Process Lasso | `powercfg` processor subgroup values (see references) |
| "Ultimate Performance unlocker" | `powercfg -duplicatescheme <guid>` |
| Most "latency tweakers" | HKCU GameDVR/GameBar keys + MMCSS in HKLM |

Driving it natively means no install, no background service, no admin prompt, and you can **read the values back to prove the change landed**. Prefer that. (This also supports users who prefer inspectable native configuration over installing additional helper tools.)

## Diagnostic order

Work top-down. Each step is cheap to check; stop adding changes once the numbers explain the symptom.

1. **Admin?** `net session >/dev/null 2>&1 && echo ADMIN || echo NOT_ADMIN`.
   Decides your whole strategy — see "Non-admin boundary" below. Do this **first**, not after a write fails.
2. **Display refresh vs. frame cap.** Panel Hz from `Win32_VideoController.CurrentRefreshRate`; cap from the game's config. A 60 cap on a 120 Hz panel is the single most common silent latency tax.
3. **The game's own config file.** Back it up, read it, fix the obvious. See `references/game-latency-and-configs.md`.
4. **GPU assignment** on hybrid/Optimus laptops — the panel is driven by the iGPU; the game may not be on the dGPU.
5. **Present mode** — borderless costs ~1 frame via DWM compositing; fullscreen exclusive bypasses it.
6. **VBS / HVCI** — 5–15% CPU cost, disproportionate frametime impact. Admin-only to change.
7. **Power plan + core parking + frequency floor** — `references/windows-power-and-parking.md`.
8. **Network**, for anything online. Wi-Fi channel, DFS, packet loss, jitter. A cable beats every tweak on this list combined.
9. **Thermals** — on a laptop, a 100% frequency floor can *cause* throttling. Verify you didn't make it worse.

Run `scripts/latency_audit.ps1` to snapshot steps 1–8 in one read-only pass.

## Non-admin boundary

Many Windows client machines (work-managed, or just a standard user) cannot write HKLM. Know what falls on each side **before** you promise anything:

**Works without admin:** `powercfg` on the user's own schemes (create, activate, set AC/DC values, unhide attributes), everything under HKCU (GameDVR, per-app GPU preference), game config files in `%LOCALAPPDATA%`/Documents.

**Needs admin:** VBS/HVCI, MMCSS (`SystemResponsiveness`, `NetworkThrottlingIndex`), `HwSchMode` (HAGS), service changes, driver/BIOS/MUX settings.

When you hit the boundary, don't silently skip it — **name the item, say what it would buy, and say it needs admin.** Let the user decide whether to escalate.

## Reporting rules for this class of task

- **Correct the premise plainly when it was wrong.** "Quem te disse que era X errou o alvo" is more useful than quietly doing X and moving on. Say what the real cause was and why.
- **Rank by expected impact, and show the arithmetic** where you have it (frame cap → ms). Don't present a flat list of 12 tweaks.
- **Never claim the symptom is fixed** unless the user has actually re-tested. You changed inputs; the outcome is a hypothesis until they play/run it. Say so.
- **Flag every tradeoff you introduced**: heat and fan noise (frequency floor), battery drain, reduced security (VBS), visual quality (render scale).
- **Back up any config file before editing it** and tell the user the backup path.

## Pitfalls

- **`reg add` prints "Acesso negado" and STILL exits 0.** Exit codes lie here. Parse the output text, never `$?`.
- **Heterogeneous CPUs (Intel 12th gen+) have TWO parking classes.** Setting only class 0 leaves the E-cores parking. ParkControl and the Windows panel only touch class 0. Details and GUIDs in `references/windows-power-and-parking.md`.
- **`wmic` is gone from recent Windows 11 builds** — it returns empty with exit 0. Use `Get-CimInstance` (PowerShell) instead.
- **Localized Windows + git-bash = mojibake** from `powercfg`/`reg` output; `grep` may even report "Binary file matches". Pipe through `tr -d '\r' | tr -cd '\11\12\15\40-\176'`, or read power values from the registry instead of parsing localized text.
- **`powercfg /list` can lag behind reality** right after `-duplicatescheme`. Trust `/getactivescheme` and `/setactive`, not the list.
- **Value changes need `powercfg /setactive SCHEME_CURRENT`** to actually apply.
- **A 100% frequency floor on a laptop is a real tradeoff**, not a free win. If it throttles thermally, you lost. Offer to revert the floor while keeping parking disabled.
- **Don't tune a plan the user's OEM software will overwrite.** Alienware Command Center, Lenovo Vantage, Armoury Crate, and Intel DTT can swap the active scheme and reset everything.

## Support files

- `references/windows-power-and-parking.md` — `powercfg` mechanics: hidden attributes, the processor subgroup GUID map, P/E-core dual parking classes, exact verified commands.
- `references/game-latency-and-configs.md` — game-side chain: frame cap vs. panel Hz, render scale, present mode, hybrid-GPU assignment, EA FC 26 `fcsetup.ini` key map, Wi-Fi/DFS diagnosis.
- `scripts/latency_audit.ps1` — read-only one-shot snapshot of the whole chain. Changes nothing.
