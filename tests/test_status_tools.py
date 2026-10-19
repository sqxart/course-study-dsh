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


if __name__ == '__main__':
    unittest.main()
