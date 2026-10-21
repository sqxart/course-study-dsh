"""Turn post-submission result pages into a course question bank.

The v24 result page (`selectWorkQuestionYiPiYue`, titled 查看已批阅作业) is the only
place the platform returns question text as plaintext: the waiting page obfuscates
glyphs through an embedded font, while the review page hands back 题面 / 选项 /
我的答案 / 得分. It shows 正确答案 only when the teacher enables it, so `correct`
may legitimately be null on a quiz that was submitted and scored.

A question answered for full marks does carry an answer by implication. That one is
recorded as `correct_source: derived_from_full_score` instead of pretending the
platform printed it; every other unanswered key stays null. No inference from
subject knowledge happens here — the bank reports what the platform said.

Captures are written by the browser driver in references/bank.md. This module only
validates them, normalises them, merges them per course, and renders the two
deliverables: `bank.json` (machine) and `bank.md` (human).
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

SCHEMA_VERSION = 1
CAPTURE_KIND = 'quiz-bank-capture'
BANK_KIND = 'quiz-bank'
EXIT_INVALID = 2
EXIT_EMPTY = 3

TYPE_MAP = (
    ('单选', 'single'),
    ('多选', 'multi'),
    ('判断', 'judge'),
    ('填空', 'blank'),
    ('简答', 'essay'),
    ('问答', 'essay'),
)
# Result-page markup puts a ✓/✗ glyph in .CorrectOrNot > span; the class carries it.
MARK_MAP = {'marking_dui': 'correct', 'marking_cuo': 'wrong'}
SECTION_CODE = re.compile(r'^(\d+(?:\.\d+)*)\s+(.*\S)\s*$')


def clean(value):
    """Collapse the whitespace the review page sprinkles between labels and text."""
    if value is None:
        return ''
    return re.sub(r'\s+', ' ', str(value).replace('\u00a0', ' ')).strip()


def classify_type(label):
    """Map 【单选题】… to a stable type token; unknown labels fall through as `other`."""
    text = clean(label)
    for needle, token in TYPE_MAP:
        if needle in text:
            return token
    return 'other'


def parse_verdict(mark, score, max_score):
    """Prefer the platform's own ✓/✗ class; fall back to the per-question score.

    A multi-select answered short is marked wrong by the platform yet still scores
    half — calling that `wrong` would hide the reason it was not a full mark.
    """
    token = MARK_MAP.get(clean(mark))
    if token == 'wrong' and score is not None and max_score and 0 < score < max_score:
        return 'partial'
    if token:
        return token
    if score is None or not max_score:
        return 'unknown'
    if score >= max_score - 0.01:
        return 'correct'
    if score <= 0:
        return 'wrong'
    return 'partial'


def split_section_title(text):
    """`4.1 标定的意义` -> ('4.1', '标定的意义'); leaves text without a code alone."""
    match = SECTION_CODE.match(clean(text))
    if not match:
        return None, clean(text)
    return match.group(1), match.group(2)


def normalize_question(raw, index, full_score, count):
    """One question record. `correct` stays null unless the page printed it or the score proves it."""
    max_score = round(full_score / count, 2) if full_score and count else None
    score = raw.get('score')
    verdict = parse_verdict(raw.get('mark'), score, max_score)
    page_answer = clean(raw.get('correct')) or None
    my_answer = clean(raw.get('my_answer'))
    correct, source = page_answer, ('page' if page_answer else None)
    if not correct and verdict == 'correct' and my_answer:
        correct, source = my_answer, 'derived_from_full_score'
    return {
        'idx': index + 1,
        'qid': clean(raw.get('qid')) or None,
        'type': classify_type(raw.get('qtype_text')),
        'type_label': clean(raw.get('qtype_text')) or None,
        'stem': clean(raw.get('stem')),
        'options': [
            {'key': clean(option.get('key')), 'text': clean(option.get('text'))}
            for option in (raw.get('options') or [])
            if clean(option.get('text'))
        ],
        'my_answer': my_answer or None,
        'correct': correct,
        'correct_source': source,
        'verdict': verdict,
        'score': score,
        'max_score': max_score,
        'max_score_source': 'equal_split' if max_score is not None else None,
    }


def normalize_capture(capture):
    """Validate one capture and return a node record; raises ValueError on structural drift."""
    if not isinstance(capture, dict):
        raise ValueError('capture is not an object')
    if capture.get('kind') != CAPTURE_KIND:
        raise ValueError('unexpected kind: {0!r}'.format(capture.get('kind')))
    questions = capture.get('questions') or []
    meta = capture.get('meta') or {}
    count = meta.get('question_count') or len(questions)
    if not questions:
        raise ValueError('capture has no questions')
    if count != len(questions):
        raise ValueError('question_count {0} != captured {1}'.format(count, len(questions)))
    full_score = meta.get('full_score')
    code, title = split_section_title(capture.get('section_title'))
    section = clean(capture.get('section')) or code
    if not section:
        raise ValueError('capture has no section code')
    return {
        'section': section,
        'section_title': title or None,
        'chapter': capture.get('chapter') or None,
        'work_id': clean(capture.get('work_id')) or None,
        'work_answer_id': clean(capture.get('work_answer_id')) or None,
        'attempt': meta.get('attempt'),
        'question_count': count,
        'full_score': full_score,
        'total_score': meta.get('total_score'),
        'answer_visible': bool(capture.get('answer_visible')),
        'page_kind': capture.get('page'),
        'fields': capture.get('fields') or {},
        'toc_changed': bool((capture.get('toc') or {}).get('changed')),
        'captured_at': capture.get('captured_at'),
        'account': capture.get('account'),
        'channel': capture.get('channel'),
        'questions': [
            normalize_question(question, index, full_score, count)
            for index, question in enumerate(questions)
        ],
    }


def sort_key(section):
    return [int(part) for part in re.findall(r'\d+', str(section))]


def build_bank(nodes, course, course_title=None, expected=None, generated_at=None):
    """Merge node records into one bank. `expected` names sections that should exist."""
    nodes = sorted(nodes, key=lambda node: sort_key(node['section']))
    chapters = []
    for node in nodes:
        label = node.get('chapter') or node['section'].split('.')[0]
        if not chapters or chapters[-1]['label'] != label:
            chapter_code, chapter_title = split_section_title(label)
            chapters.append({'label': label, 'code': chapter_code or label.split(' ')[0],
                             'title': chapter_title or None, 'sections': []})
        chapters[-1]['sections'].append(node)

    questions = [question for node in nodes for question in node['questions']]
    verdicts = [question['verdict'] for question in questions]
    answered = [question for question in questions if question['correct']]
    captured = {node['section'] for node in nodes}
    bank = {
        'schema_version': SCHEMA_VERSION,
        'kind': BANK_KIND,
        'course': course,
        'course_title': course_title,
        'generated_at': generated_at or datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        'source': {
            'platform': 'chaoxing',
            'page': 'selectWorkQuestionYiPiYue',
            'evidence_level': 'result-page',
            'answer_visible': any(node['answer_visible'] for node in nodes),
        },
        'stats': {
            'sections': len(nodes),
            'questions': len(questions),
            'with_answer': len(answered),
            'with_stem_only': len(questions) - len(answered),
            'correct': verdicts.count('correct'),
            'wrong': verdicts.count('wrong'),
            'partial': verdicts.count('partial'),
            'unknown': verdicts.count('unknown'),
            'score': {'total': sum((node['total_score'] or 0) for node in nodes),
                      'full': sum((node['full_score'] or 0) for node in nodes)},
        },
        'chapters': chapters,
    }
    if expected is not None:
        missing = sorted(set(expected) - captured, key=sort_key)
        bank['coverage'] = {
            'expected_sections': len(expected),
            'captured_sections': len(captured),
            'missing_sections': missing,
        }
    return bank


def _answer_cell(question):
    if question['correct'] and question['correct_source'] == 'page':
        return '{0}（结果页给出）'.format(question['correct'])
    if question['correct']:
        return '{0}（满分反推）'.format(question['correct'])
    return '未提供（平台未开放正确答案）'


def render_bank_markdown(bank):
    """Human-readable mirror of bank.json: one block per question, answers marked honestly."""
    stats = bank['stats']
    from_page = sum(1 for chapter in bank['chapters'] for section in chapter['sections']
                    for question in section['questions'] if question['correct_source'] == 'page')
    lines = [
        '# {0} 题库'.format(bank.get('course_title') or bank['course']),
        '',
        '- 课程键：`{0}`'.format(bank['course']),
        '- 数据源：提交后的结果页（`selectWorkQuestionYiPiYue`），明文题面与「我的答案」',
        '- 生成时间：{0}'.format(bank['generated_at']),
        '- 覆盖：{0} 节 / {1} 题，其中 {2} 题有答案（{3} 题结果页给出、{4} 题满分反推），'
        '{5} 题只有题面与我的答案'.format(
            stats['sections'], stats['questions'], stats['with_answer'], from_page,
            stats['with_answer'] - from_page, stats['with_stem_only']),
        '- 对错：答对 {0} / 答错 {1} / 部分得分 {2} / 未判定 {3}'.format(
            stats['correct'], stats['wrong'], stats['partial'], stats['unknown']),
    ]
    if not bank['source']['answer_visible']:
        lines.append('- **正确答案键不可用**：本课教师关闭了查看答案，结果页只显示「我的答案」；'
                     '满分题按「我的答案即正确答案」记录，其余标 null，不猜。')
    if bank.get('coverage'):
        coverage = bank['coverage']
        lines.append('- 应覆盖 {0} 节，实采 {1} 节，缺 {2} 节{3}'.format(
            coverage['expected_sections'], coverage['captured_sections'],
            len(coverage['missing_sections']),
            '：' + '、'.join(coverage['missing_sections'][:20]) if coverage['missing_sections'] else ''))
    for chapter in bank['chapters']:
        lines += ['', '## {0}'.format(chapter['label']), '']
        for section in chapter['sections']:
            lines.append('### {0} {1}'.format(section['section'], section['section_title'] or '').strip())
            lines.append('')
            lines.append('`work {0}` · {1}/{2} 分 · 第 {3} 次作答'.format(
                section['work_id'] or '?', section['total_score'],
                section['full_score'], section['attempt'] or '?'))
            lines.append('')
            for question in section['questions']:
                mark = {'correct': '✓', 'wrong': '✗', 'partial': '△'}.get(question['verdict'], '?')
                lines.append('{0}. {1}{2}'.format(question['idx'], question['type_label'] or '', question['stem']))
                for option in question['options']:
                    lines.append('   - {0}、{1}'.format(option['key'], option['text']))
                lines.append('   - 我的答案：{0} {1} 得分 {2}/{3}'.format(
                    question['my_answer'] or '—', mark, question['score'], question['max_score']))
                lines.append('   - 正确答案：{0}'.format(_answer_cell(question)))
                if question['qid']:
                    lines.append('   - 题号：{0}'.format(question['qid']))
                lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def load_captures(directory):
    """Read every *.json capture in a directory; skip render artifacts and report failures."""
    nodes, skipped = [], []
    for path in sorted(Path(directory).glob('*.json')):
        try:
            capture = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            skipped.append('{0}: {1}'.format(path.name, error))
            continue
        if not isinstance(capture, dict) or capture.get('kind') != CAPTURE_KIND:
            skipped.append('{0}: not a {1}'.format(path.name, CAPTURE_KIND))
            continue
        try:
            nodes.append(normalize_capture(capture))
        except ValueError as error:
            skipped.append('{0}: {1}'.format(path.name, error))
    return nodes, skipped


def check_capture(path):
    """Self-check used by each node agent: structure, counts, and the read-only guarantees."""
    capture = json.loads(Path(path).read_text(encoding='utf-8'))
    problems = []
    if capture.get('kind') != CAPTURE_KIND:
        problems.append('kind is {0!r}'.format(capture.get('kind')))
    if capture.get('page') != 'selectWorkQuestionYiPiYue':
        problems.append('page is {0!r}, expected the review page'.format(capture.get('page')))
    fields = capture.get('fields') or {}
    if fields.get('submit_button'):
        problems.append('review frame still had a submit button')
    if (capture.get('toc') or {}).get('changed'):
        problems.append('catalogue row changed while reading the review page')
    try:
        node = normalize_capture(capture)
    except ValueError as error:
        problems.append(str(error))
        node = None
    if node is None:
        return {'ok': False, 'problems': problems}
    answered = sum(1 for question in node['questions'] if question['correct'])
    return {
        'ok': not problems,
        'problems': problems,
        'section': node['section'],
        'questions': node['question_count'],
        'answer_visible': node['answer_visible'],
        'with_answer': answered,
        'score': '{0}/{1}'.format(node['total_score'], node['full_score']),
    }


def brief(bank):
    stats = bank['stats']
    lines = [
        'COURSE={0} SECTIONS={1} QUESTIONS={2} WITH_ANSWER={3} STEM_ONLY={4}'.format(
            bank['course'], stats['sections'], stats['questions'], stats['with_answer'], stats['with_stem_only']),
        'VERDICTS correct={0} wrong={1} partial={2} unknown={3} ANSWER_VISIBLE={4}'.format(
            stats['correct'], stats['wrong'], stats['partial'], stats['unknown'],
            bank['source']['answer_visible']),
    ]
    missing = (bank.get('coverage') or {}).get('missing_sections') or []
    if missing:
        lines.append('MISSING={0} {1}'.format(len(missing), ' '.join(missing)))
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    check = sub.add_parser('check', help='Validate one node capture written by the browser driver')
    check.add_argument('capture')

    build = sub.add_parser('build', help='Merge captures of one course into bank.json + bank.md')
    build.add_argument('--nodes', required=True, help='Directory of *.json captures')
    build.add_argument('--course', required=True, help='Course key, e.g. course-example')
    build.add_argument('--title', help='Course title for the markdown header')
    build.add_argument('--expected', help='JSON file with the section codes that should exist')
    build.add_argument('--out', help='bank.json path (default knowledge/<course>/bank.json)')
    build.add_argument('--md', help='bank.md path (default knowledge/<course>/bank.md)')
    build.add_argument('--json', action='store_true', help='Print the bank instead of the brief')

    cover = sub.add_parser('coverage', help='Report coverage of an existing bank.json')
    cover.add_argument('bank')
    cover.add_argument('--json', action='store_true')

    args = parser.parse_args(argv)
    if args.command == 'check':
        report = check_capture(args.capture)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['ok'] else EXIT_INVALID

    if args.command == 'coverage':
        bank = json.loads(Path(args.bank).read_text(encoding='utf-8'))
        print(json.dumps(bank.get('stats'), ensure_ascii=False, indent=2) if args.json else brief(bank))
        return 0

    expected = None
    if args.expected:
        expected = json.loads(Path(args.expected).read_text(encoding='utf-8'))
    nodes, skipped = load_captures(args.nodes)
    for line in skipped:
        print('SKIP ' + line, file=sys.stderr)
    if not nodes:
        print('no captures in ' + args.nodes, file=sys.stderr)
        return EXIT_EMPTY
    bank = build_bank(nodes, course=args.course, course_title=args.title, expected=expected)
    out = Path(args.out or Path('knowledge') / args.course / 'bank.json')
    md = Path(args.md or Path('knowledge') / args.course / 'bank.md')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bank, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    md.write_text(render_bank_markdown(bank), encoding='utf-8')
    print(json.dumps(bank, ensure_ascii=False, indent=2) if args.json else brief(bank))
    print('WROTE {0} {1}'.format(out, md), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
