# Energy Manager for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![GitHub Release](https://img.shields.io/github/v/release/faken/ha_energy_manager)](https://github.com/faken/ha_energy_manager/releases)

A Home Assistant custom integration for intelligent battery management of **EcoFlow PowerStream + Delta 2** systems. It automatically controls charging, discharging, and feed-in power based on solar production, grid consumption, and battery state.

## Features

- **4 Operating Modes**
  - **Forced Charge** — charge at maximum power regardless of solar
  - **Hold** — maintain current battery level, no charge or discharge
  - **Solar** — charge only from solar surplus, zero grid import
  - **Automatic** — FSM-based smart control with charge/hold/discharge states

- **Dynamic Feed-in** — adjusts discharge power to match household consumption in real-time
- **Gradual Power Ramping** — respects EcoFlow hardware constraints (100W charge steps, 50W feed-in steps)
- **Auto-Discovery** — automatically finds EcoFlow control entities (charge power, feed-in power, PowerStream mode)
- **Decision Logging** — ring buffer with 100 entries, HA logbook integration, and downloadable diagnostics
- **Configurable Parameters** — min SOC, deadband, dwell time, grid tolerance, and more via UI

## Requirements

- Home Assistant 2024.1 or newer
- EcoFlow integration installed and configured (PowerStream + Delta 2)
- HACS (for easy installation)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click **Integrations** → **⋮** (menu) → **Custom repositories**
3. Add `https://github.com/faken/ha_energy_manager` as **Integration**
4. Search for "Energy Manager" and install
5. Restart Home Assistant

### Manual

1. Download the latest release from [GitHub Releases](https://github.com/faken/ha_energy_manager/releases)
2. Copy `custom_components/ha_energy_manager/` to your `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

### Setup

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for "Energy Manager"
3. Select 5 entities from your EcoFlow system:

| Entity | Description | Example |
|--------|-------------|---------|
| **Grid Power** | Smart meter / grid import sensor (W) | `sensor.smart_meter_power` |
| **Solar Power** | Solar production sensor (W) | `sensor.powerstream_solar_power` |
| **Battery SOC** | Battery level (%) | `sensor.delta_2_max_battery_level` |
| **Charge Switch** | AC charging on/off | `switch.delta_2_max_ac_charging` |
| **Discharge Switch** | Discharge / feed-in on/off | `switch.powerstream_custom_load_enabled` |

The integration **automatically discovers** the remaining control entities:
- Max AC Charging Power (number)
- Custom Load Power / Feed-in (number)
- PowerStream Power Supply Mode (select)

### Options

After setup, configure via **Settings** → **Devices & Services** → **Energy Manager** → **Configure**:

| Option | Default | Description |
|--------|---------|-------------|
| Feed-in Mode | Dynamic | Dynamic (match consumption) or Static (fixed power) |
| Static Feed-in Power | 400 W | Fixed feed-in when using static mode |
| Min Battery SOC | 10% | Stop discharging at this level |
| Max Feed-in Power | 800 W | Maximum discharge into home grid |
| Grid Import Tolerance | 50 W | Acceptable grid import during discharge |
| Max Grid Import (Solar) | 0 W | Allowed grid import during solar charge (0 = pure solar) |
| Max Charge Power | 1200 W | Maximum charging speed |
| Min Charge Power | 200 W | Minimum charging speed (below = stop) |
| Update Interval | 20 s | Control loop cycle time |
| Deadband | 50 W | Power threshold before adjusting |
| Charge Power Step | 100 W | Step size per adjustment cycle |
| Min Dwell Time | 60 s | Minimum time in a state before transitioning |

## How It Works

### Automatic Mode (FSM)

The automatic mode uses a finite state machine with three states:

```
                 solar surplus
    ┌─────────── HOLD ───────────┐
    │              │              │
    │  no surplus  │  high grid   │
    │              │  consumption │
    │              ▼              │
    │           CHARGE            │
    │              │              │
    │  no surplus  │  high grid   │
    │              │  consumption │
    ▼              ▼              ▼
    HOLD ◄──── DISCHARGE ────► CHARGE
           low SOC       solar surplus
```

- **CHARGE**: Solar surplus detected → charge battery, gradually ramp power to avoid grid import
- **HOLD**: No surplus, no high consumption → do nothing
- **DISCHARGE**: High grid consumption → feed battery power into home, reduce grid import

### Power Control

- **Charge Power**: Ramped in configurable steps (default 100W) to avoid overshooting
- **Feed-in Power**: Dynamic mode calculates `grid_power - tolerance` and feeds in that amount
- **Switch Control**: Charge/discharge switches and PowerStream mode are automatically managed

## Entities

The integration creates these entities:

| Entity | Type | Description |
|--------|------|-------------|
| Status | Sensor | Current FSM state (charge/hold/discharge) |
| Grid Power | Sensor | Current grid import/export (W) |
| Solar Power | Sensor | Current solar production (W) |
| Battery SOC | Sensor | Battery state of charge (%) |
| Feed-in Power | Sensor | Current feed-in power (W) |
| Charge Power | Sensor | Current charge power (W) |
| Decision Log | Sensor | Last decision reason + full log in attributes |
| Operating Mode | Select | Forced Charge / Hold / Solar / Automatic |
| Enabled | Switch | Master on/off for the integration |
| Min Battery SOC | Number | Adjustable min SOC |
| Max Feed-in Power | Number | Adjustable max feed-in |
| Grid Import Tolerance | Number | Adjustable grid tolerance |
| Static Feed-in Power | Number | Adjustable static feed-in |

## Decision Log

The integration logs every decision (state transitions, power adjustments, mode changes) to:

1. **Decision Log sensor** — last reason as state, full history in attributes (`entries`)
2. **HA Logbook** — searchable via the logbook panel under "Energy Manager"
3. **Diagnostics** — downloadable JSON via **Settings** → **Devices & Services** → **Energy Manager** → **⋮** → **Download diagnostics**

## Troubleshooting

### Auto-discovery fails

If the integration cannot find the EcoFlow control entities, check the HA log for messages like:

```
Auto-discovery could not find: max_charge_power_number (patterns: ['ac_charging_power', 'charge_power'])
Available number entities: [...]
```

Make sure the EcoFlow integration is loaded and entities are available. The integration searches for:
- Number entities containing `ac_charging_power` or `charge_power`
- Number entities containing `custom_load_power`
- Select entities containing `power_supply_mode` or `supply_priority`

### Enable debug logging

Add to `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.ha_energy_manager: debug
```

## License

MIT
