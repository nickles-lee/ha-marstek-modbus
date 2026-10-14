"""Common fixtures for Marstek."""

from unittest.mock import patch

import pytest
from modbus_connection.mock import MockModbusConnection

from tests.common import MockConfigEntry

from . import DATA, MAC, seed


@pytest.fixture
def connection():
    """Verify connection."""
    connection = MockModbusConnection()
    seed(connection)
    return connection


@pytest.fixture
def config_entry():
    """Verify config entry."""
    return MockConfigEntry(
        domain="marstek", unique_id=MAC, data=DATA, title="Marstek m1"
    )


@pytest.fixture
async def init_integration(hass, config_entry, connection, freezer):
    """Verify init integration."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.marstek.async_get_unit",
        return_value=connection.for_unit(1),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        yield config_entry
        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
