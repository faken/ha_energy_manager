"""Tests for the Energy Manager coordinator / FSM logic."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ha_energy_manager.const import (
    CONF_CUSTOM_LOAD_POWER_NUMBER,
    CONF_MAX_CHARGE_POWER_NUMBER,
    CONF_POWER_SUPPLY_MODE_SELECT,
    DEFAULT_LOG_BUFFER_SIZE,
    MODE_AUTOMATIC,
    MODE_FORCED_CHARGE,
    MODE_HOLD,
    MODE_SOLAR,
    PS_MODE_PRIORITIZE_STORAGE,
    PS_MODE_PRIORITIZE_SUPPLY,
    STATE_CHARGE,
    STATE_DISCHARGE,
    STATE_HOLD,
)
from tests.conftest import make_state


# ── Snap to step ─────────────────────────────────────────────────────


class TestSnapToStep:
    """Test the _snap_to_step helper."""

    def test_snap_100_step(self, coordinator):
        assert coordinator._snap_to_step(150) == 200
        assert coordinator._snap_to_step(149) == 100
        assert coordinator._snap_to_step(250) == 200
        assert coordinator._snap_to_step(251) == 300
        assert coordinator._snap_to_step(0) == 0

    def test_snap_50_step(self, coordinator):
        assert coordinator._snap_to_step(30, step=50) == 50
        assert coordinator._snap_to_step(24, step=50) == 0
        assert coordinator._snap_to_step(75, step=50) == 100
        assert coordinator._snap_to_step(276, step=50) == 300


# ── Charge power setter ─────────────────────────────────────────────


class TestSetChargePower:
    """Test _async_set_charge_power."""

    @pytest.mark.asyncio
    async def test_set_charge_power_positive(self, coordinator, mock_hass):
        """Setting positive charge power sets PS mode to storage and sends number.set_value."""
        await coordinator._async_set_charge_power(400, reason="test")
        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.ps_mode", "option": PS_MODE_PRIORITIZE_STORAGE},
        )
        mock_hass.services.async_call.assert_any_call(
            "number", "set_value", {"entity_id": "number.charge_power", "value": 400}
        )
        assert coordinator._last_charge_power == 400
        assert coordinator._current_charge_power == 400

    @pytest.mark.asyncio
    async def test_set_charge_power_zero_stops_charging(self, coordinator, mock_hass):
        """Setting charge power to 0 stops charging without sending number.set_value(0)."""
        await coordinator._async_set_charge_power(0, reason="test")
        # Verify no number.set_value call was made
        assert not any(
            call[0] == ("number", "set_value")
            for call in mock_hass.services.async_call.call_args_list
        )
        assert coordinator._last_charge_power == 0
        assert coordinator._current_charge_power == 0

    @pytest.mark.asyncio
    async def test_set_charge_power_negative_stops_charging(self, coordinator, mock_hass):
        """Negative value also stops charging."""
        await coordinator._async_set_charge_power(-100, reason="test")
        assert coordinator._last_charge_power == 0
        assert coordinator._current_charge_power == 0

    @pytest.mark.asyncio
    async def test_set_charge_power_snaps_to_step(self, coordinator, mock_hass):
        """Value is snapped to 100W step."""
        await coordinator._async_set_charge_power(350, reason="test")
        # 350 snaps to 400 (min 200, max 1200)
        mock_hass.services.async_call.assert_any_call(
            "number", "set_value", {"entity_id": "number.charge_power", "value": 400}
        )

    @pytest.mark.asyncio
    async def test_set_charge_power_clamps_to_min(self, coordinator, mock_hass):
        """Value below min_power is clamped to min_power."""
        await coordinator._async_set_charge_power(50, reason="test")
        # 50 is below min 200, clamped to 200
        mock_hass.services.async_call.assert_any_call(
            "number", "set_value", {"entity_id": "number.charge_power", "value": 200}
        )

    @pytest.mark.asyncio
    async def test_set_charge_power_clamps_to_max(self, coordinator, mock_hass):
        """Value above max_power is clamped to max_power."""
        await coordinator._async_set_charge_power(5000, reason="test")
        mock_hass.services.async_call.assert_any_call(
            "number", "set_value", {"entity_id": "number.charge_power", "value": 1200}
        )

    @pytest.mark.asyncio
    async def test_set_charge_power_skips_redundant(self, coordinator, mock_hass):
        """Skips service call if value unchanged."""
        await coordinator._async_set_charge_power(400, reason="first")
        mock_hass.services.async_call.reset_mock()

        await coordinator._async_set_charge_power(400, reason="second")
        # Only charge switch call, no number.set_value
        # Actually for positive values, charge switch is not called from _async_set_charge_power
        # It's only turned off when value <= 0
        # The skip happens because _last_charge_power == snapped
        assert not any(
            call[0] == ("number", "set_value")
            for call in mock_hass.services.async_call.call_args_list
        )


# ── Feed-in power setter ────────────────────────────────────────────


class TestSetFeedInPower:
    """Test _async_set_feed_in_power."""

    @pytest.mark.asyncio
    async def test_set_feed_in_positive_sets_supply_mode(self, coordinator, mock_hass):
        """Positive feed-in sets PS mode to supply and sends custom load power."""
        await coordinator._async_set_feed_in_power(300, reason="test")
        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.ps_mode", "option": PS_MODE_PRIORITIZE_SUPPLY},
        )
        mock_hass.services.async_call.assert_any_call(
            "number", "set_value", {"entity_id": "number.custom_load", "value": 300}
        )

    @pytest.mark.asyncio
    async def test_set_feed_in_zero_sets_custom_load_zero(self, coordinator, mock_hass):
        """Zero feed-in sets custom load power to 0."""
        # First set a positive value
        await coordinator._async_set_feed_in_power(300, reason="initial")
        mock_hass.services.async_call.reset_mock()

        await coordinator._async_set_feed_in_power(0, reason="stop")
        # Verify number.set_value(0) call was made to stop custom load
        mock_hass.services.async_call.assert_any_call(
            "number", "set_value", {"entity_id": "number.custom_load", "value": 0}
        )
        assert coordinator._last_feed_in_power == 0

    @pytest.mark.asyncio
    async def test_set_feed_in_snaps_to_50_step(self, coordinator, mock_hass):
        """Feed-in is snapped to 50W steps."""
        await coordinator._async_set_feed_in_power(276, reason="test")
        mock_hass.services.async_call.assert_any_call(
            "number", "set_value", {"entity_id": "number.custom_load", "value": 300}
        )

    @pytest.mark.asyncio
    async def test_set_feed_in_clamps_to_max(self, coordinator, mock_hass):
        """Feed-in clamped to max_grid_feed_in_power."""
        await coordinator._async_set_feed_in_power(2000, reason="test")
        # Default max is 800
        mock_hass.services.async_call.assert_any_call(
            "number", "set_value", {"entity_id": "number.custom_load", "value": 800}
        )


# ── Power supply mode ────────────────────────────────────────────────


class TestPowerSupplyMode:
    """Test PS mode setter."""

    @pytest.mark.asyncio
    async def test_ps_mode_skips_redundant(self, coordinator, mock_hass):
        """PS mode setter skips if already set."""
        await coordinator._async_set_power_supply_mode(PS_MODE_PRIORITIZE_SUPPLY)
        mock_hass.services.async_call.reset_mock()
        await coordinator._async_set_power_supply_mode(PS_MODE_PRIORITIZE_SUPPLY)
        mock_hass.services.async_call.assert_not_called()


# ── FSM state transitions ───────────────────────────────────────────


class TestFSMStateTransitions:
    """Test FSM state transition logic."""

    def test_set_fsm_state_resets_tracking(self, coordinator):
        """_set_fsm_state resets all last-sent values."""
        coordinator._last_charge_power = 400
        coordinator._last_feed_in_power = 200
        coordinator._last_ps_mode = PS_MODE_PRIORITIZE_SUPPLY

        coordinator._set_fsm_state(STATE_DISCHARGE, "test")

        assert coordinator._last_charge_power is None
        assert coordinator._last_feed_in_power is None
        assert coordinator._last_ps_mode is None

    def test_set_fsm_state_no_change(self, coordinator):
        """Same state transition is a no-op."""
        coordinator._fsm_state = STATE_HOLD
        old_time = coordinator._fsm_state_entered_at

        coordinator._set_fsm_state(STATE_HOLD, "same")
        assert coordinator._fsm_state_entered_at == old_time

    def test_mode_change_resets_to_hold(self, coordinator):
        """Changing mode resets FSM to HOLD."""
        coordinator._fsm_state = STATE_DISCHARGE
        coordinator.active_mode = MODE_AUTOMATIC
        assert coordinator._fsm_state == STATE_HOLD


# ── Forced charge mode ───────────────────────────────────────────────


class TestForcedChargeMode:
    """Test forced charge mode behavior."""

    @pytest.mark.asyncio
    async def test_forced_charge_sets_max_power(self, coordinator, mock_hass):
        """Forced charge sets charge power to max and PS mode to storage."""
        coordinator._active_mode = MODE_FORCED_CHARGE
        await coordinator._run_forced_charge()

        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.ps_mode", "option": PS_MODE_PRIORITIZE_STORAGE},
        )
        assert coordinator._fsm_state == STATE_CHARGE


# ── Hold mode ────────────────────────────────────────────────────────


class TestHoldMode:
    """Test hold mode behavior."""

    @pytest.mark.asyncio
    async def test_hold_disables_everything(self, coordinator, mock_hass):
        """Hold mode stops charging and feeding in, sets PS mode to supply."""
        await coordinator._run_hold()

        # PS mode set to supply to prevent unintended charging
        mock_hass.services.async_call.assert_any_call(
            "select",
            "select_option",
            {"entity_id": "select.ps_mode", "option": PS_MODE_PRIORITIZE_SUPPLY},
        )
        assert coordinator._fsm_state == STATE_HOLD
        assert coordinator._current_charge_power == 0
        assert coordinator._current_feed_in_power == 0


# ── Automatic mode transitions ───────────────────────────────────────


class TestAutomaticMode:
    """Test automatic mode FSM transitions."""

    @pytest.mark.asyncio
    async def test_hold_to_charge_on_solar_surplus(self, coordinator, mock_hass):
        """HOLD → CHARGE when solar surplus detected."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_HOLD
        coordinator._fsm_state_entered_at = time.monotonic() - 120  # dwell exceeded

        # grid export (negative = exporting) means surplus
        await coordinator._run_automatic(
            grid_power=-100, solar_power=800, battery_soc=50
        )
        assert coordinator._fsm_state == STATE_CHARGE

    @pytest.mark.asyncio
    async def test_hold_to_discharge_on_high_consumption(self, coordinator, mock_hass):
        """HOLD → DISCHARGE when grid consumption > max_feed_in and SOC > min."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_HOLD
        coordinator._fsm_state_entered_at = time.monotonic() - 120

        # Default max_feed_in is 800, min_soc is 10
        await coordinator._run_automatic(
            grid_power=1000, solar_power=0, battery_soc=50
        )
        assert coordinator._fsm_state == STATE_DISCHARGE

    @pytest.mark.asyncio
    async def test_hold_stays_hold_low_consumption(self, coordinator, mock_hass):
        """HOLD stays HOLD when no surplus and grid within tolerance (dynamic mode)."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_HOLD
        coordinator._fsm_state_entered_at = time.monotonic() - 120

        # grid=30 is within tolerance (50), so no discharge trigger
        await coordinator._run_automatic(
            grid_power=30, solar_power=0, battery_soc=50
        )
        assert coordinator._fsm_state == STATE_HOLD

    @pytest.mark.asyncio
    async def test_charge_to_hold_no_surplus_low_soc(self, coordinator, mock_hass):
        """CHARGE → HOLD when no solar surplus and SOC <= min (can't discharge)."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_CHARGE
        coordinator._fsm_state_entered_at = time.monotonic() - 120

        # High grid import, no solar, low SOC → can't discharge → HOLD
        await coordinator._run_automatic(
            grid_power=500, solar_power=0, battery_soc=10
        )
        assert coordinator._fsm_state == STATE_HOLD

    @pytest.mark.asyncio
    async def test_charge_to_discharge_dynamic_mode(self, coordinator, mock_hass):
        """CHARGE → DISCHARGE in dynamic mode when grid > tolerance and SOC > min."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_CHARGE
        coordinator._fsm_state_entered_at = time.monotonic() - 120

        # High grid import, no solar, sufficient SOC → DISCHARGE (dynamic mode)
        await coordinator._run_automatic(
            grid_power=500, solar_power=0, battery_soc=50
        )
        assert coordinator._fsm_state == STATE_DISCHARGE

    @pytest.mark.asyncio
    async def test_charge_to_discharge_high_consumption(self, coordinator, mock_hass):
        """CHARGE → DISCHARGE when high grid consumption and SOC > min."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_CHARGE
        coordinator._fsm_state_entered_at = time.monotonic() - 120

        await coordinator._run_automatic(
            grid_power=1000, solar_power=0, battery_soc=50
        )
        assert coordinator._fsm_state == STATE_DISCHARGE

    @pytest.mark.asyncio
    async def test_discharge_to_hold_low_soc(self, coordinator, mock_hass):
        """DISCHARGE → HOLD when battery SOC <= min."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_DISCHARGE
        coordinator._fsm_state_entered_at = time.monotonic() - 120

        # SOC at min (10%)
        await coordinator._run_automatic(
            grid_power=500, solar_power=0, battery_soc=10
        )
        assert coordinator._fsm_state == STATE_HOLD

    @pytest.mark.asyncio
    async def test_discharge_to_charge_solar_surplus(self, coordinator, mock_hass):
        """DISCHARGE → CHARGE when solar surplus detected."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_DISCHARGE
        coordinator._fsm_state_entered_at = time.monotonic() - 120
        # Set current solar power (normally set by _async_update_data)
        coordinator._current_solar_power = 1000

        await coordinator._run_automatic(
            grid_power=-200, solar_power=1000, battery_soc=50
        )
        assert coordinator._fsm_state == STATE_CHARGE

    @pytest.mark.asyncio
    async def test_dwell_time_prevents_transition(self, coordinator, mock_hass):
        """Transition is blocked if dwell time not exceeded."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_HOLD
        # Set entered_at to now → dwell NOT exceeded
        coordinator._fsm_state_entered_at = time.monotonic()

        await coordinator._run_automatic(
            grid_power=-100, solar_power=800, battery_soc=50
        )
        # Should stay in HOLD despite solar surplus
        assert coordinator._fsm_state == STATE_HOLD


