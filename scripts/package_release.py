#!/usr/bin/env python3
"""Package a tested platform bundle and canonical examples without rebuilding."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = 'roc-platform-template-go'
REPOSITORY = 'lukewilliamboswell/' + NAME
AUTOMATION = 'a25b5129340b9b2ad1744d20330b8ee4d38a1849'


def package(bundle: Path, version: str, output: Path) -> Path:
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?', version):
        raise ValueError('version must be a semantic version')
    if not re.fullmatch(r'[A-Za-z0-9]+\.tar\.zst', bundle.name) or not bundle.is_file():
        raise ValueError('expected a content-addressed Roc platform bundle')
    output.mkdir(parents=True, exist_ok=True)
    destination = output / bundle.name
    if bundle.resolve() != destination.resolve():
        shutil.copyfile(bundle, destination)
    url = f'https://github.com/{REPOSITORY}/releases/download/{version}/{bundle.name}'
    spec = json.loads((ROOT / 'tests/spec.json').read_text(encoding='utf-8'))
    spec.update(release=version, dependencies=[url])
    archive = output / f'{NAME}-examples-{version}.zip'
    prefix = archive.stem
    tracked = subprocess.check_output(['git', 'ls-files', '-z', 'examples'], cwd=ROOT).decode().split('\0')
    files = {}
    pattern = re.compile(r'\bplatform "../../platform/main\.roc"')
    for name in filter(None, tracked):
        source = ROOT / name
        if source.is_symlink() or not source.is_file():
            raise ValueError(f'example must be a regular file: {name}')
        content = source.read_bytes()
        if name in {app['path'] for app in spec['apps']}:
            text, count = pattern.subn(f'platform "{url}"', content.decode('utf-8'))
            if count != 1:
                raise ValueError(f'expected one local platform dependency: {name}')
            content = text.encode('utf-8')
        files[name] = content
    files['spec.json'] = (json.dumps(spec, indent=2, ensure_ascii=False) + '\n').encode()
    files['README.md'] = (f'# {NAME} {version}\n\nInstall the latest Roc nightly and run '
                          '`roc examples/hello_world/main.roc` from this directory.\n\n'
                          f'Platform: {url}\n\nExpected behavior: `spec.json`.\n').encode()
    files['LICENSE'] = (ROOT / 'LICENSE').read_bytes()
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, content in sorted(files.items()):
            info = zipfile.ZipInfo(prefix + '/' + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zipped.writestr(info, content)
    notes = (ROOT / f'docs/releases/{version.split("-")[0]}.md').read_text()
    compiler = subprocess.check_output(['roc', 'version'], text=True).strip()
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    (output / 'release-notes.md').write_text(notes + f'\n## Built with\n\n- Compiler: `{compiler}`\n- Source: `{sha}`\n- Automation: `{AUTOMATION}`\n', encoding='utf-8')
    assets = [destination, archive]
    (output / 'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in assets))
    print(f'Release examples: {archive}')
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    package(args.bundle, args.version, args.output_dir)


if __name__ == '__main__':
    main()
