"""Constants for RATOC Systems integration."""

from __future__ import annotations

from enum import Enum

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)

DOMAIN = "ratocsystems"

# RATOC Systems Manufacturer ID (0x0B60 = 2912 in decimal)
MANUFACTURER_ID = 0x0B60


class DeviceModel(str, Enum):
    """Supported device models."""

    BTWATTCH2 = "btwattch2"
    # Add new models here:
    # OTHER_DEVICE = "other_device"


# Device model configuration
DEVICE_MODELS: dict[DeviceModel, dict[str, str]] = {
    DeviceModel.BTWATTCH2: {
        "name": "RS-BTWATTCH2",
        "default_name": "RS-BTWATTCH2",
    },
    # Add new device configurations here:
}


# Sensor definitions (shared across all models)
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
