# Local verification

Run from this skill directory with Python 3.

```text
python scripts/generate.py --self-test
python scripts/generate.py --source nonexistent.json
```

Observed: self-test exit 0; section count, shared-source update and HTML escaping passed; three invalid fixtures rejected. Missing-source command exits 1 with an actionable invalid-source message. Four generated artifacts are in `outputs/`. No PDF, embedded brand font or screenshot claim is made.

These are fixture-specific results, not general benchmark measurements.
