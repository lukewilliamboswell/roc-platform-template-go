"""Release regressions: preserve example bytes and reject unsafe archives."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import package_release
from test_release import test_archive


class ReleasePackagingTests(unittest.TestCase):
    def test_archive_changes_only_the_platform_dependency(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / 'examples/hello'
            app.mkdir(parents=True)
            source = 'app [main!] { pf: platform "../../platform/main.roc" }\n# companion stays relative\n'
            (app / 'main.roc').write_text(source)
            (app / 'input.bin').write_bytes(b'\x00\xff')
            (root / 'tests').mkdir()
            spec = dict(schema_version=1, release='working-tree', dependencies=[], apps=[dict(path='examples/hello/main.roc', cases=[])])
            (root / 'tests/spec.json').write_text(json.dumps(spec))
            (root / 'docs/releases').mkdir(parents=True)
            (root / 'docs/releases/0.1.0.md').write_text('Release notes\n')
            (root / 'LICENSE').write_text('License\n')
            bundle = root / 'ABC.tar.zst'
            bundle.write_bytes(b'reviewed platform bytes')
            def command(argv, **kwargs):
                if argv[:2] == ['git', 'ls-files']:
                    return b'examples/hello/main.roc\0examples/hello/input.bin\0'
                return 'Roc nightly-2026-10-28-bad769b' if argv[0] == 'roc' else 'a' * 40
            with patch.object(package_release, 'ROOT', root), patch.object(package_release.subprocess, 'check_output', side_effect=command):
                archive = package_release.package(bundle, '0.1.0', root / 'release')
            with zipfile.ZipFile(archive) as zipped:
                prefix = archive.stem + '/'
                published = json.loads(zipped.read(prefix + 'spec.json'))
                url = published['dependencies'][0]
                self.assertEqual(zipped.read(prefix + 'examples/hello/main.roc').decode(), source.replace('../../platform/main.roc', url))
                self.assertEqual(zipped.read(prefix + 'examples/hello/input.bin'), b'\x00\xff')
                self.assertEqual(published['release'], '0.1.0')
            self.assertEqual((app / 'main.roc').read_text(), source)
            self.assertEqual((root / 'release/ABC.tar.zst').read_bytes(), bundle.read_bytes())

    def test_release_validation_rejects_archive_traversal(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / 'examples.zip'
            with zipfile.ZipFile(archive, 'w') as zipped:
                zipped.writestr('../escape', 'bad')
            with self.assertRaisesRegex(ValueError, 'unsafe'):
                test_archive(archive, Path(temporary) / 'missing.tar.zst')


if __name__ == '__main__':
    unittest.main()
