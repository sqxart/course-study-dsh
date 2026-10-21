"""Assemble the course knowledge document from per-section exam notes and the bank.

Two deliverables, deliberately separate:

* `bank.md` / `bank.json` — the questions: stem, options, my answer, score.
* `knowledge.md` — the exam knowledge: for the concepts this section's questions test,
  what they mean, how the question is phrased, and what gets confused with what.

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

REQUIRED_SECTIONS = ('考点知识', '概念表')
FORBIDDEN_SECTIONS = ('本节讲什么', '本节结论', '要点')
DEPRECATED_MARKERS = ('【单选题】', '【多选题】', '【判断题】', '我的答案：', '正确答案：')
BANK_MARKERS = DEPRECATED_MARKERS
# The user's rule: examples go, even when they support a point. These are the markers that
# introduce one, so a note that still narrates an example fails instead of shipping.
EXAMPLE_MARKERS = ('比如', '例如', '举例', '譬如', '有一回', '曾经有', '我记得')
MIN_POINTS = 8
MIN_CHARS = 300
_CLOCK = r'\d{1,2}:\d{2}(?::\d{2})?'
# The review card carries no timeline: the user reads it to answer questions, not to jump
# into the video, so any (mm:ss) marker is noise.
TIMESTAMP = re.compile(r'[\[(（]\s*' + _CLOCK + r'(?:\s*[–—~-]\s*' + _CLOCK + r')?\s*[\])）]')
# Bullets or numbered items — the terse format is a list, not an essay.
POINT = re.compile(r'^\s*(?:[-*]|\d+[.、])\s+\S', re.M)


def clean(value):
    return re.sub(r'\s+', ' ', str(value)).strip()


def validate_note(text):
    """Return (problems, stats). A note must teach the exam points, not summarise the video."""
    problems = []
    body = (text or '').strip()
    if not body:
        return ['note is empty'], {}
    for heading in REQUIRED_SECTIONS:
        if heading not in body:
            problems.append('missing section: ' + heading)
    for heading in FORBIDDEN_SECTIONS:
        if '**{0}**'.format(heading) in body:
            problems.append('old summary format is retired: ' + heading)
    points = len(POINT.findall(body))
    timestamps = len(TIMESTAMP.findall(body))
    chars = len(re.sub(r'\s+', '', body))
    for marker in BANK_MARKERS:
        if marker in body:
            problems.append('looks like quiz text, not a note: ' + marker)
            break
    if points < MIN_POINTS:
        problems.append('only {0} knowledge bullets, need {1}'.format(points, MIN_POINTS))
    if timestamps:
        problems.append('timestamps are not wanted in a review card: drop the (00:00) markers')
    for marker in EXAMPLE_MARKERS:
        if marker in body:
            problems.append('examples are not wanted: remove the "{0}" passage'.format(marker))
            break
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


def _section_key(code):
    parts = re.findall(r'\d+', str(code))
    return [int(part) for part in parts] if parts else [0]


def merge_outline(bank, notes):
    """Bank sections plus any note that has no quiz section (video-only nodes).

    题库只收「章节测验」节，视频节的 note 不在 bank 里；知识总结不该因此漏掉它们，
    所以按节号前缀把它们挂到对应章下；题库里没有的节不写「本节测验 N 题」那行。
    """
    chapters, seen = [], set()
    for chapter in bank['chapters']:
        sections = []
        for section in chapter['sections']:
            sections.append(dict(section))
            seen.add(section['section'])
        chapters.append({'label': _chapter_label(chapter), 'sections': sections})
    for code in sorted((c for c in notes if c not in seen), key=_section_key):
        prefix = str(code).split('.')[0]
        target = next((c for c in chapters if str(c['label']).split(' ')[0] == prefix), None)
        if target is None:
            target = {'label': prefix, 'sections': []}
            chapters.append(target)
        target['sections'].append({'section': code, 'section_title': '', 'questions': []})
    chapters.sort(key=lambda c: _section_key(str(c['label']).split(' ')[0]))
    for chapter in chapters:
        chapter['sections'].sort(key=lambda s: _section_key(s['section']))
    return chapters


def build_knowledge(bank, notes, generated_at=None):
    """Stitch notes under the bank's chapter structure; never fill gaps with quiz text."""
    chapters = merge_outline(bank, notes)
    sections = [section for chapter in chapters for section in chapter['sections']]
    with_notes = [section for section in sections if section['section'] in notes]
    lines = [
        '# {0} 知识总结'.format(bank.get('course_title') or bank['course']),
        '',
        '- 覆盖：{0}/{1} 节有总结（其余无字幕或未整理）'.format(len(with_notes), len(sections)),
        '- 依据：课程视频字幕原文（无字幕则 ASR 转写）；只收能出选择题/判断题的客观知识',
        '- 与题库的关系：题目、选项、我的答案、得分在 `bank.md`，本文件只写支撑这些题的知识',
        '- 生成时间：{0}'.format(generated_at or datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()),
        '',
        '> 只写视频里讲过的内容：定义、判断依据、易混区别都来自字幕；字幕没讲的（包括平台没开放的正确答案）不补。',
    ]
    for chapter in chapters:
        lines += ['', '## {0}'.format(chapter['label']), '']
        for section in chapter['sections']:
            heading = '### {0} {1}'.format(section['section'], section.get('section_title') or '').strip()
            lines.append(heading)
            lines.append('')
            note = notes.get(section['section'])
            if note:
                lines.append(note['text'])
            else:
                lines.append('（本节没有字幕总结：没有视频内容或尚未整理；题目见 `bank.md`）')
            lines.append('')
            if section.get('questions'):
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
    total = sum(len(chapter['sections']) for chapter in merge_outline(bank, notes))
    print('COURSE={0} SECTIONS={1} NOTES={2} MISSING={3} WROTE={4}'.format(
        bank['course'], total, len(notes), total - len(notes), out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
