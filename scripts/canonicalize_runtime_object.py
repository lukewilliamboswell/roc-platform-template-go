#!/usr/bin/env python3
"""Canonicalize generated runtime objects for reproducible vendoring."""

from pathlib import Path
import struct
import sys


# This is an embedded reproducibility marker, not a filesystem location used
# by the script. Its fixed length lets us replace randomized build paths in
# generated objects without changing their section layout.
CANONICAL_ROOT = b"/tmp/roc-go-zig-runtime.CANON0"
COFF_MACHINES = {0x8664, 0xAA64}
IMAGE_SCN_LNK_REMOVE = 0x00000800


def canonicalize(object_path: Path, random_work_root: Path) -> None:
    random_root = str(random_work_root).encode()
    if len(random_root) != len(CANONICAL_ROOT):
        raise ValueError("random and canonical cache roots must have equal lengths")
    contents = object_path.read_bytes()
    object_path.write_bytes(contents.replace(random_root, CANONICAL_ROOT))


def strip_coff_debug_sections(object_path: Path) -> None:
    contents = bytearray(object_path.read_bytes())
    if len(contents) < 20:
        raise ValueError(f"COFF object is too small: {object_path}")
    machine, section_count = struct.unpack_from("<HH", contents)
    if machine not in COFF_MACHINES:
        raise ValueError(f"Unsupported COFF machine 0x{machine:04x}: {object_path}")
    optional_header_size = struct.unpack_from("<H", contents, 16)[0]
    section_table = 20 + optional_header_size
    section_table_end = section_table + section_count * 40
    if section_table_end > len(contents):
        raise ValueError(f"Invalid COFF section table: {object_path}")

    for index in range(section_count):
        header = section_table + index * 40
        name = bytes(contents[header : header + 8]).rstrip(b"\0")
        if not name.startswith(b".debug"):
            continue
        size, offset = struct.unpack_from("<II", contents, header + 16)
        end = offset + size
        if offset > len(contents) or end > len(contents):
            raise ValueError(f"Invalid COFF debug section: {object_path}")
        contents[offset:end] = bytes(size)
        characteristics = struct.unpack_from("<I", contents, header + 36)[0]
        struct.pack_into(
            "<I", contents, header + 36, characteristics | IMAGE_SCN_LNK_REMOVE
        )

    object_path.write_bytes(contents)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} OBJECT RANDOM_WORK_ROOT")

    try:
        canonicalize(Path(sys.argv[1]), Path(sys.argv[2]))
    except ValueError as error:
        raise SystemExit(str(error)) from None


if __name__ == "__main__":
    main()
