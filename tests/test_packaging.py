import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'package_skill.py'
spec = importlib.util.spec_from_file_location('package_skill', SCRIPT)
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        (self.source / 'SKILL.md').write_text('---\nname: course-study-dsh\ndescription: test\n---\n', encoding='utf-8')
        (self.source / 'local').mkdir()
        (self.source / 'local' / 'runtime.json').write_text('{"private":"PRIVATE_LOCATION"}', encoding='utf-8')
        (self.source / 'local' / 'credentials.local.json').write_text('{"private":"DO_NOT_COPY"}', encoding='utf-8')
        (self.source / 'runs').mkdir()
        (self.source / 'runs' / 'state.json').write_text('{"private":"RUNTIME_STATE"}', encoding='utf-8')

    def call(self, args):
        with patch.object(package, 'ROOT', self.source), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return package.main(args)

    def test_public_export_excludes_private_data(self):
        output = self.base / 'public'
        self.assertEqual(self.call(['export', '--out', str(output)]), 0)
        self.assertFalse((output / 'local').exists())
        self.assertFalse((output / 'runs').exists())
        self.assertTrue((output / 'SKILL.md').exists())

    def test_install_copies_location_metadata_but_no_credentials(self):
        output = self.base / 'course-study-dsh'
        self.assertEqual(self.call(['install', '--target', str(output), '--include-local']), 0)
        self.assertTrue((output / 'local' / 'runtime.json').exists())
        self.assertFalse((output / 'local' / 'credentials.local.json').exists())
        self.assertFalse((output / 'runs').exists())

    def test_nonempty_target_is_untouched(self):
        output = self.base / 'course-study-dsh'
        output.mkdir()
        original = output / 'state.json'
        original.write_text('existing data', encoding='utf-8')
        self.assertEqual(self.call(['install', '--target', str(output)]), 2)
        self.assertEqual(original.read_text(), 'existing data')
        self.assertEqual(len(list(output.iterdir())), 1)

    def test_denylist_blocks_before_output(self):
        (self.source / 'references').mkdir()
        (self.source / 'references' / 'unsafe.md').write_text('PRIVATE_MARKER', encoding='utf-8')
        denylist = self.base / 'deny.json'
        denylist.write_text(json.dumps(['PRIVATE_MARKER']), encoding='utf-8')
        output = self.base / 'public'
        self.assertEqual(self.call(['export', '--out', str(output), '--denylist', str(denylist)]), 2)
        self.assertFalse(output.exists())

    def test_public_export_skips_pytest_cache(self):
        tests = self.source / 'tests'
        cache = tests / '.pytest_cache' / 'v'
        cache.mkdir(parents=True)
        (cache / 'nodeids').write_text('[]', encoding='utf-8')
        (tests / 'test_sample.py').write_text('x = 1\n', encoding='utf-8')
        output = self.base / 'public-cache'
        self.assertEqual(self.call(['export', '--out', str(output)]), 0)
        self.assertFalse((output / 'tests' / '.pytest_cache').exists())
        self.assertTrue((output / 'tests' / 'test_sample.py').exists())

    def test_force_reinstall_replaces_files_and_keeps_local_config(self):
        output = self.base / 'course-study-dsh'
        output.mkdir()
        (output / 'SKILL.md').write_text('old', encoding='utf-8')
        (output / 'local').mkdir()
        (output / 'local' / 'private.toml').write_text('mode = "completion"\n', encoding='utf-8')
        (output / 'package-manifest.json').write_text(json.dumps({'files': [{'path': 'stale.md'}]}), encoding='utf-8')
        (output / 'stale.md').write_text('stale', encoding='utf-8')
        self.assertEqual(self.call(['install', '--target', str(output), '--force']), 0)
        self.assertEqual((output / 'SKILL.md').read_text(encoding='utf-8'),
                         (self.source / 'SKILL.md').read_text(encoding='utf-8'))
        self.assertEqual((output / 'local' / 'private.toml').read_text(encoding='utf-8'), 'mode = "completion"\n')
        self.assertFalse((output / 'stale.md').exists())

    def test_install_seeds_private_config_from_example(self):
        (self.source / 'private.toml.example').write_text('mode = "evidence"\n', encoding='utf-8')
        output = self.base / 'course-study-dsh'
        self.assertEqual(self.call(['install', '--target', str(output)]), 0)
        self.assertEqual((output / 'local' / 'private.toml').read_text(encoding='utf-8'), 'mode = "evidence"\n')

    def test_this_repository_exports_without_privacy_findings(self):
        # Regression guard: a personal path in any public file blocks the real export.
        self.assertEqual(package.public_scan(package.files(), []), [])

    def test_cannot_target_an_old_skill_name(self):
        output = self.base / 'course-homework'
        self.assertEqual(self.call(['install', '--target', str(output)]), 2)
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
