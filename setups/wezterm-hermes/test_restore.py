"""Execute the shipped Lua with real temp files and a stubbed WezTerm API.

No terminal, shell, agent, provider request or live profile is launched.
Install the optional test dependency in an isolated environment: lupa==2.8.
"""
import json
from pathlib import Path
import tempfile
import unittest

from lupa import LuaRuntime, lua_type

CONFIG = Path(__file__).with_name('wezterm.lua')


class Harness:
    def __init__(self, root, *, legacy=False, missing_home=False):
        self.root = Path(root)
        self.home = self.root / ('missing' if missing_home else 'profile')
        if not missing_home:
            (self.home / 'terminal-sessions').mkdir(parents=True, exist_ok=True)
        self.state = self.home / 'wezterm-tabs.json'
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.events = {}
        self.errors = []
        self.windows = []
        self.launches = []
        self.next_id = 0
        table = self.lua.table
        self.api = table()
        self.api.home_dir = self.root.as_posix()
        self.api.GLOBAL = table()
        self.api.config_builder = lambda: table()
        self.api.on = lambda name, handler: self.events.__setitem__(name, handler)
        self.api.log_error = self.errors.append
        codec = table(json_encode=lambda value: json.dumps(self.decode(value), sort_keys=True),
                      json_decode=lambda value: self.encode(json.loads(value)))
        if legacy:
            self.api.json_encode = codec.json_encode
            self.api.json_parse = codec.json_decode
        else:
            self.api.serde = codec
        self.api.mux = table(all_windows=lambda: self.encode(self.windows),
                             spawn_window=self.spawn_window)
        self.lua.globals().test_wezterm = self.api
        self.lua.globals().test_home = self.home.as_posix()
        self.lua.execute("package.preload['wezterm'] = function() return test_wezterm end; "
                         "os.getenv = function(key) if key == 'HERMES_HOME' then return test_home end end; "
                         "os.time = function() return 1000 end")
        self.config = self.lua.execute(CONFIG.read_text(encoding='utf-8'))

    def encode(self, value):
        if isinstance(value, dict):
            return self.lua.table_from({key: self.encode(item) for key, item in value.items()})
        if isinstance(value, (list, tuple)):
            return self.lua.table_from([self.encode(item) for item in value])
        return value

    def decode(self, value):
        if lua_type(value) != 'table':
            return value
        keys = list(value.keys())
        if keys and all(isinstance(key, int) for key in keys):
            return [self.decode(value[i]) for i in range(1, len(value) + 1)]
        return {key: self.decode(item) for key, item in value.items()}

    def pane(self, process='hermes.exe', *, active=True):
        pane_id = self.next_id
        self.next_id += 1
        pane = self.lua.table()
        pane.pane_id = lambda _self: pane_id
        pane.get_foreground_process_name = lambda _self: process
        pane.test_id = pane_id
        return self.lua.table(is_active=active, pane=pane)

    def tab(self, process='hermes.exe', *, extra_pane=False):
        infos = [self.pane(process)]
        if extra_pane:
            infos.append(self.pane('bash.exe', active=False))
        tab = self.lua.table()
        tab.panes_with_info = lambda _self: self.encode(infos)
        return tab, infos[0].pane

    def spawn_window(self, spec):
        window = self.lua.table()
        tabs = []
        window.tabs = lambda _self: self.encode(tabs)

        def spawn_tab(_self, command):
            args = self.decode(command['args']) if command['args'] else self.decode(self.config.default_prog)
            self.launches.append(args)
            tab, pane = self.tab(args[0])
            tabs.append(tab)
            return tab, pane

        window.spawn_tab = spawn_tab
        self.windows.append(window)
        tab, pane = spawn_tab(window, spec)
        return tab, pane, window

    def seed(self, value):
        self.state.write_text(json.dumps(value), encoding='utf-8')

    def breadcrumb(self, pane_id, session, ts=1000):
        path = self.home / 'terminal-sessions' / f'wezterm_pane-{pane_id}'
        path.write_text(json.dumps({'session_id': session, 'ts': ts}), encoding='utf-8')

    def start(self, command=None):
        self.events['gui-startup'](self.encode(command) if command is not None else None)

    def save(self):
        self.events['update-status']()

    def saved(self):
        return json.loads(self.state.read_text(encoding='utf-8'))


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lua-restore-')
        self.addCleanup(self.temp.cleanup)
        self.h = Harness(self.temp.name)

    def test_fresh_launch_and_defaults(self):
        self.h.start()
        self.assertEqual(self.h.launches, [['hermes']])
        self.assertEqual(self.h.decode(self.h.config.default_prog), ['hermes'])
        self.assertEqual(self.h.config.set_environment_variables.HERMES_HOME, self.h.home.as_posix())
        self.assertEqual(self.h.config.scrollback_lines, 5000)
        self.assertEqual(self.h.config.status_update_interval, 1000)

    def test_window_tab_order_and_argument_boundaries(self):
        self.h.seed([[{'kind': 'hermes', 'session': 'demo-first'}, {'kind': 'bash'},
                      {'kind': 'powershell'}], [{'kind': 'hermes', 'session': 'demo-second'}]])
        self.h.start()
        self.assertEqual(len(self.h.windows), 2)
        self.assertEqual(self.h.launches, [['hermes', '--resume', 'demo-first'],
                         ['C:/Program Files/Git/bin/bash.exe', '-l'],
                         ['powershell.exe', '-NoLogo'], ['hermes', '--resume', 'demo-second']])

    def test_save_restart_session_change_and_closed_tab(self):
        self.h.start()
        self.h.windows[0].spawn_tab(self.h.windows[0], self.h.encode({'args': ['hermes']}))
        self.h.breadcrumb(0, 'demo-first')
        self.h.breadcrumb(1, 'demo-second')
        self.h.save()
        self.assertEqual(self.h.saved(), [[{'kind': 'hermes', 'session': 'demo-first'},
                                         {'kind': 'hermes', 'session': 'demo-second'}]])
        restarted = Harness(self.temp.name)
        restarted.start()
        self.assertEqual(restarted.launches, [['hermes', '--resume', 'demo-first'],
                                              ['hermes', '--resume', 'demo-second']])
        restarted.breadcrumb(0, 'demo-new')
        # Remove the second tab from the host-side view, as if the user closed it.
        first = restarted.windows[0].tabs(restarted.windows[0])[1]
        restarted.windows[0].tabs = lambda _self: restarted.encode([first])
        restarted.save()
        self.assertEqual(restarted.saved(), [[{'kind': 'hermes', 'session': 'demo-new'}]])

    def test_restored_fallback_survives_stale_pane_id(self):
        self.h.seed([[{'kind': 'hermes', 'session': 'demo-restored'}]])
        self.h.breadcrumb(0, 'demo-stale', ts=900)
        self.h.start()
        self.h.save()
        self.assertEqual(self.h.saved()[0][0]['session'], 'demo-restored')
        self.h.breadcrumb(0, 'demo-current')
        self.h.save()
        self.assertEqual(self.h.saved()[0][0]['session'], 'demo-current')

    def test_fresh_pane_rejects_old_breadcrumb(self):
        self.h.breadcrumb(0, 'demo-stale', ts=900)
        self.h.start()
        self.h.save()
        self.assertEqual(self.h.saved(), [[{'kind': 'hermes'}]])

    def test_corrupt_and_invalid_snapshots_start_fresh(self):
        invalid = ['not-json', '{}', '[]', '[[]]', '[[false]]',
                   '[[{"kind":"arbitrary"}]]', '[[{"kind":"hermes","session":false}]]',
                   '[[{"kind":"hermes","session":"--unsafe argument"}]]',
                   '[[{"kind":"bash","session":"demo-first"}]]']
        for raw in invalid:
            with self.subTest(raw=raw):
                h = Harness(self.temp.name)
                h.state.write_text(raw, encoding='utf-8')
                h.start()
                self.assertEqual(h.launches, [['hermes']])

    def test_explicit_command_bypasses_restoration(self):
        self.h.seed([[{'kind': 'hermes', 'session': 'demo-old'}]])
        self.h.start({'args': ['powershell.exe', '-NoLogo']})
        self.assertEqual(self.h.launches, [['powershell.exe', '-NoLogo']])

    def test_only_active_pane_and_shutdown_preserves_snapshot(self):
        self.h.start()
        tab, _pane = self.h.tab(extra_pane=True)
        self.h.windows[0].tabs = lambda _self: self.h.encode([tab])
        self.h.save()
        self.assertEqual(self.h.saved(), [[{'kind': 'hermes'}]])
        before = self.h.state.read_bytes()
        self.h.windows.clear()
        self.h.save()
        self.assertEqual(self.h.state.read_bytes(), before)

    def test_shell_detection(self):
        self.h.start()
        tabs = [self.h.tab(name)[0] for name in ('bash.exe', 'pwsh.exe', 'python.exe')]
        self.h.windows[0].tabs = lambda _self: self.h.encode(tabs)
        self.h.save()
        self.assertEqual(self.h.saved(), [[{'kind': 'bash'}, {'kind': 'powershell'}, {'kind': 'hermes'}]])

    def test_legacy_json_api_and_tab_title(self):
        h = Harness(self.temp.name, legacy=True)
        h.start()
        h.breadcrumb(0, 'demo-legacy')
        h.save()
        self.assertEqual(h.saved()[0][0]['session'], 'demo-legacy')
        title = h.events['format-tab-title'](h.encode({'tab_index': 2, 'active_pane': {'title': 'python.exe'}}))
        self.assertEqual(title, ' 3: Hermes ')

    def test_bad_breadcrumb_does_not_crash(self):
        self.h.start()
        path = self.h.home / 'terminal-sessions/wezterm_pane-0'
        for raw in ('broken', 'false', '{"session_id":false,"ts":1000}',
                    '{"session_id":"demo-invalid"}'):
            with self.subTest(raw=raw):
                path.write_text(raw, encoding='utf-8')
                self.h.save()
                self.assertEqual(self.h.saved(), [[{'kind': 'hermes'}]])

    def test_separate_profile_snapshots_do_not_cross(self):
        a = Harness(Path(self.temp.name) / 'a')
        b = Harness(Path(self.temp.name) / 'b')
        a.start()
        b.start()
        a.breadcrumb(0, 'demo-profile-a')
        b.breadcrumb(0, 'demo-profile-b')
        a.save()
        b.save()
        again = Harness(Path(self.temp.name) / 'a')
        again.start()
        self.assertEqual(again.launches, [['hermes', '--resume', 'demo-profile-a']])
        self.assertEqual(b.saved()[0][0]['session'], 'demo-profile-b')

    def test_save_error_is_logged_and_retry_recovers(self):
        h = Harness(self.temp.name, missing_home=True)
        h.start()
        h.save()
        self.assertEqual(len(h.errors), 1)
        self.assertIn('Cannot save tab snapshot', h.errors[0])
        self.assertIsNone(h.api.GLOBAL.last_saved)
        h.home.mkdir()
        h.save()
        self.assertEqual(h.saved(), [[{'kind': 'hermes'}]])


if __name__ == '__main__':
    unittest.main(verbosity=2)
