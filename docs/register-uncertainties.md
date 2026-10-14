# Register and firmware uncertainties

This is a short list of unresolved protocol questions. It is not a register map or a claim that all other fields are verified on every firmware. Addresses below are decimal.

| Area | Open question | Current behavior |
|---|---|---|
| Venus D hardware | Register meanings and behavior have no direct test on a Venus D owned by this project. | Profile remains available from community protocol evidence; reports from D owners are welcome. |
| D fault/alarm words (36000, 36100) | Widths and bit meanings vary or conflict in source maps. | No inferred alarm labels are exposed. |
| D v150 current (32101) | Reported unsigned-division firmware defect. | This value is not read. |
| E v3 IP fields (30400, 30402) | Two-word and four-word definitions conflict. | Fields remain inactive. |
| E 2.0 cell temperatures | BMS-dependent scaling is reported in source mappings. | The pinned legacy scale is used; compare against a real device before relying on it. |
| Factory reset (41001) | Destructive command is not independently corroborated across models. | No factory-reset action is exposed. |
| Derived efficiency and cycle counts | Instantaneous AC/DC ratio and lifetime cycle estimates lack a validated model. | These estimates are not exposed as device readings. |
| Work mode and RS485 control | Some firmware changes work-mode readback when RS485 control is enabled. | HA Managed retains goals separately, suppresses work-mode writes while RS485 is enabled, and asserts work mode only while RS485 is disabled. Battery Managed reports actual readback without background enforcement. |

Protocol source revisions are recorded in `dev/marstek-modbus/docs/sources.json`. Use redacted, read-only observations to propose corrections. See [Safety](../SAFETY.md) before testing writes.


## SoC targets and cutoffs

Register 42011 starts a separate SoC-target mode and may replace the explicit
charge/discharge command at 42010. Its library fields, catalog entries, and
managed-control keys are commented out for every model; it is neither polled nor
written. Re-enabling requires restoring all of those definitions, including the
forced-component read range, and deliberately deciding command priority.

The [Duravolt protocol](https://duravolt.nl/wp-content/uploads/Duravolt-Plug-in-Battery-Modbus.pdf)
(page 3) lists charging cutoff 44000 as 80–100% and discharging cutoff 44001 as
12–30%, both scaled by 0.1%. These limits are goals under HA Managed control,
initially adopted from valid battery readback. Firmware-specific enforcement of
cutoffs during forced control still needs hardware verification; register
convergence alone does not demonstrate that charging stops at a threshold.

Live read-only checks on 2026-10-04 returned raw 1000/120 for all three installed
E v2 batteries. Installed E v3 M1 returned exception 02 (illegal address) for
each cutoff register; Venus A M5 returned exception 04 (device failure), while
44002 remained readable on both. Cutoffs therefore have a separate optional
slow-polled component only on E v2 and never gate initialization or application
of the main controls. A/E v3 omit cutoff components and entities entirely. D
also omits them pending hardware verification.
