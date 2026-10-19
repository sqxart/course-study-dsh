"""Build an independent install or a public export; never touches old skills."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
SKILL_NAME = 'course-study-dsh'
VERSION = '1.0.0'
PUBLIC = ('SKILL.md', 'README.md', 'ACCEPTANCE.md', 'NOTICE', 'LICENSE', '.gitignore', 'install.ps1', 'private.toml.example',
          'requirements.txt', 'requirements-ocr.txt', 'references', 'scripts', 'tests')
LOCAL_METADATA = ('homework-profile.md', 'legacy-paths.json', 'runtime.json')


def files():
    result = []
    for name in PUBLIC:
        path = ROOT / name
        candidates = [path] if path.is_file() else sorted(path.rglob('*')) if path.is_dir() else []
        for candidate in candidates:
            relative = candidate.relative_to(ROOT)
            if candidate.is_file() and '__pycache__' not in relative.parts and '.pytest_cache' not in relative.parts and candidate.suffix != '.pyc':
                if candidate.is_symlink():
                    raise ValueError('Public packages do not follow symlink resources: ' + str(relative))
                result.append((candidate, relative))
    return result


def public_scan(entries, denylist):
    findings = []
    for path, relative in entries:
        if path.suffix.lower() not in ('.md', '.py', '.js', '.mjs', '.json', '.yaml', '.yml', '.txt'):
            continue
        text = path.read_text(encoding='utf-8-sig')
        # These are only basic checks. Personal names/class/student ids require
        # an explicit local denylist and review of the exported files.
        for label, pattern in (
            ('personal-windows-path', r'[A-Za-z]:[\\/]Users[\\/](?!<|\{|\$)[A-Za-z0-9_.-]+'),
            ('phone-number', r'(?<!\d)1[3-9]\d{9}(?!\d)'),
            ('email', r'\b[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
        ):
            if re.search(pattern, text):
                findings.append({'path': str(relative), 'kind': label})
        for value in denylist:
            if value in text:
                findings.append({'path': str(relative), 'kind': 'local-denylist-match'})
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    export = sub.add_parser('export')
    export.add_argument('--out', required=True)
    export.add_argument('--denylist', help='Local JSON array of names, ids or secrets to reject; values never printed')
    install = sub.add_parser('install')
    install.add_argument('--target', required=True)
    install.add_argument('--include-local', action='store_true', help='Include only private location/config metadata, never credentials or profiles')
    install.add_argument('--force', action='store_true',
                         help='Reinstall over an existing installation: replace managed files, keep local/ data, rewrite the manifest')
    args = parser.parse_args(argv)
    try:
        output = Path(args.out if args.command == 'export' else args.target).expanduser().resolve()
        if output == ROOT or ROOT in output.parents and not (ROOT / 'dist') in output.parents:
            raise ValueError('Choose an independent output directory, or a new directory under dist/')
        if args.command == 'install' and output.name != SKILL_NAME:
            raise ValueError('Install target must be a new ' + SKILL_NAME + ' directory')
        if output.exists() and not output.is_dir():
            raise ValueError('Install target exists and is not a directory')
        nonempty = output.is_dir() and any(output.iterdir())
        if nonempty and not (args.command == 'install' and args.force):
            raise ValueError('Refusing to overwrite an existing installation or nonempty output; pass --force to reinstall')
        entries = files()
        denylist = []
        if args.command == 'export':
            if args.denylist:
                denylist = json.loads(Path(args.denylist).read_text(encoding='utf-8-sig'))
                if not isinstance(denylist, list) or any(not isinstance(v, str) or not v for v in denylist):
                    raise ValueError('denylist must be a JSON array of nonempty strings')
            findings = public_scan(entries, denylist)
            if findings:
                print(json.dumps({'status': 'blocked', 'findings': findings}, ensure_ascii=False, indent=2))
                return 2
        elif args.include_local:
            for name in LOCAL_METADATA:
                path = ROOT / 'local' / name
                if path.is_file():
                    entries.append((path, path.relative_to(ROOT)))
        old_paths = []
        old_manifest_path = output / 'package-manifest.json'
        if nonempty and args.force and old_manifest_path.is_file():
            try:
                old_manifest = json.loads(old_manifest_path.read_text(encoding='utf-8-sig'))
                old_paths = [item.get('path') for item in old_manifest.get('files', []) if isinstance(item, dict)]
            except (OSError, json.JSONDecodeError):
                old_paths = []
        output.mkdir(parents=True, exist_ok=True)
        records = []
        for source, relative in entries:
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            records.append({'path': relative.as_posix(), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
        if old_paths:
            keep = {record['path'] for record in records}
            for relative in old_paths:
                if not relative or relative in keep:
                    continue
                stale = (output / relative).resolve()
                if output.resolve() in stale.parents and stale.is_file():
                    stale.unlink()
        if args.command == 'install':
            local_dir = output / 'local'
            local_dir.mkdir(exist_ok=True)
            config = local_dir / 'private.toml'
            example = output / 'private.toml.example'
            if not config.exists() and example.is_file():
                shutil.copy2(example, config)
        manifest = {'skill': SKILL_NAME, 'version': VERSION,
                    'kind': args.command, 'includes_private_metadata': args.command == 'install' and args.include_local,
                    'files': records,
                    'note': 'Public export excludes local/runs/profiles/validation. Basic scans do not replace manual identity/secret review. No GitHub upload.'}
        (output / 'package-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({'status': 'ok', 'command': args.command, 'files': len(records),
                          'output': str(output), 'uploaded': False}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())

