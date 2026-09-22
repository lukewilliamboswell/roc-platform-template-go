"""Runtime supply-chain boundaries and reproducible archive regression tests."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import fetch_runtime as fetch
from package_runtime import package
from runtime_assets import (MANIFEST, RUNTIME_PATHS, ROOT, json_bytes, read_archive,
                            sha256, write_archive)
from runtime_release import must_be_new, prepare
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
        dependency = json.loads((self.archive.parent / 'dependency.json').read_text())
        archive_asset = next(a for a in dependency['assets'] if a['role'] == 'linker-input-archive')
        sbom_asset = next(a for a in dependency['assets'] if a['role'] == 'sbom')
        raw_lock = {
            'schema_version': 1,
            'release_tag': dependency['release_tag'],
            'archive': {key: archive_asset[key] for key in ('name', 'sha256', 'size')},
            'sbom': {key: sbom_asset[key] for key in ('name', 'sha256', 'size')},
            'source': dependency['source'],
            'signer': {
                'repository': 'lukewilliamboswell/roc-automation',
                'workflow': '.github/workflows/publish-linker-inputs.yml',
                'commit': '1' * 40,
            },
        }
        lock_path = self.root / 'linker-inputs.lock.json'
        self.raw_lock = raw_lock
        lock_path.write_bytes(json_bytes(raw_lock))
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

    def test_attestation_policy_uses_locked_identity(self):
        with patch.object(fetch.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '[{}]')) as run:
            fetch.verify_attestation(self.archive, self.lock, fetch.PROVENANCE)
        args = run.call_args.args[0]
        for key, value in [('--source-digest', self.lock['source_commit']),
                           ('--source-ref', 'refs/heads/main'), ('--signer-digest', self.lock['signer_digest']),
                           ('--signer-workflow', self.lock['signer_workflow']), ('--repo', self.lock['repository']),
                           ('--predicate-type', fetch.PROVENANCE)]:
            self.assertEqual(args[args.index(key) + 1], value)
        self.assertIn('--deny-self-hosted-runners', args)
        with patch.object(fetch.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['gh'])):
            with self.assertRaises(subprocess.CalledProcessError):
                fetch.verify_attestation(self.archive, self.lock, fetch.PROVENANCE)

    def test_release_verification_requires_provenance_and_matching_locked_sbom(self):
        document = json.loads((self.archive.parent / 'linker-inputs.spdx.json').read_text())
        def producer_verification(artifact, lock, predicate):
            if predicate != fetch.PROVENANCE:
                raise ValueError('Unexpected attestation predicate')
            return [{}]

        with patch.object(fetch, 'verify_attestation', side_effect=producer_verification) as verify:
            self.assertEqual(fetch.verify_release(self.archive.parent, self.lock), self.archive)
            self.assertEqual([c.args[2] for c in verify.call_args_list], [fetch.PROVENANCE, fetch.PROVENANCE])
        sbom = self.archive.parent / 'linker-inputs.spdx.json'
        sbom.write_bytes(b'{}')
        with patch.object(fetch, 'verify_attestation') as verify:
            with self.assertRaisesRegex(ValueError, 'SBOM differs from lock'):
                fetch.verify_release(self.archive.parent, self.lock)
            verify.assert_not_called()
        sbom.write_text(json.dumps(document))
        self.archive.write_bytes(b'tampered')
        with patch.object(fetch, 'verify_attestation') as verify:
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                fetch.verify_release(self.archive.parent, self.lock)
            verify.assert_not_called()

    def test_fetch_does_not_install_after_authentication_failure(self):
        cache = self.root / '.linker-inputs-cache' / self.lock['sha256']
        cache.mkdir(parents=True)
        for name in [self.archive.name, 'linker-inputs.spdx.json']:
            source = self.archive.parent / name
            (cache / name).write_bytes(source.read_bytes())
        with patch.object(fetch, 'ROOT', self.root), \
             patch.object(fetch, 'load_lock', return_value=self.lock), \
             patch.object(fetch, 'verify_attestation', side_effect=ValueError('invalid proof')), \
             patch.object(fetch, 'install') as install:
            with self.assertRaisesRegex(ValueError, 'invalid proof'):
                fetch.fetch()
            install.assert_not_called()

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
        cached = cache / self.archive.name
        cached.write_bytes(self.archive.read_bytes())
        with patch.object(fetch, 'ROOT', self.root), patch.dict(os.environ, {}, clear=True):
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

    def test_publication_rejects_non_main_and_existing_versions(self):
        with patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/a-pr', 'GITHUB_EVENT_NAME': 'workflow_dispatch'}):
            with self.assertRaisesRegex(ValueError, 'dispatch from main'):
                prepare('0.1.0')
        with patch('runtime_release.subprocess.run', return_value=subprocess.CompletedProcess([], 0, '{}', '')):
            with self.assertRaisesRegex(ValueError, 'already exists'):
                must_be_new('linker-inputs-v0.1.0')


if __name__ == '__main__':
    unittest.main()
