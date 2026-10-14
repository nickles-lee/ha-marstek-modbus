"""Marstek switch entities."""

from typing import Any

from modbus_connection import ModbusError

from homeassistant.components.switch import SwitchEntity
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
        MarstekSwitch(entry, spec)
        for spec in descriptions(device.model, device.pack_count)
        if spec.platform == "switch"
    )


class MarstekSwitch(MarstekEntity, SwitchEntity):
    """Marstek switch entity."""

    @property
    def is_on(self) -> bool | None:
        """Return schedule enable or the selected weekday bit."""
        value = self.value
        if value is None:
            return None
        return (
            bool(value & (1 << self.spec.day))
            if self.spec.day is not None
            else bool(value)
        )

    async def _set(self, enabled: bool) -> None:
        try:
            if self.spec.day is not None:
                await self.coordinator.device.async_set_weekday(
                    int(self.spec.component.split("_")[1]), self.spec.day, enabled
                )
            else:
                await self.write(int(enabled))
        except (ModbusError, ValueError) as err:
            raise HomeAssistantError(str(err)) from err

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable without changing other weekday bits."""
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable without changing other weekday bits."""
        await self._set(False)
