"""Offline tests for the node evidence validator."""

import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('check_evidence', ROOT / 'scripts' / 'check_evidence.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

BASE = {
    'schema_version': 1,
    'kind': 'pre-run-evidence',
    'mode': 'evidence',
    'authorization': {'source': 'local/private.toml', 'submit': False, 'redo_once': False},
    'course': {'title': '地球历史及其生命的奥秘', 'course_id': 260001},
    'section': {'code': '1.2.1', 'title': '示例章节'},
    'video': {
        'duration_seconds': 300.0, 'rate': 1, 'rate_source': 'locked', 'ended': True,
        'observer_calls': 3, 'subtitles': {'srt': [], 'allsubtitle_body': '[]'},
    },
    'popup': {'question': '...', 'selected': 'D', 'low_confidence': True, 'evidence_status': 'insufficient-evidence'},
    'quiz': {
        'work_id': 'work-example', 'submitted': False, 'decision': 'do-not-submit',
        'options_clicked': 0, 'submit_clicked': 0, 'reopened': False,
    },
    'platform': {'toc_before': {'task_points': 2}, 'toc_after': {'task_points': 1}},
    'cost': {'tool_calls': 12},
    'deviations': ['no subtitle track'],
}


def record(**changes):
    value = copy.deepcopy(BASE)
    for path, new in changes.items():
        target = value
        parts = path.split('__')
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = new
    return value


class EvidenceCheckTest(unittest.TestCase):
    def test_valid_record_passes(self):
        errors, warnings = check.validate(record(), require_readonly=True)
        self.assertEqual(errors, [])
        self.assertTrue(any('no subtitle' in item for item in warnings))

    def test_submission_in_evidence_mode_fails(self):
        errors, _ = check.validate(record(quiz__submitted=True, quiz__decision='submit'))
        self.assertTrue(any('must be false' in item for item in errors))
        self.assertTrue(any('do-not-submit' in item for item in errors))

    def test_missing_decision_fails(self):
        value = record()
        del value['quiz']['decision']
        errors, _ = check.validate(value)
        self.assertTrue(any('quiz.decision' in item for item in errors))

    def test_readonly_rejects_option_clicks(self):
        errors, _ = check.validate(record(quiz__options_clicked=1), require_readonly=True)
        self.assertTrue(any('options_clicked' in item for item in errors))

    def test_readonly_rejects_reopen(self):
        errors, _ = check.validate(record(quiz__reopened=True), require_readonly=True)
        self.assertTrue(any('reopened' in item for item in errors))

    def test_readonly_click_counts_must_be_integers(self):
        errors, _ = check.validate(record(quiz__options_clicked=False), require_readonly=True)
        self.assertTrue(any('options_clicked' in item for item in errors))

    def test_task_points_cannot_increase(self):
        errors, _ = check.validate(record(platform={'toc_before': {'task_points': 1}, 'toc_after': {'task_points': 2}}))
        self.assertTrue(any('cannot increase' in item for item in errors))

    def test_unchanged_task_points_warn(self):
        _, warnings = check.validate(record(platform={'toc_before': {'task_points': 2}, 'toc_after': {'task_points': 2}}))
        self.assertTrue(any('did not drop' in item for item in warnings))

    def test_incomplete_video_needs_the_flag(self):
        errors, _ = check.validate(record(video__ended=False))
        self.assertTrue(any('video.ended' in item for item in errors))
        errors, _ = check.validate(record(video__ended=False), allow_incomplete=True)
        self.assertEqual(errors, [])

    def test_bad_rate_source_and_mode_fail(self):
        errors, _ = check.validate(record(mode='auto', video__rate_source='guess'))
        self.assertTrue(any('mode' in item for item in errors))
        self.assertTrue(any('rate_source' in item for item in errors))

    def test_completion_submission_is_allowed(self):
        value = record(mode='completion', authorization={'submit': True, 'redo_once': False},
                       quiz={'submitted': True, 'decision': 'submit'})
        errors, _ = check.validate(value)
        self.assertEqual(errors, [])

    def test_platform_status_is_accepted_without_warning(self):
        errors, warnings = check.validate(record(quiz__platform_status='已查看'), require_readonly=True)
        self.assertEqual(errors, [])
        self.assertFalse(any('platform_status' in item for item in warnings))

    def test_unknown_platform_status_warns(self):
        _, warnings = check.validate(record(quiz__platform_status='unknown'))
        self.assertTrue(any('platform_status' in item for item in warnings))
        _, warnings = check.validate(record(quiz__platform_status=['已查看']))
        self.assertTrue(any('platform_status' in item for item in warnings))

    def test_opened_quiz_without_platform_status_warns(self):
        _, warnings = check.validate(record(quiz__work_answer_id='answer-example'))
        self.assertTrue(any('platform_status' in item for item in warnings))

    def test_platform_status_not_required_when_quiz_closed(self):
        _, warnings = check.validate(record())
        self.assertFalse(any('platform_status' in item for item in warnings))

    def test_add_times_must_be_a_nonnegative_integer(self):
        errors, _ = check.validate(record(quiz__add_times=-1))
        self.assertTrue(any('add_times' in item for item in errors))
        errors, _ = check.validate(record(quiz__add_times=True))
        self.assertTrue(any('add_times' in item for item in errors))
        errors, _ = check.validate(record(quiz__add_times=0))
        self.assertFalse(any('add_times' in item for item in errors))

    def test_limit_must_be_a_positive_integer(self):
        errors, _ = check.validate(record(quiz__limit_work_submit_times=0))
        self.assertTrue(any('limit_work_submit_times' in item for item in errors))
        errors, _ = check.validate(record(quiz__limit_work_submit_times=100))
        self.assertFalse(any('limit_work_submit_times' in item for item in errors))


class EvidenceCliTest(unittest.TestCase):
    def call(self, args):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = check.main(args)
        return code, buffer.getvalue()

    def test_ok_file_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'evidence.json'
            path.write_text(json.dumps(BASE, ensure_ascii=False), encoding='utf-8')
            code, output = self.call([str(path), '--require-readonly'])
        self.assertEqual(code, 0)
        self.assertIn('OK ', output)

    def test_failing_record_exits_five(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'evidence.json'
            path.write_text(json.dumps(record(quiz__submitted=True), ensure_ascii=False), encoding='utf-8')
            code, output = self.call([str(path)])
        self.assertEqual(code, 5)
        self.assertIn('FAIL ', output)

    def test_invalid_json_exits_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'evidence.json'
            path.write_text('{not json', encoding='utf-8')
            code, _ = self.call([str(path)])
        self.assertEqual(code, 2)

    def test_missing_file_exits_two(self):
        code, _ = self.call(['definitely-not-there.json'])
        self.assertEqual(code, 2)

    def test_json_report_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'evidence.json'
            path.write_text(json.dumps(BASE, ensure_ascii=False), encoding='utf-8')
            code, output = self.call([str(path), '--json'])
        self.assertEqual(code, 0)
        report = json.loads(output)
        self.assertEqual(report['status'], 'ok')
        self.assertEqual(report['toc'], [2, 1])
        self.assertEqual(report['submitted'], False)

    def test_json_report_reads_platform_fields(self):
        value = record(quiz__platform_status='已查看', quiz__add_times=0,
                       quiz__limit_work_submit_times=100)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'evidence.json'
            path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
            code, output = self.call([str(path), '--json'])
        self.assertEqual(code, 0)
        report = json.loads(output)
        self.assertEqual(report['platform_status'], '已查看')
        self.assertEqual(report['add_times'], 0)
        self.assertEqual(report['limit_work_submit_times'], 100)

    def test_text_report_shows_platform_status(self):
        value = record(quiz__platform_status='已查看')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'evidence.json'
            path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
            code, output = self.call([str(path), '--require-readonly'])
        self.assertEqual(code, 0)
        self.assertIn('platform=已查看', output)


if __name__ == '__main__':
    unittest.main()
