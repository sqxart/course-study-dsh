import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'split_bundles.py'
spec = importlib.util.spec_from_file_location('split_bundles', SCRIPT)
split = importlib.util.module_from_spec(spec)
spec.loader.exec_module(split)


def bundle(section='7.4', **kwargs):
    data = {
        'section': section,
        'capture': {'section': section, 'meta': {'total_score': 100}, 'questions': [{'qid': '1'}]},
        'popquiz': [],
        'evidence': {'section': {'code': section}, 'platform': {'toc_before': {'task_points': 2},
                                                                'toc_after': {'task_points': None}}},
    }
    data.update(kwargs)
    return data


class SplitBundlesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)

    def test_writes_capture_evidence_under_course_dir(self):
        result = split.split_one(bundle(), self.out, course='shufa')
        self.assertTrue(result['ok'])
        self.assertEqual(sorted(result['written']), ['capture', 'evidence'])
        capture = json.loads((self.out / 'captures' / 'shufa' / '7.4.json').read_text(encoding='utf-8'))
        self.assertEqual(capture['section'], '7.4')
        evidence = json.loads((self.out / 'nodes' / 'evidence-7.4.json').read_text(encoding='utf-8'))
        self.assertEqual(evidence['section']['code'], '7.4')

    def test_null_task_points_becomes_zero_with_deviation(self):
        result = split.split_one(bundle(), self.out, course='c')
        self.assertTrue(result['ok'])
        evidence = json.loads((self.out / 'nodes' / 'evidence-7.4.json').read_text(encoding='utf-8'))
        self.assertEqual(evidence['platform']['toc_after']['task_points'], 0)
        self.assertEqual(evidence['platform']['toc_before']['task_points'], 2)
        self.assertTrue(any('toc_after' in item for item in evidence['deviations']))

    def test_popquiz_items_get_segment_index(self):
        data = bundle(popquiz=[{'stem': 'a'}, {'stem': 'b'}])
        result = split.split_one(data, self.out, course='c')
        self.assertIn('popquiz-1', result['written'])
        second = json.loads((self.out / 'popquiz' / 'c' / '7.4-1.json').read_text(encoding='utf-8'))
        self.assertEqual(second['segment'], 1)
        self.assertEqual(second['section'], '7.4')

    def test_missing_section_is_reported(self):
        result = split.split_one({'capture': {}}, self.out)
        self.assertFalse(result['ok'])
        self.assertIn('no section', result['problems'])

    def test_empty_bundle_is_reported(self):
        result = split.split_one({'section': '1.1', 'capture': None, 'popquiz': [], 'evidence': None}, self.out)
        self.assertFalse(result['ok'])
        self.assertIn('bundle has no capture/popquiz/evidence', result['problems'])

    def test_check_mode_writes_nothing(self):
        split.split_one(bundle(), self.out, course='c', write=False)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_cli_summarises_and_defaults_out_to_parent(self):
        bundles = self.out / 'bundles'
        bundles.mkdir()
        (bundles / '7.4.json').write_text(json.dumps(bundle(), ensure_ascii=False), encoding='utf-8')
        code = split.main(['--bundles', str(bundles), '--course', 'shufa'])
        self.assertEqual(code, 0)
        self.assertTrue((self.out / 'captures' / 'shufa' / '7.4.json').exists())

    def test_cli_reports_bad_bundle(self):
        bundles = self.out / 'bundles'
        bundles.mkdir()
        (bundles / 'bad.json').write_text('{not json', encoding='utf-8')
        code = split.main(['--bundles', str(bundles), '--check'])
        self.assertEqual(code, 1)


if __name__ == '__main__':
    unittest.main()
