#!/usr/bin/env python3
"""Run vendored integration tests in the pinned core checkout's test harness."""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Copy tests into a disposable core checkout and use its real fixtures."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-checkout", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    core = args.core_checkout.resolve()
    target = core / "tests/components/marstek_preview"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(root / "tests/marstek", target)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        (str(root), str(core), env.get("PYTHONPATH", ""))
    )
    return subprocess.call(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:homeassistant",
            "-q",
            "tests/components/marstek_preview",
            "-o",
            "addopts=",
        ],
        cwd=core,
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
