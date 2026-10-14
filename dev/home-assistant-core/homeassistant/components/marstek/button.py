"""Marstek button entities."""

from modbus_connection import ModbusError

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MarstekConfigEntry
from .descriptions import descriptions
from .entity import MarstekEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MarstekConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add model-supported entities."""
    device = entry.runtime_data.coordinator.device
    async_add_entities(
        MarstekButton(entry, spec)
        for spec in descriptions(device.model, device.pack_count)
        if spec.platform == "button"
    )


class MarstekButton(MarstekEntity, ButtonEntity):
    """Marstek button entity."""

    async def async_press(self) -> None:
        """Send an explicit restart once; never retry a destructive command."""
        try:
            await self.coordinator.device.async_restart()
        except ModbusError as err:
            raise HomeAssistantError(str(err)) from err
