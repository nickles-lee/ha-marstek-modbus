"""End-to-end HA entity and action behavior."""

from datetime import time
from unittest.mock import AsyncMock, patch

import pytest
from modbus_connection import ModbusConnectionError, ModbusTimeoutError

from homeassistant.components.marstek.descriptions import HBC_KEYS, descriptions
from homeassistant.components.marstek.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.components.marstek.entity import MarstekEntity
from homeassistant.components.marstek.naming import collision, rename_slot
from homeassistant.components.marstek.switch import MarstekSwitch
from homeassistant.components.marstek.time import MarstekTime
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from marstek_modbus import Model
from tests.common import MockConfigEntry, async_fire_time_changed

from . import DATA, seed


async def test_setup_default_spacing(hass, config_entry, connection):
    """Use 160 ms for new entries while honoring an existing choice."""
    config_entry.add_to_hass(hass)
    unit = connection.for_unit(1)
    with (
        patch("homeassistant.components.marstek.async_get_unit", return_value=unit),
        patch.object(unit, "set_message_spacing") as spacing,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        spacing.assert_called_once_with(0.16)
        await hass.config_entries.async_unload(config_entry.entry_id)

    hass.config_entries.async_update_entry(
        config_entry, options={"message_spacing": 80}
    )
    with (
        patch("homeassistant.components.marstek.async_get_unit", return_value=unit),
        patch.object(unit, "set_message_spacing") as spacing,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        spacing.assert_called_once_with(0.08)
        await hass.config_entries.async_unload(config_entry.entry_id)


async def test_hbc_contract(hass, init_integration):
    """Verify hbc contract."""
    specs = descriptions(Model.E_V3, 1)
    for key in HBC_KEYS:
        spec = next(s for s in specs if s.key == key)
        assert hass.states.get(f"{spec.platform}.marstek_m1_{key}") is not None
    assert (
        hass.states.get("sensor.marstek_m1_battery_remaining_capacity").state == "2.56"
    )
    assert hass.states.get("sensor.marstek_m1_inverter_state").state == "Charge"
    assert hass.states.get("select.marstek_m1_user_work_mode").attributes[
        "options"
    ] == ["manual", "anti-feed", "ai"]
    assert hass.states.get("select.marstek_m1_forcible_charge_discharge").attributes[
        "options"
    ] == ["stop", "charge", "discharge"]


async def test_service_writes(hass, init_integration, connection):
    """Verify service writes."""
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.marstek_m1_forcible_charge_power", "value": 731},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert connection.for_unit(1).holding[42020] == 731
    assert hass.states.get("number.marstek_m1_forcible_charge_power").state == "731"
    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": "select.marstek_m1_forcible_charge_discharge",
            "option": "discharge",
        },
        blocking=True,
    )
    assert connection.for_unit(1).holding[42010] == 2


async def test_failure_grace_expiry_recovery(
    hass, init_integration, connection, freezer
):
    """Verify failure grace expiry recovery."""
    coordinator = init_integration.runtime_data.coordinator
    unit = connection.for_unit(1)
    original = unit.read_holding_registers
    unit.read_holding_registers = AsyncMock(
        side_effect=ModbusConnectionError("offline")
    )
    await coordinator.async_refresh()
    assert hass.states.get("sensor.marstek_m1_battery_power").state == "512"
    freezer.tick(181)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get("sensor.marstek_m1_battery_power").state == "unavailable"
    unit.read_holding_registers = original
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.marstek_m1_battery_power").state == "512"


async def test_partial_failure_only_expires_affected_component(
    hass, init_integration, connection, freezer
):
    """Verify partial failure only expires affected component."""
    coordinator = init_integration.runtime_data.coordinator
    unit = connection.for_unit(1)
    original = unit.read_holding_registers

    async def read(address, count):
        if address == 30006:
            raise ModbusTimeoutError("AC timeout")
        return await original(address, count)

    unit.read_holding_registers = read
    freezer.tick(181)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.marstek_m1_ac_power").state == "unavailable"
    assert hass.states.get("sensor.marstek_m1_battery_power").state == "512"


async def test_write_readback_failure_is_action_error(
    hass, init_integration, connection
):
    """Verify write readback failure is action error."""
    unit = connection.for_unit(1)
    unit.write_register = AsyncMock()
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": "number.marstek_m1_max_charge_power", "value": 900},
            blocking=True,
        )
    assert hass.states.get("number.marstek_m1_max_charge_power").state == "1500"


async def test_rename_preserves_custom_names(hass, init_integration):
    """Verify rename preserves custom names."""
    registry = er.async_get(hass)
    registry.async_update_entity(
        "sensor.marstek_m1_ac_power", new_entity_id="sensor.my_battery_ac"
    )
    rename_slot(hass, init_integration.entry_id, 1, 2)
    assert registry.async_get("sensor.my_battery_ac")
    assert registry.async_get("sensor.marstek_m2_battery_power")
    assert registry.async_get("sensor.marstek_m2_battery_power").unique_id.endswith(
        "_battery_power"
    )


