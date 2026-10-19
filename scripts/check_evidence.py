"""Check one node evidence file before reporting.

Evidence is written by the executor before it returns; this validator keeps the
record honest and machine-readable. It does not talk to the platform and it
cannot prove a submission happened or did not happen -- it checks the claims
that the platform reads were written down, and that an evidence-mode run does
not claim a submission.

Usage:

    python scripts/check_evidence.py runs/<task>/evidence.json
    python scripts/check_evidence.py runs/<task>/evidence.json --require-readonly
    python scripts/check_evidence.py runs/<task>/evidence.json --allow-incomplete --json
"""

import argparse
import json
import re
import sys
from pathlib import Path

SECTION_CODE = re.compile(r'^\d+(?:\.\d+)*$')
RATE_SOURCES = {'menu', 'property', 'rejected', 'locked'}
MODES = {'evidence', 'completion'}
PLATFORM_STATUSES = {'已查看', '未查看', '已完成'}
EXIT_INVALID = 5


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _get(record, path):
    current = record
    for part in path.split('.'):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def validate(record, require_readonly=False, allow_incomplete=False):
    errors = []
    warnings = []

    if not isinstance(record, dict):
        return ['evidence must be a JSON object'], warnings

    def need(path, predicate, message):
        value = _get(record, path)
        if value is None or not predicate(value):
            errors.append('{0}: {1}'.format(path, message))

    need('schema_version', lambda value: _is_int(value) and value >= 1, 'expected an integer >= 1')
    need('mode', lambda value: value in MODES, 'expected evidence or completion')
    need('course.title', _text, 'expected a non-empty title')
    need('course.course_id', lambda value: _is_int(value) or _text(value), 'expected a course id')
    need('section.code', lambda value: _text(value) and SECTION_CODE.match(value), 'expected a code such as 1.2.1')
    need('section.title', _text, 'expected a non-empty title')

    need('video.duration_seconds', lambda value: _is_number(value) and value > 0, 'expected seconds > 0')
    need('video.rate', lambda value: _is_number(value) and value > 0, 'expected a positive rate')
    need('video.rate_source', lambda value: value in RATE_SOURCES, 'expected one of ' + ', '.join(sorted(RATE_SOURCES)))
    if not allow_incomplete:
        need('video.ended', lambda value: value is True, 'expected true after a complete watch (use --allow-incomplete to skip)')
    if _get(record, 'video.observer_calls') is not None:
        need('video.observer_calls', lambda value: _is_int(value) and value >= 0, 'expected an integer >= 0')

    authorization = _get(record, 'authorization')
    if not isinstance(authorization, dict):
        errors.append('authorization: expected an object with submit/redo_once')
    else:
        need('authorization.submit', lambda value: isinstance(value, bool), 'expected true or false')

    submitted = _get(record, 'quiz.submitted')
    if not isinstance(submitted, bool):
        errors.append('quiz.submitted: expected true or false')
    mode = _get(record, 'mode')
    submit_allowed = isinstance(authorization, dict) and authorization.get('submit') is True
    if isinstance(submitted, bool) and (mode == 'evidence' or not submit_allowed):
        if submitted:
            errors.append('quiz.submitted: must be false in evidence mode / without submit authorization')
        decision = _get(record, 'quiz.decision')
        if decision != 'do-not-submit':
            errors.append('quiz.decision: expected do-not-submit in evidence mode / without submit authorization')
    if require_readonly:
        need('quiz.options_clicked', lambda value: _is_int(value) and value == 0, 'expected integer 0 in a read-only quiz pass')
        need('quiz.submit_clicked', lambda value: _is_int(value) and value == 0, 'expected integer 0 in a read-only quiz pass')
        need('quiz.reopened', lambda value: value is False, 'expected false; do not reopen an attempt')
        if submitted:
            errors.append('quiz.submitted: a read-only pass cannot submit')

    quiz = _get(record, 'quiz')
    if isinstance(quiz, dict):
        status = quiz.get('platform_status')
        if status is not None and (not isinstance(status, str) or status not in PLATFORM_STATUSES):
            warnings.append('quiz.platform_status={0!r}: expected 已查看, 未查看 or 已完成'.format(status))
        if mode == 'evidence' and status is None and quiz.get('work_answer_id'):
            warnings.append('quiz.platform_status: record 已查看/未查看 from 学习记录 for an opened quiz')
        add_times = quiz.get('add_times')
        if add_times is not None and not (_is_int(add_times) and add_times >= 0):
            errors.append('quiz.add_times: expected an integer >= 0')
        limit = quiz.get('limit_work_submit_times')
        if limit is not None and not (_is_int(limit) and limit >= 1):
            errors.append('quiz.limit_work_submit_times: expected an integer >= 1')

    need('platform.toc_before.task_points', lambda value: _is_int(value) and value >= 0, 'expected an integer >= 0')
    need('platform.toc_after.task_points', lambda value: _is_int(value) and value >= 0, 'expected an integer >= 0')
    before = _get(record, 'platform.toc_before.task_points')
    after = _get(record, 'platform.toc_after.task_points')
    if _is_int(before) and _is_int(after):
        if after > before:
            errors.append('platform.toc_after.task_points: task points cannot increase ({0} -> {1})'.format(before, after))
        elif after == before:
            warnings.append('task points did not drop ({0}); check the platform marker'.format(before))

    need('cost.tool_calls', lambda value: _is_int(value) and value >= 1, 'expected an integer >= 1')
    calls = _get(record, 'cost.tool_calls')
    if _is_int(calls) and calls > 30:
        warnings.append('cost.tool_calls={0} is over the node budget; read references/quickstart.md'.format(calls))

    deviations = _get(record, 'deviations')
    if deviations is not None:
        if not isinstance(deviations, list) or not all(isinstance(item, str) for item in deviations):
            errors.append('deviations: expected a list of strings')

    subtitles = _get(record, 'video.subtitles')
    if mode == 'evidence' and isinstance(subtitles, dict):
        srt = subtitles.get('srt')
        count = len(srt) if isinstance(srt, list) else srt
        if count is None:
            count = subtitles.get('srt_urls')
        if count == 0 or subtitles.get('allsubtitle_body') in ('[]', ''):
            warnings.append('no subtitle track: evidence mode has no original text for the quiz')

    popup = _get(record, 'popup')
    if isinstance(popup, dict) and popup.get('low_confidence') is True:
        if popup.get('evidence_status') not in (None, 'insufficient-evidence'):
            warnings.append('popup.low_confidence is true but evidence_status is not insufficient-evidence')

    return errors, warnings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', help='runs/<task>/evidence.json')
    parser.add_argument('--require-readonly', action='store_true',
                        help='also require 0 option clicks, 0 submit clicks, and no reopen')
    parser.add_argument('--allow-incomplete', action='store_true',
                        help='accept video.ended=false (interrupted node)')
    parser.add_argument('--json', action='store_true', help='raw JSON instead of the text report')
    args = parser.parse_args(argv)

    path = Path(args.evidence)
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
    except OSError as failure:
        print(json.dumps({'status': 'error', 'error': str(failure)}, ensure_ascii=False))
        return 2
    except json.JSONDecodeError as failure:
        print(json.dumps({'status': 'error', 'error': 'invalid JSON: ' + str(failure)}, ensure_ascii=False))
        return 2

    errors, warnings = validate(record, require_readonly=args.require_readonly,
                                allow_incomplete=args.allow_incomplete)
    report = {
        'status': 'ok' if not errors else 'fail',
        'path': str(path),
        'mode': _get(record, 'mode'),
        'submitted': _get(record, 'quiz.submitted'),
        'toc': [_get(record, 'platform.toc_before.task_points'), _get(record, 'platform.toc_after.task_points')],
        'tool_calls': _get(record, 'cost.tool_calls'),
        'platform_status': _get(record, 'quiz.platform_status'),
        'add_times': _get(record, 'quiz.add_times'),
        'limit_work_submit_times': _get(record, 'quiz.limit_work_submit_times'),
        'errors': errors,
        'warnings': warnings,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if errors:
            print('FAIL {0} errors={1}'.format(path, len(errors)))
            for item in errors:
                print('- ' + item)
        else:
            print('OK {0} mode={1} submitted={2} toc={3}->{4} calls={5} platform={6}'.format(
                path, report['mode'], report['submitted'], report['toc'][0], report['toc'][1],
                report['tool_calls'], report['platform_status'] or '-'))
        for item in warnings:
            print('WARN ' + item)
    return 0 if not errors else EXIT_INVALID


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
