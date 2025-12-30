"""Sensor platform for RS-BTWATTCH2."""

from __future__ import annotations

import logging
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CONF_AUTO_DISCOVER, BTWATTCH2Coordinator, BTWATTCH2DeviceData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: BTWATTCH2Coordinator = hass.data[DOMAIN][entry.entry_id]

    if entry.data.get(CONF_AUTO_DISCOVER, False):
        # Auto-discover mode: create entities for discovered devices dynamically
        added_devices: set[str] = set()

        @callback
        def create_entities_for_device(device: BTWATTCH2DeviceData) -> None:
            """Create sensor entities for a newly discovered device."""
            if device.address in added_devices:
                return
            added_devices.add(device.address)

            entities: list[SensorEntity] = [
                BTWATTCH2PowerSensorAuto(coordinator, device),
                BTWATTCH2VoltageSensorAuto(coordinator, device),
                BTWATTCH2CurrentSensorAuto(coordinator, device),
            ]
            async_add_entities(entities)
            _LOGGER.info("Added sensor entities for device %s", device.address)

        # Add entities for already discovered devices
        for device in coordinator.get_all_devices():
            create_entities_for_device(device)

        # Register callback for new devices
        entry.async_on_unload(coordinator.add_new_device_callback(create_entities_for_device))
    else:
        # Single device mode
        entities: list[SensorEntity] = [
            BTWATTCH2PowerSensor(coordinator, entry),
            BTWATTCH2VoltageSensor(coordinator, entry),
            BTWATTCH2CurrentSensor(coordinator, entry),
        ]
        async_add_entities(entities)


class BTWATTCH2SensorBase(SensorEntity):
    """Base class for RS-BTWATTCH2 sensors."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: BTWATTCH2Coordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
        icon: str | None,
    ) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._key = key
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = f"{coordinator.address}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            name=coordinator.name,
            manufacturer="RATOC Systems",
            model="RS-BTWATTCH2",
        )
        self._remove_listener: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        self._remove_listener = self._coordinator.add_listener(self._handle_coordinator_update)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        if self._remove_listener:
            self._remove_listener()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._coordinator.data is not None


class BTWATTCH2SensorBaseAuto(SensorEntity):
    """Base class for RS-BTWATTCH2 sensors in auto-discover mode."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: BTWATTCH2Coordinator,
        device: BTWATTCH2DeviceData,
        key: str,
        name: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
        icon: str | None,
    ) -> None:
        """Initialize the sensor."""
        self._coordinator = coordinator
        self._device = device
        self._key = key
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = f"{device.address}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.address)},
            name=device.name,
            manufacturer="RATOC Systems",
            model="RS-BTWATTCH2",
        )
        self._remove_listener: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added."""
        self._remove_listener = self._device.add_listener(self._handle_device_update)

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        if self._remove_listener:
            self._remove_listener()

    @callback
    def _handle_device_update(self) -> None:
        """Handle updated data from the device."""
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._device.data is not None


# Single device mode sensors
class BTWATTCH2PowerSensor(BTWATTCH2SensorBase):
    """Sensor for power measurement."""

    def __init__(self, coordinator: BTWATTCH2Coordinator, entry: ConfigEntry) -> None:
        """Initialize the power sensor."""
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            key="power",
            name="Power",
            device_class=SensorDeviceClass.POWER,
            unit=UnitOfPower.WATT,
            icon="mdi:flash",
        )
        self._attr_suggested_display_precision = 3

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        if self._coordinator.data is None:
            return None
        return self._coordinator.data.power


class BTWATTCH2VoltageSensor(BTWATTCH2SensorBase):
    """Sensor for voltage measurement."""

    def __init__(self, coordinator: BTWATTCH2Coordinator, entry: ConfigEntry) -> None:
        """Initialize the voltage sensor."""
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            key="voltage",
            name="Voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            unit=UnitOfElectricPotential.VOLT,
            icon="mdi:sine-wave",
        )
        self._attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        if self._coordinator.data is None:
            return None
        return self._coordinator.data.voltage


class BTWATTCH2CurrentSensor(BTWATTCH2SensorBase):
    """Sensor for current measurement."""

    def __init__(self, coordinator: BTWATTCH2Coordinator, entry: ConfigEntry) -> None:
        """Initialize the current sensor."""
        super().__init__(
            coordinator=coordinator,
            entry=entry,
            key="current",
            name="Current",
            device_class=SensorDeviceClass.CURRENT,
            unit=UnitOfElectricCurrent.MILLIAMPERE,
            icon="mdi:current-ac",
        )

    @property
    def native_value(self) -> int | None:
        """Return the sensor value."""
        if self._coordinator.data is None:
            return None
        return self._coordinator.data.current


# Auto-discover mode sensors
class BTWATTCH2PowerSensorAuto(BTWATTCH2SensorBaseAuto):
    """Sensor for power measurement in auto-discover mode."""

    def __init__(self, coordinator: BTWATTCH2Coordinator, device: BTWATTCH2DeviceData) -> None:
        """Initialize the power sensor."""
        super().__init__(
            coordinator=coordinator,
            device=device,
            key="power",
            name="Power",
            device_class=SensorDeviceClass.POWER,
            unit=UnitOfPower.WATT,
            icon="mdi:flash",
        )
        self._attr_suggested_display_precision = 3

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        if self._device.data is None:
            return None
        return self._device.data.power


class BTWATTCH2VoltageSensorAuto(BTWATTCH2SensorBaseAuto):
    """Sensor for voltage measurement in auto-discover mode."""

    def __init__(self, coordinator: BTWATTCH2Coordinator, device: BTWATTCH2DeviceData) -> None:
        """Initialize the voltage sensor."""
        super().__init__(
            coordinator=coordinator,
            device=device,
            key="voltage",
            name="Voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            unit=UnitOfElectricPotential.VOLT,
            icon="mdi:sine-wave",
        )
        self._attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        if self._device.data is None:
            return None
        return self._device.data.voltage


class BTWATTCH2CurrentSensorAuto(BTWATTCH2SensorBaseAuto):
    """Sensor for current measurement in auto-discover mode."""

    def __init__(self, coordinator: BTWATTCH2Coordinator, device: BTWATTCH2DeviceData) -> None:
        """Initialize the current sensor."""
        super().__init__(
            coordinator=coordinator,
            device=device,
            key="current",
            name="Current",
            device_class=SensorDeviceClass.CURRENT,
            unit=UnitOfElectricCurrent.MILLIAMPERE,
            icon="mdi:current-ac",
        )

    @property
    def native_value(self) -> int | None:
        """Return the sensor value."""
        if self._device.data is None:
            return None
        return self._device.data.current
