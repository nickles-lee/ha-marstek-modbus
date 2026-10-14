#!/usr/bin/env python3
"""Create an installable archive containing custom_components/marstek."""

import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
(root / "dist").mkdir(exist_ok=True)
version = json.loads((root / "custom_components/marstek/manifest.json").read_text())[
    "version"
]
output = root / f"dist/marstek-{version}.zip"
with ZipFile(output, "w", ZIP_DEFLATED) as archive:
    for path in sorted((root / "custom_components/marstek").rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            archive.write(path, path.relative_to(root))
print(output)
