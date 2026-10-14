"""HA control intent survives firmware drift and transport failures."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from modbus_connection import ModbusConnectionError

from custom_components.marstek._vendor.marstek_modbus import Model
from custom_components.marstek.const import CONF_CONTROL_MANAGEMENT, HA_MANAGED
from homeassistant.exceptions import HomeAssistantError
from tests.common import MockConfigEntry

from . import DATA, MAC, seed


@pytest.fixture
def config_entry(request):
    """An existing entry without the new selector must migrate to HA managed."""
    return MockConfigEntry(
        domain="marstek",
        unique_id=MAC,
        data={
            **{
                key: value
                for key, value in DATA.items()
                if key != CONF_CONTROL_MANAGEMENT
            },
            "model": getattr(request, "param", "e_v3"),
        },
        title="M1",
    )


@pytest.fixture
def connection(config_entry):
    """Seed the exact selected model, including legacy identity registers."""
    from modbus_connection.mock import MockModbusConnection

    connection = MockModbusConnection()
    seed(connection, Model(config_entry.data["model"]))
    return connection


async def run_controls(hass, entry, freezer, seconds=0):
    """Run only the control timer, avoiding unrelated periodic polling."""
    freezer.tick(seconds)
    controls = entry.runtime_data.coordinator.controls
    controls.request()
    if controls._task is not None:
        await controls._task
    await hass.async_block_till_done()


async def set_goal(hass, entry, key, value):
    """Exercise the same goal path as HA services without awaiting transport."""
    controls = entry.runtime_data.coordinator.controls
    spec = controls.specs[key]
    await entry.runtime_data.coordinator.write(spec.component, spec.field, value)
    await hass.async_block_till_done()


async def test_migration_and_snapshot(hass, init_integration, connection, freezer):
    """Upgrade adopts the initial controls, including enabled RS485."""
    assert init_integration.data[CONF_CONTROL_MANAGEMENT] == HA_MANAGED
    controls = init_integration.runtime_data.coordinator.controls
    assert controls.ready
    assert controls.goals["rs485_control_mode"] == 21930
    assert controls.goals["max_charge_power"] == 1500
    assert controls.status("user_work_mode") == "deferred"
    await run_controls(hass, init_integration, freezer, 5)
    assert controls.dirty == {"user_work_mode"}


async def test_goal_survives_reset(hass, init_integration, connection, freezer):
    """Display retained intent while readback disagrees, then repair drift."""
    coordinator = init_integration.runtime_data.coordinator
    await run_controls(hass, init_integration, freezer, 5)
    await set_goal(hass, init_integration, "forcible_charge_power", 731)
    unit = connection.for_unit(1)
    unit.holding[42020] = 0
    await coordinator.async_refresh()
    state = hass.states.get("number.marstek_m1_forcible_charge_power")
    assert state.state == "731"
    assert state.attributes["observed_value"] == 0
    await run_controls(hass, init_integration, freezer, 10)
    assert unit.holding[42020] == 731
    await coordinator.async_refresh()
    assert (
        hass.states.get("number.marstek_m1_forcible_charge_power").attributes[
            "control_status"
        ]
        == "converged"
    )


async def test_heartbeat_and_order(hass, init_integration, connection, freezer):
    """Matching readback still receives a heartbeat, with direction last."""
    await run_controls(hass, init_integration, freezer, 5)
    coordinator = init_integration.runtime_data.coordinator
    await coordinator.async_refresh()
    unit = connection.for_unit(1)
    with patch.object(unit, "write_register", wraps=unit.write_register) as writes:
        await run_controls(hass, init_integration, freezer, 54)
        writes.assert_not_awaited()
        await run_controls(hass, init_integration, freezer, 1)
        assert [call.args[0] for call in writes.await_args_list] == [42000]
        await run_controls(hass, init_integration, freezer, 5)
        addresses = [call.args[0] for call in writes.await_args_list]
        assert addresses == [
            42000,
            44002,
            44003,
            41200,
            42020,
            42021,
            42010,
        ]
        assert 43000 not in addresses


async def test_disabled_branch(hass, init_integration, connection, freezer):
    """Disabled authority asserts work mode and queues all external goals."""
    await set_goal(hass, init_integration, "rs485_control_mode", 21947)
    await set_goal(hass, init_integration, "user_work_mode", 2)
    await set_goal(hass, init_integration, "forcible_discharge_power", 900)
    unit = connection.for_unit(1)
    with patch.object(unit, "write_register", wraps=unit.write_register) as writes:
        await run_controls(hass, init_integration, freezer, 5)
        assert [call.args[0] for call in writes.await_args_list] == [43000]
    assert unit.holding[42021] == 0
    assert unit.holding[43000] == 2
    assert (
        init_integration.runtime_data.coordinator.controls.status(
            "forcible_discharge_power"
        )
        == "deferred"
    )
    await set_goal(hass, init_integration, "rs485_control_mode", 21930)
    await run_controls(hass, init_integration, freezer, 5)
    assert unit.holding[42021] == 900


async def test_unreliable_readback(hass, init_integration, connection, freezer):
    """Even a lying RS485 readback cannot gate requested external writes."""
    await run_controls(hass, init_integration, freezer, 5)
    unit = connection.for_unit(1)
    original = unit.write_register

    async def write(address, value):
        if address != 42000:
            await original(address, value)

    with patch.object(unit, "write_register", side_effect=write):
        unit.holding[42000] = 21947
        await init_integration.runtime_data.coordinator.async_refresh()
        await run_controls(hass, init_integration, freezer, 10)
        await set_goal(hass, init_integration, "forcible_charge_power", 731)
        await run_controls(hass, init_integration, freezer, 5)
        assert unit.holding[42000] == 21947
        assert unit.holding[42020] == 731
        assert hass.states.get("select.marstek_m1_rs485_control_mode").state == "enable"


async def test_failure_backoff_and_offline_goals(
    hass, init_integration, connection, freezer
):
    """Transport failure retains service intent and uses bounded backoff."""
    await run_controls(hass, init_integration, freezer, 5)
    unit = connection.for_unit(1)
    coordinator = init_integration.runtime_data.coordinator
    with patch.object(
        unit, "write_register", side_effect=ModbusConnectionError("offline")
    ) as writes:
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": "number.marstek_m1_forcible_charge_power", "value": 731},
            blocking=True,
        )
        await run_controls(hass, init_integration, freezer)
        assert writes.await_count == 1
        assert coordinator.controls.goals["forcible_charge_power"] == 731
        await run_controls(hass, init_integration, freezer, 9)
        assert writes.await_count == 1
        await run_controls(hass, init_integration, freezer, 1)
        assert writes.await_count == 2
        await run_controls(hass, init_integration, freezer, 19)
        assert writes.await_count == 2
        await run_controls(hass, init_integration, freezer, 1)
        assert writes.await_count == 3
    with patch.object(
        unit, "read_holding_registers", side_effect=ModbusConnectionError("offline")
    ):
        await coordinator.async_refresh()
        freezer.tick(181)
        coordinator.async_update_listeners()
        assert hass.states.get("number.marstek_m1_forcible_charge_power").state == "731"
        assert hass.states.get("sensor.marstek_m1_battery_power").state == "unavailable"
        await set_goal(hass, init_integration, "forcible_charge_power", 800)
    await coordinator.async_refresh()
    await run_controls(hass, init_integration, freezer, 5)
    assert unit.holding[42020] == 800


async def test_reload_restores_intent(hass, init_integration, connection, freezer):
    """A new runtime uses durable goals rather than rebooted registers."""
    await set_goal(hass, init_integration, "forcible_charge_power", 731)
    await hass.config_entries.async_unload(init_integration.entry_id)
    connection.for_unit(1).holding[42020] = 0
    connection.for_unit(1).holding[42000] = 21947
    assert await hass.config_entries.async_setup(init_integration.entry_id)
    await hass.async_block_till_done()
    assert (
        init_integration.runtime_data.coordinator.controls.goals[
            "forcible_charge_power"
        ]
        == 731
    )
    assert (
        init_integration.runtime_data.coordinator.controls.goals["rs485_control_mode"]
        == 21930
    )
    await run_controls(hass, init_integration, freezer, 5)
    assert connection.for_unit(1).holding[42020] == 731


async def test_storage_failure_does_not_accept_goal(hass, init_integration):
    """A persistence error leaves the previous intent intact."""
    controls = init_integration.runtime_data.coordinator.controls
    with patch.object(controls._store, "async_save", side_effect=OSError):
        with pytest.raises(HomeAssistantError, match="persist"):
            await set_goal(hass, init_integration, "forcible_charge_power", 731)
    assert controls.goals["forcible_charge_power"] == 0


async def test_validation_without_transport(hass, init_integration, connection):
    """Invalid goals are rejected before saving or touching the device."""
    unit = connection.for_unit(1)
    with patch.object(unit, "write_register", new_callable=AsyncMock) as writes:
        with pytest.raises(ValueError):
            await set_goal(hass, init_integration, "forcible_charge_power", 2501)
        with pytest.raises(ValueError):
            await set_goal(hass, init_integration, "max_charge_power", -1)
        writes.assert_not_awaited()


async def test_latest_goal_wins_after_device_lock(
    hass, init_integration, connection, freezer
):
    """A queued old command must recheck its generation under the lock."""
    await run_controls(hass, init_integration, freezer, 5)
    coordinator = init_integration.runtime_data.coordinator
    unit = connection.for_unit(1)
    async with coordinator.device._lock:
        await set_goal(hass, init_integration, "forcible_charge_power", 500)
        task = coordinator.controls._task
        await set_goal(hass, init_integration, "forcible_charge_power", 731)
    await task
    assert unit.holding[42020] == 0
    await run_controls(hass, init_integration, freezer)
    assert unit.holding[42020] == 731


async def test_disable_during_settling(hass, init_integration, connection, freezer):
    """Disable preempts the remaining enable sequence."""
    unit = connection.for_unit(1)
    await set_goal(hass, init_integration, "forcible_charge_power", 731)
    await set_goal(hass, init_integration, "rs485_control_mode", 21947)
    await run_controls(hass, init_integration, freezer, 5)
    assert unit.holding[42000] == 21947
    assert unit.holding[42020] == 0


async def test_unload_cancels_blocked_write(
    hass, init_integration, connection, freezer
):
    """Entry shutdown must cancel a stalled control command."""
    await run_controls(hass, init_integration, freezer, 5)
    pending = asyncio.Event()

    async def blocked(*args):
        await pending.wait()

    with patch.object(connection.for_unit(1), "write_register", side_effect=blocked):
        await set_goal(hass, init_integration, "forcible_charge_power", 731)
        task = init_integration.runtime_data.coordinator.controls._task
        await hass.config_entries.async_unload(init_integration.entry_id)
        assert task.cancelled()


@pytest.mark.parametrize("model", list(Model))
async def test_managed_all_models(hass, config_entry, connection, freezer, model):
    """Every model uses the same goal contract and its physical limits."""
    seed(connection, model)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, data={**config_entry.data, "model": model.value}
    )
    with patch(
        "custom_components.marstek.async_get_unit",
        return_value=connection.for_unit(1),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        await set_goal(hass, config_entry, "forcible_discharge_power", model.max_power)
        await run_controls(hass, config_entry, freezer, 5)
        assert connection.for_unit(1).holding[42021] == model.max_power
        with pytest.raises(ValueError):
            await set_goal(
                hass, config_entry, "forcible_discharge_power", model.max_power + 1
            )
        await hass.config_entries.async_unload(config_entry.entry_id)


async def test_mode_switch_fresh_snapshot(hass, init_integration, connection, freezer):
    """Battery managed opt-out stops enforcement; returning adopts fresh values."""
    entry = init_integration
    await set_goal(hass, entry, "forcible_charge_power", 731)
    await hass.config_entries.async_unload(entry.entry_id)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_CONTROL_MANAGEMENT: "battery_managed"}
    )
    await hass.async_block_till_done()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert not entry.runtime_data.coordinator.controls.managed
    await entry.runtime_data.coordinator.write("forced", "forcible_charge_power", 800)
    assert connection.for_unit(1).holding[42020] == 800
    with patch.object(
        connection.for_unit(1), "write_register", new_callable=AsyncMock
    ) as writes:
        await run_controls(hass, entry, freezer, 65)
        writes.assert_not_awaited()
    await hass.config_entries.async_unload(entry.entry_id)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_CONTROL_MANAGEMENT: HA_MANAGED}
    )
    await hass.async_block_till_done()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.coordinator.controls.goals["forcible_charge_power"] == 800


async def test_incomplete_snapshot(hass, config_entry, connection, freezer):
    """Do not enforce incomplete or invalid startup observations."""
    unit = connection.for_unit(1)
    unit.holding[44002] = 65535
    config_entry.add_to_hass(hass)
    with patch("custom_components.marstek.async_get_unit", return_value=unit):
        with patch.object(unit, "write_register", new_callable=AsyncMock) as writes:
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
            coordinator = config_entry.runtime_data.coordinator
            assert not coordinator.controls.ready
            assert (
                hass.states.get("number.marstek_m1_max_charge_power").state == "unknown"
            )
            await run_controls(hass, config_entry, freezer, 60)
            writes.assert_not_awaited()
            await set_goal(hass, config_entry, "max_charge_power", 1500)
            assert coordinator.controls.ready
            assert coordinator.controls.goals["max_charge_power"] == 1500
        await run_controls(hass, config_entry, freezer, 5)
        assert unit.holding[44002] == 1500
        await hass.config_entries.async_unload(config_entry.entry_id)


async def test_explicit_goal_before_missing_snapshot_recovers(
    hass, config_entry, connection, freezer
):
    """A delayed component read cannot overwrite a newer user request."""
    unit = connection.for_unit(1)
    original = unit.read_holding_registers

    async def read(address, count):
        if address in (42010, 42020):
            raise ModbusConnectionError("forced unavailable")
        return await original(address, count)

    config_entry.add_to_hass(hass)
    with patch("custom_components.marstek.async_get_unit", return_value=unit):
        with patch.object(unit, "read_holding_registers", side_effect=read):
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
            coordinator = config_entry.runtime_data.coordinator
            assert not coordinator.controls.ready
            await set_goal(hass, config_entry, "forcible_charge_power", 731)
        await coordinator.async_refresh()
        assert coordinator.controls.ready
        assert coordinator.controls.goals["forcible_charge_power"] == 731
        await run_controls(hass, config_entry, freezer, 5)
        assert unit.holding[42020] == 731
        await hass.config_entries.async_unload(config_entry.entry_id)


async def test_acknowledged_but_ignored_write(
    hass, init_integration, connection, freezer
):
    """Successful transport cannot discard a goal the firmware ignored."""
    await run_controls(hass, init_integration, freezer, 5)
    coordinator = init_integration.runtime_data.coordinator
    with patch.object(
        connection.for_unit(1), "write_register", new_callable=AsyncMock
    ) as writes:
        await set_goal(hass, init_integration, "forcible_charge_power", 731)
        await coordinator.async_refresh()
        assert coordinator.controls.status("forcible_charge_power") == "pending"
        await run_controls(hass, init_integration, freezer, 10)
        assert writes.await_count == 2
        assert coordinator.controls.goals["forcible_charge_power"] == 731
    await run_controls(hass, init_integration, freezer, 10)
    assert connection.for_unit(1).holding[42020] == 731


async def test_new_runtime_restores_storage(hass, init_integration):
    """Persisted intent can initialize a runtime with no battery observations."""
    from custom_components.marstek.control import ManagedControls

    coordinator = init_integration.runtime_data.coordinator
    await set_goal(hass, init_integration, "forcible_charge_power", 731)
    restored = ManagedControls(coordinator)
    await restored.async_load()
    assert restored.ready
    assert restored.goals["forcible_charge_power"] == 731
    assert not restored._started


async def test_corrupt_goals_do_not_enable_writes(
    hass, config_entry, connection, hass_storage
):
    """Malformed durable goals must fail setup instead of taking new authority."""
    from homeassistant.config_entries import ConfigEntryState

    key = f"marstek.control.{config_entry.entry_id}"
    hass_storage[key] = {
        "version": 1,
        "minor_version": 1,
        "key": key,
        "data": {
            "mode": HA_MANAGED,
            "model": "e_v3",
            "goals": {"forcible_charge_power": 9000},
        },
    }
    config_entry.add_to_hass(hass)
    unit = connection.for_unit(1)
    with (
        patch("custom_components.marstek.async_get_unit", return_value=unit),
        patch.object(unit, "write_register", new_callable=AsyncMock) as writes,
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.SETUP_ERROR
        writes.assert_not_awaited()


async def test_backoff_survives_success_of_earlier_field(
    hass, init_integration, connection, freezer
):
    """Repeated transport errors keep backoff even if another field succeeds."""
    await run_controls(hass, init_integration, freezer, 5)
    unit = connection.for_unit(1)
    original = unit.write_register
    calls = 0

    async def write(address, value):
        nonlocal calls
        if address == 42020:
            calls += 1
            raise ModbusConnectionError("failed power command")
        await original(address, value)

    coordinator = init_integration.runtime_data.coordinator
    async with coordinator.device._lock:
        await set_goal(hass, init_integration, "max_charge_power", 900)
        await set_goal(hass, init_integration, "forcible_charge_power", 731)
    await coordinator.controls._task
    with patch.object(unit, "write_register", side_effect=write):
        await run_controls(hass, init_integration, freezer)
        assert calls == 1
        await run_controls(hass, init_integration, freezer, 10)
        assert calls == 2
        await run_controls(hass, init_integration, freezer, 10)
        assert calls == 2
        await run_controls(hass, init_integration, freezer, 10)
        assert calls == 3


@pytest.mark.parametrize("config_entry", ["e_v2"], indirect=True)
async def test_retired_soc_goal_is_discarded(hass, init_integration, freezer):
    """An upgrade must never replay a persisted SoC-target command."""
    from custom_components.marstek.control import ManagedControls

    coordinator = init_integration.runtime_data.coordinator
    goals = {**coordinator.controls.goals, "charge_to_soc": 100}
    goals.pop("charging_cutoff_capacity")
    goals.pop("discharging_cutoff_capacity")
    await coordinator.controls._save(goals)
    restored = ManagedControls(coordinator)
    await restored.async_load()
    assert "charge_to_soc" not in restored.goals
    assert "charge_to_soc" not in (await restored._store.async_load())["goals"]
    assert restored.ready
    await restored.observe({"cutoffs"})
    assert restored.ready
    assert restored.goals["charging_cutoff_capacity"] == 100
    assert hass.states.get("number.marstek_m1_charge_to_soc") is None


@pytest.mark.parametrize("config_entry", ["e_v2"], indirect=True)
async def test_fractional_cutoff_goal_survives_reload(
    hass, init_integration, connection, freezer
):
    """Fractional limits persist and repair drift without activating SoC mode."""
    from custom_components.marstek.control import ManagedControls

    await run_controls(hass, init_integration, freezer, 5)
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.marstek_m1_charging_cutoff_capacity", "value": 93.5},
        blocking=True,
    )
    unit = connection.for_unit(1)
    unit.holding[44000] = 800
    await init_integration.runtime_data.coordinator.async_refresh()
    with patch.object(unit, "write_register", wraps=unit.write_register) as writes:
        await run_controls(hass, init_integration, freezer, 10)
        assert 42011 not in [call.args[0] for call in writes.await_args_list]
    assert unit.holding[44000] == 935
    restored = ManagedControls(init_integration.runtime_data.coordinator)
    await restored.async_load()
    assert restored.goals["charging_cutoff_capacity"] == 93.5


@pytest.mark.parametrize("config_entry", ["e_v2"], indirect=True)
async def test_unsupported_cutoffs_do_not_block_controls(
    hass, config_entry, connection, freezer
):
    """Firmware rejecting the optional block must retain normal power control."""
    from modbus_connection import ModbusError

    unit = connection.for_unit(1)
    original = unit.read_holding_registers

    async def read(address, count):
        if address == 44000:
            raise ModbusError("illegal address")
        return await original(address, count)

    config_entry.add_to_hass(hass)
    with patch("custom_components.marstek.async_get_unit", return_value=unit):
        with patch.object(unit, "read_holding_registers", side_effect=read):
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
            controls = config_entry.runtime_data.coordinator.controls
            assert controls.ready
            assert "charging_cutoff_capacity" not in controls.goals
            assert (
                hass.states.get("number.marstek_m1_charging_cutoff_capacity").state
                == "unavailable"
            )
            with patch.object(
                unit, "write_register", wraps=unit.write_register
            ) as writes:
                await run_controls(hass, config_entry, freezer, 5)
                await set_goal(hass, config_entry, "forcible_charge_power", 731)
                await run_controls(hass, config_entry, freezer, 10)
                addresses = [call.args[0] for call in writes.await_args_list]
                assert not {42011, 44000, 44001}.intersection(addresses)
                assert unit.holding[42020] == 731
            await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.parametrize("config_entry", ["a", "d", "e_v3"], indirect=True)
async def test_cutoffs_omitted_on_unconfirmed_models(
    hass, init_integration, connection, freezer
):
    """Do not read, expose, or replay unsupported cutoff addresses."""
    controls = init_integration.runtime_data.coordinator.controls
    assert controls.ready
    assert "charging_cutoff_capacity" not in controls.specs
    assert hass.states.get("number.marstek_m1_charging_cutoff_capacity") is None
    unit = connection.for_unit(1)
    assert all(
        not {44000, 44001}.intersection(
            range(event.address, event.address + event.count)
        )
        for event in unit.read_events
    )
    with patch.object(unit, "write_register", wraps=unit.write_register) as writes:
        await run_controls(hass, init_integration, freezer, 5)
        assert not {42011, 44000, 44001}.intersection(
            call.args[0] for call in writes.await_args_list
        )


async def test_readback_and_sync_reflect_observations(
    hass, init_integration, connection
):
    """Readback and sync compare cached observations, not optimistic goals."""
    coordinator = init_integration.runtime_data.coordinator
    coordinator.controls.stop()
    unit = connection.for_unit(1)
    reads = len(unit.read_events)
    assert (
        hass.states.get("sensor.marstek_m1_rs485_control_mode_readback").state
        == "enable"
    )
    assert (
        hass.states.get("sensor.marstek_m1_max_charge_power_readback").state == "1500"
    )
    assert hass.states.get("binary_sensor.marstek_m1_controls_in_sync").state == "on"
    assert (
        hass.states.get("binary_sensor.marstek_m1_user_work_mode_in_sync").state
        == "unavailable"
    )
    assert len(unit.read_events) == reads
    await set_goal(hass, init_integration, "forcible_charge_power", 731)
    assert hass.states.get("number.marstek_m1_forcible_charge_power").state == "731"
    assert (
        hass.states.get("sensor.marstek_m1_forcible_charge_power_readback").state == "0"
    )
    assert (
        hass.states.get("binary_sensor.marstek_m1_forcible_charge_power_in_sync").state
        == "off"
    )
    assert hass.states.get("binary_sensor.marstek_m1_controls_in_sync").state == "off"
    assert len(unit.read_events) == reads
    unit.holding[42020] = 731
    await coordinator.async_refresh()
    assert (
        hass.states.get("sensor.marstek_m1_forcible_charge_power_readback").state
        == "731"
    )
    assert hass.states.get("binary_sensor.marstek_m1_controls_in_sync").state == "on"


async def test_stale_readback_makes_sync_unavailable(hass, init_integration, freezer):
    """Unavailable differs from an observed mismatch, without hiding retained goals."""
    from time import monotonic

    coordinator = init_integration.runtime_data.coordinator
    coordinator.controls.stop()
    coordinator.last_success["forced"] = monotonic() - coordinator.stale_timeout - 1
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert hass.states.get("number.marstek_m1_forcible_charge_power").state == "0"
    assert (
        hass.states.get("sensor.marstek_m1_forcible_charge_power_readback").state
        == "unavailable"
    )
    assert (
        hass.states.get("binary_sensor.marstek_m1_forcible_charge_power_in_sync").state
        == "unavailable"
    )
    assert (
        hass.states.get("binary_sensor.marstek_m1_controls_in_sync").state
        == "unavailable"
    )
    assert (
        hass.states.get("binary_sensor.marstek_m1_max_charge_power_in_sync").state
        == "on"
    )


async def test_sync_excludes_deferred_controls(hass, init_integration, connection):
    """Only the requested RS485 branch participates in the aggregate."""
    coordinator = init_integration.runtime_data.coordinator
    coordinator.controls.stop()
    await set_goal(hass, init_integration, "rs485_control_mode", 21947)
    await set_goal(hass, init_integration, "forcible_charge_power", 731)
    unit = connection.for_unit(1)
    unit.holding[42000] = 21947
    await coordinator.async_refresh()
    assert hass.states.get("binary_sensor.marstek_m1_controls_in_sync").state == "on"
    assert (
        hass.states.get("binary_sensor.marstek_m1_forcible_charge_power_in_sync").state
        == "unavailable"
    )
    assert (
        hass.states.get("binary_sensor.marstek_m1_user_work_mode_in_sync").state == "on"
    )
    assert (
        hass.states.get("sensor.marstek_m1_forcible_charge_power_readback").state == "0"
    )
    await set_goal(hass, init_integration, "user_work_mode", 1)
    assert hass.states.get("binary_sensor.marstek_m1_controls_in_sync").state == "off"


@pytest.mark.parametrize("config_entry", ["e_v2"], indirect=True)
async def test_optional_cutoff_freshness_counts_for_sync(hass, init_integration):
    """A retained cutoff with stale observations cannot silently disappear."""
    from time import monotonic

    coordinator = init_integration.runtime_data.coordinator
    coordinator.controls.stop()
    assert (
        hass.states.get("sensor.marstek_m1_charging_cutoff_capacity_readback").state
        == "100.0"
    )
    assert (
        hass.states.get(
            "binary_sensor.marstek_m1_charging_cutoff_capacity_in_sync"
        ).state
        == "on"
    )
    coordinator.last_success["cutoffs"] = monotonic() - coordinator.stale_timeout - 1
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert (
        hass.states.get("binary_sensor.marstek_m1_controls_in_sync").state
        == "unavailable"
    )
    assert (
        hass.states.get("sensor.marstek_m1_charging_cutoff_capacity_readback").state
        == "unavailable"
    )
    assert (
        hass.states.get(
            "binary_sensor.marstek_m1_charging_cutoff_capacity_in_sync"
        ).state
        == "unavailable"
    )
