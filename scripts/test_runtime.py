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
        self.lock = json.loads((self.archive.parent / 'runtime-release.json').read_text())

    def test_archive_reproducibility_and_sbom_coverage(self):
        second = self.root / 'second.tar.gz'
        write_archive(second, dict(reversed(list(self.files.items()))))
        self.assertEqual(self.archive.read_bytes(), second.read_bytes())
        sbom = json.loads((self.archive.parent / 'runtime.spdx.json').read_text())
        self.assertEqual({f['fileName'] for f in sbom['files']}, {f'./{p}' for p in self.files})
        source_relations = [r for r in sbom['relationships'] if r['relationshipType'] == 'GENERATED_FROM']
        self.assertEqual(len(source_relations), len(RUNTIME_PATHS))

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
            fetch.verify_attestation(self.archive, self.root / 'proof', self.lock, fetch.PROVENANCE)
        args = run.call_args.args[0]
        for key, value in [('--source-digest', self.lock['source_commit']),
                           ('--source-ref', 'refs/heads/main'), ('--signer-digest', self.lock['signer_digest']),
                           ('--signer-workflow', self.lock['signer_workflow']), ('--repo', self.lock['repository']),
                           ('--predicate-type', fetch.PROVENANCE)]:
            self.assertEqual(args[args.index(key) + 1], value)
        self.assertIn('--deny-self-hosted-runners', args)
        with patch.object(fetch.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, ['gh'])):
            with self.assertRaises(subprocess.CalledProcessError):
                fetch.verify_attestation(self.archive, self.root / 'proof', self.lock, fetch.SBOM_TYPE)

    def test_release_verification_requires_both_predicates_and_matching_sbom(self):
        document = json.loads((self.archive.parent / 'runtime.spdx.json').read_text())
        verified = [{'verificationResult': {'statement': {'predicate': document}}}]
        with patch.object(fetch, 'verify_attestation', return_value=verified) as verify:
            self.assertEqual(fetch.verify_release(self.archive.parent, self.lock), self.archive)
            self.assertEqual([c.args[3] for c in verify.call_args_list], [fetch.PROVENANCE, fetch.PROVENANCE, fetch.SBOM_TYPE])
        with patch.object(fetch, 'verify_attestation', return_value=[{'verificationResult': {'statement': {'predicate': {}}}}]):
            with self.assertRaisesRegex(ValueError, 'signed predicate'):
                fetch.verify_release(self.archive.parent, self.lock)
        self.archive.write_bytes(b'tampered')
        with patch.object(fetch, 'verify_attestation') as verify:
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                fetch.verify_release(self.archive.parent, self.lock)
            verify.assert_not_called()

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
        lock_path.write_bytes(json_bytes(self.lock))
        cache = self.root / '.runtime-cache' / self.lock['sha256']
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
            with self.assertRaisesRegex(ValueError, 'Cached runtime archive'):
                fetch.verify_installed(platform, lock_path)

    def test_publication_rejects_non_main_and_existing_versions(self):
        with patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/a-pr', 'GITHUB_EVENT_NAME': 'workflow_dispatch'}):
            with self.assertRaisesRegex(ValueError, 'dispatch from main'):
                prepare('0.1.0')
        with patch('runtime_release.subprocess.run', return_value=subprocess.CompletedProcess([], 0, '{}', '')):
            with self.assertRaisesRegex(ValueError, 'already exists'):
                must_be_new('runtime-v0.1.0')


if __name__ == '__main__':
    unittest.main()
