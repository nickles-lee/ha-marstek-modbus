#!/usr/bin/env python3
"""Run the integration suite from an extracted release archive."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile


def main() -> int:
    """Use only the archive's implementation with the pinned core test harness."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-checkout", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    version = json.loads(
        (root / "custom_components/marstek/manifest.json").read_text()
    )["version"]
    with TemporaryDirectory(prefix="marstek-artifact-") as directory:
        extracted = Path(directory)
        with ZipFile(root / f"dist/marstek-{version}.zip") as archive:
            archive.extractall(extracted)
        shutil.copytree(root / "tests", extracted / "tests")
        (extracted / "scripts").mkdir()
        shutil.copy(root / "scripts/test.py", extracted / "scripts/test.py")
        return subprocess.call(
            [
                sys.executable,
                str(extracted / "scripts/test.py"),
                "--core-checkout",
                str(args.core_checkout.resolve()),
            ]
        )


if __name__ == "__main__":
    raise SystemExit(main())
