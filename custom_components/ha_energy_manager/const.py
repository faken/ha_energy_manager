"""Constants for the Energy Manager integration."""

DOMAIN = "ha_energy_manager"

# Config keys - entity IDs selected during setup
CONF_GRID_POWER_SENSOR = "grid_power_sensor"
CONF_SOLAR_POWER_SENSOR = "solar_power_sensor"
CONF_BATTERY_SOC_SENSOR = "battery_soc_sensor"
CONF_POWER_SUPPLY_MODE_SELECT = "power_supply_mode_select"
CONF_MAX_CHARGE_POWER_NUMBER = "max_charge_power_number"
CONF_CUSTOM_LOAD_POWER_NUMBER = "custom_load_power_number"
CONF_CHARGE_SWITCH = "charge_switch"
CONF_DISCHARGE_SWITCH = "discharge_switch"

# Options keys - adjustable at runtime via options flow
OPT_FEED_IN_MODE = "feed_in_mode"
OPT_FEED_IN_STATIC_POWER = "feed_in_static_power"
OPT_MIN_BATTERY_SOC = "min_battery_soc"
OPT_MAX_GRID_FEED_IN_POWER = "max_grid_feed_in_power"
OPT_GRID_POWER_TOLERANCE_DISCHARGE = "grid_power_tolerance_discharge"
OPT_MAX_GRID_IMPORT_SOLAR_CHARGE = "max_grid_import_solar_charge"
OPT_MAX_CHARGE_POWER = "max_charge_power"
OPT_MIN_CHARGE_POWER = "min_charge_power"
OPT_UPDATE_INTERVAL = "update_interval"
OPT_DEADBAND = "deadband"
OPT_CHARGE_POWER_STEP = "charge_power_step"
OPT_FEED_IN_POWER_STEP = "feed_in_power_step"
OPT_MIN_DWELL_TIME = "min_dwell_time"

# Default values for options
DEFAULT_FEED_IN_MODE = "dynamic"
DEFAULT_FEED_IN_STATIC_POWER = 400
DEFAULT_MIN_BATTERY_SOC = 10
DEFAULT_MAX_GRID_FEED_IN_POWER = 800
DEFAULT_GRID_POWER_TOLERANCE_DISCHARGE = 50
DEFAULT_MAX_GRID_IMPORT_SOLAR_CHARGE = 0
DEFAULT_MAX_CHARGE_POWER = 1200
DEFAULT_MIN_CHARGE_POWER = 200
DEFAULT_UPDATE_INTERVAL = 20
DEFAULT_DEADBAND = 50
DEFAULT_CHARGE_POWER_STEP = 100
DEFAULT_FEED_IN_POWER_STEP = 50
DEFAULT_MIN_DWELL_TIME = 60
DEFAULT_PROPORTIONAL_DAMPING = 0.8

# Operating modes (user-facing)
MODE_FORCED_CHARGE = "forced_charge"
MODE_HOLD = "hold"
MODE_SOLAR = "solar"
MODE_AUTOMATIC = "automatic"

MODES = [MODE_FORCED_CHARGE, MODE_HOLD, MODE_SOLAR, MODE_AUTOMATIC]

# FSM states (internal, for automatic mode)
STATE_CHARGE = "charge"
STATE_HOLD = "hold"
STATE_DISCHARGE = "discharge"

# Feed-in modes
FEED_IN_DYNAMIC = "dynamic"
FEED_IN_STATIC = "static"

# PowerStream power supply mode options
PS_MODE_PRIORITIZE_STORAGE = "Prioritize power storage"
PS_MODE_PRIORITIZE_SUPPLY = "Prioritize power supply"

# Logging
DEFAULT_LOG_BUFFER_SIZE = 100

# Platforms
PLATFORMS = ["sensor", "select", "number", "switch"]
