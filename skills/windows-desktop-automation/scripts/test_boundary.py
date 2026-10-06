"""Run generated PowerShell without activating or touching desktop windows."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

CORPUS = ['plain', 'a "quoted" b', 'ends with \\', 'path "C:\\a b\\" x',
          'x\\"a b\\"y', 'multi\nline "x" 100% & | ^ $env:X %PATH%',
          'tail\\\\', 'Unicode "ü" 😀', '"starts and ends"', '-dash', "it's",
          '`backtick` $(whoami)', '']
def literal(text):
    return "'" + str(text).replace("'", "''") + "'"
def main():
    ps = shutil.which('powershell.exe')
    node = shutil.which('node')
    if not ps or not node:
        print('Requires Windows PowerShell 5.1 and a native node.exe on PATH.', file=sys.stderr)
        return 2
    out = Path(__file__).resolve().parents[1] / 'outputs'
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='argv space ', dir=out) as temp:
        folder = Path(temp)
        dump = folder / 'dump.cjs'
        dump.write_text("console.log(JSON.stringify(process.argv.slice(2)))", encoding='utf-8')
        script = folder / 'generated.ps1'
        script.write_text('& ' + literal(node) + ' --% %TOOL_ARGS%\n', encoding='utf-8-sig')
        for text in CORPUS:
            expected = ['--add-dir', 'example directory', '--', text]
            env = dict(os.environ, TOOL_ARGS=subprocess.list2cmdline([str(dump)] + expected))
            result = subprocess.run([ps, '-NoProfile', '-NonInteractive', '-File', str(script)],
                                    env=env, capture_output=True, text=True, encoding='utf-8')
            assert result.returncode == 0, result.stderr
            assert json.loads(result.stdout) == expected, repr(text)
        # Pure ScriptBlock stubs: no COM object, clipboard, user32 or activation call.
        guard = """
param([string]$Scenario)
$events = [System.Collections.Generic.List[string]]::new()
$activate = { $Scenario -ne 'activation-false' }
$foreground = { param($stage) -not (($Scenario -eq 'before-paste' -and $stage -eq 'paste') -or ($Scenario -eq 'after-paste' -and $stage -eq 'enter')) }
$clipboard = { $events.Add('clipboard') }
$send = { param($key) $events.Add($key) }
try {
 if (-not (& $activate)) { throw 'activation failed' }
 & $clipboard
 if (-not (& $foreground 'paste')) { throw 'lost focus before paste' }
 & $send 'paste'
 if (-not (& $foreground 'enter')) { throw 'lost focus after paste' }
 & $send 'enter'
} catch { $events.Add('abort') }
ConvertTo-Json -InputObject @($events) -Compress
"""
        script.write_text(guard, encoding='utf-8-sig')
        scenarios = {'ok':['clipboard','paste','enter'], 'activation-false':['abort'],
                     'before-paste':['clipboard','abort'], 'after-paste':['clipboard','paste','abort']}
        for scenario, expected in scenarios.items():
            result = subprocess.run([ps, '-NoProfile', '-NonInteractive', '-File', str(script), scenario],
                                    capture_output=True, text=True)
            assert result.returncode == 0, result.stderr
            assert json.loads(result.stdout) == expected
    print(f'PASS: {len(CORPUS)} native argv round-trips; {len(scenarios)} stubbed focus scenarios; temporary scripts removed')
    return 0
if __name__ == '__main__':
    sys.exit(main())
