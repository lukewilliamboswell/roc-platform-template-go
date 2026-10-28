#!/usr/bin/env python3
"""Source policy, maintenance tests, Roc units, formatting and public docs."""
import subprocess
import sys
from pathlib import Path
from compiler_pins import header_pin

ROOT = Path(__file__).resolve().parents[1]


def main():
    for name in ('.roc-version', '.github/roc-nightly.json'):
        if (ROOT / name).exists():
            raise SystemExit(f'Remove obsolete compiler pin file: {name}')
    for directory in ('platform', 'examples'):
        for source in (ROOT / directory).rglob('*.roc'):
            if header_pin(source.read_text(encoding='utf-8')) is not None:
                raise SystemExit(f'Product source must not pin the compiler: {source}')
    for command in (
        [sys.executable, '-m', 'unittest', 'discover', '-s', 'scripts', '-p', 'test_*.py'],
        [sys.executable, 'scripts/check_no_binaries.py'],
        [sys.executable, 'scripts/check_roc_format.py'],
        ['roc', 'test', 'platform/main.roc'],
        ['roc', 'docs', 'platform/main.roc', '--output=ci-docs', '--no-cache'],
    ):
        subprocess.run(command, cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
