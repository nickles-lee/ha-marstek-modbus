"""Setup identity, duplicate and options validation."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from modbus_connection import ModbusTimeoutError

from custom_components.marstek.config_flow import probe
from homeassistant.data_entry_flow import FlowResultType

from . import DATA, MAC


@pytest.mark.parametrize("model", ["e_v2", "e_v3"])
async def test_user_flow(hass, model):
    """Verify user flow."""
    with (
        patch("custom_components.marstek.config_flow.probe", return_value=MAC),
        patch("custom_components.marstek.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            "marstek", context={"source": "user"}, data=dict(DATA, model=model)
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].unique_id == MAC


async def test_duplicate(hass, config_entry):
    """Verify duplicate."""
    config_entry.add_to_hass(hass)
    with patch("custom_components.marstek.config_flow.probe", return_value=MAC):
        result = await hass.config_entries.flow.async_init(
            "marstek", context={"source": "user"}, data=dict(DATA, battery_slot=2)
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_invalid_identity(hass):
    """Verify invalid identity."""
    with patch("custom_components.marstek.config_flow.probe", side_effect=ValueError()):
        result = await hass.config_entries.flow.async_init(
            "marstek", context={"source": "user"}, data=DATA
        )
        assert result["errors"] == {"base": "invalid_identity"}


async def test_timeout(hass):
    """Verify timeout."""
    with patch(
        "custom_components.marstek.config_flow.probe",
        side_effect=ModbusTimeoutError(),
    ):
        result = await hass.config_entries.flow.async_init(
            "marstek", context={"source": "user"}, data=DATA
        )
        assert result["errors"] == {"base": "cannot_connect"}


async def test_options(hass, config_entry):
    """Verify options."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    spacing = next(
        key for key in result["data_schema"].schema if key.schema == "message_spacing"
    )
    assert spacing.default() == 160
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"stale_timeout": 240, "message_spacing": 100}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options["stale_timeout"] == 240
    assert config_entry.options["message_spacing"] == 100
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    spacing = next(
        key for key in result["data_schema"].schema if key.schema == "message_spacing"
    )
    assert spacing.default() == 100


async def test_invalid_pack_count(hass):
    """Verify invalid pack count."""
    result = await hass.config_entries.flow.async_init(
        "marstek", context={"source": "user"}, data=dict(DATA, model="a", pack_count=7)
    )
    assert result["errors"] == {"pack_count": "invalid_pack_count"}


async def test_slot_collision(hass, config_entry):
    """Verify slot collision."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "marstek", context={"source": "user"}, data=DATA
    )
    assert result["errors"] == {"battery_slot": "slot_in_use"}


async def test_initial_form_skips_occupied_slot(hass, config_entry):
    """Verify initial form skips occupied slot."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "marstek", context={"source": "user"}
    )
    key = next(
        key for key in result["data_schema"].schema if key.schema == "battery_slot"
    )
    assert key.default() == 2


