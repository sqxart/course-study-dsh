"""Offline tests for the TOC status reader and the session cost report."""

import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


toc = load('toc_status')
cost = load('session_cost')

SNAPSHOT = '''
- iframe [ref=f1e1]:
  - list [ref=f1e5]:
    - listitem [ref=f1e6]:
      - link "1.1.1 古老的美好神话" [ref=f1e7]:
    - listitem:
      - link "1.3.1 原始地球的熔融与圈层分异 2" [ref=f3e113]:
    - listitem:
      - link "1.3.2 照亮地球内部的明灯 1" [ref=f3e122]:
    - listitem:
      - link "1.3.2 重复出现的行 1" [ref=f3e122]:
    - listitem:
      - link "2.1 ”发财“记 2" [ref=f3e200]:
'''


class TocStatusTest(unittest.TestCase):
    def test_parses_codes_titles_and_badges(self):
        sections = toc.parse_snapshot(SNAPSHOT)
        self.assertEqual([s['code'] for s in sections], ['1.1.1', '1.3.1', '1.3.2', '2.1'])
        self.assertEqual(sections[0]['unfinished'], 0)
        self.assertEqual(sections[1]['unfinished'], 2)
        self.assertEqual(sections[2]['title'], '照亮地球内部的明灯')

    def test_duplicate_codes_are_collapsed(self):
        codes = [s['code'] for s in toc.parse_snapshot(SNAPSHOT)]
        self.assertEqual(codes.count('1.3.2'), 1)

    def test_summary_counts_sections_and_tasks(self):
        report = toc.summarize(toc.parse_snapshot(SNAPSHOT))
        self.assertEqual(report['sections'], 4)
        self.assertEqual(report['unfinished_sections'], 3)
        self.assertEqual(report['unfinished_tasks'], 5)
        self.assertEqual(report['chapters']['1']['unfinished_tasks'], 3)
        self.assertEqual(report['chapters']['2']['unfinished_sections'], 1)

    def test_prefix_filter(self):
        sections = toc.filter_prefix(toc.parse_snapshot(SNAPSHOT), '1.3')
        self.assertEqual([s['code'] for s in sections], ['1.3.1', '1.3.2'])

    def test_no_links_is_an_error(self):
        import contextlib
        import sys
        previous = sys.stdin
        sys.stdin = io.StringIO('nothing that looks like a section link')
        try:
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                code = toc.main(['-'])
        finally:
            sys.stdin = previous
        self.assertEqual(code, 2)

    def test_brief_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'snap.yml'
            path.write_text(SNAPSHOT, encoding='utf-8')
            buffer = io.StringIO()
            import contextlib
            with contextlib.redirect_stdout(buffer):
                code = toc.main([str(path), '--fail-if-unfinished'])
            self.assertEqual(code, toc.EXIT_UNFINISHED)
            self.assertIn('UNFINISHED_TASKS=5', buffer.getvalue())

    def test_missing_file_returns_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            buffer = io.StringIO()
            import contextlib
            with contextlib.redirect_stdout(buffer):
                code = toc.main([str(Path(tmp) / 'nope.yml')])
            self.assertEqual(code, 2)


ROWS = {
    'rows': [
        {'sec': '1.1', 'name': '甲', 'pt': None},
        {'sec': '1.2', 'name': '乙', 'pt': '2'},
        {'sec': '1.3', 'name': '丙', 'pt': 1},
        {'sec': '1.4', 'name': '丁', 'pt': '0'},
        {'sec': '1.5', 'name': '戊', 'pt': '1个待完成任务点'},
        {'sec': '', 'name': '第一章 标题行'},
        {'sec': '1.5', 'name': '戊（重复行）', 'pt': 4},
    ]
}


class TocRowsTest(unittest.TestCase):
    def test_null_and_zero_mean_clear(self):
        by_code = {s['code']: s for s in toc.parse_rows(ROWS)}
        self.assertEqual(by_code['1.1']['unfinished'], 0)
        self.assertEqual(by_code['1.4']['unfinished'], 0)

    def test_int_and_labelled_text_are_read(self):
        by_code = {s['code']: s for s in toc.parse_rows(ROWS)}
        self.assertEqual(by_code['1.2']['unfinished'], 2)
        self.assertEqual(by_code['1.3']['unfinished'], 1)
        self.assertEqual(by_code['1.5']['unfinished'], 1)

    def test_untitled_rows_are_skipped_and_duplicates_collapsed(self):
        sections = toc.parse_rows(ROWS)
        self.assertEqual([s['code'] for s in sections], ['1.1', '1.2', '1.3', '1.4', '1.5'])

    def test_bare_list_is_accepted(self):
        self.assertEqual(len(toc.parse_rows([{'sec': '2.1', 'pt': None}])), 1)

    def test_probe_tuple_rows_are_accepted(self):
        data = {'rows': [['1.1', '绪论', '2', 'c-1'], ['1.2', '简史', None, 'c-2'], ['9.9']]}
        sections = toc.parse_rows(data)
        self.assertEqual([s['code'] for s in sections], ['1.1', '1.2'])
        self.assertEqual(sections[0]['unfinished'], 2)
        self.assertEqual(sections[1]['unfinished'], 0)
        self.assertEqual(sections[0]['title'], '绪论')

    def test_rows_file_drives_the_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'toc-final.json'
            path.write_text(json.dumps(ROWS), encoding='utf-8')
            buffer = io.StringIO()
            import contextlib
            with contextlib.redirect_stdout(buffer):
                code = toc.main(['--rows', str(path), '--fail-if-unfinished'])
            self.assertEqual(code, toc.EXIT_UNFINISHED)
            self.assertIn('UNFINISHED_TASKS=4', buffer.getvalue())

    def test_rows_and_snapshot_together_is_an_error(self):
        buffer = io.StringIO()
        import contextlib
        with contextlib.redirect_stdout(buffer):
            code = toc.main(['-', '--rows', 'x.json'])
        self.assertEqual(code, 2)

    def test_bad_rows_json_returns_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'toc.json'
            path.write_text('{"rows": "not a list"}', encoding='utf-8')
            buffer = io.StringIO()
            import contextlib
            with contextlib.redirect_stdout(buffer):
                code = toc.main(['--rows', str(path)])
            self.assertEqual(code, 2)
            self.assertIn('cannot read rows', buffer.getvalue())


