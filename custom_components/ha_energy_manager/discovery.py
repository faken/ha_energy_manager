"""Auto-discovery of EcoFlow control entities."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_BATTERY_SOC_SENSOR,
    CONF_CUSTOM_LOAD_POWER_NUMBER,
    CONF_GRID_POWER_SENSOR,
    CONF_MAX_CHARGE_POWER_NUMBER,
    CONF_POWER_SUPPLY_MODE_SELECT,
    CONF_SOLAR_POWER_SENSOR,
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


def _find_matching(
    candidates: list[str],
    patterns: list[str],
) -> str | None:
    """Find the first entity matching any pattern."""
    for entity_id in candidates:
        if _match_entity(entity_id, patterns):
            return entity_id
    return None


async def async_discover_control_entities(
    hass: HomeAssistant,
    config_data: dict[str, Any],
) -> dict[str, str]:
    """Discover EcoFlow control entities.

    Strategy:
    1. Find devices from configured sensor entities
    2. Search sibling entities on those devices first
    3. If not all found, fall back to searching ALL entities in the system

    Returns a dict with discovered entity IDs.
    """
    registry = er.async_get(hass)

    # Collect device IDs from the configured entities
    configured_entity_ids = [
        config_data[key]
        for key in (
            CONF_GRID_POWER_SENSOR,
            CONF_SOLAR_POWER_SENSOR,
            CONF_BATTERY_SOC_SENSOR,
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

    # Collect candidates from device siblings
    device_numbers: list[str] = []
    device_selects: list[str] = []
    # Also collect ALL entities as fallback
    all_numbers: list[str] = []
    all_selects: list[str] = []

    for entry in registry.entities.values():
        if entry.domain == "number":
            all_numbers.append(entry.entity_id)
            if entry.device_id in device_ids:
                device_numbers.append(entry.entity_id)
        elif entry.domain == "select":
            all_selects.append(entry.entity_id)
            if entry.device_id in device_ids:
                device_selects.append(entry.entity_id)

    _LOGGER.debug(
        "Auto-discovery candidates: device(%d numbers, %d selects), "
        "all(%d numbers, %d selects)",
        len(device_numbers),
        len(device_selects),
        len(all_numbers),
        len(all_selects),
    )

    # Try device siblings first, then fall back to all entities
    discovered: dict[str, str] = {}

    # Max charge power number
    match = _find_matching(device_numbers, _CHARGE_POWER_PATTERNS)
    if not match:
        match = _find_matching(all_numbers, _CHARGE_POWER_PATTERNS)
        if match:
            _LOGGER.info("Auto-discovered charge power (global search): %s", match)
    else:
        _LOGGER.info("Auto-discovered charge power (device): %s", match)
    if match:
        discovered[CONF_MAX_CHARGE_POWER_NUMBER] = match

    # Custom load power number
    match = _find_matching(device_numbers, _CUSTOM_LOAD_PATTERNS)
    if not match:
        match = _find_matching(all_numbers, _CUSTOM_LOAD_PATTERNS)
        if match:
            _LOGGER.info("Auto-discovered custom load power (global search): %s", match)
    else:
        _LOGGER.info("Auto-discovered custom load power (device): %s", match)
    if match:
        discovered[CONF_CUSTOM_LOAD_POWER_NUMBER] = match

    # Power supply mode select
    match = _find_matching(device_selects, _PS_MODE_PATTERNS)
    if not match:
        match = _find_matching(all_selects, _PS_MODE_PATTERNS)
        if match:
            _LOGGER.info("Auto-discovered power supply mode (global search): %s", match)
    else:
        _LOGGER.info("Auto-discovered power supply mode (device): %s", match)
    if match:
        discovered[CONF_POWER_SUPPLY_MODE_SELECT] = match

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
            all_numbers,
            all_selects,
        )

    return discovered
