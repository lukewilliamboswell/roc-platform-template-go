#!/usr/bin/env python3
"""Check, build and run the exact release examples ZIP with an empty cache."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import zipfile
from test import serve_bundle


def test_archive(archive: Path, bundle: Path, target: str | None = None):
    with tempfile.TemporaryDirectory(prefix='go-platform-release-') as temporary:
        workspace = Path(temporary)
        with zipfile.ZipFile(archive) as zipped:
            names = set()
            for info in zipped.infolist():
                path = Path(info.filename)
                if path.is_absolute() or '..' in path.parts or info.filename in names or stat.S_IFMT(info.external_attr >> 16) != stat.S_IFREG:
                    raise ValueError(f'unsafe or duplicate ZIP member: {info.filename}')
                names.add(info.filename)
                if path.parts[0] != archive.stem:
                    raise ValueError('archive root differs from filename')
            zipped.extractall(workspace)
        suite = workspace / archive.stem
        spec = json.loads((suite / 'spec.json').read_text(encoding='utf-8'))
        if spec['schema_version'] != 1 or len(spec['dependencies']) != 1:
            raise ValueError('expected the shared release suite contract')
        dependency = spec['dependencies'][0]
        if not dependency.endswith('/' + spec['release'] + '/' + bundle.name):
            raise ValueError('suite does not name this release and platform bundle')
        env = {**os.environ, 'ROC_CACHE_DIR': str(workspace / 'cache'), 'XDG_CACHE_HOME': str(workspace / 'xdg-cache')}
        env.pop('GH_TOKEN', None)
        env.pop('GITHUB_TOKEN', None)
        before = {p.relative_to(suite): hashlib.sha256(p.read_bytes()).hexdigest() for p in suite.rglob('*') if p.is_file()}
        with serve_bundle(bundle.resolve()) as url:
            for index, app in enumerate(spec['apps']):
                source = suite / app['path']
                binary = workspace / f'app-{index}{".exe" if os.name == "nt" else ""}'
                for command in (
                    ['roc', 'check', str(source), '--replace-dep', dependency, url],
                    ['roc', 'test', str(source), '--replace-dep', dependency, url],
                    ['roc', 'build', str(source), '--opt=dev', f'--output={binary}', '--replace-dep', dependency, url] + ([f'--target={target}'] if target else []),
                ):
                    print('+', subprocess.list2cmdline(command), flush=True)
                    subprocess.run(command, env=env, check=True, timeout=300)
                for case in app['cases']:
                    ran = subprocess.run([str(binary), *case['args']], cwd=source.parent, env=env,
                                         input=case['stdin'].encode(), capture_output=True, timeout=10)
                    print(f'{app["path"]} / {case["name"]}', flush=True)
                    if ran.returncode != case['exit_code'] or ran.stdout != case['stdout'].encode() or ran.stderr != case['stderr'].encode():
                        raise ValueError(f'case mismatch: {case["name"]}; exit={ran.returncode}, stdout={ran.stdout!r}, stderr={ran.stderr!r}')
        for relative, digest in before.items():
            if hashlib.sha256((suite / relative).read_bytes()).hexdigest() != digest:
                raise ValueError(f'archived file was modified: {relative}')
        print(f'Exact release archive passed: {len(spec["apps"])} applications, {sum(len(app["cases"]) for app in spec["apps"])} cases')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--target')
    args = parser.parse_args()
    test_archive(args.archive, args.bundle, args.target)


if __name__ == '__main__':
    main()
