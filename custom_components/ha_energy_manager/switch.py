"""Switch platform for Energy Manager."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EnergyManagerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Energy Manager switch entities."""
    coordinator: EnergyManagerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([EnergyManagerEnabledSwitch(coordinator, entry)])


class EnergyManagerEnabledSwitch(
    CoordinatorEntity[EnergyManagerCoordinator], SwitchEntity, RestoreEntity
):
    """Switch to enable/disable the energy manager."""

    _attr_has_entity_name = True
    _attr_translation_key = "enabled"

    def __init__(
        self,
        coordinator: EnergyManagerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_enabled"

    @property
    def is_on(self) -> bool:
        """Return whether the manager is enabled."""
        return self.coordinator.is_enabled

    async def async_turn_on(self, **kwargs) -> None:
        """Enable the energy manager."""
        self.coordinator.is_enabled = True
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable the energy manager."""
        self.coordinator.is_enabled = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore last state on startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state:
            self.coordinator.is_enabled = last_state.state == "on"
