"""Draw up the per-course section plan the question bank is expected to cover.

Two local records disagree about the past: the run ledger (`progress.json`) knows every
node that was completed, while the evidence files are missing the ones an overwriting
write destroyed. So the ledger is the coverage baseline and evidence is only used to
attach `work_id` / `score` / `question_count` for a later cross-check.

    runs/<task>/expected-<key>.json   sorted section codes — the coverage baseline
    runs/<task>/plan-<key>.json       per-section record: account, title, evidence values

Usage:
    python scripts/bank_plan.py \\
      --plan silk-road=account-a@runs/full-20261021/progress.json \\
      --plan course-example=account-c@runs/full-20261021/progress.json \\
      --plan lang-culture=account-c@runs/lang-culture-20261021/progress.json \\
      --course 无人驾驶车辆=course-example \\
      --evidence runs/full-20261021 runs/lang-culture-20261021 \\
      --out-dir runs/bank
"""

import argparse
import glob
import json
import os
import re
import sys


def sort_key(section):
    return [int(part) for part in re.findall(r'\d+', str(section))]


def read_ledger(path, account):
    """Return {section: record} for one account's nodes.

    Two ledger shapes exist in this repository: the multi-account run keys `nodes` by
    `account:section` and carries an `account` field, while the single-account run keys
    `detail` by section and has no account at all. `account` is only a filter when the
    ledger actually names accounts.
    """
    payload = json.load(open(path, encoding='utf-8'))
    raw = payload.get('nodes')
    if not isinstance(raw, dict):
        raw = payload.get('detail')
    if not isinstance(raw, dict):
        raw = {}
    sections = {}
    for node in raw.values():
        if not isinstance(node, dict) or not node.get('code'):
            continue
        if node.get('account') and account and node['account'] != account:
            continue
        sections[node['code']] = {
            'section': node['code'],
            'section_title': node.get('title'),
            'account': node.get('account') or account,
            'ledger_status': node.get('status'),
            'ledger_score': node.get('score'),
            'ledger_questions': node.get('questions'),
            'ledger_work_id': node.get('work_id'),
            'ledger_evidence': node.get('evidence'),
        }
    return sections


def read_evidence(paths):
    records = []
    for run in paths:
        for path in sorted(glob.glob(os.path.join(run, 'evidence-*.json'))):
            try:
                payload = json.load(open(path, encoding='utf-8'))
            except (OSError, ValueError):
                continue
            quiz = payload.get('quiz') or {}
            section = (payload.get('section') or {}).get('code')
            course = (payload.get('course') or {}).get('title')
            if not section or not course:
                continue
            records.append({
                'course': course, 'section': section,
                'work_id': quiz.get('work_id'), 'question_count': quiz.get('question_count'),
                'score': quiz.get('score'), 'file': os.path.basename(path),
            })
    return records


def attach_evidence(plan, course_key, records, mapping):
    """Copy work_id/score onto the plan when evidence for (course, section) exists."""
    by_section = {}
    for record in records:
        if mapping.get(record['course']) != course_key:
            continue
        previous = by_section.get(record['section'])
        if previous is None or (record['score'] or 0) > (previous['score'] or 0):
            by_section[record['section']] = record
    matched = 0
    for section, entry in plan.items():
        record = by_section.get(section)
        if not record:
            entry['evidence'] = None
            continue
        matched += 1
        entry['work_id'] = record['work_id']
        entry['evidence_score'] = record['score']
        entry['evidence_questions'] = record['question_count']
        entry['evidence_file'] = record['file']
        entry['evidence'] = record['file']
    return matched


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--plan', action='append', default=[], metavar='KEY=ACCOUNT@LEDGER',
                        help='One course: bank key, ledger account alias, ledger path')
    parser.add_argument('--course', action='append', default=[], metavar='TITLE=KEY',
                        help='Map an evidence course title to its bank key')
    parser.add_argument('--title', action='append', default=[], metavar='KEY=TITLE',
                        help='Human course title for the markdown header')
    parser.add_argument('--evidence', nargs='*', default=[], help='Run directories with evidence-*.json')
    parser.add_argument('--out-dir', default='runs/bank')
    args = parser.parse_args(argv)

    mapping = {}
    for entry in args.course:
        title, key = entry.split('=', 1)
        mapping[title.strip()] = key.strip()
    titles = {}
    for entry in args.title:
        key, title = entry.split('=', 1)
        titles[key.strip()] = title.strip()

    if not args.plan:
        parser.error('at least one --plan KEY=ACCOUNT@LEDGER is required')
    records = read_evidence(args.evidence)
    os.makedirs(args.out_dir, exist_ok=True)
    failures = 0
    for entry in args.plan:
        try:
            key, rest = entry.split('=', 1)
            account, ledger = rest.split('@', 1)
        except ValueError:
            parser.error('--plan needs KEY=ACCOUNT@LEDGER, got ' + entry)
        plan = read_ledger(ledger, account)
        if not plan:
            print('EMPTY {0}: no {1} nodes in {2}'.format(key, account, ledger), file=sys.stderr)
            failures += 1
            continue
        matched = attach_evidence(plan, key, records, mapping)
        codes = sorted(plan, key=sort_key)
        expected = os.path.join(args.out_dir, 'expected-{0}.json'.format(key))
        detailed = os.path.join(args.out_dir, 'plan-{0}.json'.format(key))
        with open(expected, 'w', encoding='utf-8') as handle:
            json.dump(codes, handle, ensure_ascii=False, indent=1)
        payload = {'key': key, 'title': titles.get(key), 'account': account, 'ledger': ledger,
                   'sections': [plan[code] for code in codes]}
        with open(detailed, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=1)
        scores = [plan[code].get('evidence_score') for code in codes]
        print('{key:<14} sections={s:<4} evidence={m:<4} full_marks={f:<4} questions={q}'.format(
            key=key, s=len(codes), m=matched, f=scores.count(100),
            q=sum(plan[code].get('evidence_questions') or 0 for code in codes)))
        if matched < len(codes):
            missing = [code for code in codes if not plan[code].get('evidence')]
            print('  evidence missing for {0}: {1}'.format(len(missing), ' '.join(missing[:30])))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
