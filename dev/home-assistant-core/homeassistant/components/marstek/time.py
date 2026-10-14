"""Marstek time entities."""

from datetime import time
from typing import Any

from homeassistant.components.time import TimeEntity
from homeassistant.core import HomeAssistant
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
        MarstekTime(entry, spec)
        for spec in descriptions(device.model, device.pack_count)
        if spec.platform == "time"
    )


class MarstekTime(MarstekEntity, TimeEntity):
    """Marstek time entity."""

    @property
    def native_value(self) -> Any:
        """Decode HHMM; invalid device times are unknown."""
        value = self.value
        if value is None or not 0 <= value <= 2359 or value % 100 > 59:
            return None
        return time(value // 100, value % 100)

    async def async_set_value(self, value: time) -> None:
        """Encode a clock time to HHMM."""
        await self.write(value.hour * 100 + value.minute)
