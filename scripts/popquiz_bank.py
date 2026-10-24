"""Aggregate in-video popup quizzes (弹题) into a course popup bank.

Chapter quizzes live in `bank.json` / `bank.md` and are read from the submitted review
page; popups are a different source: they appear during playback over the video frame and
the platform does not publish their correct answer. Keeping them in one table with the
chapter quizzes would mix two kinds of evidence, so this script writes a separate
`popquiz.json` / `popquiz.md` and hands `quiz_bank.py` a small index so `bank.md` only
carries one pointer line per section.

Capture shape (one file per popup, `<section>-<n>.json`):

    {"schema_version": 1, "kind": "video-quiz-capture", "course": "earth-history",
     "account": "account-example", "channel": "mcp__browser", "section": "1.4.2",
     "segment": 0, "qtype": "single",
     "stem": "...", "options": [{"key": "A", "text": "..."}],
     "my_answer": "B", "verdict": "correct", "revealed_correct": null,
     "evidence_status": "transcript", "quote": "...", "video_time": 329,
     "note": "..."}

Usage:
    python scripts/popquiz_bank.py check runs/<task>/popquiz/<course>/1.4.2-0.json
    python scripts/popquiz_bank.py build --popquiz-dir runs/<task>/popquiz/<course> \\
        --course example-course --title 示例课程
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIND = 'video-quiz-capture'
SECTION = re.compile(r'^\d+(?:\.\d+)*$')
VERDICTS = ('correct', 'wrong', 'unknown')
EVIDENCE = ('transcript', 'page', 'none', 'guess')
QTYPES = {'single': '单选', 'multi': '多选', 'judge': '判断'}


def normalize_capture(capture):
    """Validate one popup capture and return the fields the bank needs."""
    if not isinstance(capture, dict):
        raise ValueError('capture is not an object')
    if capture.get('kind') != KIND:
        raise ValueError('kind is {0!r}'.format(capture.get('kind')))
    section = str(capture.get('section') or '').strip()
    if not SECTION.match(section):
        raise ValueError('bad section {0!r}'.format(section))
    stem = str(capture.get('stem') or '').strip()
    if not stem:
        raise ValueError('empty stem')
    options = []
    for index, option in enumerate(capture.get('options') or []):
        if not isinstance(option, dict):
            raise ValueError('option {0} is not an object'.format(index))
        key = str(option.get('key') or '').strip().upper()
        text = str(option.get('text') or '').strip()
        if not key or not text:
            raise ValueError('option {0} lacks key/text'.format(index))
        options.append({'key': key, 'text': text})
    if not options:
        raise ValueError('no options')
    keys = [option['key'] for option in options]
    qtype = str(capture.get('qtype') or 'single')
    if qtype not in QTYPES:
        raise ValueError('bad qtype {0!r}'.format(qtype))
    mine = capture.get('my_answer')
    mine = str(mine).strip().upper() if mine not in (None, '') else None
    if mine is not None:
        # A multi-select popup answers several letters at once ("AB"), single ones only one.
        picked = [key for key in keys if key in mine] if qtype == 'multi' else ([mine] if mine in keys else [])
        if not picked or ''.join(picked) != mine:
            raise ValueError('my_answer {0!r} does not match the options {1}'.format(mine, keys))
    verdict = str(capture.get('verdict') or 'unknown')
    if verdict not in VERDICTS:
        raise ValueError('bad verdict {0!r}'.format(verdict))
    revealed = capture.get('revealed_correct')
    if revealed not in (None, '', []):
        revealed = [str(key).strip().upper() for key in (revealed if isinstance(revealed, list) else [revealed])]
        outside = [key for key in revealed if key not in keys]
        if outside:
            raise ValueError('revealed_correct {0} is not an option'.format(outside))
    else:
        revealed = None
    status = str(capture.get('evidence_status') or 'none')
    if status not in EVIDENCE:
        raise ValueError('bad evidence_status {0!r}'.format(status))
    segment = capture.get('segment')
    segment = int(segment) if isinstance(segment, (int, float, str)) and str(segment).strip().isdigit() else 0
    return {
        'section': section,
        'segment': segment,
        'qtype': qtype,
        'stem': stem,
        'options': options,
        'my_answer': mine,
        'verdict': verdict,
        'revealed_correct': revealed,
        'evidence_status': status,
        'quote': str(capture.get('quote') or '').strip(),
        'video_time': capture.get('video_time'),
        'note': str(capture.get('note') or '').strip(),
        'account': capture.get('account'),
        'channel': capture.get('channel'),
    }


def sort_key(section):
    return [int(part) for part in section.split('.')]


def load_captures(directory):
    nodes, skipped = [], []
    for path in sorted(Path(directory).glob('*.json')):
        try:
            capture = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            skipped.append('{0}: {1}'.format(path.name, error))
            continue
        if not isinstance(capture, dict) or capture.get('kind') != KIND:
            skipped.append('{0}: not a {1}'.format(path.name, KIND))
            continue
        try:
            nodes.append(normalize_capture(capture))
        except ValueError as error:
            skipped.append('{0}: {1}'.format(path.name, error))
    return nodes, skipped


def build_bank(nodes, course, course_title=None, generated_at=None):
    grouped = {}
    for node in nodes:
        grouped.setdefault(node['section'], []).append(node)
    sections = []
    for section in sorted(grouped, key=sort_key):
        items = sorted(grouped[section], key=lambda item: item['segment'])
        sections.append({'section': section, 'questions': items})
    total = sum(len(section['questions']) for section in sections)
    with_answer = sum(1 for section in sections for question in section['questions'] if question['revealed_correct'])
    return {
        'schema_version': 1,
        'kind': 'popup-bank',
        'course': course,
        'course_title': course_title,
        'generated_at': generated_at or '',
        'stats': {
            'sections': len(sections),
            'questions': total,
            'with_answer': with_answer,
            'stem_only': total - with_answer,
            'correct': sum(1 for section in sections for question in section['questions'] if question['verdict'] == 'correct'),
            'wrong': sum(1 for section in sections for question in section['questions'] if question['verdict'] == 'wrong'),
            'unknown': sum(1 for section in sections for question in section['questions'] if question['verdict'] == 'unknown'),
        },
        'sections': sections,
    }


def _clock(seconds):
    try:
        seconds = int(round(float(seconds)))
    except (TypeError, ValueError):
        return None
    return '{0:02d}:{1:02d}'.format(seconds // 60, seconds % 60)


def render_markdown(bank):
    stats = bank['stats']
    lines = [
        '# {0} 弹题库'.format(bank.get('course_title') or bank['course']),
        '',
        '- 课程键：`{0}`'.format(bank['course']),
        '- 数据源：播放中的弹题浮层（`.ans-videoquiz`）明文题干与选项；**与章节测验分开，不混表**',
        '- 覆盖：{0} 节 / {1} 题；平台公布正确答案 {2} 题，其余 {3} 题只记题干/选项/我的答案'.format(
            stats['sections'], stats['questions'], stats['with_answer'], stats['stem_only']),
        '- 我的判定：答对 {0} / 答错 {1} / 未判定 {2}'.format(stats['correct'], stats['wrong'], stats['unknown']),
        '- 弹题不产生任务点，本表只作题库与复盘',
    ]
    if stats['with_answer'] == 0:
        lines.append('- **平台未公布任何弹题正确答案**：`revealed_correct` 全为空，不猜；'
                     '判定只看浮层是否关闭（答错不关）。')
    for section in bank['sections']:
        lines += ['', '## {0}'.format(section['section']), '']
        for question in section['questions']:
            clock = _clock(question['video_time'])
            header = '- {0}'.format(QTYPES.get(question['qtype'], question['qtype']))
            if clock:
                header += ' · 视频 {0}'.format(clock)
            lines.append(header)
            lines.append('  - 题干：{0}'.format(question['stem']))
            revealed = question['revealed_correct'] or []
            for option in question['options']:
                tick = ' ✓' if option['key'] in revealed else ''
                lines.append('  - {0}、{1}{2}'.format(option['key'], option['text'], tick))
            if question['revealed_correct']:
                lines.append('  - 正确答案：{0}'.format('、'.join(revealed)))
            if question['my_answer']:
                lines.append('  - 我的答案：{0}（判定：{1}）'.format(question['my_answer'], question['verdict']))
            if question['quote']:
                lines.append('  - 依据：「{0}」'.format(question['quote']))
            if question['note']:
                lines.append('  - 备注：{0}'.format(question['note']))
            lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def check_capture(path):
    capture = json.loads(Path(path).read_text(encoding='utf-8'))
    problems = []
    try:
        node = normalize_capture(capture)
    except ValueError as error:
        return {'ok': False, 'problems': [str(error)]}
    if node['revealed_correct'] and node['verdict'] == 'correct' and node['my_answer'] not in node['revealed_correct']:
        problems.append('verdict says correct but my_answer is not a revealed key')
    if node['evidence_status'] == 'transcript' and not node['quote']:
        problems.append('evidence_status=transcript without a quote')
    if node['evidence_status'] == 'guess' and not node['note']:
        problems.append('evidence_status=guess without a note')
    return {
        'ok': not problems,
        'problems': problems,
        'section': node['section'],
        'qtype': node['qtype'],
        'options': len(node['options']),
        'my_answer': node['my_answer'],
        'verdict': node['verdict'],
        'revealed': node['revealed_correct'],
    }


def brief(bank):
    stats = bank['stats']
    return 'COURSE={0} SECTIONS={1} QUESTIONS={2} WITH_ANSWER={3} CORRECT={4} WRONG={5}'.format(
        bank['course'], stats['sections'], stats['questions'], stats['with_answer'],
        stats['correct'], stats['wrong'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    check = sub.add_parser('check', help='Validate one popup capture')
    check.add_argument('capture')

    build = sub.add_parser('build', help='Aggregate captures into popquiz.json + popquiz.md')
    build.add_argument('--popquiz-dir', required=True)
    build.add_argument('--course', required=True)
    build.add_argument('--title')
    build.add_argument('--out-json')
    build.add_argument('--out-md')
    build.add_argument('--index-out', help='Write {section: count} for quiz_bank.py --popquiz-index')
    build.add_argument('--json', action='store_true')

    args = parser.parse_args(argv)
    if args.command == 'check':
        result = check_capture(args.capture)
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 0 if result['ok'] else 2

    nodes, skipped = load_captures(args.popquiz_dir)
    if not nodes:
        print(json.dumps({'ok': False, 'skipped': skipped}, ensure_ascii=False, indent=1))
        return 2
    bank = build_bank(nodes, args.course, args.title)
    out_json = Path(args.out_json or (ROOT / 'knowledge' / args.course / 'popquiz.json'))
    out_md = Path(args.out_md or (ROOT / 'knowledge' / args.course / 'popquiz.md'))
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(bank, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    out_md.write_text(render_markdown(bank), encoding='utf-8', newline='\n')
    if args.index_out:
        index = {section['section']: len(section['questions']) for section in bank['sections']}
        Path(args.index_out).write_text(json.dumps(index, ensure_ascii=False, indent=1) + '\n',
                                        encoding='utf-8', newline='\n')
    if args.json:
        print(json.dumps(bank, ensure_ascii=False, indent=1))
    else:
        print(brief(bank))
        print('WROTE {0}'.format(out_json), file=sys.stderr)
        print('WROTE {0}'.format(out_md), file=sys.stderr)
    if skipped:
        print('SKIPPED ' + '; '.join(skipped[:10]), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
