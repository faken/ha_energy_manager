"""Number platform for Energy Manager."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEFAULT_FEED_IN_STATIC_POWER,
    DEFAULT_MAX_GRID_FEED_IN_POWER,
    DEFAULT_MIN_BATTERY_SOC,
    DEFAULT_GRID_POWER_TOLERANCE_DISCHARGE,
    DOMAIN,
    OPT_FEED_IN_STATIC_POWER,
    OPT_GRID_POWER_TOLERANCE_DISCHARGE,
    OPT_MAX_GRID_FEED_IN_POWER,
    OPT_MIN_BATTERY_SOC,
)
from .coordinator import EnergyManagerCoordinator


@dataclass
class NumberEntityDescription:
    """Description for a number entity."""

    key: str
    name: str
    option_key: str
    default: float
    native_min_value: float
    native_max_value: float
    native_step: float
    native_unit_of_measurement: str
    mode: NumberMode


NUMBER_DESCRIPTIONS: list[NumberEntityDescription] = [
    NumberEntityDescription(
        key="min_battery_soc",
        name="Min Battery SOC",
        option_key=OPT_MIN_BATTERY_SOC,
        default=DEFAULT_MIN_BATTERY_SOC,
        native_min_value=0,
        native_max_value=100,
        native_step=5,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
    ),
    NumberEntityDescription(
        key="max_feed_in_power",
        name="Max Feed-in Power",
        option_key=OPT_MAX_GRID_FEED_IN_POWER,
        default=DEFAULT_MAX_GRID_FEED_IN_POWER,
        native_min_value=0,
        native_max_value=800,
        native_step=50,
        native_unit_of_measurement=UnitOfPower.WATT,
        mode=NumberMode.SLIDER,
    ),
    NumberEntityDescription(
        key="grid_tolerance",
        name="Grid Import Tolerance",
        option_key=OPT_GRID_POWER_TOLERANCE_DISCHARGE,
        default=DEFAULT_GRID_POWER_TOLERANCE_DISCHARGE,
        native_min_value=0,
        native_max_value=200,
        native_step=10,
        native_unit_of_measurement=UnitOfPower.WATT,
        mode=NumberMode.SLIDER,
    ),
    NumberEntityDescription(
        key="static_feed_in_power",
        name="Static Feed-in Power",
        option_key=OPT_FEED_IN_STATIC_POWER,
        default=DEFAULT_FEED_IN_STATIC_POWER,
        native_min_value=0,
        native_max_value=800,
        native_step=50,
        native_unit_of_measurement=UnitOfPower.WATT,
        mode=NumberMode.SLIDER,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Energy Manager number entities."""
    coordinator: EnergyManagerCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            EnergyManagerNumber(coordinator, entry, desc)
            for desc in NUMBER_DESCRIPTIONS
        ]
    )


class EnergyManagerNumber(RestoreNumber):
    """Number entity for a configurable parameter."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EnergyManagerCoordinator,
        entry: ConfigEntry,
        description: NumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        self._coordinator = coordinator
        self._entry = entry
        self._description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = description.name
        self._attr_native_min_value = description.native_min_value
        self._attr_native_max_value = description.native_max_value
        self._attr_native_step = description.native_step
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_mode = description.mode
        self._attr_native_value = entry.options.get(
            description.option_key, description.default
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the value and push to coordinator options."""
        self._attr_native_value = value
        # Update the config entry options so the coordinator picks up the change
        new_options = {**self._entry.options, self._description.option_key: value}
        self.hass.config_entries.async_update_entry(self._entry, options=new_options)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore last value on startup."""
        await super().async_added_to_hass()
        last_data = await self.async_get_last_number_data()
        if last_data and last_data.native_value is not None:
            self._attr_native_value = last_data.native_value
            # Sync restored value back to options
            new_options = {
                **self._entry.options,
                self._description.option_key: last_data.native_value,
            }
            self.hass.config_entries.async_update_entry(
                self._entry, options=new_options
            )
