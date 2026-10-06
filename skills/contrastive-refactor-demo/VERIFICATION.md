# Local verification

Run from this skill directory with Python 3.

```text
python scripts/audit.py
python scripts/audit.py --mutate
```

Observed: normal exit 0, 4 identical input cases, 1 before failure and 0 after failures. Mutation exit 1, 1 after failure. Input SHA-256: `3a112f2f08550765202212216f8f7057a2735a8da6253711a60bf81a61d9bae7`. The boundary at 10 is deliberately planted. No browser, accessibility score or performance claim is made.

These are fixture-specific results, not general benchmark measurements.
