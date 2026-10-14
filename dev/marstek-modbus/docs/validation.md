# Device library validation

The canonical library is checked in under `dev/marstek-modbus` and copied into the installable HACS package by `scripts/sync.py`. From the repository root, `./scripts/setup stable && ./scripts/check stable` runs the library suite, strict mypy, lint, integration suite, and packaged archive smoke against a pinned Home Assistant Core baseline. The `development` baseline exercises the newer transport API. The full Core checkouts stay in the ignored `.test-core/` directory.

The author reports about a week of live use on Venus A, E 2.0, and E v3; Venus D has not been hardware-tested. See the root [hardware status](../../../docs/hardware-validation.md) and [register uncertainties](../../../docs/register-uncertainties.md).
