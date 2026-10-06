# Local verification

Run from this skill directory with Python 3.

```text
python scripts/test_boundary.py
```

Observed on Windows PowerShell 5.1: exit 0; 13 native node.exe argv round-trips, including empty text, quoted Unicode, newline and percent tokens. Four generated-script focus scenarios passed: success, activation false, lost focus before paste, lost focus after paste. Temporary scripts were removed. Desktop interactions are ScriptBlock stubs: no live COM, clipboard, focus or SendKeys calls. The real application CLI, global scheduling and command-length cap are not tested by this minimal harness.

These are fixture-specific results, not general benchmark measurements.
