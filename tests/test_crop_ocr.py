"""Offline tests for anchor-based quiz screenshot cropping."""

import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "crop_ocr.py"
SPEC = importlib.util.spec_from_file_location("crop_ocr", SCRIPT)
cropper = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cropper)


def ocr_line(text, x, y, width=200, height=24):
    return {
        "text": text,
        "confidence": 0.9,
        "box": [[x, y], [x + width, y], [x + width, y + height], [x, y + height]],
    }


class FindRegionTest(unittest.TestCase):
    def test_region_from_anchors(self):
        lines = [
            ocr_line("一.单选题", 139, 390),
            ocr_line("1【单选题】题干", 210, 444),
            ocr_line("二.判断题", 139, 700),
        ]
        start, end = cropper.find_region(lines, "一.单选题", "二.判断题")
        self.assertEqual(start[1], 390)
        self.assertEqual(end[1], 700)

    def test_missing_start(self):
        lines = [ocr_line("二.判断题", 139, 700)]
        self.assertEqual(cropper.find_region(lines, "一.单选题", "二.判断题"), (None, None))

    def test_missing_end(self):
        lines = [ocr_line("一.单选题", 139, 390)]
        start, end = cropper.find_region(lines, "一.单选题", "二.判断题")
        self.assertEqual(start[1], 390)
        self.assertIsNone(end)

    def test_text_anchor_inside_long_line(self):
        lines = [ocr_line("1【单选题】以下哪句话不能体现", 210, 444), ocr_line("二.判断题", 139, 900)]
        start, _ = cropper.find_region(lines, "【单选题】", "二.判断题")
        self.assertEqual(start[1], 444)


class QuestionAnchorTest(unittest.TestCase):
    def test_numbered_stems_are_question_starts(self):
        for text in ("1【单选题】题干", "2、判断题", "3. 题干", "12【多选题】", "4) 题干"):
            self.assertTrue(cropper.question_start(text), text)

    def test_section_headers_and_prose_are_not(self):
        for text in ("一.单选题", "AI技术", "答案：A", "，1【单选题】错位"):
            self.assertFalse(cropper.question_start(text), text)

    def test_section_codes_and_scores_are_not_questions(self):
        for text in ("1.2", "1.2.3 什么是生命宜居带？", "50.0分", "2013年9月"):
            self.assertFalse(cropper.question_start(text), text)

    def test_section_headers_are_recognised(self):
        self.assertTrue(cropper.section_header("一.单选题"))
        self.assertTrue(cropper.section_header("二、判断题"))
        self.assertFalse(cropper.section_header("1【单选题】题干"))


class AutoRegionTest(unittest.TestCase):
    def test_region_runs_from_first_stem_to_next_stem(self):
        lines = [
            ocr_line("一.单选题", 139, 390),
            ocr_line("1【单选题】题干一", 210, 444),
            ocr_line("A 选项", 210, 492),
            ocr_line("2【单选题】题干二", 210, 600),
        ]
        start, end, stem = cropper.auto_region(lines)
        self.assertEqual((start[1], end[1]), (444, 600))
        self.assertEqual(stem, "1【单选题】题干一")

    def test_region_ends_at_the_next_section_header(self):
        lines = [ocr_line("1【单选题】题干", 210, 444), ocr_line("二.判断题", 139, 700)]
        start, end, _ = cropper.auto_region(lines)
        self.assertEqual(end[1], 700)

    def test_unsorted_lines_are_sorted_by_height(self):
        lines = [ocr_line("2【单选题】题干二", 210, 600), ocr_line("1【单选题】题干一", 210, 444)]
        start, end, stem = cropper.auto_region(lines)
        self.assertEqual((start[1], end[1]), (444, 600))
        self.assertEqual(stem, "1【单选题】题干一")

    def test_section_code_header_is_skipped(self):
        lines = [
            ocr_line("章节测验", 22, 21),
            ocr_line("1.2", 36, 86),
            ocr_line("1【单选题】题干一", 210, 444),
            ocr_line("A 选项", 210, 492),
            ocr_line("2【判断题】题干二", 210, 600),
        ]
        start, end, stem = cropper.auto_region(lines)
        self.assertEqual((start[1], end[1]), (444, 600))
        self.assertEqual(stem, "1【单选题】题干一")

    def test_no_question_returns_empty_anchors(self):
        self.assertEqual(cropper.auto_region([ocr_line("目录", 1176, 59)]), (None, None, ""))


if __name__ == "__main__":
    unittest.main()
