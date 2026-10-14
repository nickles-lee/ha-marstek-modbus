"""Behavior tests for real component decoders and failed exchanges."""

import asyncio
from typing import cast
from unittest.mock import AsyncMock

import pytest
from conftest import seed
from modbus_connection import ModbusConnectionError, ModbusTimeoutError
from modbus_connection.mock import MockModbusUnit

from marstek_modbus import InvalidResponse, Model, ReadbackError
from marstek_modbus.components import Cutoffs


@pytest.mark.parametrize("model", list(Model))
async def test_decoding_and_read_budget(unit: MockModbusUnit, model: Model) -> None:
    device = seed(unit, model, model.max_packs)
    unit.holding[30001] = 65536 - 650
    unit.holding[30101] = 65536 - 122
    if model is Model.E_V2:
        unit.holding.update({32101: 65536 - 1220, 32102: 65535, 32103: 65536 - 650})
    report = await device.async_update()
    assert report.complete
    assert device.battery.battery_power == -650
    assert device.battery.battery_current == -12.2
    assert device.battery.battery_state_of_charge == 50
    assert device.mac_address == "aa:bb:cc:dd:ee:ff"
    assert all(e.count <= 32 for e in unit.read_events)
    allowed = {
        r.address + i
        for c in device.components.values()
        for r in c.resolved_fields.values()
        for i in range(r.count)
    }
    assert all(
        set(range(e.address, e.address + e.count)) <= allowed for e in unit.read_events
    )
    assert (32101 in allowed) == (model is Model.E_V2)
    assert (34033 in allowed) == (model in (Model.D, Model.E_V3))
    if model is Model.D:
        assert device.components["pack_7"].resolved_fields["voltage"].address == 34600


async def test_isolated_failure_and_recovery(unit: MockModbusUnit) -> None:
    device = seed(unit)
    await device.async_update()
    unit.holding[30006] = 900
    unit.holding[30001] = 999
    original = unit.read_holding_registers

    async def fail(address: int, count: int) -> list[int]:
        if address == 30001:
            raise ModbusTimeoutError("noise")
        return await original(address, count)

    unit.read_holding_registers = fail  # type: ignore[method-assign]
    report = await device.async_update()
    assert "battery" in report.failed
    assert device.battery.battery_power == 512
    # First component timeout intentionally stops this poll.
    unit.read_holding_registers = original  # type: ignore[method-assign]
    await device.async_update()
    assert device.battery.battery_power == 999


async def test_partial_success_survives_dead_link(unit: MockModbusUnit) -> None:
    device = seed(unit)
    await device.async_update()
    unit.holding[30001] = 123
    original = unit.read_holding_registers

    async def fail(address: int, count: int) -> list[int]:
        if address == 30006:
            raise ModbusConnectionError("disconnected")
        return await original(address, count)

    unit.read_holding_registers = fail  # type: ignore[method-assign]
    report = await device.async_update_readings()
    assert "battery" in report.updated
    assert "ac" in report.failed
    assert device.battery.battery_power == 123
    assert device.ac.ac_power == 500


async def test_malformed_component_rolls_back(unit: MockModbusUnit) -> None:
    device = seed(unit)
    await device.async_update()
    original = unit.read_holding_registers

    async def fail(address: int, count: int) -> list[int]:
        return [] if address == 30100 else await original(address, count)

    unit.read_holding_registers = fail  # type: ignore[method-assign]
    report = await device.async_update()
    assert isinstance(report.failed["battery"], InvalidResponse)
    assert device.battery.battery_voltage == 51.2


@pytest.mark.parametrize("model", [Model.E_V2, Model.E_V3])
async def test_failed_write_and_readback(unit: MockModbusUnit, model: Model) -> None:
    device = seed(unit, model)
    await device.async_update()
    await device.async_write("forced", "forcible_charge_power", 731)
    assert device.components["forced"].forcible_charge_power == 731  # type: ignore[attr-defined]
    with pytest.raises(ValueError):
        await device.async_write("forced", "forcible_charge_power", 2501)
    unit.write_register = AsyncMock()  # type: ignore[method-assign]
    with pytest.raises(ReadbackError):
        await device.async_write("forced", "forcible_charge_power", 900)
    assert device.components["forced"].forcible_charge_power == 731  # type: ignore[attr-defined]
    assert unit.write_register.await_count == 1


