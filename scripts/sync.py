#!/usr/bin/env python3
"""Deterministically vendor library and core files, or check their parity."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def expected(lib: Path, core: Path) -> dict[str, bytes]:
    """Build exact expected package bytes from independent source folders."""
    result = {}
    for source in sorted(core.glob("*")):
        if (
            source.name == "quality_scale.yaml"
            or not source.is_file()
            or source.suffix not in (".py", ".json", ".yaml")
        ):
            continue
        content = source.read_text()
        if source.suffix == ".py":
            content = content.replace(
                "from marstek_modbus", "from ._vendor.marstek_modbus"
            )
        if source.name == "manifest.json":
            manifest = json.loads(content)
            manifest.pop("quality_scale", None)
            manifest.update(
                version="0.1.0",
                requirements=[],
                documentation="https://github.com/nickles-lee/ha-marstek-modbus",
                issue_tracker="https://github.com/nickles-lee/ha-marstek-modbus/issues",
            )
            manifest = {
                key: manifest[key]
                for key in (
                    "domain",
                    "name",
                    *sorted(set(manifest) - {"domain", "name"}),
                )
            }
            content = json.dumps(manifest, indent=2) + "\n"
        result[source.name] = content.encode()
    result["translations/en.json"] = result["strings.json"]
    assets = Path(__file__).resolve().parents[1] / "assets"
    for name in ("icon.png", "icon@2x.png"):
        result[f"brand/{name}"] = (assets / name).read_bytes()
    result["_vendor/__init__.py"] = (
        b'"""Vendored device library; synchronize with scripts/sync.py."""\n'
    )
    for source in sorted((lib / "src/marstek_modbus").glob("*")):
        if source.is_file() and (source.suffix == ".py" or source.name == "py.typed"):
            result["_vendor/marstek_modbus/" + source.name] = source.read_bytes()
    for name, source in [
        ("LICENSE", lib / "LICENSE"),
        ("NOTICE", lib / "NOTICE"),
    ]:
        result["_vendor/marstek_modbus/" + name] = source.read_bytes()
    for name, data in result.items():
        if name.endswith(".py") and not name.startswith("_vendor/"):
            result[name] = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "check",
                    "--select",
                    "I",
                    "--fix",
                    "--stdin-filename",
                    str(
                        Path(__file__).resolve().parents[1]
                        / "custom_components/marstek"
                        / name
                    ),
                    "-",
                ],
                input=data,
                capture_output=True,
                check=True,
            ).stdout
    for name in result:
        if name.endswith(".py") and not name.startswith("_vendor/"):
            result[name] = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "format",
                    "--stdin-filename",
                    str(
                        Path(__file__).resolve().parents[1]
                        / "custom_components/marstek"
                        / name
                    ),
                    "-",
                ],
                input=result[name],
                capture_output=True,
                check=True,
            ).stdout
    return result


def expected_tests(core: Path, repo: Path) -> dict[Path, bytes]:
    """Convert core tests without importing any non-vendored device code."""
    output = {}
    # core path is overlay/homeassistant/components/marstek.
    test_source = core.parents[2] / "tests/components/marstek"
    if test_source.is_dir():
        for source in sorted(test_source.glob("*.py")):
            content = (
                source.read_text()
                .replace(
                    "homeassistant.components.marstek", "custom_components.marstek"
                )
                .replace(
                    "from marstek_modbus",
                    "from custom_components.marstek._vendor.marstek_modbus",
                )
            )
            if source.name == "conftest.py":
                content += (
                    "\n\n@pytest.fixture(autouse=True)\n"
                    "def allow_custom(enable_custom_integrations):\n"
                    '    """Allow the local custom integration in core tests."""\n'
                )
            destination = repo / "tests/marstek" / source.name
            output[destination] = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "check",
                    "--select",
                    "I,D202",
                    "--fix",
                    "--stdin-filename",
                    str(destination),
                    "-",
                ],
                input=content.encode(),
                capture_output=True,
                check=True,
            ).stdout
    for destination in output:
        output[destination] = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                "format",
                "--stdin-filename",
                str(destination),
                "-",
            ],
            input=output[destination],
            capture_output=True,
            check=True,
        ).stdout
    return output


def main() -> int:
    """Copy source snapshots or fail when any package bytes differ."""
    parser = argparse.ArgumentParser(description=__doc__)
    repo = Path(__file__).resolve().parents[1]
    parser.add_argument("--library", type=Path, default=repo / "dev/marstek-modbus")
    parser.add_argument(
        "--core",
        type=Path,
        default=repo / "dev/home-assistant-core/homeassistant/components/marstek",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = repo / "custom_components/marstek"
    files = expected(args.library, args.core)
    test_files = expected_tests(args.core, repo)
    mismatches = [
        name
        for name, data in files.items()
        if not (target / name).exists() or (target / name).read_bytes() != data
    ]
    mismatches.extend(
        str(p)
        for p, data in test_files.items()
        if not p.exists() or p.read_bytes() != data
    )
    extras = [
        p
        for p in target.rglob("*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and p.relative_to(target).as_posix() not in files
    ]
    if args.check:
        if mismatches or extras:
            print("Out of sync:", *mismatches, *extras, sep="\n")
            return 1
        print("Core and vendored library match.")
        return 0
    for source in extras:
        source.unlink()
    for name, data in files.items():
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    for path, data in test_files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    checksums = {
        name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())
    }
    (repo / "source-hashes.json").write_text(json.dumps(checksums, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
