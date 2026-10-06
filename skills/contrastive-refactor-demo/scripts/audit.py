"""Deliberately planted boundary divergence; not an accessibility benchmark."""
import argparse
import hashlib
import json
import sys

INPUTS = (0, 9, 10, 11)
def before(value):
    return [value < 10, value <= 10, value < 10]
def rule(value):
    return value < 10
def after(value, mutate=False):
    result = value <= 10 if mutate else rule(value)
    return [result] * 3

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mutate', action='store_true')
    args = parser.parse_args()
    before_inputs = tuple(INPUTS)
    after_inputs = tuple(INPUTS)
    assert before_inputs == after_inputs
    expected = [[v < 10] * 3 for v in INPUTS]
    old = [before(v) for v in before_inputs]
    new = [after(v, args.mutate) for v in after_inputs]
    failures = lambda values: sum(a != b for a, b in zip(values, expected))
    report = {'input_sha256': hashlib.sha256(json.dumps(INPUTS).encode()).hexdigest(),
              'same_inputs': before_inputs == after_inputs, 'cases': len(INPUTS),
              'before_failures': failures(old), 'after_failures': failures(new),
              'boundary': {'input': 10, 'before': old[2], 'after': new[2]}}
    print(json.dumps(report, indent=2))
    return 0 if failures(old) > failures(new) and new == expected else 1
if __name__ == '__main__':
    sys.exit(main())
