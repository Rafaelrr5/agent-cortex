"""Offline verification. Run: python -I -B third_party/verify_bundle.py."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
manifest = json.loads((ROOT / 'third_party/manifest.json').read_text(encoding='utf-8'))
count = 0
for skill in manifest['skills']:
    for item in skill['files']:
        assert hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() == item['sha256'], item['path']
        count += 1
    text = (ROOT / 'third_party' / skill['name'] / 'SKILL.md').read_text(encoding='utf-8')
    header = text.split('---', 2)[1]
    assert 'name:' in header and 'description:' in header
print(f'PASS: {count} upstream file hashes; four skill frontmatters')

script = ROOT / 'third_party/grounded-citations/scripts/sources.py'
# Tests deliberately cannot write a live Hermes ledger. All runtime writes stay
# inside the permitted third_party subtree; the test directory is cleaned up.
with tempfile.TemporaryDirectory(prefix='.verification-', dir=ROOT / 'third_party') as td:
    tmp = Path(td)
    env = os.environ.copy()
    env['HERMES_HOME'] = str(tmp / 'isolated-home')
    env.pop('HERMES_CITATION_LEDGER', None)
    ledger = tmp / 'ledger.json'
    def run(*args, ok=True, explicit=True):
        cmd = [sys.executable, '-I', '-B', str(script)]
        if explicit:
            cmd += ['--ledger', str(ledger)]
        result = subprocess.run(cmd + list(args), env=env, capture_output=True, text=True)
        assert (result.returncode == 0) == ok, (args, result.stdout, result.stderr)
        return result.stdout
    run('reset')
    run('add', 'https://example.com/a', '--title', 'Fixture')
    run('add', 'https://example.com/a')
    assert len(json.loads(run('list', '--json'))) == 1
    page = tmp / 'page.txt'
    page.write_text('This is a controlled offline evidence fixture.', encoding='utf-8')
    draft = tmp / 'draft.md'
    draft.write_text('This is a controlled offline evidence fixture.[1]\n', encoding='utf-8')
    run('verify', str(draft), '--evidence', ok=False)
    run('quote', '1', '--text', 'This is a controlled offline evidence fixture.', '--from', str(page))
    run('quote', '1', '--text', 'Invented evidence.', '--from', str(page), ok=False)
    run('render', '--style', 'evidence', '--replace-in', str(draft))
    before = draft.read_bytes()
    run('render', '--style', 'evidence', '--replace-in', str(draft))
    assert draft.read_bytes() == before
    run('verify', str(draft), '--evidence', '--strict')
    draft.write_text('Unknown source supports this sentence.[999]\n', encoding='utf-8')
    run('verify', str(draft), ok=False)
    run('reset')
    assert json.loads(run('list', '--json')) == []
    # Python isolated mode omits the installed Hermes package: verify fallback.
    run('reset', explicit=False)
    assert (tmp / 'isolated-home/cache/citations/ledger.json').is_file()
    env['HERMES_CITATION_LEDGER'] = str(tmp / 'override.json')
    run('reset', explicit=False)
    assert (tmp / 'override.json').is_file()
print('PASS: reset/add/deduplicate/list/quote/render/verify/reset lifecycle; negative evidence and unknown-id gates; idempotent rendering; standalone Hermes-absent fallback; environment ledger override')
print('Prose-only Ponytail, Caveman, ML Paper Writing: no executable test applies.')
