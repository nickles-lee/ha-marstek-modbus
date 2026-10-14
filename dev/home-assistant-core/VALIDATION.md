# Core overlay validation

This directory contains only Marstek-specific Core integration files and tests. The full upstream Home Assistant Core checkout is fetched at pinned commits into the ignored root `.test-core/` directory.

From the repository root, run `./scripts/setup stable && ./scripts/check stable`; repeat with `development` for the newer pinned baseline. The check command verifies the generated HACS package against this overlay and runs integration tests in the downloaded Core harness. The HACS version bundles the device library; this overlay is retained as canonical source and is not an independent Home Assistant Core submission.

See root [validation](../../docs/validation.md), [hardware status](../../docs/hardware-validation.md), and [Safety](../../SAFETY.md).
