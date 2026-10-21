"""Syntax-check the copy-paste JavaScript blocks in references/*.md."""

SNIPPET_DOCS = ('quickstart.md', 'bank.md')

import re
import shutil
import subprocess
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')


class QuickstartSnippetTest(unittest.TestCase):
    @unittest.skipUnless(NODE, 'node is not installed')
    def test_js_blocks_parse(self):
        minimum = {'quickstart.md': 5, 'bank.md': 1}
        failures = []
        for name in SNIPPET_DOCS:
            text = (ROOT / 'references' / name).read_text(encoding='utf-8')
            blocks = re.findall(r'```js\n(.*?)```', text, re.S)
            self.assertGreaterEqual(len(blocks), minimum[name], name + ' lost its code blocks')
            for index, block in enumerate(blocks, 1):
                with tempfile.TemporaryDirectory() as temporary:
                    path = Path(temporary) / ('block-%d.js' % index)
                    path.write_text(block, encoding='utf-8')
                    result = subprocess.run([NODE, '--check', str(path)], capture_output=True,
                                            text=True, encoding='utf-8', errors='replace')
                    if result.returncode != 0:
                        failures.append('{0} block {1}: {2}'.format(
                            name, index, result.stderr.strip()[:300]))
        self.assertEqual(failures, [])


if __name__ == '__main__':
    unittest.main()
