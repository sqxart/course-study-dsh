"""Unit tests for the result-page question bank (scripts/quiz_bank.py)."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'quiz_bank.py'


def load():
    spec = importlib.util.spec_from_file_location('quiz_bank', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bank = load()


def question(**over):
    base = {
        'idx': 1, 'qid': 'q1', 'qtype_text': '【单选题】', 'stem': '题干一',
        'options': [{'key': 'A', 'text': '选项甲'}, {'key': 'B', 'text': '选项乙'}],
        'my_answer': 'B', 'correct': None, 'score': 50, 'mark': 'marking_dui',
    }
    base.update(over)
    return base


def capture(**over):
    base = {
        'schema_version': 1, 'kind': 'quiz-bank-capture', 'course': 'demo', 'account': 'account-c',
        'channel': 'mcp__browser3', 'section': '1.1', 'section_title': '1.1 测试节',
        'chapter': '1 测试章', 'page': 'selectWorkQuestionYiPiYue',
        'page_path': '/mooc-ans/work/selectWorkQuestionYiPiYue', 'work_id': '100',
        'work_answer_id': '200', 'answer_visible': False,
        'meta': {'question_count': 2, 'full_score': 100, 'attempt': 1, 'total_score': 50,
                 'title': '1.1 测试节'},
        'fields': {'add_times': None, 'limit_work_submit_times': None, 'submit_button': False,
                   'timu': 2},
        'questions': [question(), question(qid='q2', idx=2, qtype_text='【多选题】', stem='题干二',
                                           my_answer='ABD', score=0, mark='marking_cuo')],
        'pagination_suspected': False,
        'toc': {'before': {'t': '1.1 测试节', 'p': []}, 'after': {'t': '1.1 测试节', 'p': []},
                'changed': False},
        'captured_at': '2026-10-21T05:00:00Z',
    }
    base.update(over)
    return base


class NormalizeQuestionTest(unittest.TestCase):
    def test_full_marks_derive_the_answer_but_label_the_source(self):
        record = bank.normalize_question(question(), 0, 100, 2)
        self.assertEqual(record['verdict'], 'correct')
        self.assertEqual(record['correct'], 'B')
        self.assertEqual(record['correct_source'], 'derived_from_full_score')
        self.assertEqual(record['max_score'], 50)

    def test_wrong_answer_stays_null_instead_of_guessing(self):
        record = bank.normalize_question(question(score=0, mark='marking_cuo'), 0, 100, 2)
        self.assertEqual(record['verdict'], 'wrong')
        self.assertIsNone(record['correct'])
        self.assertIsNone(record['correct_source'])
        self.assertEqual(record['my_answer'], 'B')

    def test_page_printed_answer_wins_over_the_score(self):
        record = bank.normalize_question(question(correct='D', score=50, mark='marking_dui'), 0, 100, 2)
        self.assertEqual(record['correct'], 'D')
        self.assertEqual(record['correct_source'], 'page')

    def test_partial_score_is_not_a_correct_verdict(self):
        record = bank.normalize_question(question(type=None, score=33.3, mark=None), 0, 100, 3)
        self.assertEqual(record['verdict'], 'partial')
        self.assertIsNone(record['correct'])

    def test_short_multi_select_is_partial_even_when_marked_wrong(self):
        record = bank.normalize_question(question(qtype_text='【多选题】', my_answer='AB',
                                                  score=16.7, mark='marking_cuo'), 0, 100, 3)
        self.assertEqual(record['verdict'], 'partial')
        self.assertIsNone(record['correct'])

    def test_judge_question_keeps_its_token(self):
        record = bank.normalize_question(question(qtype_text='【判断题】', options=[], my_answer='错'),
                                         0, 100, 2)
        self.assertEqual(record['type'], 'judge')
        self.assertEqual(record['options'], [])
        self.assertEqual(record['correct'], '错')

    def test_types_cover_blank_and_essay(self):
        self.assertEqual(bank.classify_type('【填空题】'), 'blank')
        self.assertEqual(bank.classify_type('【简答题】'), 'essay')
        self.assertEqual(bank.classify_type('【不定项】'), 'other')
        self.assertEqual(bank.classify_type(None), 'other')


class NormalizeCaptureTest(unittest.TestCase):
    def test_section_and_chapter_are_split_from_the_title(self):
        node = bank.normalize_capture(capture())
        self.assertEqual(node['section'], '1.1')
        self.assertEqual(node['section_title'], '测试节')
        self.assertEqual(node['question_count'], 2)

    def test_count_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            bank.normalize_capture(capture(meta={'question_count': 3, 'full_score': 100}))

    def test_empty_questions_are_rejected(self):
        with self.assertRaises(ValueError):
            bank.normalize_capture(capture(questions=[], meta={'question_count': 0}))

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            bank.normalize_capture(capture(kind='quiz-bank'))


class BuildBankTest(unittest.TestCase):
    def nodes(self):
        one = bank.normalize_capture(capture())
        two = bank.normalize_capture(capture(
            section='2.1', section_title='2.1 第二节', chapter='2 第二章', work_id='101',
            questions=[question(qid='q3', score=100, mark='marking_dui')],
            meta={'question_count': 1, 'full_score': 100, 'attempt': 1, 'total_score': 100}))
        return [two, one]

    def test_sections_sort_numerically_and_group_by_chapter(self):
        built = bank.build_bank(self.nodes(), course='demo', course_title='演示课')
        self.assertEqual([chapter['label'] for chapter in built['chapters']], ['1 测试章', '2 第二章'])
        self.assertEqual([section['section'] for chapter in built['chapters']
                          for section in chapter['sections']], ['1.1', '2.1'])

    def test_stats_count_answers_and_verdicts(self):
        built = bank.build_bank(self.nodes(), course='demo')
        stats = built['stats']
        self.assertEqual((stats['sections'], stats['questions']), (2, 3))
        self.assertEqual(stats['with_answer'], 2)
        self.assertEqual(stats['with_stem_only'], 1)
        self.assertEqual((stats['correct'], stats['wrong']), (2, 1))
        self.assertFalse(built['source']['answer_visible'])

    def test_coverage_names_the_missing_sections(self):
        built = bank.build_bank(self.nodes(), course='demo', expected=['1.1', '2.1', '3.1'])
        self.assertEqual(built['coverage']['missing_sections'], ['3.1'])
        self.assertEqual(built['coverage']['captured_sections'], 2)


class RenderTest(unittest.TestCase):
    def test_markdown_states_that_the_platform_hid_the_answer_key(self):
        built = bank.build_bank([bank.normalize_capture(capture())], course='demo', course_title='演示课')
        text = bank.render_bank_markdown(built)
        self.assertIn('正确答案键不可用', text)
        self.assertIn('B（满分反推）', text)
        self.assertIn('未提供（平台未开放正确答案）', text)
        self.assertIn('## 1 测试章', text)
        self.assertIn('### 1.1 测试节', text)
        self.assertNotIn('题号：', text)

    def test_markdown_flags_page_supplied_answers(self):
        built = bank.build_bank([bank.normalize_capture(capture(
            answer_visible=True, meta={'question_count': 1, 'full_score': 100, 'attempt': 1,
                                       'total_score': 100},
            questions=[question(correct='B', score=50, mark='marking_dui')]))], course='demo')
        text = bank.render_bank_markdown(built)
        self.assertIn('B（结果页给出）', text)
        self.assertNotIn('正确答案键不可用', text)
        # The tick sits on the correct option itself, and only there.
        self.assertIn('   - B、选项乙 ✓', text)
        self.assertNotIn('选项甲 ✓', text)
        self.assertNotIn('题号：', text)
        # Multi-select: every correct option gets its own tick.
        multi = bank.build_bank([bank.normalize_capture(capture(
            answer_visible=True, meta={'question_count': 1, 'full_score': 100, 'attempt': 1,
                                       'total_score': 100},
            questions=[question(qtype_text='【多选题】', correct='AB', score=100,
                                mark='marking_dui')]))], course='demo')
        multi_text = bank.render_bank_markdown(multi)
        self.assertIn('   - A、选项甲 ✓', multi_text)
        self.assertIn('   - B、选项乙 ✓', multi_text)
        # An outside key only shows up where the platform gave nothing, and says so.
        hinted = bank.build_bank([bank.normalize_capture(capture())], course='demo',
                                 external={'1.1': {'2': {'answer': 'ABD', 'source': '尔雅题库 测试'}}})
        hinted_text = bank.render_bank_markdown(hinted)
        self.assertIn('外部题库参考：ABD（尔雅题库 测试，非平台答案，谨慎采用）', hinted_text)
        self.assertNotIn('外部题库参考', text)


class CheckCaptureTest(unittest.TestCase):
    def write(self, payload):
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(payload, handle, ensure_ascii=False)
        handle.close()
        self.addCleanup(Path(handle.name).unlink)
        return handle.name

    def test_clean_capture_passes(self):
        report = bank.check_capture(self.write(capture()))
        self.assertTrue(report['ok'])
        self.assertEqual(report['with_answer'], 1)

    def test_submit_button_or_toc_drift_fails_the_check(self):
        report = bank.check_capture(self.write(capture(fields={'submit_button': True})))
        self.assertFalse(report['ok'])
        self.assertIn('submit button', ' '.join(report['problems']))
        report = bank.check_capture(self.write(capture(toc={'changed': True})))
        self.assertFalse(report['ok'])
        self.assertIn('catalogue row changed', ' '.join(report['problems']))

    def test_answer_page_capture_fails_the_check(self):
        report = bank.check_capture(self.write(capture(page='doHomeWorkNew')))
        self.assertFalse(report['ok'])


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                              text=True, encoding='utf-8', errors='replace')

    def test_check_exit_codes(self):
        with tempfile.TemporaryDirectory() as temporary:
            good = Path(temporary) / 'good.json'
            good.write_text(json.dumps(capture(), ensure_ascii=False), encoding='utf-8')
            self.assertEqual(self.run_cli('check', str(good)).returncode, 0)
            bad = Path(temporary) / 'bad.json'
            bad.write_text(json.dumps(capture(kind='other'), ensure_ascii=False), encoding='utf-8')
            self.assertEqual(self.run_cli('check', str(bad)).returncode, bank.EXIT_INVALID)

    def test_build_writes_both_deliverables_and_reports_coverage(self):
        with tempfile.TemporaryDirectory() as temporary:
            nodes = Path(temporary) / 'nodes'
            nodes.mkdir()
            (nodes / '1.1.json').write_text(json.dumps(capture(), ensure_ascii=False), encoding='utf-8')
            (nodes / 'notes.json').write_text(json.dumps({'kind': 'other'}), encoding='utf-8')
            expected = Path(temporary) / 'expected.json'
            expected.write_text(json.dumps(['1.1', '1.2']), encoding='utf-8')
            out = Path(temporary) / 'bank.json'
            md = Path(temporary) / 'bank.md'
            result = self.run_cli('build', '--nodes', str(nodes), '--course', 'demo',
                                  '--title', '演示课', '--expected', str(expected),
                                  '--out', str(out), '--md', str(md))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('SECTIONS=1', result.stdout)
            payload = json.loads(out.read_text(encoding='utf-8'))
            self.assertEqual(payload['coverage']['missing_sections'], ['1.2'])
            self.assertEqual(payload['course_title'], '演示课')
            self.assertIn('演示课 题库', md.read_text(encoding='utf-8'))
            self.assertIn('notes.json', result.stderr)

    def test_build_without_captures_exits_empty(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_cli('build', '--nodes', temporary, '--course', 'demo')
            self.assertEqual(result.returncode, bank.EXIT_EMPTY)


if __name__ == '__main__':
    unittest.main()
