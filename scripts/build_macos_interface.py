#!/usr/bin/env python3
"""Render the repository-authored, dual-architecture libSystem TAPI interface."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "linker-inputs/macos/interfaces.json"


def read_catalog(path: Path = CATALOG) -> dict:
    value = json.loads(path.read_text())
    expected = {"format", "targets", "install_name", "selection", "symbols", "evidence"}
    if set(value) != expected or value["format"] != 1:
        raise ValueError("Unsupported macOS interface catalog")
    if value["targets"] != ["arm64-macos", "x86_64-macos"]:
        raise ValueError("The libSystem interface must cover both advertised macOS targets")
    if value["install_name"] != "/usr/lib/libSystem.B.dylib":
        raise ValueError("Unexpected libSystem install name")
    symbols = value["symbols"]
    if symbols != sorted(set(symbols)):
        raise ValueError("macOS symbols must be sorted and unique")
    if any(re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$.]*", symbol) is None for symbol in symbols):
        raise ValueError("Invalid macOS symbol")
    if not value["selection"] or set(value["evidence"]) != {"host_recipe", "go_source", "public_api", "method"}:
        raise ValueError("Incomplete macOS interface provenance")
    return value


def render(catalog: dict) -> bytes:
    targets = ", ".join(catalog["targets"])
    lines = ["--- !tapi-tbd", "tbd-version: 4", f"targets: [ {targets} ]",
             f"install-name: '{catalog['install_name']}'", "exports:",
             f"  - targets: [ {targets} ]", "    symbols:"]
    lines.extend(f"      - '{symbol}'" for symbol in catalog["symbols"])
    return ("\n".join(lines + ["...", ""])).encode()


def build(destination: Path, catalog_path: Path = CATALOG) -> None:
    destination.write_bytes(render(read_catalog(catalog_path)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    build(args.output)
