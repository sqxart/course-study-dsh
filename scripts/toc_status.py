"""Read a course TOC from an accessibility snapshot and report unfinished task points.

The v24 catalogue renders each section as `link "1.3.2 照亮地球内部的明灯 1"`; the
trailing number is the count of unfinished task points. A section without the
number is fully complete. This is the cheapest completion check the platform
offers, and it must be read from a freshly loaded page.
"""

import argparse
import json
import re
import sys
from pathlib import Path

LINK = re.compile(r'^\s*-\s+link\s+"(\d+(?:\.\d+)*)\s+([^"]*)"')
TRAILING = re.compile(r'^(.*\S)\s+(\d+)$')
EXIT_UNFINISHED = 5


def parse_snapshot(text):
    """Return [{code, title, unfinished}] in document order, de-duplicated by code."""
    sections = []
    seen = {}
    for line in text.splitlines():
        match = LINK.match(line)
        if not match:
            continue
        code, rest = match.group(1), match.group(2).strip()
        if not rest:
            continue
        unfinished = 0
        tail = TRAILING.match(rest)
        if tail:
            rest, unfinished = tail.group(1).strip(), int(tail.group(2))
        if code in seen:
            continue
        record = {'code': code, 'title': rest, 'unfinished': unfinished}
        seen[code] = record
        sections.append(record)
    return sections


def summarize(sections):
    per_chapter = {}
    for section in sections:
        top = section['code'].split('.')[0]
        per_chapter.setdefault(top, {'sections': 0, 'unfinished_sections': 0, 'unfinished_tasks': 0})
        bucket = per_chapter[top]
        bucket['sections'] += 1
        if section['unfinished']:
            bucket['unfinished_sections'] += 1
            bucket['unfinished_tasks'] += section['unfinished']
    return {
        'sections': len(sections),
        'unfinished_sections': sum(1 for s in sections if s['unfinished']),
        'unfinished_tasks': sum(s['unfinished'] for s in sections),
        'chapters': per_chapter,
        'items': [s for s in sections if s['unfinished']],
    }


def filter_prefix(sections, prefix):
    return [s for s in sections if s['code'] == prefix or s['code'].startswith(prefix + '.')]


def brief(report):
    lines = ['SECTIONS={0} UNFINISHED_SECTIONS={1} UNFINISHED_TASKS={2}'.format(
        report['sections'], report['unfinished_sections'], report['unfinished_tasks'])]
    for item in report['items'][:40]:
        lines.append('{0:<10} {1:<44} {2}'.format(item['code'], item['title'][:44], item['unfinished']))
    if len(report['items']) > 40:
        lines.append('... {0} more'.format(len(report['items']) - 40))
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', help='Accessibility snapshot text file, or - for stdin')
    parser.add_argument('--prefix', help='Only sections under this code, e.g. 1.3')
    parser.add_argument('--json', action='store_true', help='Full JSON instead of the brief table')
    parser.add_argument('--fail-if-unfinished', action='store_true',
                        help='Exit 5 when any task point is still unfinished')
    args = parser.parse_args(argv)

    if args.snapshot == '-':
        text = sys.stdin.read()
    else:
        path = Path(args.snapshot)
        if not path.is_file():
            print(json.dumps({'status': 'error', 'error': 'snapshot not found: ' + str(path)}, ensure_ascii=False))
            return 2
        text = path.read_text(encoding='utf-8', errors='replace')

    sections = parse_snapshot(text)
    if not sections:
        print(json.dumps({'status': 'error', 'error': 'no section links found; snapshot may be a different page'},
                         ensure_ascii=False))
        return 2
    if args.prefix:
        sections = filter_prefix(sections, args.prefix)
    report = summarize(sections)
    report['status'] = 'ok'
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else brief(report))
    if args.fail_if_unfinished and report['unfinished_tasks']:
        return EXIT_UNFINISHED
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
