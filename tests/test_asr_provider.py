"""The ASR step is provider-agnostic: MiMo by default, any OpenAI-compatible endpoint by flags."""

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location('asr_mimo', ROOT / 'scripts' / 'asr_mimo.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


asr = load()


class Response:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode('utf-8')

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class ProviderTest(unittest.TestCase):
    def test_defaults_stay_on_mimo(self):
        self.assertEqual(asr.ENDPOINT, 'https://api.xiaomimimo.com/v1/chat/completions')
        self.assertEqual(asr.MODEL, 'mimo-v2.5-asr')

    def test_provider_env_is_consulted_before_the_key_file(self):
        class Args:
            api_key = None
            key_file = 'does-not-exist'
            provider_key_env = 'GROQ_API_KEY'

        with mock.patch.dict(os.environ, {'GROQ_API_KEY': 'gsk-test'}, clear=False):
            self.assertEqual(asr.read_key(Args()), 'gsk-test')

    def test_bearer_style_and_model_override_reach_the_request(self):
        handle = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        handle.write(b'not-really-mp3')
        handle.close()
        self.addCleanup(Path(handle.name).unlink)
        seen = {}

        def fake_urlopen(request, timeout=None):
            seen['url'] = request.full_url
            seen['headers'] = {key.lower(): value for key, value in request.header_items()}
            seen['body'] = json.loads(request.data.decode('utf-8'))
            return Response({'choices': [{'message': {'content': ' 你好 '}}], 'usage': {'seconds': 3}})

        with mock.patch('urllib.request.urlopen', fake_urlopen):
            text, usage = asr.transcribe('gsk-test', handle.name, 'zh',
                                         endpoint='https://api.groq.com/openai/v1/chat/completions',
                                         model='whisper-large-v3-turbo', auth_style='bearer')
        self.assertEqual(text, '你好')
        self.assertEqual(usage['seconds'], 3)
        self.assertEqual(seen['url'], 'https://api.groq.com/openai/v1/chat/completions')
        self.assertEqual(seen['headers'].get('authorization'), 'Bearer gsk-test')
        self.assertNotIn('api-key', seen['headers'])
        self.assertEqual(seen['body']['model'], 'whisper-large-v3-turbo')


if __name__ == '__main__':
    unittest.main()
