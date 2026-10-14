"""Marstek select entities."""

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MarstekConfigEntry
from .descriptions import OPTIONS, Description, descriptions
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
        MarstekSelect(entry, spec)
        for spec in descriptions(device.model, device.pack_count)
        if spec.platform == "select"
    )


class MarstekSelect(MarstekEntity, SelectEntity):
    """Marstek select entity."""

    def __init__(self, entry: MarstekConfigEntry, spec: Description) -> None:
        """Initialize platform metadata."""
        super().__init__(entry, spec)
        self._attr_options = list(OPTIONS[spec.key])

    @property
    def current_option(self) -> str | None:
        """Map raw codes to the exact HBC option strings."""
        return next(
            (
                key
                for key, value in OPTIONS[self.spec.key].items()
                if value == self.value
            ),
            None,
        )

    async def async_select_option(self, option: str) -> None:
        """Write one requested mode."""
        await self.write(OPTIONS[self.spec.key][option])
