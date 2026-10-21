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

GOOD_NOTE = """**本节讲什么**
这一节回答「智能汽车为什么必须换掉分布式电子电气架构」，先讲线控底盘留下的问题，
再给出新架构的三项硬指标，最后说明从域集中走向中央计算的路线图。结论是架构演进由带宽、
实时性与功能安全三条约束共同推动，不是单纯的硬件升级。

**要点**
1. **分布式架构的瓶颈**（00:00:46）：每个功能一个 ECU，线束长度和接插件数量随功能线性增长，
   整车重量、成本与故障点都被拖高，软件升级也只能逐个控制器刷写。
2. **高带宽**（00:01:17）：摄像头、激光雷达、毫米波雷达同时输出原始数据，带宽需求从几十 Mbps
   抬到 Gbps 量级，分布式总线扛不住。
3. **高实时性**（00:01:21）：底盘控制回路要求毫秒级确定性时延，网关转发的排队抖动不可接受。
4. **高安全性与高可靠性**（00:01:22）：制动、转向属于功能安全范畴，任一节点失效都要有冗余路径。
5. **域集中式**（00:03:40）：按功能域把多个 ECU 合并成域控制器，线束与算力集中，仍保留域间边界。
6. **跨域集中与中央计算**（00:05:10）：进一步把座舱、智驾、车控跨域融合，最后收拢到中央计算平台
   加区域控制器，软件按服务部署。

**关键概念**
- 电子电气架构（EEA）：整车控制器、传感器、执行器之间的拓扑与通信方式，决定线束、算力与升级路径。
- 域控制器：按功能域聚合多个 ECU 的控制器，负责本域的实时调度与故障隔离。
- 区域控制器：按物理位置聚合 IO，把「按功能」变成「按位置」，减少跨车线束。

**易混淆 / 易错**
- 域集中式与跨域集中式：前者按功能域划分且域间边界清晰，后者打破域边界、由中央计算统一调度。
- 高带宽与高实时性不是一回事：带宽解决数据量，实时性解决确定性时延，两者要分开设计。

**本节结论**
智能汽车需要高带宽、高实时性、高安全性与高可靠性的统一架构，演进路线是分布式 → 域集中 →
跨域集中 → 中央计算，驱动力是数据量、时延与功能安全三条硬约束。
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
        self.assertGreaterEqual(stats['points'], 5)
        self.assertGreaterEqual(stats['timestamps'], 3)
        self.assertGreaterEqual(stats['chars'], 400)

    def test_word_salad_is_rejected(self):
        thin = ('**本节讲什么**\n高带宽。\n\n**要点**\n1. 高带宽\n2. 高实时性\n3. 高安全性\n'
                '\n**关键概念**\n无\n\n**本节结论**\n就是这些。\n')
        problems, _ = knowledge.validate_note(thin)
        self.assertTrue(any('numbered points' in p for p in problems))
        self.assertTrue(any('chars' in p for p in problems))

    def test_quiz_text_is_rejected(self):
        problems, _ = knowledge.validate_note(GOOD_NOTE + '\n【单选题】下面哪项正确\n')
        self.assertTrue(any('quiz text' in p for p in problems))

    def test_missing_section_is_named(self):
        problems, _ = knowledge.validate_note(GOOD_NOTE.replace('**关键概念**', '**概念**'))
        self.assertIn('missing section: 关键概念', problems)

    def test_empty_note(self):
        problems, stats = knowledge.validate_note('')
        self.assertEqual(problems, ['note is empty'])
        self.assertEqual(stats, {})

    def test_time_ranges_count_as_anchors(self):
        # The spec prefers ranges, so the counter must not silently ignore them.
        text = GOOD_NOTE.replace('（00:01:17）', '（00:01:17–00:01:21）')
        problems, stats = knowledge.validate_note(text)
        self.assertEqual(problems, [])
        self.assertGreaterEqual(stats['timestamps'], 3)
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
