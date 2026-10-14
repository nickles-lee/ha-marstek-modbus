#!/usr/bin/env python3
"""Fetch a pinned Home Assistant Core test checkout into .test-core/."""

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINES = json.loads((ROOT / "core-baselines.json").read_text())


def run(*args: str, cwd: Path | None = None) -> str:
    """Run git and return its output."""
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def fetch(baseline: str) -> Path:
    """Return an exact pinned checkout, refusing a different existing HEAD."""
    commit = BASELINES[baseline]["commit"]
    target = ROOT / ".test-core" / baseline
    if target.exists() and not (target / ".git").is_dir():
        raise SystemExit(f"{target} exists but is not a Git checkout")
    if (target / ".git").is_dir():
        try:
            actual = run("git", "rev-parse", "HEAD", cwd=target)
        except subprocess.CalledProcessError:
            actual = ""
        if actual and actual != commit:
            raise SystemExit(
                f"Wrong Core revision at {target}: {actual}; expected {commit}"
            )
        if actual == commit:
            print(f"Core {baseline}: {target} ({commit})")
            return target
    else:
        target.mkdir(parents=True)
        run("git", "init", "-q", str(target))
        run(
            "git",
            "remote",
            "add",
            "origin",
            "https://github.com/home-assistant/core.git",
            cwd=target,
        )
    run("git", "fetch", "-q", "--depth", "1", "origin", commit, cwd=target)
    run("git", "checkout", "-q", "--detach", commit, cwd=target)
    actual = run("git", "rev-parse", "HEAD", cwd=target)
    if actual != commit:
        raise SystemExit(f"Core revision mismatch: {actual} != {commit}")
    print(f"Core {baseline}: {target} ({commit})")
    return target


def main() -> None:
    """Fetch the selected supported Core baseline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", choices=BASELINES)
    args = parser.parse_args()
    fetch(args.baseline)


if __name__ == "__main__":
    main()
