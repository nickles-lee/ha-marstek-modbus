# Register research

Source revisions are recorded in `docs/sources.json`. The root [uncertainty note](../../../docs/register-uncertainties.md) records open questions. Addresses are decimal with no subtraction.

## Evidence hierarchy

1. Device-specific observations and firmware analysis with stated version.
2. Independent mappings agreeing on address, width, scale and meaning.
3. Community mappings with no conflicting evidence, explicitly pending physical validation.
4. Conflicting or speculative definitions remain inactive.

Core A measurements and controls agree with the Fonske native TCP reference; extended A observations still require physical verification.

## Corrections and inactive fields

- D research reports a 32-word FC03 limit and disconnects after invalid-address exceptions. Do not span unknown gaps or scan the full address space.
- Pack spacing is 100 decimal, not 0x100. A has 13 cells; D and E3 have 16. Additional D pack scalars follow device scans. Protection words are numeric without invented alarm labels.
- E3 SoC is 34002 × 0.1. A/D aggregate SoC is 32104 × 1; per-pack is 34N02 × 0.1.
- Current uses signed 30101 × 0.1. D v150 register 32101 has an unsigned-division firmware defect and is not read.
- E3 backup power is a single signed word at 32302. A/D use the corroborated word at 30007. Consumers derive backup current from power / voltage; 32301 is not used.
- IP definitions conflict: reported two-word versus four-word firmware encoding. They are inactive.
- Alarm/fault widths and meanings are not established across selected variants; no E v1/v2 meaning is borrowed.
- Factory reset is inactive pending independent verification. Restart 41000/0x55AA is explicit-only.
- Nominal-cycle and instantaneous-efficiency estimates are inactive.
- AI work-mode readback can revert. On observed D firmware, work-mode and RS485 writes interfere. The confirmed-write API preserves actual readback. The caller-owned control-write API does not require readback confirmation; callers must manage authority and retries. HA Managed suppresses work-mode writes while RS485 is enabled.
- Capacity is instantaneous storage capacity, not an accumulated energy counter.

## Reproduction

Use the pinned revisions in sources.json where available, alongside these protocol references:

- [Fonske native TCP map](https://github.com/fonske/MarstekVenusV3-modbus-TCP-IP/blob/main/marstek_m1_modbus_tcp.yaml) and [Fonske RS485 map](https://github.com/fonske/MarstekVenus-LilygoRS485/blob/main/lilygo_mt1.yaml).
- [Duravolt RS485 protocol document](https://duravolt.nl/wp-content/uploads/Duravolt-Plug-in-Battery-Modbus.pdf) and the [Tweakers Modbus discussion](https://gathering.tweakers.net/forum/list_messages/2282240).
- [Firmware research](https://github.com/sphings79/Marstek-Venus-D-Firmware-Reverse-Engineering): `Modbus_RS485_TCP/Marstek_Modbus_TCP_Verbindungsreferenz.md` and `FW_Bug_Report_EN_Read_Serializer.md`.

Collect read-only snapshots with model, firmware, pack count and operating state before proposing corrections.

## Venus E 2.0 legacy profile

`e_v2` is the E 2.0 profile. Its register facts can be checked against the
Duravolt protocol document, Fonske RS485 map and Tweakers discussion above.
Common controls, schedules,
network, energy and restart blocks match the existing E v3 definitions.
Identity, firmware, battery, AC, backup, temperature and cell-extrema definitions
are explicitly mapped for E 2.0. No 34xxx pack blocks are probed.

Power at 32102, 32202 and 32302 is signed 32-bit, high word first. Current at
32101 and 32201 is signed ×0.01; frequency at 32204 is ×0.01. Battery SoC is
32104 ×1. Cell temperatures are signed whole degrees, unlike the modern maps.
The Fonske RS485 project reports BMS-dependent temperature scaling; confirm across
additional E 2.0 firmware before changing it. VMS and individual cell voltages are not included in
this profile. Software version is 31100 ×0.01. Inverter state 4 means backup mode
and 5 OTA upgrade. HBC's `ai` option is the legacy code-2 `trade_mode` alias.

The gateway transport stays standard Modbus TCP. Elfin's Modbus conversion mode
or suitable LilyGO TCP-to-RTU firmware terminates MBAP framing and serializes
RTU requests. This change neither flashes nor configures gateway hardware.
