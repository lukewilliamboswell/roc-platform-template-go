"""Runtime supply-chain boundaries and reproducible archive regression tests."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import fetch_runtime as fetch
from package_runtime import package
from runtime_assets import (MANIFEST, RUNTIME_PATHS, ROOT, json_bytes, read_archive,
                            sha256, write_archive)
import build_input_release
from build_macos_interface import read_catalog, render


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        targets = self.root / 'targets'
        for name in RUNTIME_PATHS:
            path = targets / name.removeprefix('targets/')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode())
        with contextlib.redirect_stdout(io.StringIO()):
            self.archive = package(targets, self.root / 'dist', '0.1.0')
        self.manifest, self.files = read_archive(self.archive)
        raw_lock = self.content_lock()
        lock_path = self.root / 'link-inputs.lock.json'
        self.raw_lock = raw_lock
        lock_path.write_bytes(json_bytes(raw_lock))
        with patch.object(fetch, 'input_fingerprint', return_value='c' * 64):
            self.lock = fetch.load_lock(lock_path)

    def test_archive_reproducibility_and_sbom_coverage(self):
        second = self.root / 'second.tar.gz'
        write_archive(second, dict(reversed(list(self.files.items()))))
        self.assertEqual(self.archive.read_bytes(), second.read_bytes())
        sbom = json.loads((self.archive.parent / 'linker-inputs.spdx.json').read_text())
        self.assertEqual({f['fileName'] for f in sbom['files']}, {f'./{p}' for p in self.files})
        source_relations = [r for r in sbom['relationships'] if r['relationshipType'] == 'GENERATED_FROM']
        self.assertEqual(len(source_relations), len(RUNTIME_PATHS))

    def test_project_authored_macos_interface_is_dual_arch_and_deterministic(self):
        catalog = read_catalog()
        generated = render(catalog)
        self.assertEqual(generated, render(catalog))
        self.assertIn(b'targets: [ arm64-macos, x86_64-macos ]', generated)
        self.assertIn(b"install-name: '/usr/lib/libSystem.B.dylib'", generated)
        self.assertNotIn(b'uuid', generated.lower())
        self.assertNotIn(b'sdk-version', generated.lower())

    def test_rejects_unsafe_entries(self):
        for name, kind in [('../escape', tarfile.REGTYPE), ('/absolute', tarfile.REGTYPE),
                           ('targets/symlink', tarfile.SYMTYPE), ('targets/hardlink', tarfile.LNKTYPE),
                           ('targets/device', tarfile.CHRTYPE), ('targets/unknown.a', tarfile.REGTYPE)]:
            with self.subTest(name=name, kind=kind):
                archive = self.root / 'unsafe.tar.gz'
                with tarfile.open(archive, 'w:gz') as tar:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.linkname = '../escape'
                    tar.addfile(member, io.BytesIO())
                with self.assertRaisesRegex(ValueError, 'unsafe'):
                    read_archive(archive)

    def test_rejects_duplicate_missing_and_corrupt_files(self):
        bad = self.root / 'bad.tar.gz'
        with tarfile.open(bad, 'w:gz') as tar:
            for _ in range(2):
                member = tarfile.TarInfo(MANIFEST)
                tar.addfile(member, io.BytesIO())
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            read_archive(bad)
        files = self.files.copy()
        files.pop(next(iter(RUNTIME_PATHS)))
        write_archive(bad, files)
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            read_archive(bad)
        files = self.files.copy()
        files[next(iter(RUNTIME_PATHS))] = b'corrupt'
        write_archive(bad, files)
        with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
            read_archive(bad)

    def test_install_preserves_host_and_rejects_symlink_parents(self):
        platform = self.root / 'platform'
        host = platform / 'targets/x64musl/libhost.a'
        host.parent.mkdir(parents=True)
        host.write_bytes(b'current Go host')
        fetch.install(self.archive, self.lock['sha256'], platform)
        self.assertEqual(host.read_bytes(), b'current Go host')
        if os.name != 'nt':
            second = self.root / 'linked-platform'
            second.mkdir()
            (second / 'targets').symlink_to(platform / 'targets', target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                fetch.install(self.archive, self.lock['sha256'], second)

    def test_installed_and_cached_tampering_fails(self):
        platform = self.root / 'platform'
        fetch.install(self.archive, self.lock['sha256'], platform)
        lock_path = self.root / 'lock.json'
        lock_path.write_bytes(json_bytes(self.raw_lock))
        cache = self.root / '.linker-inputs-cache' / self.lock['sha256']
        cache.mkdir(parents=True)
        cached = cache / self.lock['asset']
        cached.write_bytes(self.archive.read_bytes())
        with patch.object(fetch, 'ROOT', self.root), \
             patch.object(fetch, 'input_fingerprint', return_value='c' * 64), \
             patch.dict(os.environ, {}, clear=True):
            self.assertEqual(fetch.verify_installed(platform, lock_path), self.lock['sha256'])
            selected = next(iter(RUNTIME_PATHS))
            (platform / selected).write_bytes(b'tampered')
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                fetch.verify_installed(platform, lock_path)
            # Changing the installed manifest must not bless those bytes.
            self.manifest['files'][selected] = hashlib.sha256(b'tampered').hexdigest()
            (platform / MANIFEST).write_bytes(json_bytes(self.manifest))
            with self.assertRaisesRegex(ValueError, 'authenticated archive'):
                fetch.verify_installed(platform, lock_path)
            cached.write_bytes(b'bad cache')
            with self.assertRaisesRegex(ValueError, 'Cached linker-input archive'):
                fetch.verify_installed(platform, lock_path)

    def content_lock(self):
        data = self.archive.read_bytes()
        return {
            'schema_version': 1, 'kind': 'roc-go-link-inputs', 'repository': fetch.REPO,
            'release': 'link-inputs-sha256-' + 'a' * 64,
            'manifest': {'asset': 'build-input-release.json', 'sha256': 'b' * 64},
            'source': {'repository': fetch.REPO, 'sha': self.manifest['source_commit'],
                       'ref': 'refs/heads/linker-change',
                       'workflow': fetch.REPO + '/.github/workflows/release-runtime.yml',
                       'input_fingerprint': 'c' * 64},
            'targets': {'all': {'asset': 'link-inputs-all.tar',
                                'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data)}},
        }

    def test_content_lock_cache_hit_rehashes_without_network(self):
        lock = self.content_lock()
        path = self.root / 'content.lock.json'
        path.write_bytes(json_bytes(lock))
        with patch.object(fetch, 'input_fingerprint', return_value='c' * 64):
            selected = fetch.load_lock(path)
        cache = self.root / '.linker-inputs-cache' / selected['sha256']
        cache.mkdir(parents=True)
        (cache / selected['asset']).write_bytes(self.archive.read_bytes())
        with patch.object(fetch, 'ROOT', self.root), patch.object(fetch, 'load_lock', return_value=selected), \
             patch.dict(os.environ, {}, clear=True), \
             patch.object(fetch, 'download') as download:
            fetch.fetch()
        download.assert_not_called()

    def test_publisher_asset_is_a_genuine_plain_tar(self):
        output = self.root / 'publisher'
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': fetch.REPO,
                                     'GITHUB_SHA': self.manifest['source_commit'],
                                     'GITHUB_REF': 'refs/heads/linker-change'}), \
             patch.object(build_input_release, 'fingerprint', return_value='c' * 64):
            build_input_release.prepare(self.archive.parent, output)
        asset = output / 'link-inputs-all.tar'
        self.assertTrue(tarfile.is_tarfile(asset))
        self.assertNotEqual(asset.read_bytes()[:2], b'\x1f\x8b')
        self.assertEqual(read_archive(asset)[1], self.files)
        manifest = json.loads((output / 'build-input-release.json').read_text())
        self.assertEqual(set(output.iterdir()), {asset, output / 'build-input-release.json'})
        self.assertEqual(manifest['assets']['all']['sha256'], sha256(asset))


if __name__ == '__main__':
    unittest.main()