# ── Dynamic feed-in calculation ──────────────────────────────────────


class TestDynamicFeedIn:
    """Test dynamic feed-in power calculation in discharge state.

    Dynamic feed-in uses GRADUAL adjustment (one 50W step per cycle)
    to prevent oscillation from delayed grid sensor readings.
    """

    @pytest.mark.asyncio
    async def test_dynamic_feed_in_ramps_up_one_step(self, coordinator, mock_hass):
        """Dynamic feed-in increases by one step when grid import > tolerance."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_DISCHARGE
        coordinator._fsm_state_entered_at = time.monotonic() - 120
        coordinator._current_feed_in_power = 0  # starting from 0

        # grid=500, tolerance=50 → grid > tolerance → ramp up by 50W
        await coordinator._run_automatic(
            grid_power=500, solar_power=0, battery_soc=50
        )
        assert coordinator._current_feed_in_power == 50  # 0 + 50

    @pytest.mark.asyncio
    async def test_dynamic_feed_in_ramps_up_from_existing(self, coordinator, mock_hass):
        """Dynamic feed-in increases from current value by one step."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_DISCHARGE
        coordinator._fsm_state_entered_at = time.monotonic() - 120
        coordinator._current_feed_in_power = 300
        coordinator._last_feed_in_power = 300

        # grid=500, tolerance=50 → ramp up 300 → 350
        await coordinator._run_automatic(
            grid_power=500, solar_power=0, battery_soc=50
        )
        assert coordinator._current_feed_in_power == 350  # 300 + 50

    @pytest.mark.asyncio
    async def test_dynamic_feed_in_clamped_to_max(self, coordinator, mock_hass):
        """Dynamic feed-in ramp-up is clamped to max_grid_feed_in_power."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_DISCHARGE
        coordinator._fsm_state_entered_at = time.monotonic() - 120
        coordinator._current_feed_in_power = 800  # already at max
        coordinator._last_feed_in_power = 800

        # grid=2000, tolerance=50 → wants to ramp up but already at max 800
        await coordinator._run_automatic(
            grid_power=2000, solar_power=0, battery_soc=50
        )
        assert coordinator._current_feed_in_power == 800

    @pytest.mark.asyncio
    async def test_dynamic_feed_in_ramps_down_on_export(self, coordinator, mock_hass):
        """Dynamic feed-in decreases by one step when grid export > tolerance."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_DISCHARGE
        coordinator._fsm_state_entered_at = time.monotonic() - 120
        coordinator._current_feed_in_power = 400
        coordinator._last_feed_in_power = 400

        # grid=-100 (exporting), tolerance=50 → ramp down 400 → 350
        await coordinator._run_automatic(
            grid_power=-100, solar_power=0, battery_soc=50
        )
        assert coordinator._current_feed_in_power == 350  # 400 - 50

    @pytest.mark.asyncio
    async def test_dynamic_feed_in_holds_within_tolerance(self, coordinator, mock_hass):
        """Dynamic feed-in holds steady when grid within tolerance band."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_DISCHARGE
        coordinator._fsm_state_entered_at = time.monotonic() - 120
        coordinator._current_feed_in_power = 300
        coordinator._last_feed_in_power = 300

        # grid=30, tolerance=50 → within band → hold at 300
        await coordinator._run_automatic(
            grid_power=30, solar_power=0, battery_soc=50
        )
        assert coordinator._current_feed_in_power == 300

    @pytest.mark.asyncio
    async def test_dynamic_feed_in_zero_when_already_zero_and_low_grid(self, coordinator, mock_hass):
        """Dynamic feed-in stays 0 when grid within tolerance and starting at 0."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_DISCHARGE
        coordinator._fsm_state_entered_at = time.monotonic() - 120
        coordinator._current_feed_in_power = 0

        # grid=30, tolerance=50 → within tolerance → hold at 0
        await coordinator._run_automatic(
            grid_power=30, solar_power=0, battery_soc=50
        )
        assert coordinator._current_feed_in_power == 0

    @pytest.mark.asyncio
    async def test_dynamic_feed_in_converges_over_cycles(self, coordinator, mock_hass):
        """Multiple cycles gradually approach target feed-in."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_DISCHARGE
        coordinator._fsm_state_entered_at = time.monotonic() - 120
        coordinator._current_feed_in_power = 0

        # Simulate 5 cycles with consistent high grid import
        for i in range(5):
            await coordinator._run_automatic(
                grid_power=500, solar_power=0, battery_soc=50
            )
        # After 5 cycles: 0 → 50 → 100 → 150 → 200 → 250
        assert coordinator._current_feed_in_power == 250


# ── Solar surplus detection ──────────────────────────────────────────


class TestSolarSurplus:
    """Test has_solar_surplus logic."""

    @pytest.mark.asyncio
    async def test_surplus_when_grid_export(self, coordinator, mock_hass):
        """Grid export (negative) means surplus."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_HOLD
        coordinator._fsm_state_entered_at = time.monotonic() - 120

        await coordinator._run_automatic(
            grid_power=-50, solar_power=300, battery_soc=50
        )
        assert coordinator._fsm_state == STATE_CHARGE

    @pytest.mark.asyncio
    async def test_no_surplus_high_grid_import(self, coordinator, mock_hass):
        """High grid import with some solar = no surplus."""
        coordinator._active_mode = MODE_AUTOMATIC
        coordinator._fsm_state = STATE_HOLD
        coordinator._fsm_state_entered_at = time.monotonic() - 120

        # grid_power=1100 > deadband=50, solar=753 > min_power=200
        # but grid_power(1100) >= deadband(50) so has_solar_surplus is False
        await coordinator._run_automatic(
            grid_power=1100, solar_power=753, battery_soc=50
        )
        # Should go to DISCHARGE (high consumption) not CHARGE
        assert coordinator._fsm_state == STATE_DISCHARGE


