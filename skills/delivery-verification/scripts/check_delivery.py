"""Validate recorded completion, not the truth of evidence."""
import json
import sys


def validate(report):
    if not isinstance(report, dict):
        raise ValueError("report must be an object")
    criteria = report.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("criteria must be a nonempty list")
    if report.get("pending") != []:
        raise ValueError("pending must be explicitly empty")
    seen = set()
    for item in criteria:
        if not isinstance(item, dict):
            raise ValueError("criterion must be an object")
        key = item.get("id")
        if not isinstance(key, str) or not key.strip() or key in seen:
            raise ValueError("criterion IDs must be nonempty and unique")
        seen.add(key)
        if item.get("status") != "verified":
            raise ValueError("criterion is not verified: " + key)
        evidence = item.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError("missing evidence: " + key)
    return len(criteria)


if __name__ == "__main__":
    try:
        with open(sys.argv[1], encoding="utf-8") as stream:
            count = validate(json.load(stream))
        print(f"recorded completion valid: {count} criteria; evidence needs independent review")
    except (ValueError, OSError, IndexError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
