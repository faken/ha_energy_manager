"""Tests for the auto-discovery module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.ha_energy_manager.const import (
    CONF_BATTERY_SOC_SENSOR,
    CONF_CUSTOM_LOAD_POWER_NUMBER,
    CONF_GRID_POWER_SENSOR,
    CONF_MAX_CHARGE_POWER_NUMBER,
    CONF_POWER_SUPPLY_MODE_SELECT,
    CONF_SOLAR_POWER_SENSOR,
)
from custom_components.ha_energy_manager.discovery import (
    _match_entity,
    async_discover_control_entities,
)


# ── Pattern matching ─────────────────────────────────────────────────


class TestMatchEntity:
    """Test the _match_entity helper."""

    def test_matches_substring(self):
        assert _match_entity("number.delta_2_ac_charging_power", ["ac_charging_power"])

    def test_matches_case_insensitive(self):
        assert _match_entity("number.Delta_2_AC_Charging_Power", ["ac_charging_power"])

    def test_no_match(self):
        assert not _match_entity("number.delta_2_max_ac_timeout", ["ac_charging_power"])

    def test_matches_any_pattern(self):
        assert _match_entity(
            "number.delta_2_charge_power", ["ac_charging_power", "charge_power"]
        )

    def test_custom_load_pattern(self):
        assert _match_entity(
            "number.powerstream_custom_load_power", ["custom_load_power"]
        )

    def test_ps_mode_pattern(self):
        assert _match_entity(
            "select.powerstream_power_supply_mode", ["power_supply_mode"]
        )

    def test_ps_mode_timeout_no_match(self):
        """AC timeout should NOT match power supply mode patterns."""
        assert not _match_entity(
            "select.delta_2_max_ac_timeout",
            ["power_supply_mode", "supply_priority"],
        )


# ── Auto-discovery ───────────────────────────────────────────────────


def _make_registry_entry(entity_id: str, device_id: str, domain: str):
    """Create a mock entity registry entry."""
    entry = MagicMock()
    entry.entity_id = entity_id
    entry.device_id = device_id
    entry.domain = domain
    return entry


class TestAutoDiscovery:
    """Test async_discover_control_entities."""

    @pytest.mark.asyncio
    async def test_discovers_all_entities(self):
        """Finds all three control entities from device siblings."""
        hass = MagicMock()

        config_data = {
            CONF_GRID_POWER_SENSOR: "sensor.grid_power",
            CONF_SOLAR_POWER_SENSOR: "sensor.solar_power",
            CONF_BATTERY_SOC_SENSOR: "sensor.delta_2_battery_level",
        }

        # Registry entries
        entries = {
            "sensor.grid_power": _make_registry_entry(
                "sensor.grid_power", "device_meter", "sensor"
            ),
            "sensor.solar_power": _make_registry_entry(
                "sensor.solar_power", "device_ps", "sensor"
            ),
            "sensor.delta_2_battery_level": _make_registry_entry(
                "sensor.delta_2_battery_level", "device_delta", "sensor"
            ),
            # Control entities to discover
            "number.delta_2_max_ac_charging_power": _make_registry_entry(
                "number.delta_2_max_ac_charging_power", "device_delta", "number"
            ),
            "number.powerstream_custom_load_power": _make_registry_entry(
                "number.powerstream_custom_load_power", "device_ps", "number"
            ),
            "select.powerstream_power_supply_mode": _make_registry_entry(
                "select.powerstream_power_supply_mode", "device_ps", "select"
            ),
            # Unrelated entities (should not match)
            "select.delta_2_max_ac_timeout": _make_registry_entry(
                "select.delta_2_max_ac_timeout", "device_delta", "select"
            ),
            "number.delta_2_max_ac_timeout_value": _make_registry_entry(
                "number.delta_2_max_ac_timeout_value", "device_delta", "number"
            ),
        }

        registry = MagicMock()
        registry.async_get = MagicMock(side_effect=lambda eid: entries.get(eid))
        registry.entities = MagicMock()
        registry.entities.values = MagicMock(return_value=entries.values())

        with patch(
            "custom_components.ha_energy_manager.discovery.er.async_get",
            return_value=registry,
        ):
            discovered = await async_discover_control_entities(hass, config_data)

        assert discovered[CONF_MAX_CHARGE_POWER_NUMBER] == "number.delta_2_max_ac_charging_power"
        assert discovered[CONF_CUSTOM_LOAD_POWER_NUMBER] == "number.powerstream_custom_load_power"
        assert discovered[CONF_POWER_SUPPLY_MODE_SELECT] == "select.powerstream_power_supply_mode"

    @pytest.mark.asyncio
    async def test_missing_entities_returns_partial(self):
        """Returns partial results when some entities can't be found."""
        hass = MagicMock()

        config_data = {
            CONF_GRID_POWER_SENSOR: "sensor.grid_power",
            CONF_SOLAR_POWER_SENSOR: "sensor.solar_power",
            CONF_BATTERY_SOC_SENSOR: "sensor.battery_soc",
        }

        entries = {
            "sensor.grid_power": _make_registry_entry(
                "sensor.grid_power", "device_1", "sensor"
            ),
            "sensor.solar_power": _make_registry_entry(
                "sensor.solar_power", "device_1", "sensor"
            ),
            "sensor.battery_soc": _make_registry_entry(
                "sensor.battery_soc", "device_1", "sensor"
            ),
            # Only charge power available, no custom_load or ps_mode
            "number.delta_2_max_ac_charging_power": _make_registry_entry(
                "number.delta_2_max_ac_charging_power", "device_1", "number"
            ),
        }

        registry = MagicMock()
        registry.async_get = MagicMock(side_effect=lambda eid: entries.get(eid))
        registry.entities = MagicMock()
        registry.entities.values = MagicMock(return_value=entries.values())

        with patch(
            "custom_components.ha_energy_manager.discovery.er.async_get",
            return_value=registry,
        ):
            discovered = await async_discover_control_entities(hass, config_data)

        assert CONF_MAX_CHARGE_POWER_NUMBER in discovered
        assert CONF_CUSTOM_LOAD_POWER_NUMBER not in discovered
        assert CONF_POWER_SUPPLY_MODE_SELECT not in discovered

    @pytest.mark.asyncio
    async def test_no_device_ids_returns_empty(self):
        """Returns empty dict when configured entities have no device_id."""
        hass = MagicMock()

        config_data = {
            CONF_GRID_POWER_SENSOR: "sensor.grid_power",
            CONF_SOLAR_POWER_SENSOR: "sensor.solar_power",
            CONF_BATTERY_SOC_SENSOR: "sensor.battery_soc",
        }

        registry = MagicMock()
        # async_get returns None for all entities (not in registry)
        registry.async_get = MagicMock(return_value=None)
        registry.entities = MagicMock()
        registry.entities.values = MagicMock(return_value=[])

        with patch(
            "custom_components.ha_energy_manager.discovery.er.async_get",
            return_value=registry,
        ):
            discovered = await async_discover_control_entities(hass, config_data)

        assert discovered == {}
