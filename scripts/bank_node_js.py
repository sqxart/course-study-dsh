"""Materialise the per-node capture driver from references/bank.md.

The browser tool resolves `filename` against the browser profile root
(`~/.dsh/profiles/desktop`), so the driver can be loaded instead of pasted — no
copying of a 4 KB script per node, and one source of truth for the code.

    python scripts/bank_node_js.py --section 3.2.1 --course course-example \\
        --account account-c --channel mcp__browser3

Prints the path to pass as `filename` relative to the profile root (`bank/<name>.js`).
`--plan-json` writes one driver per section of a course plan in a single call.

Files are written as UTF-8 without BOM: a BOM in front of `async` reaches the browser
VM as a stray glyph (PowerShell's `Set-Content -Encoding utf8` adds one on 5.1).
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / 'references' / 'bank.md'
BLOCK = re.compile(r'```js\n(.*?)```', re.S)
CONST = re.compile(r"(const {key} = )'[^']*';")
PROFILE_ROOT = Path(os.path.expanduser('~')) / '.dsh' / 'profiles' / 'desktop'


def driver_source(path=DOC):
    match = BLOCK.search(Path(path).read_text(encoding='utf-8'))
    if not match:
        raise SystemExit('no ```js block in {0}'.format(path))
    return match.group(1).strip() + '\n'


def with_params(source, section, course, account, channel):
    values = {'SECTION': section, 'COURSE': course, 'ACCOUNT': account, 'CHANNEL': channel}
    result = source
    for key, value in values.items():
        pattern = CONST.pattern.format(key=key)
        if not re.search(pattern, result):
            raise SystemExit('driver lost its {0} constant'.format(key))
        result = re.sub(pattern, lambda match, v=value: "{0}'{1}';".format(match.group(1), v), result)
    return result


def write_driver(target, source):
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(source)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--section', help='Section code, e.g. 3.2.1')
    parser.add_argument('--course', required=True, help='Course key, e.g. course-example')
    parser.add_argument('--account', required=True, help='Account alias, e.g. account-c')
    parser.add_argument('--channel', required=True, help='Browser channel, e.g. mcp__browser3')
    parser.add_argument('--plan-json', help='Course plan from bank_plan.py; write one driver per section')
    parser.add_argument('--out-dir', default=str(PROFILE_ROOT / 'bank'))
    parser.add_argument('--doc', default=str(DOC))
    args = parser.parse_args(argv)

    base = driver_source(args.doc)
    out_dir = Path(args.out_dir)
    if args.plan_json:
        payload = json.loads(Path(args.plan_json).read_text(encoding='utf-8'))
        sections = [entry['section'] for entry in payload.get('sections', [])]
        if not sections:
            print('plan has no sections', file=sys.stderr)
            return 2
        written = []
        for section in sections:
            name = '{0}-{1}.js'.format(args.course, section)
            target = write_driver(out_dir / name, with_params(base, section, args.course, args.account, args.channel))
            written.append('bank/' + target.name)
        print('WROTE {0} drivers to {1}'.format(len(written), out_dir))
        print('\n'.join(written))
        return 0
    if not args.section:
        parser.error('--section is required without --plan-json')
    name = '{0}-{1}.js'.format(args.course, args.section)
    target = write_driver(out_dir / name, with_params(base, args.section, args.course, args.account, args.channel))
    print('bank/' + target.name)
    return 0


if __name__ == '__main__':
    sys.exit(main())
