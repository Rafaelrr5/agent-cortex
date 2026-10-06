# Argv quoting recipe and offline test harness

## Quoting function (MSVC / CommandLineToArgvW rules)

```js
// Double the backslashes that precede a quote and escape the quote; double trailing
// backslashes (a closing quote follows them).
const winArg = s => `"${String(s).replace(/(\\*)"/g, '$1$1\\"').replace(/(\\*)$/, '$1$1')}"`;
const line = [userFlags, dir ? `--add-dir ${winArg(dir)}` : '', '--', winArg(prompt)]
  .filter(Boolean).join(' ');
```

Python equivalent: `subprocess.list2cmdline([...])` produces the same quoting.

## Script template (new visible PowerShell window)

Write `line` to `args_<uuid>.txt`, then write the script with a leading `\ufeff`:

```powershell
$env:TOOL_ARGS = [System.IO.File]::ReadAllText('C:\...\args_<uuid>.txt')
Remove-Item 'C:\...\args_<uuid>.txt' -ErrorAction SilentlyContinue
Remove-Item 'C:\...\run_<uuid>.ps1' -ErrorAction SilentlyContinue
Set-Location -LiteralPath 'C:\work dir'
& 'C:\...\tool.exe' --% %TOOL_ARGS%
```

Launch it with
`Start-Process powershell -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-File','<script>'`.
`-File` takes a single path, so the path is never re-split.

Alternative that also round-trips, for when the child doesn't need the current console:
`[Diagnostics.Process]::Start((New-Object Diagnostics.ProcessStartInfo -ArgumentList $exe, $line -Property @{UseShellExecute=$false}))`.

## Hostile corpus (all must round-trip as ONE argv entry)

`plain` · `a "quoted" b` · `ends with \` · `path "C:\a b\" x` · `x\"a b\"y` ·
`multi\nline "x" 100% & | ^ $env:X %PATH%` · `tail\\` · `ação "ü" 😀` · `"starts and ends"` ·
`-dash` · `it's` · `` `backtick` $(whoami) ``. Run them inside a temp dir whose name has spaces.

`%PATH%` inside the payload is not expanded by `--%`: only the `%TOOL_ARGS%` reference on the
script line is expanded, and its value isn't rescanned.

## Focus guard snippet

```powershell
if (-not ('X.Win32' -as [type])) {
  Add-Type -Namespace X -Name Win32 -MemberDefinition '[DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();'
}
if (-not $wshell.AppActivate($proc.Id)) { throw "Unable to activate window for PID $pid" }
Set-Clipboard -Value $text; Start-Sleep -Milliseconds 800
if ([X.Win32]::GetForegroundWindow() -ne $proc.MainWindowHandle) { throw "lost focus before paste; nothing was sent" }
$wshell.SendKeys('^v'); Start-Sleep -Milliseconds 500
if ([X.Win32]::GetForegroundWindow() -ne $proc.MainWindowHandle) { throw "lost focus after paste; Enter was not sent" }
$wshell.SendKeys('{ENTER}')
```

## Offline harness (Node, node:test)

- Load the server module with `vm.runInNewContext(source, { module, require: fakeRequire, process: {env: {...}}, ... })`
  so env vars and `child_process` can be injected per test.
- **Window typing:** the fake `exec` writes a wrapper script that defines stand-ins first
  (`function New-Object` returning an object with `AppActivate`/`SendKeys` ScriptMethods that
  append events to a file, plus `Get-Process`, `Set-Clipboard`, `Start-Sleep`), appends the
  generated script, and runs `powershell.exe -NoProfile -NonInteractive -File wrapper.ps1`.
  Pre-register the `Add-Type` class under the same namespace/name, with a static counter
  and a scenario field, so the `-as [type]` guard skips the real P/Invoke. Stubbed
  `MainWindowHandle` must be `[IntPtr]` for the `-ne` comparison. Assert the exact event
  sequence per scenario (ok / activation false / focus lost before paste / after paste).
- **New-session argv:** set the exe override env to `process.execPath` and the user-flags env to a
  quoted dump-script path. The "CLI" is then node, writing `argv` + `cwd` to a file. The
  fake `exec` pulls the `-File` path out of the `Start-Process` line and runs it inline
  instead of opening a window. Assert `deepStrictEqual(argv, ['--', prompt])` and the
  variadic case `['--add-dir', dir, '--', prompt]`. Assert that the temp script and args
  files are gone.
- Compare directories with `fs.realpathSync.native`. `os.tmpdir()` may return the 8.3 short
  form (`USER~1`) while the child reports the long path.
- Ordering and serialization tests need no PowerShell: inject async delivery fakes and
  assert call order, input-order results, and `active === 1` across two `fire()` calls
  started with `Promise.all`.
- One smoke run against the real exe in non-interactive mode proves the argument parsing
  worked, even when the server refuses for quota or auth reasons.
