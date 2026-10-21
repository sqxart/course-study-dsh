"""Parse a 尔雅 answer-key PDF and compare it with the questions we captured.

Answer keys of this shape are human-made: a section heading, then numbered questions with
A./B./C./D. options and a `答案：X` line. Point `--pdf` at one of yours (the author keeps a
folder of them locally; nothing in this repo assumes a fixed location). Matching them against
the live bank answers "is this key still current", which the user asked before trusting it.

    python scripts/bank_crosscheck.py --pdf "<pdf>" --bank knowledge/paper-writing/bank.json
"""

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

SECTION = re.compile(r'^(?:(?:一|二|三|四|五|六|七|八|九|十)+[、.]\s*)?([^\d\s].{0,40})$')
QUESTION = re.compile(r'^\s*(\d{1,3})\s*[.．、]\s*(.+?)\s*$')
OPTION = re.compile(r'^\s*([A-D])\s*[.．、]\s*(.+?)\s*$')
ANSWER = re.compile(r'^\s*答案\s*[:：]\s*([A-D对错√×]+|正确|错误)\s*$')
NOISE = re.compile(r'^\s*(?:第\s*\d+\s*页|共\s*\d+\s*页|【|】|\d{4}|超星|尔雅)')


def normalize(text):
    """Same normalisation on both sides: width, punctuation and spaces are noise here."""
    text = unicodedata.normalize('NFKC', text or '')
    text = re.sub(r'[“”"‘’\'《》<>【】\[\]()（）,，.。;；:：!！?？、\s]', '', text)
    return text.lower()


def parse_pdf_text(text):
    """Yield {section, stem, options, answer} blocks; tolerant of wrapped option lines."""
    records, section, current = [], None, None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or NOISE.match(line):
            continue
        answer = ANSWER.match(line)
        if answer and current:
            value = answer.group(1)
            current['answer'] = {'正确': '对', '错误': '错'}.get(value, value)
            continue
        option = OPTION.match(line)
        if option and current:
            current['options'].append({'key': option.group(1), 'text': option.group(2)})
            continue
        question = QUESTION.match(line)
        if question:
            if current:
                records.append(current)
            current = {'section': section, 'number': int(question.group(1)),
                       'stem': question.group(2), 'options': [], 'answer': None}
            continue
        if current and not current['options'] and current['answer'] is None and len(line) < 30:
            current['stem'] += line          # a wrapped stem line
            continue
        if not current or (current and current['answer'] is not None):
            section = line
    if current:
        records.append(current)
    return records


def load_pdf(path):
    try:
        import pymupdf
    except ImportError:                       # older installs expose fitz
        import fitz as pymupdf
    document = pymupdf.open(path)
    text = '\n'.join(page.get_text() for page in document)
    document.close()
    return text


def compare(records, bank):
    """Match each captured question to a PDF record by normalised stem containment."""
    index = [(normalize(record['stem']), record) for record in records]
    rows, matched = [], 0
    for chapter in bank['chapters']:
        for section in chapter['sections']:
            for question in section['questions']:
                key = normalize(question['stem'])
                hit = None
                for other_key, record in index:
                    if key and (key in other_key or other_key in key) and len(key) >= 8:
                        hit = record
                        break
                if hit:
                    matched += 1
                    rows.append({
                        'section': section['section'], 'idx': question['idx'],
                        'stem': question['stem'], 'bank_correct': question['correct'],
                        'pdf_answer': hit['answer'], 'pdf_section': hit['section'],
                        'agree': (question['correct'] or '') == (hit['answer'] or '')
                    })
                else:
                    rows.append({'section': section['section'], 'idx': question['idx'],
                                 'stem': question['stem'], 'bank_correct': question['correct'],
                                 'pdf_answer': None, 'agree': None})
    return rows, matched


def build_candidates(rows, source_name):
    """Only the questions the platform left blank: the key is a hint, never an override."""
    candidates = {}
    for row in rows:
        if row.get('bank_correct'):
            continue
        if not row.get('pdf_answer'):
            continue
        candidates.setdefault(row['section'], {})[str(row['idx'])] = {
            'answer': row['pdf_answer'],
            'source': '尔雅题库 {0}'.format(source_name),
        }
    return candidates


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--pdf', required=True)
    parser.add_argument('--bank', required=True)
    parser.add_argument('--json')
    parser.add_argument('--external-out', help='Write candidate answers for the questions the platform left blank')
    parser.add_argument('--list', action='store_true', help='List every parsed PDF record')
    args = parser.parse_args(argv)

    records = parse_pdf_text(load_pdf(args.pdf))
    print('PDF records={0} sections={1}'.format(
        len(records), len({record['section'] for record in records if record['section']})))
    if args.list:
        for record in records:
            print('{0} | {1} | {2} | {3}'.format(record['section'], record['number'],
                                                 record['answer'], record['stem'][:60]))
    bank = json.loads(open(args.bank, encoding='utf-8').read())
    rows, matched = compare(records, bank)
    agree = [row for row in rows if row['agree'] is True]
    disagree = [row for row in rows if row['agree'] is False]
    unmatched = [row for row in rows if row['agree'] is None]
    print('BANK questions={0} matched_in_pdf={1} agree={2} disagree={3} not_in_pdf={4}'.format(
        len(rows), matched, len(agree), len(disagree), len(unmatched)))
    for row in disagree:
        print('DISAGREE {0}-{1} bank={2} pdf={3} :: {4}'.format(
            row['section'], row['idx'], row['bank_correct'], row['pdf_answer'], row['stem'][:50]))
    for row in unmatched:
        print('NOT_IN_PDF {0}-{1} :: {2}'.format(row['section'], row['idx'], row['stem'][:50]))
    if args.json:
        with open(args.json, 'w', encoding='utf-8') as handle:
            json.dump({'records': records, 'rows': rows}, handle, ensure_ascii=False, indent=1)
    if args.external_out:
        candidates = build_candidates(rows, Path(args.pdf).stem)
        with open(args.external_out, 'w', encoding='utf-8') as handle:
            json.dump(candidates, handle, ensure_ascii=False, indent=1)
        total = sum(len(entries) for entries in candidates.values())
        print('EXTERNAL_CANDIDATES={0} SECTIONS={1} WROTE={2}'.format(total, len(candidates), args.external_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
