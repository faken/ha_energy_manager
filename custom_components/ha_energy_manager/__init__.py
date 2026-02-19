"""The Energy Manager integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_CHARGE_SWITCH,
    CONF_CUSTOM_LOAD_POWER_NUMBER,
    CONF_DISCHARGE_SWITCH,
    CONF_MAX_CHARGE_POWER_NUMBER,
    CONF_POWER_SUPPLY_MODE_SELECT,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import EnergyManagerCoordinator
from .discovery import async_discover_control_entities

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Energy Manager from a config entry."""
    # Merge configured entities with auto-discovered control entities
    entity_ids = dict(entry.data)

    # Auto-discover control entities if not already in config data
    needs_discovery = (
        CONF_MAX_CHARGE_POWER_NUMBER not in entity_ids
        or CONF_CUSTOM_LOAD_POWER_NUMBER not in entity_ids
        or CONF_POWER_SUPPLY_MODE_SELECT not in entity_ids
    )

    if needs_discovery:
        discovered = await async_discover_control_entities(hass, entity_ids)
        entity_ids.update(discovered)

        # Verify all required entities are available
        missing = []
        if CONF_MAX_CHARGE_POWER_NUMBER not in entity_ids:
            missing.append("Max Charge Power (number with 'ac_charging_power' in name)")
        if CONF_CUSTOM_LOAD_POWER_NUMBER not in entity_ids:
            missing.append("Custom Load Power (number with 'custom_load_power' in name)")
        if CONF_POWER_SUPPLY_MODE_SELECT not in entity_ids:
            missing.append("Power Supply Mode (select with 'power_supply_mode' in name)")

        if missing:
            raise ConfigEntryNotReady(
                f"Could not auto-discover EcoFlow control entities: {', '.join(missing)}. "
                f"Make sure the EcoFlow integration is loaded and entities are available."
            )

    # Verify switch entities are configured
    missing_switches = []
    if CONF_CHARGE_SWITCH not in entity_ids:
        missing_switches.append("Charge Switch (Shelly relay for charger)")
    if CONF_DISCHARGE_SWITCH not in entity_ids:
        missing_switches.append("Discharge Switch (Shelly relay for PowerStream)")
    if missing_switches:
        raise ConfigEntryNotReady(
            f"Missing switch entities: {', '.join(missing_switches)}. "
            f"Please reconfigure the integration and select the Shelly switch entities."
        )

        _LOGGER.info(
            "Auto-discovered control entities: charge_power=%s, custom_load=%s, ps_mode=%s",
            entity_ids.get(CONF_MAX_CHARGE_POWER_NUMBER),
            entity_ids.get(CONF_CUSTOM_LOAD_POWER_NUMBER),
            entity_ids.get(CONF_POWER_SUPPLY_MODE_SELECT),
        )

    coordinator = EnergyManagerCoordinator(hass, entry, entity_ids)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    coordinator: EnergyManagerCoordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.update_options()
