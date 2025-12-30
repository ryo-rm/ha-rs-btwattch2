"""Constants for RS-BTWATTCH2 integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)

DOMAIN = "rs_btwattch2"

# RS-BTWATTCH2 Manufacturer ID (0x0B60 = 2912 in decimal)
MANUFACTURER_ID = 0x0B60

# Sensor definitions
SENSOR_TYPES: dict[str, tuple[str, str | None, SensorDeviceClass | None, str | None]] = {
    "power": ("Power", UnitOfPower.WATT, SensorDeviceClass.POWER, "mdi:flash"),
    "voltage": (
        "Voltage",
        UnitOfElectricPotential.VOLT,
        SensorDeviceClass.VOLTAGE,
        "mdi:sine-wave",
    ),
    "current": (
        "Current",
        UnitOfElectricCurrent.MILLIAMPERE,
        SensorDeviceClass.CURRENT,
        "mdi:current-ac",
    ),
}

# Binary sensor for relay state
RELAY_SENSOR = "relay"

# Default name prefix
DEFAULT_NAME = "RS-BTWATTCH2"
