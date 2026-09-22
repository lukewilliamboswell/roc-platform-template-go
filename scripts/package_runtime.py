#!/usr/bin/env python3
"""Package generated runtimes and emit an SPDX source/file inventory."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess

from runtime_assets import (ROOT, REPO, MANIFEST, SOURCES, NOTICES, MACOS_METADATA, RUNTIME_PATHS,
                            archive_name, component_for, json_bytes, sha256,
                            write_archive, read_archive)


def package(targets: Path, output: Path, version: str) -> Path:
    name = archive_name(version)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    timestamp = int(subprocess.check_output(["git", "show", "-s", "--format=%ct", "HEAD"], cwd=ROOT, text=True))
    files = {path: (targets / path.removeprefix("targets/")).read_bytes() for path in RUNTIME_PATHS}
    sources = json.loads((ROOT / "scripts/runtime_sources.json").read_text())
    files[SOURCES] = json_bytes(sources)
    for notice in NOTICES:
        files[f"linker-inputs/licenses/{notice}"] = (ROOT / "licenses" / notice).read_bytes()
    for path in MACOS_METADATA:
        files[path] = (ROOT / path).read_bytes()
    manifest = {"format": 1, "version": version, "source_commit": commit,
                "files": {path: hashlib.sha256(data).hexdigest() for path, data in files.items()}}
    files[MANIFEST] = json_bytes(manifest)
    archive = output / name
    write_archive(archive, files)
    read_archive(archive)
    digest = sha256(archive)
    sbom = {
        "spdxVersion": "SPDX-2.3", "dataLicense": "CC0-1.0", "SPDXID": "SPDXRef-DOCUMENT",
        "name": name,
        "documentNamespace": f"https://github.com/{REPO}/linker-inputs-sbom/{digest}",
        "creationInfo": {"creators": ["Tool: roc-go-package-linker-inputs-1"],
                         "created": datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "packages": [{"SPDXID": "SPDXRef-archive", "name": "roc-go-linker-inputs", "versionInfo": version,
                      "downloadLocation": f"https://github.com/{REPO}/releases/download/linker-inputs-v{version}/{name}",
                      "filesAnalyzed": False, "licenseConcluded": "NOASSERTION", "licenseDeclared": "NOASSERTION",
                      "copyrightText": "NOASSERTION", "checksums": [{"algorithm": "SHA256", "checksumValue": digest}]}],
        "files": [],
        "relationships": [{"spdxElementId": "SPDXRef-DOCUMENT", "relationshipType": "DESCRIBES", "relatedSpdxElement": "SPDXRef-archive"}],
    }
    for key, component in sources["components"].items():
        download_location = (sources["zig"]["url"] if key != "darwin"
                             else f"https://github.com/{REPO}/tree/{commit}/linker-inputs/macos")
        sbom["packages"].append({
            "SPDXID": f"SPDXRef-{key}", "name": component["name"], "versionInfo": component["version"],
            "downloadLocation": download_location, "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION", "licenseDeclared": component["license"], "copyrightText": "NOASSERTION",
            "sourceInfo": json.dumps({"distribution_sha256": sources["zig"]["sha256"] if key != "darwin" else None,
                                      "paths": component["source_paths"], "notes": component["notes"]}, sort_keys=True),
        })
        sbom["relationships"].append({"spdxElementId": "SPDXRef-archive", "relationshipType": "CONTAINS", "relatedSpdxElement": f"SPDXRef-{key}"})
    for index, path in enumerate(sorted(files)):
        file_id = f"SPDXRef-file-{index}"
        sbom["files"].append({"SPDXID": file_id, "fileName": f"./{path}",
                              "checksums": [{"algorithm": "SHA256", "checksumValue": hashlib.sha256(files[path]).hexdigest()}],
                              "licenseConcluded": "NOASSERTION", "copyrightText": "NOASSERTION"})
        sbom["relationships"].append({"spdxElementId": "SPDXRef-archive", "relationshipType": "CONTAINS", "relatedSpdxElement": file_id})
        if path in RUNTIME_PATHS:
            sbom["relationships"].append({"spdxElementId": file_id, "relationshipType": "GENERATED_FROM", "relatedSpdxElement": f"SPDXRef-{component_for(path)}"})
    sbom_path = output / "linker-inputs.spdx.json"
    sbom_path.write_bytes(json_bytes(sbom))
    sums = output / "SHA256SUMS"
    sums.write_text(f"{digest}  {name}\n{sha256(sbom_path)}  linker-inputs.spdx.json\n")
    fingerprint = hashlib.sha256(json_bytes({
        "sources": sources,
        "catalog": json.loads((ROOT / "linker-inputs/macos/interfaces.json").read_text()),
        "recipe": hashlib.sha256((ROOT / "scripts/vendor_zig_runtime.py").read_bytes()).hexdigest(),
    })).hexdigest()
    dependency = {
        "schema_version": 1,
        "release_tag": f"linker-inputs-v{version}",
        "source": {"repository": REPO, "commit": commit, "ref": "refs/heads/main"},
        "input_fingerprint": fingerprint,
        "targets": sorted({path.split("/")[1] for path in RUNTIME_PATHS if path.startswith("targets/")}),
        "dependencies": sources["components"],
        "license_summary": "See linker-inputs.spdx.json and the notices inside the archive.",
        "assets": [
            {"name": name, "sha256": digest, "size": archive.stat().st_size, "role": "linker-input-archive", "media_type": "application/gzip"},
            {"name": "linker-inputs.spdx.json", "sha256": sha256(sbom_path), "size": sbom_path.stat().st_size, "role": "sbom", "media_type": "application/spdx+json"},
            {"name": "SHA256SUMS", "sha256": sha256(sums), "size": sums.stat().st_size, "role": "checksums", "media_type": "text/plain"},
        ],
    }
    # dependency.json is the controller manifest, so it cannot self-hash.
    (output / "dependency.json").write_bytes(json_bytes(dependency))
    print(f"{archive}: {digest}")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    package(args.targets_dir, args.output_dir, args.version)
