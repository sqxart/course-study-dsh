"""Unit tests for the knowledge document (scripts/knowledge_doc.py)."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'knowledge_doc.py'


def load():
    spec = importlib.util.spec_from_file_location('knowledge_doc', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


knowledge = load()

GOOD_NOTE = """**考点知识**

- 公地的悲剧：公共资源产权边界不清、谁都能用而无人爱护，因而被过度使用。
- 它属于法律经济学、特别是产权经济学的视角。
- 福利经济学把同一现象称为外部性：一方使用资源，成本由另一方承担。
- 庇古传统据此主张政府管制与税收调节。
- 视角不同，推导出的方案不同：产权视角导向私有化，福利经济学导向管制。
- 「以前也是公有、为什么只有今年」这一问，说明单一时视角解释不了时间上的差异。
- 人口学视角把关键因素落在年龄分布上：儿童才会挖沙坑堆沙堡。
- 工程材料视角：沙与泥混合成砂浆，人工铺沙被台风削薄才露出泥潭。

**概念表**

- 公地的悲剧：产权不明晰导致的公共资源过度使用。
- 外部性：一些人使用资源、成本由另一些人承担。
- 庇古经济学：福利经济学传统，主张政府管制与税收调节。
"""


def bank():
    return {
        'schema_version': 1, 'kind': 'quiz-bank', 'course': 'demo', 'course_title': '演示课',
        'generated_at': '2026-10-21T00:00:00Z', 'source': {'answer_visible': False},
        'stats': {'sections': 2, 'questions': 2},
        'chapters': [{'label': '3 架构', 'code': '3', 'title': '架构', 'sections': [
            {'section': '3.1', 'section_title': '电子电气架构', 'questions': [{'idx': 1}]},
            {'section': '3.2', 'section_title': '传感器', 'questions': [{'idx': 1}]},
        ]}],
    }


class ValidateTest(unittest.TestCase):
    def test_a_real_note_passes(self):
        problems, stats = knowledge.validate_note(GOOD_NOTE)
        self.assertEqual(problems, [])
        self.assertGreaterEqual(stats['points'], 8)
        self.assertEqual(stats['timestamps'], 0)
        self.assertGreaterEqual(stats['chars'], 300)

    def test_word_salad_is_rejected(self):
        thin = ('**考点知识**\n- 高带宽\n- 高实时性\n\n**概念表**\n- 高带宽\n')
        problems, _ = knowledge.validate_note(thin)
        self.assertTrue(any('knowledge bullets' in p for p in problems))
        self.assertTrue(any('chars' in p for p in problems))

    def test_old_summary_format_is_retired(self):
        old = GOOD_NOTE.replace('**考点知识**', '**本节讲什么**').replace('**概念表**', '**本节结论**')
        problems, _ = knowledge.validate_note(old)
        self.assertTrue(any('old summary format' in p for p in problems))

    def test_quiz_text_is_rejected(self):
        problems, _ = knowledge.validate_note(GOOD_NOTE + '\n【单选题】下面哪项正确\n')
        self.assertTrue(any('quiz text' in p for p in problems))

    def test_missing_section_is_named(self):
        problems, _ = knowledge.validate_note(GOOD_NOTE.replace('**概念表**', '**概念**'))
        self.assertIn('missing section: 概念表', problems)

    def test_empty_note(self):
        problems, stats = knowledge.validate_note('')
        self.assertEqual(problems, ['note is empty'])
        self.assertEqual(stats, {})

    def test_time_ranges_count_as_anchors(self):
        # The review card must not carry a timeline at all.
        text = GOOD_NOTE.replace('- 公地的悲剧：公共资源', '- 公地的悲剧（00:01:17）：公共资源')
        problems, stats = knowledge.validate_note(text)
        self.assertTrue(any('timestamps are not wanted' in p for p in problems))
        self.assertGreaterEqual(stats['timestamps'], 1)
        self.assertEqual(len(knowledge.TIMESTAMP.findall('（00:01:17–00:01:21）')), 1)
        self.assertEqual(len(knowledge.TIMESTAMP.findall('(00:01:17 - 00:01:21)')), 1)


class BuildTest(unittest.TestCase):
    def test_notes_are_stitched_under_bank_headings(self):
        text = knowledge.build_knowledge(bank(), {'3.1': {'text': GOOD_NOTE, 'problems': [], 'stats': {}}})
        self.assertIn('## 3 架构', text)
        self.assertIn('### 3.1 电子电气架构', text)
        self.assertIn('### 3.2 传感器', text)
        self.assertIn('本节测验 1 题', text)
        self.assertIn('（本节暂无字幕总结，待补；题目见 bank.md）', text)

    def test_header_separates_bank_from_knowledge(self):
        text = knowledge.build_knowledge(bank(), {})
        self.assertIn('题目、选项、我的答案、得分在 `bank.md`', text)
        self.assertIn('覆盖：0/2 节', text)

    def test_quiz_text_never_leaks_into_the_document(self):
        text = knowledge.build_knowledge(bank(), {})
        for marker in ('【单选题】', '【多选题】', '【判断题】', '我的答案：'):
            self.assertNotIn(marker, text)
        self.assertIn('题目、选项、我的答案、得分在 `bank.md`', text)


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                              text=True, encoding='utf-8', errors='replace')

    def test_check_exit_codes(self):
        with tempfile.TemporaryDirectory() as temporary:
            good = Path(temporary) / 'good.md'
            good.write_text(GOOD_NOTE, encoding='utf-8')
            self.assertEqual(self.run_cli('check', str(good)).returncode, 0)
            bad = Path(temporary) / 'bad.md'
            bad.write_text('**本节讲什么**\n不知道\n', encoding='utf-8')
            self.assertEqual(self.run_cli('check', str(bad)).returncode, 2)

    def test_build_reports_weak_notes_and_writes_the_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            bank_path = directory / 'bank.json'
            bank_path.write_text(json.dumps(bank(), ensure_ascii=False), encoding='utf-8')
            notes = directory / 'notes'
            notes.mkdir()
            (notes / '3.1.md').write_text(GOOD_NOTE, encoding='utf-8')
            (notes / '3.2.md').write_text('**本节讲什么**\n太短了\n', encoding='utf-8')
            result = self.run_cli('build', '--bank', str(bank_path), '--notes', str(notes))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('NOTES=2', result.stdout)
            self.assertIn('WEAK 3.2.md', result.stderr)
            self.assertTrue((directory / 'knowledge.md').exists())


if __name__ == '__main__':
    unittest.main()
