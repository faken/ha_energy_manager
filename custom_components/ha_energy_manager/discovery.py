"""Auto-discovery of EcoFlow control entities."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_BATTERY_SOC_SENSOR,
    CONF_CHARGE_SWITCH,
    CONF_CUSTOM_LOAD_POWER_NUMBER,
    CONF_DISCHARGE_SWITCH,
    CONF_MAX_CHARGE_POWER_NUMBER,
    CONF_POWER_SUPPLY_MODE_SELECT,
)

_LOGGER = logging.getLogger(__name__)

# Patterns to match entity IDs (substrings, case-insensitive)
_CHARGE_POWER_PATTERNS = ["ac_charging_power", "charge_power"]
_CUSTOM_LOAD_PATTERNS = ["custom_load_power"]
_PS_MODE_PATTERNS = ["power_supply_mode", "supply_priority"]


def _match_entity(entity_id: str, patterns: list[str]) -> bool:
    """Check if an entity_id matches any of the given patterns."""
    lower = entity_id.lower()
    return any(p in lower for p in patterns)


async def async_discover_control_entities(
    hass: HomeAssistant,
    config_data: dict[str, Any],
) -> dict[str, str]:
    """Discover EcoFlow control entities based on configured sensor/switch entities.

    Uses the device registry to find sibling entities on the same devices,
    then matches them by known EcoFlow naming patterns.

    Returns a dict with discovered entity IDs:
      - CONF_MAX_CHARGE_POWER_NUMBER
      - CONF_CUSTOM_LOAD_POWER_NUMBER
      - CONF_POWER_SUPPLY_MODE_SELECT

    Raises ConfigEntryNotReady if required entities cannot be found.
    """
    registry = er.async_get(hass)

    # Collect device IDs from the configured entities
    configured_entity_ids = [
        config_data[key]
        for key in (
            CONF_GRID_POWER_SENSOR,
            CONF_SOLAR_POWER_SENSOR,
            CONF_BATTERY_SOC_SENSOR,
            CONF_CHARGE_SWITCH,
            CONF_DISCHARGE_SWITCH,
        )
        if key in config_data
    ]

    device_ids: set[str] = set()
    for entity_id in configured_entity_ids:
        entry = registry.async_get(entity_id)
        if entry and entry.device_id:
            device_ids.add(entry.device_id)

    _LOGGER.debug(
        "Auto-discovery: found %d devices from configured entities: %s",
        len(device_ids),
        device_ids,
    )

    # Collect all entities belonging to those devices
    candidate_numbers: list[str] = []
    candidate_selects: list[str] = []

    for entry in registry.entities.values():
        if entry.device_id not in device_ids:
            continue
        if entry.domain == "number":
            candidate_numbers.append(entry.entity_id)
        elif entry.domain == "select":
            candidate_selects.append(entry.entity_id)

    _LOGGER.debug(
        "Auto-discovery candidates: %d numbers, %d selects",
        len(candidate_numbers),
        len(candidate_selects),
    )

    # Match patterns
    discovered: dict[str, str] = {}

    # Max charge power number
    for entity_id in candidate_numbers:
        if _match_entity(entity_id, _CHARGE_POWER_PATTERNS):
            discovered[CONF_MAX_CHARGE_POWER_NUMBER] = entity_id
            _LOGGER.info("Auto-discovered charge power: %s", entity_id)
            break

    # Custom load power number
    for entity_id in candidate_numbers:
        if _match_entity(entity_id, _CUSTOM_LOAD_PATTERNS):
            discovered[CONF_CUSTOM_LOAD_POWER_NUMBER] = entity_id
            _LOGGER.info("Auto-discovered custom load power: %s", entity_id)
            break

    # Power supply mode select
    for entity_id in candidate_selects:
        if _match_entity(entity_id, _PS_MODE_PATTERNS):
            discovered[CONF_POWER_SUPPLY_MODE_SELECT] = entity_id
            _LOGGER.info("Auto-discovered power supply mode: %s", entity_id)
            break

    # Log what was not found
    missing = []
    if CONF_MAX_CHARGE_POWER_NUMBER not in discovered:
        missing.append("max_charge_power_number (patterns: %s)" % _CHARGE_POWER_PATTERNS)
    if CONF_CUSTOM_LOAD_POWER_NUMBER not in discovered:
        missing.append("custom_load_power_number (patterns: %s)" % _CUSTOM_LOAD_PATTERNS)
    if CONF_POWER_SUPPLY_MODE_SELECT not in discovered:
        missing.append("power_supply_mode_select (patterns: %s)" % _PS_MODE_PATTERNS)

    if missing:
        _LOGGER.warning(
            "Auto-discovery could not find: %s. "
            "Available number entities: %s. Available select entities: %s",
            missing,
            candidate_numbers,
            candidate_selects,
        )

    return discovered