async def test_reconfigure_identity_mismatch(hass, config_entry):
    """Verify reconfigure identity mismatch."""
    config_entry.add_to_hass(hass)
    with patch(
        "custom_components.marstek.config_flow.probe",
        return_value="aa:bb:cc:dd:ee:01",
    ):
        result = await hass.config_entries.flow.async_init(
            "marstek",
            context={"source": "reconfigure", "entry_id": config_entry.entry_id},
            data=dict(DATA, battery_slot=2),
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


async def test_reconfigure_success(hass, config_entry):
    """Verify reconfigure success."""
    config_entry.add_to_hass(hass)
    with (
        patch("custom_components.marstek.config_flow.probe", return_value=MAC),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload", return_value=True
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            "marstek",
            context={"source": "reconfigure", "entry_id": config_entry.entry_id},
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=dict(DATA, battery_slot=2)
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data["battery_slot"] == 2


async def test_probe_retries_readonly(hass, connection):
    """Verify probe retries readonly."""
    unit = connection.for_unit(1)
    original = unit.read_holding_registers
    calls = 0

    async def flaky(address, count):
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ModbusTimeoutError
        return await original(address, count)

    unit.read_holding_registers = flaky
    unit.write_register = AsyncMock()

    @asynccontextmanager
    async def temporary(*args):
        yield unit

    with (
        patch(
            "custom_components.marstek.config_flow.async_get_temporary_unit",
            temporary,
        ),
        patch.object(unit, "set_message_spacing") as spacing,
    ):
        assert await probe(hass, DATA) == MAC
    spacing.assert_called_once_with(0.16)
    unit.write_register.assert_not_awaited()


async def test_probe_exhausts_retries(hass, connection):
    """Verify probe exhausts retries."""
    unit = connection.for_unit(1)
    unit.read_holding_registers = AsyncMock(side_effect=ModbusTimeoutError())

    @asynccontextmanager
    async def temporary(*args):
        yield unit

    with (
        patch(
            "custom_components.marstek.config_flow.async_get_temporary_unit",
            temporary,
        ),
        pytest.raises(ModbusTimeoutError),
    ):
        await probe(hass, DATA)
    assert unit.read_holding_registers.await_count == 3


async def test_e_v2_probe_uses_gateway_and_legacy_identity(hass, connection):
    """Pass the gateway endpoint and unit through; probe the battery MAC."""
    from custom_components.marstek._vendor.marstek_modbus import Model

    from . import seed

    unit = seed(connection, Model.E_V2)
    unit.write_register = AsyncMock()

    @asynccontextmanager
    async def temporary(hass_arg, params, unit_id):
        assert params.host == "192.0.2.42"
        assert params.port == 1502
        assert unit_id == 7
        yield unit

    with patch(
        "custom_components.marstek.config_flow.async_get_temporary_unit",
        temporary,
    ):
        assert (
            await probe(
                hass, dict(DATA, model="e_v2", host="192.0.2.42", port=1502, unit_id=7)
            )
            == MAC
        )
    assert {e.address for e in unit.read_events} == {30402, 31000}
    unit.write_register.assert_not_awaited()


@pytest.mark.parametrize("modbus_version", ["4.10.0", "4.12.1"])
async def test_timeout_option_matches_transport(hass, config_entry, modbus_version):
    """Only offer per-unit timeout settings on transports that implement them."""
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={"stale_timeout": 240, "message_spacing": 100, "request_timeout": 5},
    )
    with patch(
        "custom_components.marstek.config_flow.version",
        return_value=modbus_version,
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        keys = {key.schema for key in result["data_schema"].schema}
        assert ("request_timeout" in keys) == (modbus_version == "4.12.1")
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"stale_timeout": 240, "message_spacing": 100},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "request_timeout" not in config_entry.options


async def test_form_controls(hass):
    """Serialize explicit controls and live model-dependent visibility."""
    from probatio import to_field_list

    from homeassistant.helpers import config_validation as cv

    result = await hass.config_entries.flow.async_init(
        "marstek", context={"source": "user"}
    )
    fields = {
        f["name"]: f
        for f in to_field_list(
            result["data_schema"], custom_serializer=cv.custom_serializer
        )
    }
    assert fields["unit_id"]["default"] == 1
    assert fields["unit_id"]["selector"]["number"]["mode"] == "box"
    packs = fields["pack_count"]
    assert packs["visible"] == {"field": "model", "operator": "in", "value": ["a", "d"]}
    assert packs["selector"]["number"] == {
        "min": 1,
        "max": 6,
        "step": 1,
        "mode": "slider",
    }
    assert [o["label"] for o in fields["model"]["selector"]["select"]["options"]] == [
        "Venus A",
        "Venus D",
        "Venus E 2.0",
        "Venus E 3.0",
    ]


@pytest.mark.parametrize("model", ["e_v2", "e_v3"])
@pytest.mark.parametrize("packs", [None, 5])
async def test_hidden_pack_count_is_one(hass, model, packs):
    """E models ignore omitted or stale hidden A/D pack counts."""
    data = dict(DATA, model=model)
    data.pop("pack_count")
    if packs is not None:
        data["pack_count"] = packs
    with (
        patch("custom_components.marstek.config_flow.probe", return_value=MAC),
        patch("custom_components.marstek.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            "marstek", context={"source": "user"}, data=data
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["pack_count"] == 1


@pytest.mark.parametrize("management", ["ha_managed", "battery_managed"])
async def test_control_management_selector(hass, management):
    """Show authority beside model, default to HA, and retain either choice."""
    with (
        patch("custom_components.marstek.config_flow.probe", return_value=MAC),
        patch("custom_components.marstek.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            "marstek", context={"source": "user"}
        )
        fields = list(result["data_schema"].schema)
        model_index = next(i for i, key in enumerate(fields) if key.schema == "model")
        control = fields[model_index + 1]
        assert control.schema == "control_management"
        assert control.default() == "ha_managed"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={**DATA, "control_management": management}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["result"].data["control_management"] == management


async def test_new_entry_defaults_to_ha_managed(hass):
    """Missing selector data from older clients still gets the new default."""
    with (
        patch("custom_components.marstek.config_flow.probe", return_value=MAC),
        patch("custom_components.marstek.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            "marstek",
            context={"source": "user"},
            data={
                key: value for key, value in DATA.items() if key != "control_management"
            },
        )
        assert result["result"].data["control_management"] == "ha_managed"


async def test_reconfigure_preserves_management_if_omitted(hass, config_entry):
    """Older reconfigure clients must not silently switch ownership."""
    config_entry.add_to_hass(hass)
    with (
        patch("custom_components.marstek.config_flow.probe", return_value=MAC),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload", return_value=True
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            "marstek",
            context={"source": "reconfigure", "entry_id": config_entry.entry_id},
            data={
                key: value for key, value in DATA.items() if key != "control_management"
            },
        )
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data["control_management"] == "battery_managed"
