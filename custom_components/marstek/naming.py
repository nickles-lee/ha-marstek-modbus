"""Collision-safe HBC naming and explicit slot changes."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from .const import CONF_SLOT, DOMAIN
from .descriptions import Description


def collision(
    hass: HomeAssistant,
    data: dict[str, Any],
    specs: tuple[Description, ...],
    entry_id: str | None = None,
) -> str | None:
    """Check both registered and unregistered entity IDs and allocated slots."""
    slot = data[CONF_SLOT]
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id != entry_id and entry.data[CONF_SLOT] == slot:
            return f"marstek_m{slot}"
    registry = er.async_get(hass)
    for spec in specs:
        candidate = f"{spec.platform}.marstek_m{slot}_{spec.key}"
        registered = registry.async_get(candidate)
        if registered is not None:
            if (
                registered.config_entry_id != entry_id
                or registered.unique_id.split("_", 1)[-1] != spec.key
            ):
                return candidate
        elif hass.states.get(candidate) is not None:
            return candidate
    return None


def rename_slot(hass: HomeAssistant, entry_id: str, old: int, new: int) -> None:
    """Rename only default IDs; preserve explicit user customizations."""
    registry = er.async_get(hass)
    preserved = []
    for entity in er.async_entries_for_config_entry(registry, entry_id):
        suffix = entity.unique_id.split("_", 1)[1]
        expected = f"{entity.domain}.marstek_m{old}_{suffix}"
        if entity.entity_id != expected:
            preserved.append(entity.entity_id)
            continue
        registry.async_update_entity(
            entity.entity_id, new_entity_id=f"{entity.domain}.marstek_m{new}_{suffix}"
        )
    if preserved:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"manual_names_{entry_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="manual_names",
            translation_placeholders={"entities": ", ".join(preserved)},
        )
