#!/usr/bin/env python3
"""Install and check the exact upstream distribution used by runtime CI."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

from fetch_runtime import download
from runtime_assets import ROOT, sha256


def main():
    sources = json.loads((ROOT / "scripts/runtime_sources.json").read_text())
    zig = sources["zig"]
    parent = Path(os.environ["RUNNER_TEMP"])
    destination = parent / "runtime-zig"
    destination.mkdir()
    with tempfile.TemporaryDirectory(dir=parent) as temporary:
        archive = Path(temporary) / "zig.tar.xz"
        download(zig["url"], archive)
        if sha256(archive) != zig["sha256"]:
            raise SystemExit("Zig distribution checksum mismatch")
        subprocess.run(["tar", "-xJf", str(archive), "--strip-components=1", "-C", str(destination)], check=True)
    version = subprocess.check_output([str(destination / "zig"), "version"], text=True).strip()
    if version != zig["version"]:
        raise SystemExit("Zig distribution version mismatch")
    for component in sources["components"].values():
        for path in component["source_paths"]:
            if not (destination / path).exists():
                raise SystemExit(f"Missing declared source: {path}")
        upstream = (destination / component["source_notice"]).read_text().splitlines()
        recorded = (ROOT / "licenses" / component["notice"]).read_text().splitlines()
        if [line.rstrip() for line in upstream] != [line.rstrip() for line in recorded]:
            raise SystemExit(f"License notice differs from trusted distribution: {component['notice']}")
    with Path(os.environ["GITHUB_PATH"]).open("a") as stream:
        stream.write(f"{destination}\n")


if __name__ == "__main__":
    main()