async def test_collision_unregistered_entity(hass):
    """Verify collision unregistered entity."""
    hass.states.async_set("sensor.marstek_m2_ac_power", 123)
    assert (
        collision(hass, dict(DATA, battery_slot=2), descriptions(Model.E_V3, 1))
        == "sensor.marstek_m2_ac_power"
    )


async def test_diagnostics_redaction(hass, init_integration):
    """Verify diagnostics redaction."""
    result = await async_get_config_entry_diagnostics(hass, init_integration)
    text = str(result)
    assert "192.0.2.1" not in text
    assert "aa:bb:cc" not in text
    assert "age_seconds" in result


async def test_non_english_ids(hass, config_entry, connection):
    """Verify non english ids."""
    hass.config.language = "nl"
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.marstek.async_get_unit",
        return_value=connection.for_unit(1),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.marstek_m1_battery_state_of_charge")
        await hass.config_entries.async_unload(config_entry.entry_id)


async def test_stored_energy_matches_capacity(hass, init_integration):
    """Verify stored energy matches capacity."""
    spec = next(s for s in descriptions(Model.E_V3, 1) if s.key == "stored_energy")
    entity = MarstekEntity(init_integration, spec)
    assert entity.value == 2.56
    assert spec.sources == ("battery",)


async def test_failed_initial_poll_retries_setup(hass, config_entry, connection):
    """Verify failed initial poll retries setup."""
    config_entry.add_to_hass(hass)
    original = connection.for_unit(1).read_holding_registers

    async def read(address, count):
        if address == 30001:
            raise ModbusConnectionError("offline")
        return await original(address, count)

    connection.for_unit(1).read_holding_registers = read
    with patch(
        "homeassistant.components.marstek.async_get_unit",
        return_value=connection.for_unit(1),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_schedule_actions_preserve_bits(hass, init_integration, connection):
    """Clock and weekday actions encode correctly without clearing reserved bits."""
    specs = descriptions(Model.E_V3, 1)
    unit = connection.for_unit(1)
    unit.holding[43100] = 0x8002
    clock = MarstekTime(
        init_integration, next(s for s in specs if s.key == "schedule_1_start")
    )
    await clock.async_set_value(time(7, 35))
    assert unit.holding[43101] == 735
    assert clock.native_value == time(7, 35)
    weekday = MarstekSwitch(
        init_integration, next(s for s in specs if s.key == "schedule_1_monday")
    )
    await weekday.async_turn_on()
    assert unit.holding[43100] == 0x8003
    await weekday.async_turn_off()
    assert unit.holding[43100] == 0x8002


async def test_collision_with_own_manually_renamed_entity(hass, init_integration):
    """A manual name must not occupy another field's future default ID."""
    registry = er.async_get(hass)
    registry.async_update_entity(
        "sensor.marstek_m1_ac_power", new_entity_id="sensor.marstek_m2_battery_power"
    )
    assert (
        collision(
            hass,
            dict(DATA, battery_slot=2),
            descriptions(Model.E_V3, 1),
            init_integration.entry_id,
        )
        == "sensor.marstek_m2_battery_power"
    )


@pytest.mark.parametrize("model", list(Model))
async def test_model_setup_limits(hass, config_entry, connection, model):
    """Each model exposes the exact HBC contract and its own power bounds."""
    seed(connection, model)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, data=dict(DATA, model=model.value)
    )
    with patch(
        "homeassistant.components.marstek.async_get_unit",
        return_value=connection.for_unit(1),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        power = hass.states.get("number.marstek_m1_forcible_charge_power")
        assert power.attributes["max"] == model.max_power
        assert power.attributes["step"] == 1
        if model is Model.E_V2:
            specs = descriptions(model, 1)
            assert not any(s.component.startswith("pack_") for s in specs)
            assert not any(s.component == "pv" for s in specs)
            device = config_entry.runtime_data.coordinator.device
            for spec in specs:
                if spec.field:
                    assert (
                        spec.field in device.components[spec.component].resolved_fields
                    )
            assert hass.states.get("sensor.marstek_m1_ac_power").state == "500"
            assert hass.states.get("sensor.marstek_m1_battery_power").state == "512"
        assert (
            hass.states.get("sensor.marstek_m1_battery_remaining_capacity").state
            == "2.56"
        )
        await hass.config_entries.async_unload(config_entry.entry_id)


async def test_two_batteries_have_independent_entities(
    hass, init_integration, connection
):
    """Different identities and slots coexist without generated ID suffixes."""
    other = MockConfigEntry(
        domain="marstek",
        unique_id="aa:bb:cc:dd:ee:11",
        data=dict(DATA, battery_slot=2, host="192.0.2.2"),
        title="Marstek m2",
    )
    other.add_to_hass(hass)
    connection.for_unit(1).holding[30309] = int.from_bytes(b"11", "big")
    with patch(
        "homeassistant.components.marstek.async_get_unit",
        return_value=connection.for_unit(1),
    ):
        assert await hass.config_entries.async_setup(other.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.marstek_m1_battery_power")
        assert hass.states.get("sensor.marstek_m2_battery_power")
        assert not hass.states.get("sensor.marstek_m1_battery_power_2")
        await hass.config_entries.async_unload(other.entry_id)


async def test_connection_watchdog_retries_and_recovers(
    hass, init_integration, freezer
):
    """Reset a silent connection repeatedly, but never reset a responsive one."""
    coordinator = init_integration.runtime_data.coordinator
    with (
        patch.object(
            coordinator.timed, "disconnect", new_callable=AsyncMock
        ) as disconnect,
        patch.object(coordinator, "async_request_refresh", new_callable=AsyncMock),
    ):
        freezer.tick(89)
        coordinator._expire(None)
        assert coordinator._recovery_task is None
        freezer.tick(2)
        coordinator._expire(None)
        await coordinator._recovery_task
        disconnect.assert_awaited_once()
        coordinator._expire(None)
        assert disconnect.await_count == 1
        freezer.tick(90)
        coordinator._expire(None)
        await coordinator._recovery_task
        assert disconnect.await_count == 2
        await coordinator.timed.read_holding_registers(30006, 1)
        freezer.tick(89)
        coordinator._expire(None)
        assert disconnect.await_count == 2


async def test_watchdog_disconnect_timeout(hass, init_integration, freezer):
    """A reset failure must not permanently disable subsequent recovery."""
    coordinator = init_integration.runtime_data.coordinator
    with (
        patch.object(
            coordinator.timed, "disconnect", side_effect=TimeoutError
        ) as disconnect,
        patch.object(coordinator, "async_request_refresh", new_callable=AsyncMock),
    ):
        for _ in range(2):
            freezer.tick(91)
            coordinator._expire(None)
            await coordinator._recovery_task
        assert disconnect.await_count == 2


async def test_display_names_and_rte_default(hass, init_integration):
    """Default labels change without changing stable automation entity IDs."""
    assert init_integration.title == "M1"
    registry = er.async_get(hass)
    rte = registry.async_get("sensor.marstek_m1_round_trip_efficiency_total")
    assert rte.disabled_by is None
    from homeassistant.helpers import device_registry as dr

    device = dr.async_get(hass).async_get(rte.device_id)
    assert device.name == "M1"


@pytest.mark.parametrize(
    "disabled_by", [er.RegistryEntryDisabler.INTEGRATION, er.RegistryEntryDisabler.USER]
)
async def test_rte_existing_default(hass, config_entry, connection, disabled_by):
    """Enable the old integration default while preserving explicit user choices."""
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    entity = registry.async_get_or_create(
        "sensor",
        "marstek",
        f"{config_entry.unique_id}_round_trip_efficiency_total",
        config_entry=config_entry,
        suggested_object_id="marstek_m1_round_trip_efficiency_total",
        disabled_by=disabled_by,
    )
    with patch(
        "homeassistant.components.marstek.async_get_unit",
        return_value=connection.for_unit(1),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert registry.async_get(entity.entity_id).disabled_by is (
            er.RegistryEntryDisabler.USER
            if disabled_by is er.RegistryEntryDisabler.USER
            else None
        )
        await hass.config_entries.async_unload(config_entry.entry_id)


async def test_watchdog_while_refresh_stalled(hass, init_integration, freezer):
    """A pending refresh cannot block repeated resets, and unload cancels it."""
    import asyncio

    coordinator = init_integration.runtime_data.coordinator
    pending = asyncio.Event()
    with (
        patch.object(
            coordinator.timed, "disconnect", new_callable=AsyncMock
        ) as disconnect,
        patch.object(coordinator, "async_request_refresh", side_effect=pending.wait),
    ):
        freezer.tick(91)
        coordinator._expire(None)
        await coordinator._recovery_task
        task = coordinator._recovery_refresh
        freezer.tick(91)
        coordinator._expire(None)
        await coordinator._recovery_task
        assert disconnect.await_count == 2
        assert coordinator._recovery_refresh is task
        await hass.config_entries.async_unload(init_integration.entry_id)
        assert task.cancelled()


async def test_battery_managed_readback_has_no_goal_comparison(hass, init_integration):
    """Readback remains meaningful without retained HA-managed goals."""
    assert (
        hass.states.get("sensor.marstek_m1_rs485_control_mode_readback").state
        == "enable"
    )
    assert (
        hass.states.get("sensor.marstek_m1_forcible_charge_power_readback").state == "0"
    )
    assert (
        hass.states.get("binary_sensor.marstek_m1_controls_in_sync").state
        == "unavailable"
    )
    assert (
        hass.states.get("binary_sensor.marstek_m1_forcible_charge_power_in_sync").state
        == "unavailable"
    )
