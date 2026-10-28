#!/usr/bin/env python3
"""Run native Go ABI/ownership tests and vet with the locked C toolchain."""
import os
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, 'CC': 'zig cc', 'CGO_ENABLED': '1'}
    for operation in ('test', 'vet'):
        subprocess.run(['go', '-C', str(root / 'host'), operation, './...'], env=env, check=True)


if __name__ == '__main__':
    main()