@pytest.mark.parametrize("model", [Model.E_V2, Model.E_V3])
async def test_rs485_precondition_does_not_auto_enable(
    unit: MockModbusUnit, model: Model
) -> None:
    device = seed(unit, model)
    unit.holding[42000] = 21947
    unit.write_register = AsyncMock()  # type: ignore[method-assign]
    with pytest.raises(ValueError, match="Enable RS485"):
        await device.async_write("forced", "forcible_charge_power", 800)
    unit.write_register.assert_not_awaited()


async def test_weekday_preserves_reserved_bits(unit: MockModbusUnit) -> None:
    device = seed(unit)
    unit.holding[43100] = 0x8001
    await device.async_set_weekday(1, 2, True)
    assert unit.holding[43100] == 0x8005
    await device.async_set_weekday(1, 0, False)
    assert unit.holding[43100] == 0x8004


@pytest.mark.parametrize(
    "field,value", [("start", 1260), ("end", 2400), ("mode", 0), ("mode", -99)]
)
async def test_schedule_validation(
    unit: MockModbusUnit, field: str, value: int
) -> None:
    device = seed(unit)
    with pytest.raises(ValueError):
        await device.async_write("schedule_1", field, value)


@pytest.mark.parametrize("identity", ["000000000000", "FFFFFFFFFFFF", "XXXXXXXXXXXX"])
@pytest.mark.parametrize("model", [Model.E_V2, Model.E_V3])
async def test_invalid_identity(
    unit: MockModbusUnit, identity: str, model: Model
) -> None:
    device = seed(unit, model)
    for i in range(0, 12, 2):
        unit.holding[(30402 if model is Model.E_V2 else 30304) + i // 2] = (
            int.from_bytes(identity[i : i + 2].encode(), "big")
        )
    with pytest.raises(ValueError, match="identity"):
        await device.async_identify()


async def test_concurrent_writes_serialized(unit: MockModbusUnit) -> None:
    device = seed(unit)
    await device.async_update()
    await asyncio.gather(
        *(device.async_write("limits", "max_charge_power", v) for v in [100, 200, 300])
    )
    assert device.components["limits"].max_charge_power == 300  # type: ignore[attr-defined]


async def test_pack_failure_does_not_invalidate_other_packs(
    unit: MockModbusUnit,
) -> None:
    device = seed(unit, Model.D, 2)
    await device.async_update()
    first = device.components["pack_1"]._values.copy()
    original = unit.read_holding_registers

    async def read(address: int, count: int) -> list[int]:
        if address == 34000:
            raise ModbusTimeoutError("pack unavailable")
        return await original(address, count)

    unit.read_holding_registers = read  # type: ignore[method-assign]
    report = await device.async_update_readings()
    assert "pack_1" in report.failed
    assert "pack_2" in report.updated
    assert device.components["pack_1"]._values == first


async def test_raw_diagnostics_failure_preserves_cache(unit: MockModbusUnit) -> None:
    device = seed(unit)
    await device.async_update()
    original = unit.read_holding_registers
    unit.holding[30001] = 999

    async def read(address: int, count: int) -> list[int]:
        return [] if address == 30100 else await original(address, count)

    unit.read_holding_registers = read  # type: ignore[method-assign]
    with pytest.raises(InvalidResponse):
        await device.async_read_raw(["battery"])
    assert device.battery.battery_power == 512


async def test_transient_failure_retries_once(unit: MockModbusUnit) -> None:
    device = seed(unit)
    original = unit.read_holding_registers
    attempts = 0

    async def read(address: int, count: int) -> list[int]:
        nonlocal attempts
        if address == 30006:
            attempts += 1
            if attempts == 1:
                raise ModbusTimeoutError("noise")
        return await original(address, count)

    unit.read_holding_registers = read  # type: ignore[method-assign]
    report = await device.async_update_readings()
    assert "ac" in report.updated
    assert "ac" not in report.failed
    assert attempts == 2


