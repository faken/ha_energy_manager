"""DataUpdateCoordinator for Energy Manager - core FSM logic."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from datetime import timedelta

from .const import (
    CONF_BATTERY_SOC_SENSOR,
    CONF_CHARGE_SWITCH,
    CONF_CUSTOM_LOAD_POWER_NUMBER,
    CONF_DISCHARGE_SWITCH,
    CONF_GRID_POWER_SENSOR,
    CONF_MAX_CHARGE_POWER_NUMBER,
    CONF_POWER_SUPPLY_MODE_SELECT,
    CONF_SOLAR_POWER_SENSOR,
    DEFAULT_CHARGE_POWER_STEP,
    DEFAULT_DEADBAND,
    DEFAULT_FEED_IN_MODE,
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
    MODE_AUTOMATIC,
    MODE_FORCED_CHARGE,
    MODE_HOLD,
    MODE_SOLAR,
    OPT_CHARGE_POWER_STEP,
    OPT_DEADBAND,
    OPT_FEED_IN_MODE,
    OPT_FEED_IN_STATIC_POWER,
    OPT_GRID_POWER_TOLERANCE_DISCHARGE,
    OPT_MAX_CHARGE_POWER,
    OPT_MAX_GRID_FEED_IN_POWER,
    OPT_MAX_GRID_IMPORT_SOLAR_CHARGE,
    OPT_MIN_BATTERY_SOC,
    OPT_MIN_CHARGE_POWER,
    OPT_MIN_DWELL_TIME,
    OPT_UPDATE_INTERVAL,
    PS_MODE_PRIORITIZE_STORAGE,
    PS_MODE_PRIORITIZE_SUPPLY,
    STATE_CHARGE,
    STATE_DISCHARGE,
    STATE_HOLD,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class EnergyManagerData:
    """Data from the coordinator."""

    grid_power: float = 0.0
    solar_power: float = 0.0
    battery_soc: float = 0.0
    fsm_state: str = STATE_HOLD
    active_mode: str = MODE_HOLD
    feed_in_power: float = 0.0
    charge_power: float = 0.0
    is_enabled: bool = True


class EnergyManagerCoordinator(DataUpdateCoordinator[EnergyManagerData]):
    """Coordinator for the Energy Manager integration."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self._config_entry = config_entry
        self._entity_ids = config_entry.data

        # Internal FSM state
        self._fsm_state: str = STATE_HOLD
        self._fsm_state_entered_at: float = time.monotonic()
        self._active_mode: str = MODE_HOLD
        self._is_enabled: bool = True

        # Track last-sent values to avoid redundant service calls
        self._last_charge_power: float | None = None
        self._last_feed_in_power: float | None = None
        self._last_charge_switch: bool | None = None
        self._last_discharge_switch: bool | None = None
        self._last_ps_mode: str | None = None

        # Current applied values
        self._current_charge_power: float = 0.0
        self._current_feed_in_power: float = 0.0

        interval = config_entry.options.get(OPT_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )

    def _get_option(self, key: str, default: Any) -> Any:
        """Get an option value, falling back to default."""
        return self._config_entry.options.get(key, default)

    @property
    def active_mode(self) -> str:
        """Return the current operating mode."""
        return self._active_mode

    @active_mode.setter
    def active_mode(self, mode: str) -> None:
        """Set the operating mode and reset FSM state."""
        self._active_mode = mode
        self._fsm_state = STATE_HOLD
        self._fsm_state_entered_at = time.monotonic()
        # Reset last-sent values to force re-application
        self._last_charge_power = None
        self._last_feed_in_power = None
        self._last_charge_switch = None
        self._last_discharge_switch = None
        self._last_ps_mode = None

    @property
    def is_enabled(self) -> bool:
        """Return whether the manager is enabled."""
        return self._is_enabled

    @is_enabled.setter
    def is_enabled(self, value: bool) -> None:
        """Set the enabled state."""
        self._is_enabled = value
        if not value:
            # Reset tracking when disabled
            self._last_charge_power = None
            self._last_feed_in_power = None
            self._last_charge_switch = None
            self._last_discharge_switch = None
            self._last_ps_mode = None

    def update_options(self) -> None:
        """Update coordinator settings from config entry options."""
        interval = self._get_option(OPT_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        self.update_interval = timedelta(seconds=interval)

    def _snap_to_step(self, value: float, step: float | None = None) -> int:
        """Round a value to the nearest valid step increment."""
        if step is None:
            step = self._get_option(OPT_CHARGE_POWER_STEP, DEFAULT_CHARGE_POWER_STEP)
        return int(round(value / step) * step)

    def _get_entity_state_float(self, entity_id: str, default: float = 0.0) -> float:
        """Get the float state of an entity."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return default
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return default

    def _get_entity_state_str(self, entity_id: str) -> str | None:
        """Get the string state of an entity."""
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        return state.state

    def _dwell_time_exceeded(self) -> bool:
        """Check if minimum dwell time in current state has been exceeded."""
        min_dwell = self._get_option(OPT_MIN_DWELL_TIME, DEFAULT_MIN_DWELL_TIME)
        return (time.monotonic() - self._fsm_state_entered_at) >= min_dwell

    def _set_fsm_state(self, new_state: str) -> None:
        """Transition to a new FSM state."""
        if new_state != self._fsm_state:
            _LOGGER.info(
                "FSM transition: %s -> %s", self._fsm_state, new_state
            )
            self._fsm_state = new_state
            self._fsm_state_entered_at = time.monotonic()
            # Reset last-sent values to force re-application of switch/mode states
            self._last_charge_switch = None
            self._last_discharge_switch = None
            self._last_ps_mode = None

    async def _async_set_charge_switch(self, on: bool) -> None:
        """Turn the charge switch on or off."""
        if self._last_charge_switch == on:
            return
        entity_id = self._entity_ids[CONF_CHARGE_SWITCH]
        service = "turn_on" if on else "turn_off"
        await self.hass.services.async_call(
            "switch", service, {"entity_id": entity_id}
        )
        self._last_charge_switch = on

    async def _async_set_discharge_switch(self, on: bool) -> None:
        """Turn the discharge switch on or off."""
        if self._last_discharge_switch == on:
            return
        entity_id = self._entity_ids[CONF_DISCHARGE_SWITCH]
        service = "turn_on" if on else "turn_off"
        await self.hass.services.async_call(
            "switch", service, {"entity_id": entity_id}
        )
        self._last_discharge_switch = on

    async def _async_set_power_supply_mode(self, mode: str) -> None:
        """Set the PowerStream power supply mode."""
        if self._last_ps_mode == mode:
            return
        entity_id = self._entity_ids[CONF_POWER_SUPPLY_MODE_SELECT]
        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": entity_id, "option": mode},
        )
        self._last_ps_mode = mode

    async def _async_set_charge_power(self, value: float) -> None:
        """Set the max AC charging power (snapped to step)."""
        min_power = self._get_option(OPT_MIN_CHARGE_POWER, DEFAULT_MIN_CHARGE_POWER)
        max_power = self._get_option(OPT_MAX_CHARGE_POWER, DEFAULT_MAX_CHARGE_POWER)
        snapped = self._snap_to_step(max(min(value, max_power), min_power))
        if self._last_charge_power == snapped:
            return
        entity_id = self._entity_ids[CONF_MAX_CHARGE_POWER_NUMBER]
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": entity_id, "value": snapped},
        )
        self._last_charge_power = snapped
        self._current_charge_power = snapped

    async def _async_set_feed_in_power(self, value: float) -> None:
        """Set the custom load (feed-in) power."""
        max_feed_in = self._get_option(
            OPT_MAX_GRID_FEED_IN_POWER, DEFAULT_MAX_GRID_FEED_IN_POWER
        )
        snapped = self._snap_to_step(max(min(value, max_feed_in), 0), step=50)
        if self._last_feed_in_power == snapped:
            return
        entity_id = self._entity_ids[CONF_CUSTOM_LOAD_POWER_NUMBER]
        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": entity_id, "value": snapped},
        )
        self._last_feed_in_power = snapped
        self._current_feed_in_power = snapped

    async def _async_update_data(self) -> EnergyManagerData:
        """Fetch data and run control logic."""
        # Read sensor values
        grid_power = self._get_entity_state_float(
            self._entity_ids[CONF_GRID_POWER_SENSOR]
        )
        solar_power = self._get_entity_state_float(
            self._entity_ids[CONF_SOLAR_POWER_SENSOR]
        )
        battery_soc = self._get_entity_state_float(
            self._entity_ids[CONF_BATTERY_SOC_SENSOR]
        )

        # Run control logic if enabled
        if self._is_enabled:
            if self._active_mode == MODE_FORCED_CHARGE:
                await self._run_forced_charge()
            elif self._active_mode == MODE_HOLD:
                await self._run_hold()
            elif self._active_mode == MODE_SOLAR:
                await self._run_solar(grid_power, solar_power)
            elif self._active_mode == MODE_AUTOMATIC:
                await self._run_automatic(grid_power, solar_power, battery_soc)

        return EnergyManagerData(
            grid_power=grid_power,
            solar_power=solar_power,
            battery_soc=battery_soc,
            fsm_state=self._fsm_state,
            active_mode=self._active_mode,
            feed_in_power=self._current_feed_in_power,
            charge_power=self._current_charge_power,
            is_enabled=self._is_enabled,
        )

    async def _run_forced_charge(self) -> None:
        """Execute forced charge mode logic."""
        max_power = self._get_option(OPT_MAX_CHARGE_POWER, DEFAULT_MAX_CHARGE_POWER)

        await self._async_set_charge_switch(True)
        await self._async_set_discharge_switch(False)
        await self._async_set_power_supply_mode(PS_MODE_PRIORITIZE_STORAGE)
        await self._async_set_feed_in_power(0)
        await self._async_set_charge_power(max_power)
        self._fsm_state = STATE_CHARGE

    async def _run_hold(self) -> None:
        """Execute hold mode logic."""
        min_power = self._get_option(OPT_MIN_CHARGE_POWER, DEFAULT_MIN_CHARGE_POWER)

        await self._async_set_charge_switch(False)
        await self._async_set_discharge_switch(False)
        await self._async_set_power_supply_mode(PS_MODE_PRIORITIZE_SUPPLY)
        await self._async_set_charge_power(min_power)
        await self._async_set_feed_in_power(0)
        self._fsm_state = STATE_HOLD

    async def _run_solar(self, grid_power: float, solar_power: float) -> None:
        """Execute solar charge mode logic."""
        min_power = self._get_option(OPT_MIN_CHARGE_POWER, DEFAULT_MIN_CHARGE_POWER)
        max_power = self._get_option(OPT_MAX_CHARGE_POWER, DEFAULT_MAX_CHARGE_POWER)
        deadband = self._get_option(OPT_DEADBAND, DEFAULT_DEADBAND)
        step = self._get_option(OPT_CHARGE_POWER_STEP, DEFAULT_CHARGE_POWER_STEP)

        # If no solar available, behave like hold
        if solar_power < min_power:
            await self._run_hold()
            return

        await self._async_set_charge_switch(True)
        await self._async_set_discharge_switch(False)
        await self._async_set_power_supply_mode(PS_MODE_PRIORITIZE_STORAGE)
        await self._async_set_feed_in_power(0)

        # Gradual adjustment: one step per cycle
        current = self._current_charge_power or min_power
        if grid_power > deadband:
            # We're pulling from grid — reduce charge power
            new_power = current - step
        elif grid_power < -deadband:
            # We're exporting to grid — can increase charge power
            new_power = current + step
        else:
            # Within deadband — stable
            new_power = current

        new_power = max(min(new_power, max_power), min_power)
        await self._async_set_charge_power(new_power)
        self._fsm_state = STATE_CHARGE

    async def _run_automatic(
        self, grid_power: float, solar_power: float, battery_soc: float
    ) -> None:
        """Execute automatic FSM mode logic."""
        min_soc = self._get_option(OPT_MIN_BATTERY_SOC, DEFAULT_MIN_BATTERY_SOC)
        min_power = self._get_option(OPT_MIN_CHARGE_POWER, DEFAULT_MIN_CHARGE_POWER)
        max_power = self._get_option(OPT_MAX_CHARGE_POWER, DEFAULT_MAX_CHARGE_POWER)
        deadband = self._get_option(OPT_DEADBAND, DEFAULT_DEADBAND)
        step = self._get_option(OPT_CHARGE_POWER_STEP, DEFAULT_CHARGE_POWER_STEP)
        feed_in_mode = self._get_option(OPT_FEED_IN_MODE, DEFAULT_FEED_IN_MODE)
        feed_in_static = self._get_option(
            OPT_FEED_IN_STATIC_POWER, DEFAULT_FEED_IN_STATIC_POWER
        )
        max_feed_in = self._get_option(
            OPT_MAX_GRID_FEED_IN_POWER, DEFAULT_MAX_GRID_FEED_IN_POWER
        )
        grid_tolerance = self._get_option(
            OPT_GRID_POWER_TOLERANCE_DISCHARGE, DEFAULT_GRID_POWER_TOLERANCE_DISCHARGE
        )

        has_solar_surplus = solar_power > min_power
        dwell_ok = self._dwell_time_exceeded()

        if self._fsm_state == STATE_CHARGE:
            await self._auto_charge(
                grid_power, solar_power, battery_soc, min_soc,
                min_power, max_power, deadband, step,
                max_feed_in, has_solar_surplus, dwell_ok,
            )
        elif self._fsm_state == STATE_HOLD:
            await self._auto_hold(
                grid_power, battery_soc, min_soc,
                has_solar_surplus, dwell_ok,
            )
        elif self._fsm_state == STATE_DISCHARGE:
            await self._auto_discharge(
                grid_power, battery_soc, min_soc,
                feed_in_mode, feed_in_static, max_feed_in,
                grid_tolerance, has_solar_surplus, dwell_ok,
            )

    async def _auto_charge(
        self,
        grid_power: float,
        solar_power: float,
        battery_soc: float,
        min_soc: float,
        min_power: float,
        max_power: float,
        deadband: float,
        step: float,
        max_feed_in: float,
        has_solar_surplus: bool,
        dwell_ok: bool,
    ) -> None:
        """Automatic mode: CHARGE state."""
        await self._async_set_charge_switch(True)
        await self._async_set_discharge_switch(False)
        await self._async_set_power_supply_mode(PS_MODE_PRIORITIZE_STORAGE)
        await self._async_set_feed_in_power(0)

        # Gradual charge power adjustment
        current = self._current_charge_power or min_power
        if grid_power > deadband:
            # Pulling too much from grid — reduce
            new_power = current - step
        elif grid_power < -deadband:
            # Solar surplus available — increase
            new_power = current + step
        else:
            new_power = current

        new_power = max(min(new_power, max_power), min_power)
        await self._async_set_charge_power(new_power)

        # State transitions
        if dwell_ok:
            # Transition to DISCHARGE if high grid consumption and battery has charge
            if battery_soc > min_soc and grid_power > max_feed_in:
                self._set_fsm_state(STATE_DISCHARGE)
                return

            # Transition to HOLD if no solar surplus
            if not has_solar_surplus:
                self._set_fsm_state(STATE_HOLD)

    async def _auto_hold(
        self,
        grid_power: float,
        battery_soc: float,
        min_soc: float,
        has_solar_surplus: bool,
        dwell_ok: bool,
    ) -> None:
        """Automatic mode: HOLD state."""
        min_power = self._get_option(OPT_MIN_CHARGE_POWER, DEFAULT_MIN_CHARGE_POWER)
        max_feed_in = self._get_option(
            OPT_MAX_GRID_FEED_IN_POWER, DEFAULT_MAX_GRID_FEED_IN_POWER
        )

        await self._async_set_charge_switch(False)
        await self._async_set_discharge_switch(False)
        await self._async_set_power_supply_mode(PS_MODE_PRIORITIZE_SUPPLY)
        await self._async_set_charge_power(min_power)
        await self._async_set_feed_in_power(0)

        # State transitions
        if dwell_ok:
            # Transition to CHARGE if solar surplus
            if has_solar_surplus:
                self._set_fsm_state(STATE_CHARGE)
                return

            # Transition to DISCHARGE if high grid consumption and battery has charge
            if battery_soc > min_soc and grid_power > max_feed_in:
                self._set_fsm_state(STATE_DISCHARGE)

    async def _auto_discharge(
        self,
        grid_power: float,
        battery_soc: float,
        min_soc: float,
        feed_in_mode: str,
        feed_in_static: float,
        max_feed_in: float,
        grid_tolerance: float,
        has_solar_surplus: bool,
        dwell_ok: bool,
    ) -> None:
        """Automatic mode: DISCHARGE state."""
        await self._async_set_charge_switch(False)
        await self._async_set_discharge_switch(True)
        await self._async_set_power_supply_mode(PS_MODE_PRIORITIZE_SUPPLY)

        # Calculate feed-in power
        if feed_in_mode == FEED_IN_DYNAMIC:
            # Dynamic: try to cover household consumption, leaving grid_tolerance
            target = grid_power - grid_tolerance
            feed_in = max(min(target, max_feed_in), 0)
        else:
            # Static: fixed feed-in value
            feed_in = min(feed_in_static, max_feed_in)

        await self._async_set_feed_in_power(feed_in)

        min_power = self._get_option(OPT_MIN_CHARGE_POWER, DEFAULT_MIN_CHARGE_POWER)
        await self._async_set_charge_power(min_power)

        # State transitions
        if battery_soc <= min_soc:
            self._set_fsm_state(STATE_HOLD)
            return

        if dwell_ok and has_solar_surplus:
            self._set_fsm_state(STATE_CHARGE)