# ── Logging ──────────────────────────────────────────────────────────


class TestLogging:
    """Test decision logging."""

    def test_log_buffer_records_entries(self, coordinator):
        """Log entries are added to the ring buffer."""
        coordinator._log_decision("test_event", "test reason")
        assert len(coordinator.log_entries) == 1
        assert coordinator.log_entries[0]["event"] == "test_event"
        assert coordinator.log_entries[0]["reason"] == "test reason"

    def test_log_buffer_max_size(self, coordinator):
        """Log buffer respects max size."""
        for i in range(150):
            coordinator._log_decision("event", f"reason {i}")
        assert len(coordinator.log_entries) == DEFAULT_LOG_BUFFER_SIZE

    def test_mode_change_logs(self, coordinator):
        """Mode change creates a log entry."""
        coordinator.active_mode = MODE_AUTOMATIC
        entries = coordinator.log_entries
        assert any("Mode changed" in e["reason"] for e in entries)

    def test_enabled_change_logs(self, coordinator):
        """Enabling/disabling creates a log entry."""
        coordinator.is_enabled = False
        entries = coordinator.log_entries
        assert any("disabled" in e["reason"] for e in entries)


# ── Enabled/disabled ─────────────────────────────────────────────────


class TestEnabled:
    """Test enable/disable behavior."""

    @pytest.mark.asyncio
    async def test_disabled_skips_control(self, coordinator, mock_hass):
        """When disabled, no mode logic runs."""
        coordinator._is_enabled = False
        coordinator._active_mode = MODE_FORCED_CHARGE

        data = await coordinator._async_update_data()
        # No service calls should be made
        mock_hass.services.async_call.assert_not_called()

    def test_disable_resets_tracking(self, coordinator):
        """Disabling resets all last-sent values."""
        coordinator._last_charge_power = 400
        coordinator._last_ps_mode = PS_MODE_PRIORITIZE_SUPPLY

        coordinator.is_enabled = False

        assert coordinator._last_charge_power is None
        assert coordinator._last_ps_mode is None
