"""The video flow should keep the text it already reads: SRT first, ASR only as a fallback."""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location('media_keep', ROOT / 'scripts' / 'media_keep.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


media = load()


class PlanTest(unittest.TestCase):
    def test_subtitles_win_over_the_video(self):
        evidence = {'section': '1.1',
                    'subs': {'srt': ['http://cs.example/1.srt']},
                    'media': {'mp4': ['http://s2.example/sd.mp4']}}
        self.assertEqual(media.plan(evidence), {'mode': 'srt', 'url': 'http://cs.example/1.srt'})

    def test_no_subtitles_falls_back_to_the_signed_mp4(self):
        evidence = {'section': '2.1', 'subs': {'srt': []},
                    'media': {'mp4': ['http://s2.example/sd.mp4?at_=1']}}
        self.assertEqual(media.plan(evidence), {'mode': 'asr', 'url': 'http://s2.example/sd.mp4?at_=1'})

    def test_nothing_to_keep_is_reported_not_silently_skipped(self):
        self.assertEqual(media.plan({'subs': {'srt': []}}),
                         {'mode': 'skip', 'reason': 'no-subtitle-and-no-mp4'})

    def test_asr_is_refused_when_the_switch_is_off(self):
        import json
        import tempfile
        evidence = {'section': '7.2', 'media': {'mp4': ['http://s2.example/sd.mp4']}}
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(evidence, handle)
        handle.close()
        self.addCleanup(Path(handle.name).unlink)
        report = media.keep(handle.name, asr_enabled=False)
        self.assertEqual(report['mode'], 'asr')
        self.assertEqual(report['skipped'], 'asr-disabled')
        self.assertIsNone(report['wrote'])


if __name__ == '__main__':
    unittest.main()
