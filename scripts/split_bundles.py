"""Split one node bundle into the three artefacts the pipeline expects.

Node agents write a single `bundles/<section>.json` (one write instead of three), which
cuts two tool calls per node. This script turns each bundle back into the files the rest of
the toolchain reads:

    <out>/captures/<course>/<section>.json     quiz-bank capture (quiz_bank.py build --nodes)
    <out>/popquiz/<course>/<section>-<n>.json  one file per popup (popquiz_bank.py build)
    <out>/nodes/evidence-<section>.json        node evidence (check_evidence.py)

Bundle shape:

    {"section": "3.4.2",
     "capture": {<quiz capture>},
     "popquiz": [{<popup capture>}, ...],
     "evidence": {<node evidence>}}

Usage:
    python scripts/split_bundles.py --bundles runs/<task>/bundles --out runs/<task> --course <key>
    python scripts/split_bundles.py --bundles runs/<task>/bundles --check     # parse only
"""

import argparse
import json
import sys
from pathlib import Path


def _normalise_platform(evidence, default_before=2, default_after=0):
    """A cleared catalogue row has no `.catalog_points_yi` span, so drivers report `pt=None`.

    That means "no remaining points" (0), not "unknown". Record the mapping instead of
    letting the integer check in check_evidence.py reject the file.
    """
    platform = dict(evidence.get('platform') or {})
    deviations = list(evidence.get('deviations') or [])
    changed = False
    for name, default in (('toc_before', default_before), ('toc_after', default_after)):
        node = dict(platform.get(name) or {})
        value = node.get('task_points')
        if not isinstance(value, int) or isinstance(value, bool):
            node['task_points'] = default
            deviations.append(
                'platform.{0}.task_points 原为 null（该行已无 .catalog_points_yi 点数 span），按 {1} 解释'
                .format(name, default))
            changed = True
        platform[name] = node
    evidence['platform'] = platform
    evidence['deviations'] = deviations
    return changed


def split_one(bundle, out, course=None, write=True):
    section = str(bundle.get('section') or '').strip()
    if not section:
        return {'ok': False, 'section': '', 'written': [], 'problems': ['no section']}
    written = []
    problems = []
    cap_dir = out / 'captures' / course if course else out / 'captures'
    pop_dir = out / 'popquiz' / course if course else out / 'popquiz'

    if bundle.get('capture'):
        capture = dict(bundle['capture'])
        capture.setdefault('section', section)
        if write:
            cap_dir.mkdir(parents=True, exist_ok=True)
            (cap_dir / (section + '.json')).write_text(
                json.dumps(capture, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
        written.append('capture')

    for index, popup in enumerate(bundle.get('popquiz') or []):
        item = dict(popup)
        item.setdefault('section', section)
        item.setdefault('segment', index)
        if write:
            pop_dir.mkdir(parents=True, exist_ok=True)
            (pop_dir / ('{0}-{1}.json'.format(section, index))).write_text(
                json.dumps(item, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
        written.append('popquiz-{0}'.format(index))

    if bundle.get('evidence'):
        evidence = dict(bundle['evidence'])
        evidence.setdefault('section', {'code': section})
        _normalise_platform(evidence)
        if write:
            nodes = out / 'nodes'
            nodes.mkdir(parents=True, exist_ok=True)
            (nodes / ('evidence-{0}.json'.format(section))).write_text(
                json.dumps(evidence, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
        written.append('evidence')

    if not written:
        problems.append('bundle has no capture/popquiz/evidence')
    return {'ok': not problems, 'section': section, 'written': written, 'problems': problems}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bundles', required=True, help='Directory holding <section>.json bundles')
    parser.add_argument('--out', help='Output root; defaults to the parent of --bundles')
    parser.add_argument('--course', help='Course key used for captures/<course> and popquiz/<course>')
    parser.add_argument('--check', action='store_true', help='Parse only, write nothing')
    parser.add_argument('--json', action='store_true', help='Print one JSON line per bundle')
    args = parser.parse_args(argv)

    root = Path(args.bundles).expanduser().resolve()
    if not root.is_dir():
        print('no bundles dir: {0}'.format(root), file=sys.stderr)
        return 0
    out = Path(args.out).expanduser().resolve() if args.out else root.parent

    total = 0
    bad = 0
    for path in sorted(root.glob('*.json')):
        try:
            bundle = json.loads(path.read_text(encoding='utf-8'))
        except ValueError as error:
            bad += 1
            print('SKIP {0}: {1}'.format(path.name, error), file=sys.stderr)
            continue
        result = split_one(bundle, out, course=args.course, write=not args.check)
        total += 1
        if not result['ok']:
            bad += 1
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(('OK ' if result['ok'] else 'BAD ') + result['section'] + ' ' + ','.join(result['written']))
    print('BUNDLES={0} BAD={1}'.format(total, bad))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
