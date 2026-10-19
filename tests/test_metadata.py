"""Guards the skill's public surface: metadata consistency and no dangling links."""

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


package = load('package_skill')
LINK = re.compile(r'\]\((references/[^)#]+|scripts/[^)#]+|LICENSE|NOTICE|README\.md)\)')


class MetadataTest(unittest.TestCase):
    def test_skill_frontmatter_name_matches_package_name(self):
        text = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        name = re.search(r'^name:\s*(\S+)\s*$', text, re.M).group(1)
        self.assertEqual(name, package.SKILL_NAME)

    def test_doctor_version_matches_package_version(self):
        text = (ROOT / 'scripts' / 'doctor.py').read_text(encoding='utf-8')
        version = re.search(r"'version':\s*'([^']+)'", text).group(1)
        self.assertEqual(version, package.VERSION)

    def test_public_entry_points_exist(self):
        for name in ('SKILL.md', 'README.md', 'NOTICE', 'LICENSE', 'install.ps1'):
            self.assertTrue((ROOT / name).is_file(), name)

    def test_no_dangling_links_in_public_docs(self):
        missing = []
        for doc in ('SKILL.md', 'README.md'):
            text = (ROOT / doc).read_text(encoding='utf-8')
            for target in LINK.findall(text):
                if not (ROOT / target).exists():
                    missing.append('%s -> %s' % (doc, target))
        self.assertEqual(missing, [])

    def test_removed_scope_stays_removed(self):
        for gone in ('references/homework-flow.md', 'references/homework-output.md',
                     'references/polymas.md', 'scripts/delivery_gate.py'):
            self.assertFalse((ROOT / gone).exists(), gone)
        text = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        self.assertNotIn('homework-flow.md', text)
        self.assertNotIn('delivery_gate.py', text)


if __name__ == '__main__':
    unittest.main()
