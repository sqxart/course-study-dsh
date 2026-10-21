"""Assemble `review.md` from the question bank, quoting subtitles only where they exist.

The review document has three parts per section and each has one source:

* 本节要点 — subtitle cues that contain an option text of this section's questions, quoted
  verbatim with their timestamps. Nothing is paraphrased, so a reader can open the video at
  that minute and hear the same words.
* 考点 — the bank record: stem, options, my answer, the verdict and the score.
* 易错点 — the questions answered wrong or partially, with what was chosen instead.

A course without subtitles still gets the 考点 and 易错点; the header says
`evidence_level: quiz-only` instead of inventing narration.
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

MAX_QUOTES = 8
MIN_TERM_LENGTH = 3
MAX_QUOTE_CHARS = 220


def load_subtitle_module():
    """Reuse the tested SRT/VTT loader instead of writing a second parser."""
    path = Path(__file__).with_name('subtitle_evidence.py')
    spec = importlib.util.spec_from_file_location('subtitle_evidence', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def key_terms(questions):
    """Option texts double as search terms: they are short, distinctive and verbatim."""
    terms = []
    for question in questions:
        for option in question.get('options') or []:
            text = str(option.get('text') or '').strip()
            if len(text) >= MIN_TERM_LENGTH and text not in terms:
                terms.append(text)
    return terms


def quote_cues(cues, terms, limit=MAX_QUOTES):
    """Return the first cues containing any term, one quote per term, in subtitle order."""
    if not terms:
        return []
    hits, seen = [], set()
    for cue in cues:
        text = str(cue.get('text') or '').strip()
        if not text or cue.get('start_ms') is None:
            continue
        matched = next((term for term in terms if term and term in text), None)
        if not matched or matched in seen:
            continue
        seen.add(matched)
        hits.append(cue)
        if len(hits) >= limit:
            break
    return hits


def _answer_line(question):
    mark = {'correct': '✓', 'wrong': '✗', 'partial': '△'}.get(question.get('verdict'), '?')
    score = '{0}/{1}'.format(question.get('score'), question.get('max_score'))
    return '我的答案：{0} {1}（得分 {2}）'.format(question.get('my_answer') or '—', mark, score)


def _correct_line(question):
    if question.get('correct') and question.get('correct_source') == 'page':
        return '正确答案：{0}（结果页给出）'.format(question['correct'])
    if question.get('correct'):
        return '正确答案：{0}（满分反推）'.format(question['correct'])
    return '正确答案：未开放（平台未给出，不猜）'


def render_section(section, subtitle):
    lines = ['### {0} {1}'.format(section['section'], section.get('section_title') or '').strip(), '']
    questions = section['questions']
    quotes = quote_cues(subtitle, key_terms(questions)) if subtitle else []
    lines.append('**本节要点（字幕原话）**')
    if quotes:
        for cue in quotes:
            text = ' '.join(str(cue.get('text') or '').split())
            if len(text) > MAX_QUOTE_CHARS:
                text = text[:MAX_QUOTE_CHARS].rstrip() + '…'
            lines.append('- [{0}] {1}'.format(_mmss(cue['start_ms']), text))
    elif subtitle:
        lines.append('- 字幕里没有与本节考点重合的原话。')
    else:
        lines.append('- 本节无字幕，只有题库。')
    lines += ['', '**考点**', '']
    for question in questions:
        lines.append('{0}. {1}{2}'.format(question['idx'], question.get('type_label') or '', question['stem']))
        for option in question.get('options') or []:
            lines.append('   - {0}、{1}'.format(option['key'], option['text']))
        lines.append('   - ' + _answer_line(question))
        lines.append('   - ' + _correct_line(question))
    wrong = [question for question in questions if question.get('verdict') in ('wrong', 'partial')]
    lines += ['', '**易错点**', '']
    if not wrong:
        lines.append('- 本节没有错题。')
    else:
        for question in wrong:
            lines.append('- 第 {0} 题{1}：我选 {2}，{3}。（题号 {4}）'.format(
                question['idx'], question.get('type_label') or '', question.get('my_answer') or '—',
                '部分得分' if question.get('verdict') == 'partial' else '判错',
                question.get('qid') or '?'))
    lines.append('')
    return '\n'.join(lines)


def _mmss(milliseconds):
    seconds = int(milliseconds) // 1000
    return '{0:02d}:{1:02d}:{2:02d}'.format(seconds // 3600, (seconds // 60) % 60, seconds % 60)


def build_review(bank, subtitles, generated_at=None):
    """`subtitles` maps section code -> list of cues (or None when the section has no SRT)."""
    sections = [section for chapter in bank['chapters'] for section in chapter['sections']]
    with_subs = [section for section in sections if subtitles.get(section['section'])]
    stats = bank['stats']
    lines = [
        '# {0} 复习文档'.format(bank.get('course_title') or bank['course']),
        '',
        '- 题库依据：{0} 节 / {1} 题（来自提交后的结果页）'.format(stats['sections'], stats['questions']),
        '- 字幕依据：{0}/{1} 节有 SRT'.format(len(with_subs), len(sections)),
        '- evidence_level: {0}'.format('bank+subtitle' if with_subs else 'quiz-only'),
        '- 生成时间：{0}'.format(generated_at or bank.get('generated_at')),
        '',
        '> 口径：题面与「我的答案」来自提交后的结果页；「正确答案」只在结果页给出或该题满分时才有值，'
        '其余标「未开放」，不做学科推断。要点是字幕原话，时间轴为字幕时间，可直接回看视频。',
    ]
    if stats['with_stem_only']:
        lines.append('> 本课有 {0} 题平台未开放正确答案。'.format(stats['with_stem_only']))
    if not with_subs:
        lines.append('> 本课没有可用字幕，文档只有题库部分（quiz-only），不含视频要点。')
    for chapter in bank['chapters']:
        lines += ['', '## {0}'.format(chapter['label']), '']
        for section in chapter['sections']:
            lines.append(render_section(section, subtitles.get(section['section'])))
    return '\n'.join(lines).rstrip() + '\n'


def load_subtitles(directory):
    """Read every `<section>.srt` in a directory; unreadable files are reported, not fatal."""
    if not directory:
        return {}, []
    module = load_subtitle_module()
    subtitles, broken = {}, []
    for path in sorted(Path(directory).glob('*.srt')):
        try:
            subtitles[path.stem] = module.load_corpus(path)['cues']
        except Exception as error:  # noqa: BLE001 - a broken SRT must not stop the document
            broken.append('{0}: {1}'.format(path.name, error))
    return subtitles, broken


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--bank', required=True, help='knowledge/<course>/bank.json')
    parser.add_argument('--subs', help='Directory of <section>.srt files')
    parser.add_argument('--out', help='review.md path (default: next to the bank)')
    args = parser.parse_args(argv)

    bank = json.loads(Path(args.bank).read_text(encoding='utf-8'))
    subtitles, broken = load_subtitles(args.subs)
    for line in broken:
        print('SKIP ' + line, file=sys.stderr)
    text = build_review(bank, subtitles)
    out = Path(args.out or Path(args.bank).with_name('review.md'))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding='utf-8')
    quoted = sum(1 for section in subtitles if subtitles[section])
    print('COURSE={0} SECTIONS={1} WITH_SUBTITLE={2} LEVEL={3} WROTE={4}'.format(
        bank['course'], bank['stats']['sections'], quoted,
        'bank+subtitle' if quoted else 'quiz-only', out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
