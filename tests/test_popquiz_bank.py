"""Unit tests for the in-video popup bank (scripts/popquiz_bank.py) and its bank.md hook."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'popquiz_bank.py'
QUIZ = ROOT / 'scripts' / 'quiz_bank.py'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


popquiz = load(SCRIPT, 'popquiz_bank')
quiz_bank = load(QUIZ, 'quiz_bank')


def capture(**over):
    base = {
        'schema_version': 1, 'kind': 'video-quiz-capture', 'course': 'earth-history',
        'account': 'account-a', 'channel': 'mcp__browser', 'section': '1.4.2', 'segment': 0,
        'qtype': 'single', 'stem': '臭氧层的作用？',
        'options': [{'key': 'A', 'text': '氧气'}, {'key': 'B', 'text': '臭氧'}],
        'my_answer': 'B', 'verdict': 'correct', 'revealed_correct': None,
        'evidence_status': 'transcript', 'quote': '臭氧层对紫外线起到屏障作用。',
        'video_time': 329,
    }
    base.update(over)
    return base


class NormalizeTest(unittest.TestCase):
    def test_plain_capture(self):
        node = popquiz.normalize_capture(capture())
        self.assertEqual(node['section'], '1.4.2')
        self.assertEqual([option['key'] for option in node['options']], ['A', 'B'])
        self.assertIsNone(node['revealed_correct'])

    def test_wrong_kind_rejected(self):
        with self.assertRaises(ValueError):
            popquiz.normalize_capture(capture(kind='quiz-bank-capture'))

    def test_answer_outside_options_rejected(self):
        with self.assertRaises(ValueError):
            popquiz.normalize_capture(capture(my_answer='D'))

    def test_revealed_key_outside_options_rejected(self):
        with self.assertRaises(ValueError):
            popquiz.normalize_capture(capture(revealed_correct=['Z']))

    def test_empty_stem_rejected(self):
        with self.assertRaises(ValueError):
            popquiz.normalize_capture(capture(stem='  '))

    def test_bad_section_rejected(self):
        with self.assertRaises(ValueError):
            popquiz.normalize_capture(capture(section='第一节'))


class CheckTest(unittest.TestCase):
    def test_clean_capture_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '1.4.2-0.json'
            path.write_text(json.dumps(capture(), ensure_ascii=False), encoding='utf-8')
            report = popquiz.check_capture(path)
        self.assertTrue(report['ok'], report['problems'])
        self.assertEqual(report['section'], '1.4.2')

    def test_transcript_without_quote_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'x.json'
            path.write_text(json.dumps(capture(quote=''), ensure_ascii=False), encoding='utf-8')
            report = popquiz.check_capture(path)
        self.assertFalse(report['ok'])
        self.assertIn('without a quote', ' '.join(report['problems']))

    def test_correct_verdict_must_match_revealed_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'x.json'
            path.write_text(json.dumps(capture(revealed_correct=['A']), ensure_ascii=False), encoding='utf-8')
            report = popquiz.check_capture(path)
        self.assertFalse(report['ok'])


class BuildTest(unittest.TestCase):
    def nodes(self):
        return [popquiz.normalize_capture(capture(segment=1, stem='第二题')),
                popquiz.normalize_capture(capture()),
                popquiz.normalize_capture(capture(section='1.2.3', my_answer='A', verdict='wrong'))]

    def test_groups_by_section_and_orders_segments(self):
        bank = popquiz.build_bank(self.nodes(), 'earth-history', '地球历史')
        self.assertEqual([section['section'] for section in bank['sections']], ['1.2.3', '1.4.2'])
        self.assertEqual([question['stem'] for question in bank['sections'][1]['questions']], ['臭氧层的作用？', '第二题'])
        self.assertEqual(bank['stats']['sections'], 2)
        self.assertEqual(bank['stats']['questions'], 3)
        self.assertEqual(bank['stats']['with_answer'], 0)
        self.assertEqual(bank['stats']['wrong'], 1)

    def test_markdown_keeps_sources_separate_and_ticks_only_revealed(self):
        bank = popquiz.build_bank(self.nodes(), 'earth-history', '地球历史')
        text = popquiz.render_markdown(bank)
        self.assertIn('弹题库', text)
        self.assertIn('与章节测验分开', text)
        self.assertIn('平台未公布任何弹题正确答案', text)
        self.assertIn('视频 05:29', text)
        self.assertIn('判定：wrong', text)
        self.assertNotIn(' ✓', text)

    def test_markdown_ticks_revealed_option(self):
        bank = popquiz.build_bank([popquiz.normalize_capture(capture(revealed_correct=['B']))], 'earth-history')
        text = popquiz.render_markdown(bank)
        self.assertIn('B、臭氧 ✓', text)
        self.assertIn('正确答案：B', text)

    def test_index_out_counts_per_section(self):
        bank = popquiz.build_bank(self.nodes(), 'earth-history')
        index = {section['section']: len(section['questions']) for section in bank['sections']}
        self.assertEqual(index, {'1.2.3': 1, '1.4.2': 2})


class BankMarkdownHookTest(unittest.TestCase):
    def node(self):
        return {
            'section': '1.4.2', 'section_title': '1.4.2 从稠云密雾到碧野蓝天', 'chapter': '1 地球',
            'work_id': '1', 'work_answer_id': '2', 'answer_visible': False,
            'total_score': 100, 'full_score': 100, 'attempt': 1, 'question_count': 1,
            'questions': [{
                'idx': 1, 'qid': 'q1', 'qtype_text': '【单选题】', 'type_label': '【单选题】',
                'stem': '题干一',
                'options': [{'key': 'A', 'text': '甲'}], 'my_answer': 'A', 'correct': 'A',
                'correct_source': 'page', 'score': 100, 'max_score': 100, 'verdict': 'correct',
                'mark': 'marking_dui',
            }],
        }

    def test_popup_index_adds_one_pointer_line(self):
        bank = quiz_bank.build_bank([self.node()], 'earth-history', popquiz={'1.4.2': 2})
        text = quiz_bank.render_bank_markdown(bank)
        self.assertIn('本节另有弹题 2 题，见 `popquiz.md`', text)
        self.assertEqual(bank['chapters'][0]['sections'][0]['popup_count'], 2)

    def test_without_index_no_pointer_line(self):
        bank = quiz_bank.build_bank([self.node()], 'earth-history')
        text = quiz_bank.render_bank_markdown(bank)
        self.assertNotIn('popquiz.md', text)


if __name__ == '__main__':
    unittest.main()
