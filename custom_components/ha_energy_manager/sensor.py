"""Sensor platform for Energy Manager."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EnergyManagerCoordinator, EnergyManagerData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Energy Manager sensors."""
    coordinator: EnergyManagerCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            EnergyManagerStatusSensor(coordinator, entry),
            EnergyManagerPowerSensor(
                coordinator, entry,
                key="grid_power",
                name="Grid Power",
                unique_suffix="grid_power",
            ),
            EnergyManagerPowerSensor(
                coordinator, entry,
                key="solar_power",
                name="Solar Power",
                unique_suffix="solar_power",
            ),
            EnergyManagerSocSensor(coordinator, entry),
            EnergyManagerPowerSensor(
                coordinator, entry,
                key="feed_in_power",
                name="Feed-in Power",
                unique_suffix="feed_in_power",
            ),
            EnergyManagerPowerSensor(
                coordinator, entry,
                key="charge_power",
                name="Charge Power",
                unique_suffix="charge_power",
            ),
        ]
    )


class EnergyManagerStatusSensor(
    CoordinatorEntity[EnergyManagerCoordinator], SensorEntity
):
    """Sensor showing the current FSM state."""

    _attr_has_entity_name = True
    _attr_translation_key = "status"

    def __init__(
        self,
        coordinator: EnergyManagerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str | None:
        """Return the current status."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.fsm_state


class EnergyManagerPowerSensor(
    CoordinatorEntity[EnergyManagerCoordinator], SensorEntity
):
    """Sensor showing a power value."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(
        self,
        coordinator: EnergyManagerCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        unique_suffix: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self.coordinator.data is None:
            return None
        return getattr(self.coordinator.data, self._key, None)


class EnergyManagerSocSensor(
    CoordinatorEntity[EnergyManagerCoordinator], SensorEntity
):
    """Sensor showing the battery state of charge."""

    _attr_has_entity_name = True
    _attr_translation_key = "battery_soc"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        coordinator: EnergyManagerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_battery_soc"

    @property
    def native_value(self) -> float | None:
        """Return the current SOC."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.battery_soc
