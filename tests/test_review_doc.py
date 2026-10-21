"""Unit tests for the review document assembler (scripts/review_doc.py)."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'review_doc.py'


def load():
    spec = importlib.util.spec_from_file_location('review_doc', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


review = load()

SRT = """1
00:00:05,000 --> 00:00:09,000
语言的线条性是指符号只能依次出现。

2
00:00:20,000 --> 00:00:25,000
语言的层次性体现在音位、语素、词、句的层层组合。

3
00:01:40,000 --> 00:01:44,000
与本题无关的一句话。
"""


def question(**over):
    base = {
        'idx': 1, 'qid': 'q1', 'type': 'single', 'type_label': '【单选题】',
        'stem': '（）是观察人类语言和动物语言最重要的窗口之一。',
        'options': [{'key': 'A', 'text': '语言的声音'}, {'key': 'B', 'text': '语言的层次性'},
                    {'key': 'C', 'text': '语言的线条性'}],
        'my_answer': 'B', 'correct': None, 'correct_source': None, 'verdict': 'wrong',
        'score': 0, 'max_score': 50.0,
    }
    base.update(over)
    return base


def bank(**over):
    section = {'section': '1.1', 'section_title': '测试节', 'work_id': '100', 'attempt': 1,
               'full_score': 100, 'total_score': 50, 'questions': [question()]}
    base = {
        'schema_version': 1, 'kind': 'quiz-bank', 'course': 'demo', 'course_title': '演示课',
        'generated_at': '2026-10-21T00:00:00Z',
        'source': {'answer_visible': False},
        'stats': {'sections': 1, 'questions': 1, 'with_answer': 0, 'with_stem_only': 1,
                  'correct': 0, 'wrong': 1, 'partial': 0, 'unknown': 0},
        'chapters': [{'label': '1 测试章', 'code': '1', 'title': '测试章', 'sections': [section]}],
    }
    base.update(over)
    return base


class QuoteTest(unittest.TestCase):
    def cues(self):
        return review.load_subtitle_module().parse_srt(SRT)

    def test_terms_come_from_option_texts_and_skip_short_ones(self):
        terms = review.key_terms([question(options=[{'key': 'A', 'text': '声音'},
                                                    {'key': 'B', 'text': '语言的层次性'}])])
        self.assertEqual(terms, ['语言的层次性'])

    def test_only_cues_containing_a_term_are_quoted(self):
        cues = self.cues()
        quotes = review.quote_cues(cues, ['语言的层次性', '语言的线条性'])
        self.assertEqual([cue['start_ms'] for cue in quotes], [5000, 20000])

    def test_one_quote_per_term_and_order_follows_the_subtitle(self):
        cues = self.cues()
        quotes = review.quote_cues(cues, ['语言的线条性', '语言的线条性'])
        self.assertEqual(len(quotes), 1)


class RenderTest(unittest.TestCase):
    def test_quiz_only_document_says_so(self):
        text = review.build_review(bank(), {})
        self.assertIn('evidence_level: quiz-only', text)
        self.assertIn('本课没有可用字幕', text)
        self.assertIn('本节无字幕，只有题库。', text)
        self.assertIn('正确答案：未开放（平台未给出，不猜）', text)

    def test_wrong_answer_becomes_an_error_note(self):
        text = review.build_review(bank(), {})
        self.assertIn('第 1 题【单选题】：我选 B，判错。', text)
        self.assertNotIn('本节没有错题', text)

    def test_subtitle_quotes_are_timestamped_and_overlap_the_questions(self):
        cues = review.load_subtitle_module().parse_srt(SRT)
        text = review.build_review(bank(), {'1.1': cues})
        self.assertIn('evidence_level: bank+subtitle', text)
        self.assertIn('- [00:00:20] 语言的层次性体现在音位、语素、词、句的层层组合。', text)
        self.assertIn('- [00:00:05] 语言的线条性是指符号只能依次出现。', text)
        self.assertNotIn('与本题无关的一句话', text)

    def test_full_mark_answer_is_labelled_as_derived(self):
        built = bank()
        built['chapters'][0]['sections'][0]['questions'] = [
            question(verdict='correct', score=50, my_answer='B', correct='B',
                     correct_source='derived_from_full_score')]
        text = review.build_review(built, {})
        self.assertIn('正确答案：B（满分反推）', text)
        self.assertIn('本节没有错题', text)


class CliTest(unittest.TestCase):
    def test_cli_writes_review_next_to_the_bank(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            bank_path = directory / 'bank.json'
            bank_path.write_text(json.dumps(bank(), ensure_ascii=False), encoding='utf-8')
            subs = directory / 'subs'
            subs.mkdir()
            (subs / '1.1.srt').write_text(SRT, encoding='utf-8')
            (subs / '2.2.srt').write_text('not a subtitle', encoding='utf-8')
            result = subprocess.run([sys.executable, str(SCRIPT), '--bank', str(bank_path),
                                     '--subs', str(subs)], capture_output=True, text=True,
                                    encoding='utf-8', errors='replace')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('WITH_SUBTITLE=1', result.stdout)
            self.assertIn('SKIP 2.2.srt', result.stderr)
            text = (directory / 'review.md').read_text(encoding='utf-8')
            self.assertIn('演示课 复习文档', text)


if __name__ == '__main__':
    unittest.main()
