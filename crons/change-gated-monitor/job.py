import argparse
import copy
import json
import os
from pathlib import Path
import sys


def load(path, default):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return copy.deepcopy(default)
    if not isinstance(value, type(default)):
        raise ValueError("unexpected JSON root type")
    return value


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def emit(value):
    print(json.dumps(value, sort_keys=True, separators=(",", ":")), flush=True)

def tick(records, state):
    latest = None
    for record in records:
        if (not isinstance(record, dict) or not isinstance(record.get("id"), str)
                or not record["id"] or type(record.get("sequence")) is not int
                or record.get("kind") not in ("request", "reply")):
            raise ValueError("invalid request feed record")
        if record["kind"] == "request":
            key = (record["sequence"], record["id"])
            if latest is None or key > (latest["sequence"], latest["id"]):
                latest = record
    # A rolling empty feed cannot retract a previously observed request.
    if latest and (latest["sequence"], latest["id"]) > (state["sequence"], state["id"]):
        state = {"sequence": latest["sequence"], "id": latest["id"]}
    return state


def main():
    parser = argparse.ArgumentParser(description="Stable latest-request identity; local JSON feed only")
    parser.add_argument("--feed", required=True)
    parser.add_argument("--state", required=True)
    args = parser.parse_args()
    state = load(args.state, {"sequence": -1, "id": ""})
    if type(state.get("sequence")) is not int or not isinstance(state.get("id"), str):
        raise ValueError("invalid baseline")
    try:
        records = load(args.feed, [])
        # Missing feed is an outage, not an empty snapshot.
        if not Path(args.feed).is_file():
            raise FileNotFoundError("feed unavailable")
        result = tick(records, state)
        save(args.state, result)
    except (OSError, ValueError) as exc:
        emit(state)
        print(f"monitor unavailable: {exc}", file=sys.stderr)
        return 1
    emit(result)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
