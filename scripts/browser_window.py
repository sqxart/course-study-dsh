"""Keep the DSH-managed browser window out of the way.

Playwright navigation can raise the browser window to the foreground, which steals focus from
whatever the user is doing. This finds the window of *our* browser — the one whose command line
carries a DSH profile directory — and can minimise or restore it.

    python scripts/browser_window.py list
    python scripts/browser_window.py minimize            # every DSH-managed browser window
    python scripts/browser_window.py minimize --profile chrome-course
    python scripts/browser_window.py restore --profile chrome-course

Only windows whose process command line contains `--user-data-dir=` **and** the profile marker
(`.dsh` by default) are touched, so the user's own Chrome/Edge windows are never moved.

Caveats (verified 2026-10-21):

- The **new** player keeps playing while minimised; the **old** one pauses when the window loses
  focus, so do not minimise while an old-player video is running.
- Screenshots still work while minimised on this machine, but if a capture comes back blank,
  restore first and re-take it.
"""

import argparse
import ctypes
import json
import shutil
import subprocess
import sys

SW_MINIMIZE = 6
SW_RESTORE = 9
BROWSER_EXES = ('chrome.exe', 'msedge.exe', 'chromium.exe', 'brave.exe')


def profile_dir(command_line):
    """`--user-data-dir=...` from a process command line, normalised to forward slashes."""
    if not command_line:
        return None
    for token in command_line.split('" '):
        marker = '--user-data-dir='
        index = token.find(marker)
        if index >= 0:
            value = token[index + len(marker):].strip().strip('"')
            value = value.split(' ')[0]
            return value.replace('\\', '/')
    return None


def pick(rows, marker):
    """Rows that are top-level windows of a DSH-managed browser."""
    picked = []
    for row in rows:
        directory = profile_dir(row.get('command_line'))
        if not directory or marker.lower() not in directory.lower():
            continue
        if not row.get('hwnd'):
            continue
        picked.append({'pid': row.get('pid'), 'hwnd': row['hwnd'],
                       'title': row.get('title'), 'profile': directory})
    return picked


def watch(marker, minutes=60.0, interval=1.0, user32=None, sleep=None, clock=None, lister=None):
    """Keep DSH browser windows minimised for a while: whenever one comes to the front, drop it back.

    The window list is refreshed every 30 iterations so a freshly opened window is caught too;
    between refreshes only GetForegroundWindow/IsIconic are polled, which is cheap.
    """
    import time
    user32 = user32 or (ctypes.windll.user32 if sys.platform == 'win32' else None)
    sleep = sleep or time.sleep
    clock = clock or time.time
    lister = lister or windows
    if user32 is None:
        return []
    deadline = clock() + minutes * 60
    seen, events, ticks = set(), [], 0
    while clock() < deadline:
        if ticks % 30 == 0 or not seen:
            seen = {window['hwnd'] for window in pick(lister(), marker)}
        foreground = int(user32.GetForegroundWindow())
        if foreground in seen and not user32.IsIconic(ctypes.c_void_p(foreground)):
            user32.ShowWindow(ctypes.c_void_p(foreground), SW_MINIMIZE)
            events.append({'hwnd': foreground, 'at': round(clock(), 1)})
        ticks += 1
        sleep(interval)
    return events


def shell():
    """Windows PowerShell 5.1 often has no `pwsh`; use whichever exists."""
    for candidate in ('pwsh', 'powershell', 'powershell.exe'):
        path = shutil.which(candidate)
        if path:
            return path
    return 'powershell.exe'


def windows():
    """Top-level browser windows with their owning command line (one PowerShell round-trip)."""
    script = (
        '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; '
        '$cmds = @{}; '
        'Get-CimInstance Win32_Process | Where-Object { $_.Name -match "^(chrome|msedge|chromium|brave)\\.exe$" } '
        '| ForEach-Object { $cmds[[int]$_.ProcessId] = $_.CommandLine }; '
        'Get-Process | Where-Object { $_.MainWindowHandle -ne 0 -and $_.ProcessName -match "^(chrome|msedge|chromium|brave)$" } '
        '| ForEach-Object { [pscustomobject]@{ pid = $_.Id; hwnd = $_.MainWindowHandle.ToInt64(); '
        'title = $_.MainWindowTitle; command_line = $cmds[[int]$_.Id] } } | ConvertTo-Json -Compress'
    )
    listing = subprocess.run([shell(), '-NoProfile', '-Command', script],
                             capture_output=True, text=True, encoding='utf-8', errors='replace')
    if listing.returncode != 0 or not listing.stdout.strip():
        return []
    found = json.loads(listing.stdout)
    if isinstance(found, dict):
        found = [found]
    return found


def apply(action, marker, dry_run=False):
    user32 = ctypes.windll.user32 if sys.platform == 'win32' else None
    chosen = pick(windows(), marker)
    done = []
    for window in chosen:
        if user32 is None:
            window['action'] = 'unsupported-platform'
            done.append(window)
            continue
        command = SW_MINIMIZE if action == 'minimize' else SW_RESTORE
        if not dry_run:
            user32.ShowWindow(ctypes.c_void_p(window['hwnd']), command)
        window['action'] = action if not dry_run else 'dry-run'
        window['iconic'] = bool(user32.IsIconic(ctypes.c_void_p(window['hwnd'])))
        done.append(window)
    return done


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('list', 'minimize', 'restore', 'watch'):
        command = sub.add_parser(name)
        command.add_argument('--profile', default='.dsh',
                             help='Substring of the profile dir to match (default: .dsh)')
        command.add_argument('--dry-run', action='store_true')
        command.add_argument('--json', action='store_true', help='Print JSON instead of a summary')
        if name == 'watch':
            command.add_argument('--minutes', type=float, default=60.0, help='How long to keep watching')
            command.add_argument('--interval', type=float, default=1.0, help='Poll interval in seconds')
    args = parser.parse_args(argv)

    if args.command == 'list':
        user32 = ctypes.windll.user32 if sys.platform == 'win32' else None
        chosen = pick(windows(), args.profile)
        for window in chosen:
            window['iconic'] = bool(user32.IsIconic(ctypes.c_void_p(window['hwnd']))) if user32 else None
        if args.json:
            print(json.dumps(chosen, ensure_ascii=False, indent=1))
        else:
            for window in chosen:
                print('pid={pid} hwnd={hwnd} iconic={iconic} profile={profile} title={title}'.format(**window))
            if not chosen:
                print('no DSH-managed browser window found (marker: {0})'.format(args.profile))
        return 0

    if args.command == 'watch':
        events = watch(args.profile, minutes=args.minutes, interval=args.interval)
        print(json.dumps({'minimized': len(events), 'events': events[-20:]}, ensure_ascii=False))
        return 0

    done = apply(args.command, args.profile, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(done, ensure_ascii=False, indent=1))
    else:
        for window in done:
            print('{action} pid={pid} profile={profile} iconic={iconic}'.format(**window))
        if not done:
            print('nothing to do (marker: {0})'.format(args.profile))
    return 0


if __name__ == '__main__':
    sys.exit(main())
