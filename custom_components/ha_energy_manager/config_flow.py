"""Config flow for Energy Manager integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_BATTERY_SOC_SENSOR,
    CONF_CHARGE_SWITCH,
    CONF_DISCHARGE_SWITCH,
    CONF_GRID_POWER_SENSOR,
    CONF_SOLAR_POWER_SENSOR,
    DEFAULT_CHARGE_POWER_STEP,
    DEFAULT_DEADBAND,
    DEFAULT_EV_CHARGER_PHASES,
    DEFAULT_EV_MAX_CHARGING_CURRENT,
    DEFAULT_EV_MIN_CHARGING_CURRENT,
    DEFAULT_EV_MIN_EXCESS_POWER,
    DEFAULT_FEED_IN_MODE,
    DEFAULT_FEED_IN_POWER_STEP,
    DEFAULT_FEED_IN_STATIC_POWER,
    DEFAULT_MAX_CHARGE_POWER,
    DEFAULT_MAX_GRID_FEED_IN_POWER,
    DEFAULT_MAX_GRID_IMPORT_SOLAR_CHARGE,
    DEFAULT_MIN_BATTERY_SOC,
    DEFAULT_MIN_CHARGE_POWER,
    DEFAULT_MIN_DWELL_TIME,
    DEFAULT_GRID_POWER_TOLERANCE_DISCHARGE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    FEED_IN_DYNAMIC,
    FEED_IN_STATIC,
    OPT_CHARGE_POWER_STEP,
    OPT_DEADBAND,
    OPT_EV_CHARGER_CURRENT_NUMBER,
    OPT_EV_CHARGER_PHASES,
    OPT_EV_CHARGER_SWITCH,
    OPT_EV_MAX_CHARGING_CURRENT,
    OPT_EV_MIN_CHARGING_CURRENT,
    OPT_EV_MIN_EXCESS_POWER,
    OPT_FEED_IN_MODE,
    OPT_FEED_IN_POWER_STEP,
    OPT_FEED_IN_STATIC_POWER,
    OPT_GRID_POWER_TOLERANCE_DISCHARGE,
    OPT_MAX_CHARGE_POWER,
    OPT_MAX_GRID_FEED_IN_POWER,
    OPT_MAX_GRID_IMPORT_SOLAR_CHARGE,
    OPT_MIN_BATTERY_SOC,
    OPT_MIN_CHARGE_POWER,
    OPT_MIN_DWELL_TIME,
    OPT_UPDATE_INTERVAL,
)

ENTITY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_GRID_POWER_SENSOR): EntitySelector(
            EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_SOLAR_POWER_SENSOR): EntitySelector(
            EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_BATTERY_SOC_SENSOR): EntitySelector(
            EntitySelectorConfig(domain="sensor")
        ),
        vol.Required(CONF_CHARGE_SWITCH): EntitySelector(
            EntitySelectorConfig(domain="switch")
        ),
        vol.Required(CONF_DISCHARGE_SWITCH): EntitySelector(
            EntitySelectorConfig(domain="switch")
        ),
        vol.Optional(OPT_EV_CHARGER_SWITCH): EntitySelector(
            EntitySelectorConfig(domain="switch")
        ),
        vol.Optional(OPT_EV_CHARGER_CURRENT_NUMBER): EntitySelector(
            EntitySelectorConfig(domain="number")
        ),
    }
)

# Keys that belong in options, not data (when submitted via setup flow)
_EV_ENTITY_KEYS = {OPT_EV_CHARGER_SWITCH, OPT_EV_CHARGER_CURRENT_NUMBER}


def _options_schema(options: dict[str, Any] | None = None) -> vol.Schema:
    """Build the options schema with current values as defaults."""
    if options is None:
        options = {}
    return vol.Schema(
        {
            vol.Required(
                OPT_FEED_IN_MODE,
                default=options.get(OPT_FEED_IN_MODE, DEFAULT_FEED_IN_MODE),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"label": "Dynamic", "value": FEED_IN_DYNAMIC},
                        {"label": "Static", "value": FEED_IN_STATIC},
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                OPT_FEED_IN_STATIC_POWER,
                default=options.get(
                    OPT_FEED_IN_STATIC_POWER, DEFAULT_FEED_IN_STATIC_POWER
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=800,
                    step=50,
                    unit_of_measurement="W",
                    mode=NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                OPT_MIN_BATTERY_SOC,
                default=options.get(OPT_MIN_BATTERY_SOC, DEFAULT_MIN_BATTERY_SOC),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=100,
                    step=5,
                    unit_of_measurement="%",
                    mode=NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                OPT_MAX_GRID_FEED_IN_POWER,
                default=options.get(
                    OPT_MAX_GRID_FEED_IN_POWER, DEFAULT_MAX_GRID_FEED_IN_POWER
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=800,
                    step=50,
                    unit_of_measurement="W",
                    mode=NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                OPT_GRID_POWER_TOLERANCE_DISCHARGE,
                default=options.get(
                    OPT_GRID_POWER_TOLERANCE_DISCHARGE,
                    DEFAULT_GRID_POWER_TOLERANCE_DISCHARGE,
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=1000,
                    step=10,
                    unit_of_measurement="W",
                    mode=NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                OPT_MAX_GRID_IMPORT_SOLAR_CHARGE,
                default=options.get(
                    OPT_MAX_GRID_IMPORT_SOLAR_CHARGE,
                    DEFAULT_MAX_GRID_IMPORT_SOLAR_CHARGE,
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=500,
                    step=10,
                    unit_of_measurement="W",
                    mode=NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                OPT_MAX_CHARGE_POWER,
                default=options.get(OPT_MAX_CHARGE_POWER, DEFAULT_MAX_CHARGE_POWER),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=100,
                    max=2400,
                    step=100,
                    unit_of_measurement="W",
                    mode=NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                OPT_MIN_CHARGE_POWER,
                default=options.get(OPT_MIN_CHARGE_POWER, DEFAULT_MIN_CHARGE_POWER),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=100,
                    max=1200,
                    step=100,
                    unit_of_measurement="W",
                    mode=NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                OPT_UPDATE_INTERVAL,
                default=options.get(OPT_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=120,
                    step=1,
                    unit_of_measurement="s",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                OPT_DEADBAND,
                default=options.get(OPT_DEADBAND, DEFAULT_DEADBAND),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=10,
                    max=200,
                    step=10,
                    unit_of_measurement="W",
                    mode=NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                OPT_CHARGE_POWER_STEP,
                default=options.get(
                    OPT_CHARGE_POWER_STEP, DEFAULT_CHARGE_POWER_STEP
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=50,
                    max=200,
                    step=50,
                    unit_of_measurement="W",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                OPT_FEED_IN_POWER_STEP,
                default=options.get(
                    OPT_FEED_IN_POWER_STEP, DEFAULT_FEED_IN_POWER_STEP
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=10,
                    max=200,
                    step=10,
                    unit_of_measurement="W",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                OPT_MIN_DWELL_TIME,
                default=options.get(OPT_MIN_DWELL_TIME, DEFAULT_MIN_DWELL_TIME),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    max=300,
                    step=10,
                    unit_of_measurement="s",
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


class EnergyManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Energy Manager."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the entity selection step."""
        if user_input is not None:
            # Extract optional EV entity IDs → store in options (not data)
            ev_options: dict[str, Any] = {}
            for key in _EV_ENTITY_KEYS:
                if key in user_input:
                    ev_options[key] = user_input.pop(key)

            return self.async_create_entry(
                title="Energy Manager",
                data=user_input,
                options={
                    OPT_FEED_IN_MODE: DEFAULT_FEED_IN_MODE,
                    OPT_FEED_IN_STATIC_POWER: DEFAULT_FEED_IN_STATIC_POWER,
                    OPT_MIN_BATTERY_SOC: DEFAULT_MIN_BATTERY_SOC,
                    OPT_MAX_GRID_FEED_IN_POWER: DEFAULT_MAX_GRID_FEED_IN_POWER,
                    OPT_GRID_POWER_TOLERANCE_DISCHARGE: DEFAULT_GRID_POWER_TOLERANCE_DISCHARGE,
                    OPT_MAX_GRID_IMPORT_SOLAR_CHARGE: DEFAULT_MAX_GRID_IMPORT_SOLAR_CHARGE,
                    OPT_MAX_CHARGE_POWER: DEFAULT_MAX_CHARGE_POWER,
                    OPT_MIN_CHARGE_POWER: DEFAULT_MIN_CHARGE_POWER,
                    OPT_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
                    OPT_DEADBAND: DEFAULT_DEADBAND,
                    OPT_CHARGE_POWER_STEP: DEFAULT_CHARGE_POWER_STEP,
                    OPT_FEED_IN_POWER_STEP: DEFAULT_FEED_IN_POWER_STEP,
                    OPT_MIN_DWELL_TIME: DEFAULT_MIN_DWELL_TIME,
                    **ev_options,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=ENTITY_SCHEMA,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow handler."""
        return EnergyManagerOptionsFlow(config_entry)


def _ev_options_schema(options: dict[str, Any] | None = None) -> vol.Schema:
    """Build the EV options schema with current values as defaults."""
    if options is None:
        options = {}
    return vol.Schema(
        {
            vol.Optional(
                OPT_EV_CHARGER_SWITCH,
                description={
                    "suggested_value": options.get(OPT_EV_CHARGER_SWITCH),
                },
            ): EntitySelector(
                EntitySelectorConfig(domain="switch")
            ),
            vol.Optional(
                OPT_EV_CHARGER_CURRENT_NUMBER,
                description={
                    "suggested_value": options.get(OPT_EV_CHARGER_CURRENT_NUMBER),
                },
            ): EntitySelector(
                EntitySelectorConfig(domain="number")
            ),
            vol.Required(
                OPT_EV_MIN_EXCESS_POWER,
                default=options.get(
                    OPT_EV_MIN_EXCESS_POWER, DEFAULT_EV_MIN_EXCESS_POWER
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=500,
                    max=5000,
                    step=100,
                    unit_of_measurement="W",
                    mode=NumberSelectorMode.SLIDER,
                )
            ),
            vol.Required(
                OPT_EV_MIN_CHARGING_CURRENT,
                default=options.get(
                    OPT_EV_MIN_CHARGING_CURRENT, DEFAULT_EV_MIN_CHARGING_CURRENT
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=6,
                    max=16,
                    step=1,
                    unit_of_measurement="A",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                OPT_EV_MAX_CHARGING_CURRENT,
                default=options.get(
                    OPT_EV_MAX_CHARGING_CURRENT, DEFAULT_EV_MAX_CHARGING_CURRENT
                ),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=6,
                    max=32,
                    step=1,
                    unit_of_measurement="A",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                OPT_EV_CHARGER_PHASES,
                default=options.get(
                    OPT_EV_CHARGER_PHASES, DEFAULT_EV_CHARGER_PHASES
                ),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        {"label": "1 Phase", "value": 1},
                        {"label": "3 Phases", "value": 3},
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


class EnergyManagerOptionsFlow(OptionsFlow):
    """Handle options flow for Energy Manager."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._battery_options: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the battery options step."""
        if user_input is not None:
            self._battery_options = user_input
            return await self.async_step_ev()

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self._config_entry.options),
        )

    async def async_step_ev(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the EV charging options step."""
        if user_input is not None:
            merged = {**self._battery_options, **user_input}
            return self.async_create_entry(title="", data=merged)

        return self.async_show_form(
            step_id="ev",
            data_schema=_ev_options_schema(self._config_entry.options),
        )
