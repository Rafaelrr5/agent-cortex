"""Check the real installed Hermes breadcrumb writer against the shipped Lua.

Only fixture files are written. This does not open a GUI or call an LLM.
The child Python must have Hermes and its dependencies available.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_restore import Harness


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', required=True, help='Python executable with Hermes installed')
    parser.add_argument('--source', type=Path, help='Hermes source checkout, if not importable otherwise')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='native-crumb-') as root:
        harness = Harness(root)
        env = os.environ.copy()
        env['HERMES_HOME'] = str(harness.home)
        env['WEZTERM_PANE'] = '0'
        for key in ('ZELLIJ_PANE_ID', 'TMUX_PANE', 'KITTY_WINDOW_ID', 'TERM_SESSION_ID', 'WT_SESSION'):
            env.pop(key, None)
        code = (
            "from hermes_cli.terminal_breadcrumbs import get_terminal_id, write_breadcrumb; "
            "assert get_terminal_id() == 'wezterm_pane-0', get_terminal_id(); "
            "write_breadcrumb('demo-native', cwd='fixture-workspace')"
        )
        result = subprocess.run(
            [args.python, '-X', 'utf8', '-B', '-c', code],
            cwd=args.source, env=env, capture_output=True, text=True, encoding='utf-8',
            timeout=60, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if result.returncode:
            raise RuntimeError('Native breadcrumb probe failed: ' + result.stderr)
        harness.start()
        harness.save()
        assert harness.saved() == [[{'kind': 'hermes', 'session': 'demo-native'}]], harness.saved()
        restarted = Harness(root)
        restarted.start()
        assert restarted.launches == [['hermes', '--resume', 'demo-native']], restarted.launches
        print('PASS: native Hermes breadcrumb -> Lua snapshot -> restart --resume argv')
        print('No GUI, agent session or provider request was launched.')


if __name__ == '__main__':
    main()