async def test_e_v2_legacy_readings_and_controls(unit: MockModbusUnit) -> None:
    device = seed(unit, Model.E_V2)
    writer = AsyncMock(wraps=unit.write_register)
    unit.write_register = writer  # type: ignore[method-assign]
    unit.holding.update(
        {
            32200: 2300,
            32201: 65536 - 123,
            32202: 65535,
            32203: 65536 - 700,
            32204: 5000,
            32301: 123,
            32302: 1,
            32303: 2,
            35010: 35,
            35011: 65536 - 5,
        }
    )
    report = await device.async_update()
    assert report.complete
    assert device.ac.ac_power == -700
    assert device.ac.ac_current == -1.23
    assert device.ac.ac_frequency == 50
    assert device.battery.battery_voltage == 51.2
    backup = device.components["backup_readings"]
    assert backup.ac_offgrid_power == 65538  # type: ignore[attr-defined]
    assert backup.ac_offgrid_current == 1.23  # type: ignore[attr-defined]
    assert device.components["temperatures"].max_cell_temperature == 35  # type: ignore[attr-defined]
    assert device.components["temperatures"].min_cell_temperature == -5  # type: ignore[attr-defined]
    assert not any(n.startswith("pack_") for n in device.components)
    assert "pv" not in device.components
    writer.assert_not_awaited()
    await device.async_write("forced", "forcible_charge_power", 800)
    await device.async_write("forced", "forcible_charge_discharge", 1)
    assert unit.holding[42020] == 800
    assert unit.holding[42010] == 1
    await device.async_set_weekday(6, 6, True)
    assert unit.holding[43125] == 64
    with pytest.raises(ValueError):
        seed(unit, Model.E_V2, 2)


@pytest.mark.parametrize("model", list(Model))
async def test_managed_write_preserves_observation(
    unit: MockModbusUnit, model: Model
) -> None:
    """Caller-owned goals can be applied despite RS485 readback lying."""
    device = seed(unit, model)
    await device.async_update()
    unit.holding[42000] = 21947
    before = len(unit.read_events)
    assert await device.async_write_control(
        "forced", "forcible_charge_power", 731, is_current=lambda: True
    )
    assert unit.holding[42020] == 731
    assert device.components["forced"].forcible_charge_power == 0  # type: ignore[attr-defined]
    assert len(unit.read_events) == before
    await device.async_update_readings()
    assert device.components["forced"].forcible_charge_power == 731  # type: ignore[attr-defined]


async def test_managed_write_scope_and_validation(unit: MockModbusUnit) -> None:
    """The unconfirmed path cannot write schedules or invalid physical values."""
    device = seed(unit)
    unit.write_register = AsyncMock()  # type: ignore[method-assign]
    with pytest.raises(ValueError, match="managed control"):
        await device.async_write_control(
            "schedule_1", "enabled", 1, is_current=lambda: True
        )
    with pytest.raises(ValueError, match="Power"):
        await device.async_write_control(
            "forced", "forcible_charge_power", 2501, is_current=lambda: True
        )
    unit.write_register.assert_not_awaited()


async def test_managed_write_rechecks_intent_inside_lock(unit: MockModbusUnit) -> None:
    """Queued writes cannot send goals superseded while awaiting another poll."""
    device = seed(unit)
    current = True
    async with device._lock:
        task = asyncio.create_task(
            device.async_write_control(
                "forced", "forcible_charge_power", 731, is_current=lambda: current
            )
        )
        await asyncio.sleep(0)
        current = False
    assert not await task
    assert unit.holding[42020] == 0


@pytest.mark.parametrize("model", list(Model))
async def test_cutoff_scaling_and_retired_soc(
    unit: MockModbusUnit, model: Model
) -> None:
    device = seed(unit, model)
    await device.async_update()
    assert "charge_to_soc" not in device.components["forced"].resolved_fields
    assert all(
        not event.address <= 42011 < event.address + event.count
        for event in unit.read_events
    )
    if model is not Model.E_V2:
        assert "cutoffs" not in device.components
        assert all(
            not {44000, 44001}.intersection(
                range(event.address, event.address + event.count)
            )
            for event in unit.read_events
        )
        return
    await device.async_write_control(
        "cutoffs", "charging_cutoff_capacity", 93.5, is_current=lambda: True
    )
    await device.async_write_control(
        "cutoffs", "discharging_cutoff_capacity", 12.5, is_current=lambda: True
    )
    assert unit.holding[44000] == 935
    assert unit.holding[44001] == 125
    await device.async_update()
    assert cast(Cutoffs, device.components["cutoffs"]).charging_cutoff_capacity == 93.5
    assert (
        cast(Cutoffs, device.components["cutoffs"]).discharging_cutoff_capacity == 12.5
    )
    for field, values in [
        ("charging_cutoff_capacity", (79.9, 100.1, 93.55)),
        ("discharging_cutoff_capacity", (11.9, 30.1, 12.55)),
    ]:
        for value in values:
            with pytest.raises(ValueError):
                await device.async_write_control(
                    "cutoffs", field, value, is_current=lambda: True
                )
