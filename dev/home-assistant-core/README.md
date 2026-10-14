# Marstek Core overlay

This directory contains only the Marstek integration and its tests in Home Assistant Core layout. It is the canonical source for the HACS integration at the repository root. The full upstream Core source is fetched at the commits in [`core-baselines.json`](../../core-baselines.json) into ignored `.test-core/<baseline>/` directories.

From a fresh repository checkout with Python 3.14.2 or newer:

```sh
./scripts/setup stable
./scripts/check stable
```

The `development` baseline uses its own pinned Core commit and matching `modbus-connection` version. Setup refuses an existing checkout at a different revision. It installs the checked-in library source from `dev/marstek-modbus` and generates the Core test translations. No sibling repositories are needed.

Edit this overlay and the canonical library under `dev/`, then run `./.venv/stable/bin/python scripts/sync.py`. The generated HACS integration vendors the library and has no separate device-library installation step. The Core overlay's manifest retains a standalone library requirement as a development draft; this overlay is not an installable Core distribution. Do not install the Core and HACS implementations of the same `marstek` domain together.

The integration supplies Home Battery Control entity IDs of the form `marstek_mN_*`, with the lowest available N as the default. Reconfigure can change the battery number and connection details; Options controls freshness and request spacing, defaulting to 160 ms. A timeout option is available with `modbus-connection` 4.12.1 or newer. User choices already saved in Options remain in effect.

See [validation](VALIDATION.md), the [documentation draft](integration-documentation.md), [hardware status](../../docs/hardware-validation.md), and [safety guidance](../../SAFETY.md).
