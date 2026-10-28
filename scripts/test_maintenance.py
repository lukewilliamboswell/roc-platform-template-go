"""Regression checks for header migration and complete example test copies."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test as runner

from compiler_pins import header_pin
from generate_c_glue import active_revision
from test import load_spec, rewrite_examples_for_bundle


class MaintenanceTests(unittest.TestCase):
    def test_active_compiler_selects_matching_glue_source(self):
        with patch('generate_c_glue.subprocess.check_output', return_value='Roc compiler version release-bad769b'):
            self.assertEqual(active_revision(), ('Roc compiler version release-bad769b', 'bad769b'))
        with patch('generate_c_glue.subprocess.check_output', return_value='unknown'):
            with self.assertRaisesRegex(SystemExit, 'cannot identify'):
                active_revision()

    def test_bundle_copy_preserves_companions_and_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            examples = Path(temporary)
            app = examples / 'hello'
            app.mkdir()
            source = 'app [main!] { pf: platform "../../platform/main.roc" }\n'
            (app / 'main.roc').write_text(source)
            (app / 'Helper.roc').write_text('module [answer]\nanswer = 42\n')
            (app / 'input.bin').write_bytes(b'\x00\xff')
            with rewrite_examples_for_bundle(examples, 'http://127.0.0.1:1234/test.tar.zst') as copied:
                self.assertIn('http://127.0.0.1:1234/test.tar.zst', (copied / 'hello/main.roc').read_text())
                self.assertIsNone(header_pin((copied / 'hello/main.roc').read_text()))
                self.assertEqual((copied / 'hello/Helper.roc').read_bytes(), (app / 'Helper.roc').read_bytes())
                self.assertEqual((copied / 'hello/input.bin').read_bytes(), b'\x00\xff')
            self.assertEqual((app / 'main.roc').read_text(), source)

    def test_published_mode_rejects_local_dependencies_before_building(self):
        with patch('sys.argv', ['test.py', '--published']), \
             patch.object(runner.shutil, 'which', return_value='/roc'), \
             patch.object(runner.subprocess, 'check_output', return_value='roc cc03aa8'), \
             patch.object(runner, 'bundle_platform') as bundle, \
             patch.object(runner, 'run_local_suite') as suite:
            with self.assertRaisesRegex(runner.TestFailure, 'immutable release URL'):
                runner.main()
            bundle.assert_not_called()
            suite.assert_not_called()

    def test_candidate_archive_is_used_without_rebuilding(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / 'candidate.tar.zst'
            archive.write_bytes(b'exact reviewed candidate')
            with patch('sys.argv', ['test.py', '--bundle', str(archive)]), \
                 patch.object(runner.shutil, 'which', return_value='/roc'), \
                 patch.object(runner.subprocess, 'check_output', return_value='roc cc03aa8'), \
                 patch.object(runner, 'bundle_platform') as bundle, \
                 patch.object(runner, 'run_local_suite', return_value=dict.fromkeys(runner.STAGES, 0)) as suite:
                runner.main()
                bundle.assert_not_called()
                suite.assert_called_once()
            self.assertEqual(archive.read_bytes(), b'exact reviewed candidate')

    def test_repository_roots_and_spec_cover_every_example(self):
        root = Path(__file__).resolve().parents[1]
        expected = {
            p.relative_to(root).as_posix() for p in (root / 'examples').rglob('main.roc')
        }
        for directory in ('platform', 'examples'):
            for source in (root / directory).rglob('*.roc'):
                self.assertIsNone(header_pin(source.read_text()), str(source))
        self.assertFalse((root / '.roc-version').exists())
        self.assertFalse((root / '.github/roc-nightly.json').exists())
        _, apps = load_spec(root / 'examples')
        self.assertEqual({app['path'] for app in apps}, expected)


if __name__ == '__main__':
    unittest.main()
