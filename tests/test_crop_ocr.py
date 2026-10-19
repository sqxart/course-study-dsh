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


if __name__ == "__main__":
    unittest.main()