def make_session(events):
    import zstandard
    payload = '\n'.join(json.dumps(event, ensure_ascii=False) for event in events).encode('utf-8')
    return zstandard.ZstdCompressor().compress(payload)


class SessionCostTest(unittest.TestCase):
    def test_tokens_calls_and_turns(self):
        events = [
            {'type': 'turn/start', 'time': 1000, 'data': {'turn': 1}},
            {'type': 'assistant/message', 'time': 1100, 'data': {'turn': 1, 'step': 1, 'usage': {
                'inputTokens': 100, 'outputTokens': 20, 'cacheReadTokens': 900, 'cacheWriteTokens': 0,
                'totalTokens': 1020}}},
            {'type': 'tool/call', 'time': 1200, 'data': {'turn': 1, 'callId': 'c1', 'name': 'pwsh'}},
            {'type': 'tool/result', 'time': 1300, 'data': {'callId': 'c1', 'message': {'content': [{'type': 'text', 'text': 'x' * 2048}]}}},
            {'type': 'assistant/message', 'time': 1400, 'data': {'turn': 1, 'step': 2, 'usage': {
                'inputTokens': 50, 'outputTokens': 10, 'cacheReadTokens': 2000, 'cacheWriteTokens': 0,
                'totalTokens': 2060}}},
            {'type': 'tool/call', 'time': 1500, 'data': {'turn': 1, 'callId': 'c2', 'name': 'mcp__browser__browser_evaluate'}},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'session.v4.jsonl.zstd'
            path.write_bytes(make_session(events))
            report = cost.summarize(cost.load_events(str(path)))
        self.assertEqual(report['steps'], 2)
        self.assertEqual(report['tool_calls'], 2)
        self.assertEqual(report['tokens']['total'], 3080)
        self.assertEqual(report['tokens']['cache_read'], 2900)
        self.assertEqual(report['turns']['1']['calls'], 2)
        self.assertEqual(report['tool_payload_kb']['pwsh'], 2.0)

    def test_unreadable_file_is_an_error(self):
        buffer = io.StringIO()
        import contextlib
        with contextlib.redirect_stdout(buffer):
            code = cost.main([str(Path('does-not-exist.zstd'))])
        self.assertEqual(code, 2)


class SubmitAuditTest(unittest.TestCase):
    def test_popup_submit_is_not_a_quiz_submit(self):
        events = [{'type': 'tool/call', 'data': {
            'callId': 'c1', 'name': 'mcp__browser__browser_run_code_unsafe',
            'arguments': {'code': 'await frame.locator("a.ans-videoquiz-submit").click()'}}}]
        audit = cost.audit_submissions(events)
        self.assertEqual(audit['verdict'], 'clean')

    def test_quiz_submit_selector_is_flagged(self):
        events = [{'type': 'tool/call', 'data': {
            'callId': 'c1', 'name': 'mcp__browser__browser_run_code_unsafe',
            'arguments': {'code': 'document.querySelector(".btnSubmit").click()'}}}]
        audit = cost.audit_submissions(events)
        self.assertEqual(audit['verdict'], 'review')
        self.assertEqual(audit['suspects'][0]['pattern'], r'\.btnSubmit')

    def test_non_browser_calls_are_not_audited(self):
        events = [{'type': 'tool/call', 'data': {
            'callId': 'c1', 'name': 'write', 'arguments': {'content': 'the selector .btnSubmit was never used'}}}]
        self.assertEqual(cost.audit_submissions(events)['verdict'], 'clean')

    def test_audit_flag_exits_five_on_suspect(self):
        events = [{'type': 'tool/call', 'data': {
            'callId': 'c1', 'name': 'mcp__browser__browser_run_code_unsafe',
            'arguments': {'code': 'click #workpop'}}}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'session.v4.jsonl.zstd'
            path.write_bytes(make_session(events))
            buffer = io.StringIO()
            import contextlib
            with contextlib.redirect_stdout(buffer):
                code = cost.main([str(path), '--audit-submit'])
        self.assertEqual(code, cost.EXIT_SUBMIT_SUSPECT)
        self.assertIn('submit audit: review', buffer.getvalue())

    def test_audit_flag_exits_zero_when_clean(self):
        events = [{'type': 'tool/call', 'data': {
            'callId': 'c1', 'name': 'pwsh', 'arguments': {'command': 'Get-Date'}}}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'session.v4.jsonl.zstd'
            path.write_bytes(make_session(events))
            buffer = io.StringIO()
            import contextlib
            with contextlib.redirect_stdout(buffer):
                code = cost.main([str(path), '--audit-submit'])
        self.assertEqual(code, 0)
        self.assertIn('submit audit: clean', buffer.getvalue())


if __name__ == '__main__':
    unittest.main()
