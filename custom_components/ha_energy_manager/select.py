"""Select platform for Energy Manager."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    EV_MODE_FORCED,
    EV_MODE_OFF,
    EV_MODE_SURPLUS,
    EV_MODES,
    MODE_AUTOMATIC,
    MODE_FORCED_CHARGE,
    MODE_HOLD,
    MODE_SOLAR,
    MODES,
    get_device_info,
)
from .coordinator import EnergyManagerCoordinator


MODE_LABELS = {
    MODE_FORCED_CHARGE: "Forced Charge",
    MODE_HOLD: "Hold",
    MODE_SOLAR: "Solar",
    MODE_AUTOMATIC: "Automatic",
}

LABEL_TO_MODE = {v: k for k, v in MODE_LABELS.items()}

EV_MODE_LABELS = {
    EV_MODE_OFF: "Off",
    EV_MODE_SURPLUS: "Surplus",
    EV_MODE_FORCED: "Forced",
}

EV_LABEL_TO_MODE = {v: k for k, v in EV_MODE_LABELS.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Energy Manager select entities."""
    coordinator: EnergyManagerCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        EnergyManagerModeSelect(coordinator, entry),
        EnergyManagerEVModeSelect(coordinator, entry),
    ])


class EnergyManagerModeSelect(
    CoordinatorEntity[EnergyManagerCoordinator], SelectEntity, RestoreEntity
):
    """Select entity for the operating mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "mode"
    _attr_options = [MODE_LABELS[m] for m in MODES]

    def __init__(
        self,
        coordinator: EnergyManagerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_mode"
        self._attr_device_info = get_device_info(entry.entry_id)

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return MODE_LABELS.get(self.coordinator.active_mode)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        mode = LABEL_TO_MODE.get(option)
        if mode is None:
            return
        self.coordinator.active_mode = mode
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """Restore last state on startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in LABEL_TO_MODE:
            self.coordinator.active_mode = LABEL_TO_MODE[last_state.state]


class EnergyManagerEVModeSelect(
    CoordinatorEntity[EnergyManagerCoordinator], SelectEntity, RestoreEntity
):
    """Select entity for the EV charging mode."""

    _attr_has_entity_name = True
    _attr_translation_key = "ev_mode"
    _attr_options = [EV_MODE_LABELS[m] for m in EV_MODES]

    def __init__(
        self,
        coordinator: EnergyManagerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_ev_mode"
        self._attr_device_info = get_device_info(entry.entry_id)

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return EV_MODE_LABELS.get(self.coordinator.ev_mode)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        mode = EV_LABEL_TO_MODE.get(option)
        if mode is None:
            return
        self.coordinator.ev_mode = mode
        await self.coordinator.async_request_refresh()

    async def async_added_to_hass(self) -> None:
        """Restore last state on startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state in EV_LABEL_TO_MODE:
            self.coordinator.ev_mode = EV_LABEL_TO_MODE[last_state.state]
