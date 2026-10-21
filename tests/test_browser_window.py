"""Keep only the DSH-managed browser window in check — never the user's own browser."""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location('browser_window', ROOT / 'scripts' / 'browser_window.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


window = load()


class ProfileTest(unittest.TestCase):
    def test_user_data_dir_is_read_from_the_command_line(self):
        command = '"C:/Program Files/Google/Chrome/Application/chrome.exe" --user-data-dir=C:/data/.dsh/browser/chrome-course --no-first-run'
        self.assertEqual(window.profile_dir(command), 'C:/data/.dsh/browser/chrome-course')

    def test_backslashes_are_normalised(self):
        command = 'chrome.exe --user-data-dir="C:\\data\\.dsh\\browser\\chrome-clean" --other'
        self.assertEqual(window.profile_dir(command), 'C:/data/.dsh/browser/chrome-clean')

    def test_a_browser_without_the_flag_is_ignored(self):
        self.assertIsNone(window.profile_dir('chrome.exe --no-first-run'))


class PickTest(unittest.TestCase):
    def rows(self):
        return [
            {'pid': 1, 'hwnd': 11, 'title': '课程', 'command_line': 'chrome.exe --user-data-dir=C:/data/.dsh/browser/chrome-course'},
            {'pid': 2, 'hwnd': 22, 'title': '我的浏览器', 'command_line': 'chrome.exe --user-data-dir=C:/data/AppData/Local/Google/Chrome'},
            {'pid': 3, 'hwnd': 0, 'title': '', 'command_line': 'chrome.exe --user-data-dir=C:/data/.dsh/browser/chrome-clean'},
        ]

    def test_only_dsh_windows_with_a_handle_are_picked(self):
        picked = window.pick(self.rows(), '.dsh')
        self.assertEqual([row['pid'] for row in picked], [1])
        self.assertEqual(picked[0]['profile'], 'C:/data/.dsh/browser/chrome-course')

    def test_the_marker_can_narrow_to_one_profile(self):
        picked = window.pick(self.rows(), 'chrome-clean')
        self.assertEqual(picked, [])


class FakeUser32:
    def __init__(self, foreground=11, iconic=False):
        self.foreground = foreground
        self.iconic = iconic
        self.calls = []

    def GetForegroundWindow(self):
        return self.foreground

    def IsIconic(self, hwnd):
        return self.iconic

    def ShowWindow(self, hwnd, command):
        self.calls.append((hwnd, command))
        self.iconic = True


class WatchTest(unittest.TestCase):
    def test_the_foreground_dsh_window_is_minimised_then_left_alone(self):
        user32 = FakeUser32(foreground=11)
        ticks = {'now': 0.0}

        def clock():
            return ticks['now']

        def sleep(seconds):
            ticks['now'] += seconds

        rows = [{'pid': 1, 'hwnd': 11, 'title': '课程', 'command_line': 'chrome.exe --user-data-dir=C:/data/.dsh/browser/chrome-course'}]
        events = window.watch('.dsh', minutes=0.05, interval=1.0, user32=user32,
                              sleep=sleep, clock=clock, lister=lambda: rows)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['hwnd'], 11)
        self.assertEqual(int(user32.calls[0][0].value), 11)

    def test_a_foreign_window_is_never_minimised(self):
        user32 = FakeUser32(foreground=999)
        ticks = {'now': 0.0}
        rows = [{'pid': 1, 'hwnd': 11, 'title': '课程', 'command_line': 'chrome.exe --user-data-dir=C:/data/.dsh/browser/chrome-course'}]
        events = window.watch('.dsh', minutes=0.02, interval=1.0, user32=user32,
                              sleep=lambda s: ticks.update(now=ticks['now'] + s),
                              clock=lambda: ticks['now'], lister=lambda: rows)
        self.assertEqual(events, [])
        self.assertEqual(user32.calls, [])


if __name__ == '__main__':
    unittest.main()
