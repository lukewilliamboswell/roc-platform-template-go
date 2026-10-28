#!/usr/bin/env python3
"""Bind Blueprint SBOMs to the actual platform and examples archive members."""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = 'https://github.com/lukewilliamboswell/roc-platform-template-go'
CONTACT = REPO + '/issues'


def sexp(text):
    tokens = iter(re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+', text))
    def value(token):
        if token == '(':
            result = []
            for following in tokens:
                if following == ')':
                    return result
                result.append(value(following))
            raise ValueError('incomplete S-expression')
        return json.loads(token) if token.startswith('"') else token
    return value(next(tokens))


def component(identifier, name, version, license='UPL-1.0', producer='Person: Luke Boswell', identity='', sha256='', origin='reviewed'):
    return dict(id=identifier, name=name, version=version, license=license, producer=producer,
                license_url='', identity=identity, download='NOASSERTION', sha256=sha256,
                modified='', target='', origin=origin)


def edge(source, destination, relation='contains', scope='', basis='Delivered archive member, verified by SHA-256'):
    return dict(**{'from': source, 'to': destination}, relation=relation, scope=scope, basis=basis)


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def run(*args):
    subprocess.run(list(args), cwd=ROOT, check=True)


def generate(directory, version):
    directory = directory.resolve()
    spec_text = subprocess.check_output(['blueprint', 'spec'], cwd=ROOT, text=True)
    spec = dict(sexp(spec_text))
    lock = dict(sexp((ROOT / 'Blueprint.lock').read_text()))
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    timestamp = subprocess.check_output(['git', 'show', '-s', '--format=%ct', 'HEAD'], cwd=ROOT, text=True).strip()
    created = datetime.datetime.fromtimestamp(int(timestamp), datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    compiler = subprocess.check_output(['roc', 'version'], text=True).strip()
    bundle, = directory.glob('*.tar.zst')
    archive, = directory.glob('*-examples-*.zip')
    # This project deliberately has no provider tools, source files or sandbox builds.
    # A later addition must extend the inventory rather than silently omitting it.
    for key in ('sources',):
        if lock[key]:
            raise ValueError(f'extend the SBOM inventory for new {key}')
    for key in ('configured_tools', 'roc_packages', 'build_sources', 'builds'):
        if spec[key]:
            raise ValueError(f'extend the SBOM inventory for new {key}')
    for asset in (bundle, archive):
        with tempfile.TemporaryDirectory(prefix='go-platform-sbom-') as temporary:
            work = Path(temporary)
            listing = work / 'members.json'
            if asset == bundle:
                run('blueprint-sbom', 'members', str(asset), str(listing))
                members = json.loads(listing.read_text())['members']
            else:
                with zipfile.ZipFile(asset) as zipped:
                    members = [dict(name=entry.filename, size=entry.file_size,
                                    sha256=hashlib.sha256(zipped.read(entry)).hexdigest())
                               for entry in zipped.infolist() if not entry.is_dir()]
                write(listing, dict(archive=asset.name, sha256=hashlib.sha256(asset.read_bytes()).hexdigest(), members=members))
            project = component('project', 'roc-platform-template-go', version, identity=REPO + '/tree/' + sha)
            composition = dict(profile='blueprint-spdx-3.0-v1', components=[project],
                               relationships=[edge('Subject', 'project')], inputs=[], imported_documents=[], unavailable_sboms=[],
                               coverage=[dict(scope='archive-members', status='complete', reason='Every delivered regular member is listed and hashed from the final archive.', contact=CONTACT),
                                         dict(scope='native-runtime-licenses', status='incomplete' if asset == bundle else 'excluded', reason='MinGW has per-file license exceptions; see the bundled COPYING notice. Host/runtime composition is reviewed against the locked source inventory; member hashes do not establish a complete function-level native dependency closure.' if asset == bundle else 'The examples ZIP contains source and depends on the separate platform bundle; it contains no host/runtime binary.', contact=CONTACT)])
            for member in members:
                identifier = 'member-' + hashlib.sha256(member['name'].encode()).hexdigest()[:20]
                composition['components'].append(component(identifier, member['name'], 'sha256-' + member['sha256'],
                                                            license='NOASSERTION', sha256=member['sha256'],
                                                            identity='urn:roc-platform:member:' + identifier + ':' + member['sha256']))
                composition['relationships'].append(edge('project', identifier))
            if asset == bundle:
                for identifier, record in json.loads((ROOT / 'sbom/native-components.json').read_text()).items():
                    composition['components'].append(component(identifier, record['name'], record['version'], record['license'], record['producer'], record['identity'] + '#' + identifier))
                    composition['relationships'].append(edge('project', identifier, basis=record['basis']))
                runtime_lock = json.loads((ROOT / 'link-inputs.lock.json').read_text())
                identity = f'{REPO}/releases/download/{runtime_lock["release"]}/link-inputs-all.tar'
                composition['components'].append(component('linker-inputs', 'Locked linker-input archive', runtime_lock['release'], license='NOASSERTION', identity=identity, sha256=runtime_lock['targets']['all']['sha256']))
                composition['relationships'].append(edge('project', 'linker-inputs', 'dependsOn', 'build', 'Exact archive consumed to assemble the delivered linker inputs; source metadata and license notices ship inside the platform bundle.'))
            else:
                url = f'{REPO}/releases/download/{version}/{bundle.name}'
                composition['components'].append(component('platform', bundle.name, version, identity=url, sha256=hashlib.sha256(bundle.read_bytes()).hexdigest()))
                composition['relationships'].append(edge('project', 'platform', 'dependsOn', '', 'Archived app headers depend on the sibling immutable platform release, fetched by the compiler rather than contained in this ZIP.'))
            composition['components'].append(component('compiler', 'Roc compiler', compiler, identity='https://github.com/roc-lang/nightlies'))
            composition['relationships'].append(edge('Subject', 'compiler', 'dependsOn', 'build', 'Selected product compiler used for bundling and validation; no compiler code is shipped.'))
            for item in lock['fetched']:
                item = dict(item)
                composition['inputs'].append(dict(input=f'program:{item["name"]}:{item["system"]}', component='', reason='Build/test tool, not the delivered code. Go runtime and linker-input composition are recorded separately from the tool archive. Blueprint.lock records exact tool bytes.'))
            for task in spec['tasks']:
                composition['inputs'].append(dict(input='task:' + dict(task)['name'], component='', reason='Development or release orchestration task; its source is not shipped in these product archives.'))
            write(work / 'composition.json', composition)
            (work / 'Spec').write_text(spec_text)
            run('blueprint-sbom', 'inspect', str(work / 'Spec'), str(ROOT / 'Blueprint.lock'), str(work / 'composition.json'), 'source', str(work / 'inventory.json'), '--members', str(listing))
            write(work / 'subject.json', dict(filename=asset.name, version=version, target='source', sha256='', url=f'{REPO}/releases/download/{version}/{asset.name}'))
            write(work / 'context.json', dict(namespace=f'{REPO}/sbom/{sha}/{asset.name}/revision-1', revision='1', created=created, author='Person: Luke Boswell', generator='Tool: blueprint-sbom-0.8.0'))
            run('blueprint-sbom', 'bind', str(work / 'inventory.json'), str(work / 'subject.json'), str(work / 'context.json'), str(asset))
            run('blueprint-sbom', 'check', '--manifest', str(asset) + '.sbom-manifest.json', '--inventory', str(work / 'inventory.json'), '--artifacts', str(directory))
            shutil.copyfile(work / 'inventory.json', directory / (asset.name + '.inventory.json'))
    assets = sorted(path for path in directory.iterdir() if path.is_file() and path.name not in ('SHA256SUMS', 'release-notes.md'))
    (directory / 'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in assets))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    generate(args.directory, args.version)


if __name__ == '__main__':
    main()
