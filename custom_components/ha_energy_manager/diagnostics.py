"""Diagnostics support for Energy Manager."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import EnergyManagerCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: EnergyManagerCoordinator = hass.data[DOMAIN][entry.entry_id]

    data = coordinator.data

    return {
        "config": dict(entry.data),
        "options": dict(entry.options),
        "current_state": {
            "grid_power": data.grid_power if data else None,
            "solar_power": data.solar_power if data else None,
            "battery_soc": data.battery_soc if data else None,
            "fsm_state": data.fsm_state if data else None,
            "active_mode": data.active_mode if data else None,
            "feed_in_power": data.feed_in_power if data else None,
            "charge_power": data.charge_power if data else None,
            "is_enabled": data.is_enabled if data else None,
        },
        "decision_log": coordinator.log_entries,
    }
