# Game-side latency chain

The links between the user's hand and the pixel, roughly ordered by how often they're the real problem.

## 1. Frame cap vs. panel refresh rate — check this FIRST

A frame cap below the panel's refresh rate adds latency you can compute:

| Cap | Frame interval | vs. 120 Hz panel |
|---|---|---|
| 60 fps | 16.7 ms | **+8.3 ms** of pure added latency |
| 120 fps | 8.3 ms | baseline |

This is arithmetic, not tuning folklore, and it dwarfs most registry tweaks. Games ship defaulting to 60 constantly. **Always compare the game's cap to `Win32_VideoController.CurrentRefreshRate`.**

Also verify the panel is actually *running* at its max — Windows silently defaults some laptop panels to 60 Hz.

```powershell
Get-CimInstance Win32_VideoController |
  Where-Object CurrentRefreshRate |
  Select-Object Name, CurrentHorizontalResolution, CurrentVerticalResolution, CurrentRefreshRate, MaxRefreshRate
```

## 2. Render scale / supersampling

A render scale above 1.0 renders above native and downsamples. On a **4 GB laptop GPU** this saturates the card, the render queue backs up, and input lag rises. `1.2` on a 1080p panel means rendering 2304x1296 for a display that shows 1920x1080. Set to `1.0` unless the user specifically wants image quality over latency.

## 3. Present mode

- **Borderless windowed** goes through DWM compositing: roughly +1 frame.
- **Fullscreen exclusive** bypasses the compositor.

For a latency complaint, prefer fullscreen exclusive. (Modern Windows has optimizations that narrow this gap, but on a latency complaint don't gamble — take the deterministic path.)

## 4. Hybrid / Optimus GPU assignment

On most gaming laptops the internal panel is wired to the **iGPU**; the dGPU renders and copies frames across. Confirm which GPU the game is actually using, and pin it:

```bash
# GpuPreference: 0=let Windows decide, 1=power saving (iGPU), 2=high performance (dGPU)
reg add "HKCU\SOFTWARE\Microsoft\DirectX\UserGpuPreferences" \
  /v "C:\path\to\Game.exe" /t REG_SZ /d "GpuPreference=2;" /f
```

HKCU — **no admin needed**. Inspect existing per-app assignments by reading that same key; it's a quick map of what the user already tuned.

If the laptop has a **MUX switch** (BIOS or OEM app), routing the panel directly to the dGPU removes the copy entirely — biggest hybrid-laptop win, but it's a user action, not a scriptable one.

## 5. Background capture

```bash
reg add "HKCU\System\GameConfigStore" /v GameDVR_Enabled /t REG_DWORD /d 0 /f
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\GameDVR" /v AppCaptureEnabled /t REG_DWORD /d 0 /f
```

Both HKCU. The HKLM policy equivalent needs admin; skip it, the HKCU pair is enough for a single user.

## 6. VBS / HVCI

```powershell
$g = Get-CimInstance -Namespace root\Microsoft\Windows\DeviceGuard -ClassName Win32_DeviceGuard
$g.VirtualizationBasedSecurityStatus   # 2 = running
$g.SecurityServicesRunning             # 2 = HVCI / memory integrity
```

Running VBS costs roughly 5–15% CPU in games and hurts frametime consistency more than average FPS. **Disabling it requires admin and genuinely reduces security.** Present it as the user's decision with the tradeoff stated — never disable it unasked, and never bury the security cost.

## 7. Network — for online/competitive modes

Online game lag is frequently *not* a local performance problem at all.

```bash
netsh wlan show interfaces      # SSID, band, channel, signal, RSSI, rx/tx rate
ping -n 60 1.1.1.1              # 60 packets: look at max vs avg (jitter) and loss
```

**DFS channels are a classic intermittent-lag cause.** In 5 GHz, channels **52–144** are DFS (radar-shared). On radar detection the AP must stop transmitting and vacate — up to 60 s of silence. That produces exactly the "it's fine, then suddenly it isn't" pattern people describe in online matches. A short ping test during a calm period will look perfectly healthy and prove nothing.

Fix: move the router to a non-DFS channel (**36–48** or **149–161**), or use a cable.

**Always check whether the machine has an unused Ethernet port** (`Get-NetAdapter` shows Disconnected ones). For a competitive online complaint, a cable beats every tweak in this document combined. Say so plainly.

Also check for VPN adapters (Radmin, Hamachi, corporate clients) — verify the default route metric so game traffic isn't detouring through one.

## EA FC (FC 24/25/26) — `fcsetup.ini`

Location: `%LOCALAPPDATA%\EA SPORTS FC <NN>\fcsetup.ini`

**Back it up before editing.** The game rewrites this file, so re-check after the user changes anything in-game.

Latency-relevant keys:

| Key | Latency-optimal | Notes |
|---|---|---|
| `TARGET_FRAME_RATE` | = panel Hz | **Ships at 60. The most common single offender.** |
| `MAX_FRAME_RATE` | = panel Hz | |
| `RENDERING_SCALE` | `1.0` | >1.0 is supersampling; brutal on 4 GB GPUs |
| `WINDOWED_BORDERLESS` | `0` | 0 = fullscreen exclusive |
| `FULLSCREEN` | `1` | |
| `WAITFORVSYNC` | `0` | VSync adds a frame of latency |
| `REFRESH_RATE` | = panel Hz | |
| `DYNAMIC_RESOLUTION` | `0` | avoids resolution churn |
| `MOTION_BLUR` | `0` | |

Other EA-side factors worth naming to the user but not scriptable: server region, EA Anti-Cheat overhead, and the fact that **Pro Clubs is peer-sensitive** — a teammate's connection can be the actual source.

## Honesty rule for this whole file

You can verify *inputs* (config values, registry keys, refresh rate, channel). You cannot verify the *outcome* until the user plays again. Report the changes and the expected ranking, then explicitly ask them to re-test. Do not write "fixed".
