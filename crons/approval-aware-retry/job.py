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

def tick(records, state, now, cooldown, limit):
    state = copy.deepcopy(state)
    for identity, entry in state.items():
        if (not isinstance(identity, str) or not identity or not isinstance(entry, dict)
                or type(entry.get("attempts")) is not int or entry["attempts"] < 0
                or (entry.get("last") is not None and (type(entry["last"]) is not int or entry["last"] < 0))
                or (entry.get("ack") is not None and not isinstance(entry["ack"], str))):
            raise ValueError("invalid retry state")
    output = []
    seen = set()
    for item in records:
        if (not isinstance(item, dict) or not isinstance(item.get("id"), str)
                or not item["id"] or not isinstance(item.get("revision"), str)
                or not item["revision"] or item.get("kind") not in ("operational", "needs_input")
                or item.get("result") not in ("success", "error")):
            raise ValueError("invalid retry fixture")
        identity = item["id"]
        if identity in seen:
            raise ValueError("duplicate task id")
        seen.add(identity)
        previous = state.get(identity, {"attempts": 0, "last": None, "ack": None})
        if item["kind"] == "needs_input":
            output.append({"id": identity, "status": "needs_input"})
            continue  # No timer, success flag, or revision grants permission.
        if previous["ack"] == item["revision"]:
            continue
        if previous["attempts"] >= limit:
            output.append({"id": identity, "status": "exhausted"})
            continue
        if previous["last"] is not None and now - previous["last"] < cooldown:
            output.append({"id": identity, "status": "cooldown"})
            continue
        previous = dict(previous, attempts=previous["attempts"] + 1, last=now)
        if item["result"] == "success":
            previous["ack"] = item["revision"]
        state[identity] = previous
        output.append({"id": identity, "status": item["result"], "attempt": previous["attempts"]})
    return state, output


def main():
    parser = argparse.ArgumentParser(description="Simulate bounded retries using a local fixture; executes no task")
    parser.add_argument("--feed", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--now", type=int, required=True)
    parser.add_argument("--cooldown", type=int, required=True)
    parser.add_argument("--max-attempts", type=int, required=True)
    args = parser.parse_args()
    if args.cooldown < 1 or args.max_attempts < 1 or args.now < 0:
        raise ValueError("positive cooldown and attempt limit required")
    if not Path(args.feed).is_file():
        raise FileNotFoundError("feed unavailable")
    state, output = tick(load(args.feed, []), load(args.state, {}), args.now, args.cooldown, args.max_attempts)
    save(args.state, state)
    emit(output)
    return 1 if any(item["status"] in ("error", "exhausted") for item in output) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
