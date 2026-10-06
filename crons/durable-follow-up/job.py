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

def tick(records, state, now, window, capacity):
    state = copy.deepcopy(state)
    for identity, entry in state.items():
        if (not isinstance(identity, str) or not identity or not isinstance(entry, dict)
                or type(entry.get("opened")) is not int or entry["opened"] < 0
                or type(entry.get("resolved")) is not bool):
            raise ValueError("invalid obligation state")
    for item in records:
        if (not isinstance(item, dict) or not isinstance(item.get("id"), str)
                or not item["id"] or type(item.get("at")) is not int
                or item.get("kind") not in ("open", "resolved", "ack")
                or not isinstance(item.get("evidence", ""), str)):
            raise ValueError("invalid obligation record")
        identity = item["id"]
        if item["kind"] == "open":
            if now - window <= item["at"] <= now:
                state.setdefault(identity, {"opened": item["at"], "resolved": False})
        elif item["at"] <= now and item.get("evidence", "").strip():
            # Tombstones prevent replay from resurrecting completed obligations.
            entry = state.setdefault(identity, {"opened": item["at"], "resolved": False})
            if item["at"] >= entry["opened"]:
                entry["resolved"] = True
    if len(state) > capacity:
        raise ValueError("state capacity reached; no obligations discarded; archive reviewed state explicitly")
    output = [{"id": identity, "followup_key": "followup:" + identity}
              for identity, entry in sorted(state.items()) if not entry["resolved"]]
    return state, output


def main():
    parser = argparse.ArgumentParser(description="Durable local obligations with stable follow-up keys")
    parser.add_argument("--feed", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--now", type=int, required=True)
    parser.add_argument("--window", type=int, required=True)
    parser.add_argument("--capacity", type=int, required=True)
    args = parser.parse_args()
    if args.window < 1 or args.capacity < 1 or args.now < 0:
        raise ValueError("positive window and capacity required")
    if not Path(args.feed).is_file():
        raise FileNotFoundError("feed unavailable")
    state, output = tick(load(args.feed, []), load(args.state, {}), args.now, args.window, args.capacity)
    save(args.state, state)
    emit(output)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
