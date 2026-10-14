# Marstek

Draft content for the Home Assistant documentation contribution.

Marstek connects locally to the Modbus TCP interface of Venus A, D, E 2.0 and E v3
batteries. The integration provides battery, grid, backup, energy and pack
measurements, model-supported PV measurements, and explicit control actions.
The author reports about a week of real-world use with Venus A, E 2.0, and E v3. Venus D remains untested on hardware; individual fields and firmware variants may differ.

## Installation

Use Home Assistant 2026.9.0 or newer with its supplied shared
Modbus connection API. Enable the battery's Modbus TCP interface according to
its firmware instructions and verify that its address is reachable.

In Settings → Devices & services, add Marstek. Enter host, port (502), unit ID
(1), model, battery number and pack count. Use one pack for E 2.0 or E v3 and the actual
installed count for A/D. The battery number chooses the Home Battery Control
entity prefix, such as marstek_m1. Setup validates the physical MAC identity.
A duplicate identity or occupied entity ID is rejected.

Use Reconfigure to change the endpoint, model, pack count or battery number.
Default entity IDs follow a new number; manually renamed entities keep their
names and appear in a repair notice listing HBC compatibility exceptions.

## Options and updates

Live measurements and controls refresh every 10 seconds. Energy counters,
schedules and other slow measurements refresh every 60 seconds. Successful
readings survive transient errors. An affected entity becomes unavailable when
its component has not refreshed within the stale timeout (default 180 seconds,
range 120–3600). Other components remain available.

Request spacing defaults to 160 ms and can be changed in Options. An optional
request timeout uses the shared connection backend. Leave it unset to retain
the backend default. Slower links may not complete a full cycle within the
nominal polling interval; examine timing diagnostics before tuning.

## Actions

Use standard number.set_value, select.select_option, time.set_value,
switch.turn_on/turn_off and button.press actions on the corresponding entities.
Power numbers accept integer watts within the model's limits. RS485 options
are disable/enable; work mode manual/anti-feed/ai; forced mode
stop/charge/discharge. Select RS485 enable explicitly before forced controls.
Actions validate values, send once and read back; failed confirmation raises
an action error. Inspect actual state before trying again.

Schedules expose times, signed power/mode, enable and weekday controls.
Weekday edits preserve other bits. Restart is an explicit, disabled-by-default
button. Setup and reconnection do not write control modes or power settings.

## Troubleshooting and limitations

Download diagnostics from the integration entry to inspect per-component ages,
error categories and timing. The download omits endpoint and identity data.
Report model, firmware, pack count and whether the failure is intermittent.
Do not infer zero power from unavailable or never-read values.

Some firmware reports work mode differently while RS485 control is active.
The integration exposes that readback and does not repeatedly rewrite manual
mode. Unsupported register interpretations, including defective D v150 current
at 32101, are excluded. Installed packs are configured, not speculatively probed.

## Removal

Open Settings → Devices & services, select the Marstek entry, then Delete.
Polling and freshness timers stop and shared connection ownership is released.
Removal does not change the battery's operating mode or stored schedules.

## Venus E 2.0

Choose `e_v2`, one pack, and the IP/port of an Elfin or LilyGO RS485 gateway
running Modbus TCP-to-RTU translation. Use 115200/8N1 and the battery unit ID
(default 1). Transparent RTU-over-TCP tunnels are unsupported. The legacy
profile includes HBC controls and schedules but omits unverified per-cell and
pack cycle registers. E 2.0 has been used with this integration on hardware, though firmware variants may differ. See the [sanitized LilyGO bridge example](../../examples/lilygo-t-can485-modbus-bridge.yaml) and the [integration README](../../README.md) for gateway setup and legacy firmware caveats.

Home Assistant 2026.9 uses the default 10-second request timeout. Custom timeout
tuning requires modbus-connection 4.12.1 or newer; spacing works on both versions.
