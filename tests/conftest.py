"""Shared fixtures for Energy Manager tests."""

from __future__ import annotations

import time
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_energy_manager.const import (
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
    DEFAULT_LOG_BUFFER_SIZE,
    DEFAULT_MAX_CHARGE_POWER,
    DEFAULT_MAX_GRID_FEED_IN_POWER,
    DEFAULT_MIN_BATTERY_SOC,
    DEFAULT_MIN_CHARGE_POWER,
    DEFAULT_MIN_DWELL_TIME,
    DEFAULT_GRID_POWER_TOLERANCE_DISCHARGE,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MODE_HOLD,
    STATE_HOLD,
)



MOCK_ENTITY_IDS = {
    CONF_GRID_POWER_SENSOR: "sensor.grid_power",
    CONF_SOLAR_POWER_SENSOR: "sensor.solar_power",
    CONF_BATTERY_SOC_SENSOR: "sensor.battery_soc",
    CONF_POWER_SUPPLY_MODE_SELECT: "select.ps_mode",
    CONF_MAX_CHARGE_POWER_NUMBER: "number.charge_power",
    CONF_CUSTOM_LOAD_POWER_NUMBER: "number.custom_load",
    CONF_CHARGE_SWITCH: "switch.charge",
    CONF_DISCHARGE_SWITCH: "switch.discharge",
}

DEFAULT_OPTIONS = {
    "feed_in_mode": DEFAULT_FEED_IN_MODE,
    "feed_in_static_power": DEFAULT_FEED_IN_STATIC_POWER,
    "min_battery_soc": DEFAULT_MIN_BATTERY_SOC,
    "max_grid_feed_in_power": DEFAULT_MAX_GRID_FEED_IN_POWER,
    "grid_power_tolerance_discharge": DEFAULT_GRID_POWER_TOLERANCE_DISCHARGE,
    "max_grid_import_solar_charge": 0,
    "max_charge_power": DEFAULT_MAX_CHARGE_POWER,
    "min_charge_power": DEFAULT_MIN_CHARGE_POWER,
    "update_interval": DEFAULT_UPDATE_INTERVAL,
    "deadband": DEFAULT_DEADBAND,
    "charge_power_step": DEFAULT_CHARGE_POWER_STEP,
    "min_dwell_time": DEFAULT_MIN_DWELL_TIME,
}


def make_state(value):
    """Create a mock HA state object."""
    state = MagicMock()
    state.state = str(value)
    return state


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.async_create_task = MagicMock()

    # Default sensor states
    sensor_states = {
        "sensor.grid_power": make_state(100),
        "sensor.solar_power": make_state(500),
        "sensor.battery_soc": make_state(50),
    }
    hass.states.get = MagicMock(side_effect=lambda eid: sensor_states.get(eid))

    # Store reference so tests can modify states
    hass._sensor_states = sensor_states

    return hass


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = dict(MOCK_ENTITY_IDS)
    entry.options = dict(DEFAULT_OPTIONS)
    return entry


@pytest.fixture
def coordinator(mock_hass, mock_config_entry):
    """Create a coordinator with mocked dependencies."""
    from custom_components.ha_energy_manager.coordinator import (
        EnergyManagerCoordinator,
    )

    # Patch DataUpdateCoordinator.__init__ to avoid HA event loop requirements
    with patch(
        "homeassistant.helpers.update_coordinator.DataUpdateCoordinator.__init__",
        lambda self, *args, **kwargs: None,
    ):
        coord = EnergyManagerCoordinator(
            mock_hass, mock_config_entry, entity_ids=dict(MOCK_ENTITY_IDS)
        )
    # Set attributes that DataUpdateCoordinator.__init__ would normally set
    coord.hass = mock_hass
    coord.logger = MagicMock()
    coord.name = DOMAIN
    coord.update_interval = None

    # Bypass dwell time for tests by default
    coord._fsm_state_entered_at = time.monotonic() - 120
    return coord
