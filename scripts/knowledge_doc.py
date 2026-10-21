"""Assemble the course knowledge document from per-section notes and the bank.

Two deliverables, deliberately separate:

* `bank.md` / `bank.json` — the questions: stem, options, my answer, score.
* `knowledge.md` — what the video taught: concepts, reasoning, numbers, worked examples,
  each claim anchored to a subtitle timestamp.

The notes are written by one agent per section from that section's full subtitle file
(`notes/<course>/<section>.md`, format in references/knowledge.md). This module only
validates them against a minimum bar and stitches them under chapter headings — it never
invents content itself. A section without subtitles says so instead of borrowing quiz text.
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = ('本节讲什么', '要点', '关键概念', '本节结论')
_CLOCK = r'\d{1,2}:\d{2}(?::\d{2})?'
# Notes anchor a claim to a range as often as to a single cue, so both forms count.
TIMESTAMP = re.compile(r'[\[(（]\s*' + _CLOCK + r'(?:\s*[–—~-]\s*' + _CLOCK + r')?\s*[\])）]')
POINT = re.compile(r'^\s*\d+[.、]\s+\S', re.M)
MIN_POINTS = 5
MIN_CHARS = 400
BANK_MARKERS = ('【单选题】', '【多选题】', '【判断题】', '我的答案：')


def clean(value):
    return re.sub(r'\s+', ' ', str(value)).strip()


def validate_note(text):
    """Return (problems, stats). A note must explain, not list words or echo the bank."""
    problems = []
    body = (text or '').strip()
    if not body:
        return ['note is empty'], {}
    for heading in REQUIRED_SECTIONS:
        if heading not in body:
            problems.append('missing section: ' + heading)
    points = len(POINT.findall(body))
    timestamps = len(TIMESTAMP.findall(body))
    chars = len(re.sub(r'\s+', '', body))
    for marker in BANK_MARKERS:
        if marker in body:
            problems.append('looks like quiz text, not a note: ' + marker)
            break
    if points < MIN_POINTS:
        problems.append('only {0} numbered points, need {1}'.format(points, MIN_POINTS))
    if timestamps < 3:
        problems.append('only {0} timestamps, need 3'.format(timestamps))
    if chars < MIN_CHARS:
        problems.append('only {0} chars, need {1}'.format(chars, MIN_CHARS))
    return problems, {'points': points, 'timestamps': timestamps, 'chars': chars}


def load_notes(directory):
    """Map section code -> note text; report notes that fail the bar but keep them."""
    notes, rejected = {}, []
    if not directory:
        return notes, rejected
    for path in sorted(Path(directory).glob('*.md')):
        text = path.read_text(encoding='utf-8')
        problems, stats = validate_note(text)
        notes[path.stem] = {'text': text.strip(), 'problems': problems, 'stats': stats}
        if problems:
            rejected.append('{0}: {1}'.format(path.name, '; '.join(problems)))
    return notes, rejected


def _chapter_label(chapter):
    return chapter.get('label') or chapter.get('code') or ''


def build_knowledge(bank, notes, generated_at=None):
    """Stitch notes under the bank's chapter structure; never fill gaps with quiz text."""
    sections = [section for chapter in bank['chapters'] for section in chapter['sections']]
    with_notes = [section for section in sections if section['section'] in notes]
    lines = [
        '# {0} 知识总结'.format(bank.get('course_title') or bank['course']),
        '',
        '- 覆盖：{0}/{1} 节有总结（其余无字幕或未整理）'.format(len(with_notes), len(sections)),
        '- 依据：课程视频字幕原文；每条要点括号里是字幕时间，可直接回看',
        '- 与题库的关系：题目、选项、我的答案、得分在 `bank.md`，本文件不复述题目',
        '- 生成时间：{0}'.format(generated_at or datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()),
        '',
        '> 只写视频里讲过的内容：定义、判断依据、示例与结论都来自字幕；字幕没讲的（包括平台没开放的正确答案）不补。',
    ]
    for chapter in bank['chapters']:
        lines += ['', '## {0}'.format(_chapter_label(chapter)), '']
        for section in chapter['sections']:
            heading = '### {0} {1}'.format(section['section'], section.get('section_title') or '').strip()
            lines.append(heading)
            lines.append('')
            note = notes.get(section['section'])
            if note:
                lines.append(note['text'])
            else:
                lines.append('（本节暂无字幕总结，待补；题目见 bank.md）')
            lines.append('')
            lines.append('> 本节测验 {0} 题，题面与我的答案见 `bank.md`。'.format(len(section['questions'])))
            lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    check = sub.add_parser('check', help='Validate one section note written by an agent')
    check.add_argument('note')

    build = sub.add_parser('build', help='Stitch notes into knowledge.md next to the bank')
    build.add_argument('--bank', required=True)
    build.add_argument('--notes', required=True, help='Directory of <section>.md notes')
    build.add_argument('--out', help='knowledge.md path (default: next to the bank)')
    build.add_argument('--allow-gaps', action='store_true', help='Write the file even with missing notes')

    args = parser.parse_args(argv)
    if args.command == 'check':
        text = Path(args.note).read_text(encoding='utf-8')
        problems, stats = validate_note(text)
        print(json.dumps({'ok': not problems, 'problems': problems, **stats}, ensure_ascii=False, indent=2))
        return 0 if not problems else 2

    bank = json.loads(Path(args.bank).read_text(encoding='utf-8'))
    notes, rejected = load_notes(args.notes)
    for line in rejected:
        print('WEAK ' + line, file=sys.stderr)
    text = build_knowledge(bank, notes)
    out = Path(args.out or Path(args.bank).with_name('knowledge.md'))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding='utf-8')
    total = sum(len(chapter['sections']) for chapter in bank['chapters'])
    print('COURSE={0} SECTIONS={1} NOTES={2} MISSING={3} WROTE={4}'.format(
        bank['course'], total, len(notes), total - len(notes), out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
