"""Sensor platform for RATOC Systems devices."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CONF_AUTO_DISCOVER, BTWATTCH2Coordinator, BTWATTCH2DeviceData
from .const import CONF_DEVICE_MODEL, DEVICE_MODELS, DOMAIN, DeviceModel

_LOGGER = logging.getLogger(__name__)

VOC_DEVICE_CLASS = getattr(SensorDeviceClass, "VOLATILE_ORGANIC_COMPOUNDS", None)


@dataclass(frozen=True)
class RatocSensorDefinition:
    """Definition for a RATOC Systems sensor."""

    key: str
    name: str
    device_class: SensorDeviceClass | None
    unit: str | None
    icon: str | None = None
    precision: int | None = None


SENSOR_DEFINITIONS: dict[DeviceModel, list[RatocSensorDefinition]] = {
    DeviceModel.BTWATTCH2: [
        RatocSensorDefinition(
            key="power",
            name="Power",
            device_class=SensorDeviceClass.POWER,
            unit=UnitOfPower.WATT,
            icon="mdi:flash",
            precision=3,
        ),
        RatocSensorDefinition(
            key="voltage",
            name="Voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            unit=UnitOfElectricPotential.VOLT,
            icon="mdi:sine-wave",
            precision=1,
        ),
        RatocSensorDefinition(
            key="current",
            name="Current",
            device_class=SensorDeviceClass.CURRENT,
            unit=UnitOfElectricCurrent.MILLIAMPERE,
            icon="mdi:current-ac",
        ),
    ],
    DeviceModel.BTEVS1: [
        RatocSensorDefinition(
            key="co2",
            name="CO2",
            device_class=SensorDeviceClass.CO2,
            unit=CONCENTRATION_PARTS_PER_MILLION,
            icon="mdi:molecule-co2",
        ),
        RatocSensorDefinition(
            key="temperature",
            name="Temperature",
            device_class=SensorDeviceClass.TEMPERATURE,
            unit=UnitOfTemperature.CELSIUS,
            icon="mdi:thermometer",
            precision=1,
        ),
        RatocSensorDefinition(
            key="humidity",
            name="Humidity",
            device_class=SensorDeviceClass.HUMIDITY,
            unit=PERCENTAGE,
            icon="mdi:water-percent",
        ),
        RatocSensorDefinition(
            key="pm1_0",
            name="PM1.0",
            device_class=None,
            unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            icon="mdi:blur",
        ),
        RatocSensorDefinition(
            key="pm2_5",
            name="PM2.5",
            device_class=SensorDeviceClass.PM25,
            unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            icon="mdi:blur",
        ),
        RatocSensorDefinition(
            key="pm4_0",
            name="PM4.0",
            device_class=None,
            unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            icon="mdi:blur",
        ),
        RatocSensorDefinition(
            key="pm10",
            name="PM10.0",
            device_class=SensorDeviceClass.PM10,
            unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
            icon="mdi:blur",
        ),
        RatocSensorDefinition(
            key="tvoc",
            name="TVOC",
            device_class=VOC_DEVICE_CLASS,
            unit=CONCENTRATION_PARTS_PER_BILLION,
            icon="mdi:chemical-weapon",
        ),
        RatocSensorDefinition(
            key="battery_voltage",
            name="Battery Voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            unit=UnitOfElectricPotential.VOLT,
            icon="mdi:battery",
            precision=2,
        ),
    ],
}


def _format_unique_id(address: str, key: str, device_model: DeviceModel) -> str:
    if device_model == DeviceModel.BTWATTCH2:
        return f"{address}_{key}"
    return f"{device_model.value}_{address}_{key}"


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

            definitions = SENSOR_DEFINITIONS.get(device.device_model, [])
            entities = [
                RatocSensorAuto(coordinator, device, definition)
                for definition in definitions
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
        device_model_value = entry.data.get(CONF_DEVICE_MODEL, DeviceModel.BTWATTCH2.value)
        device_model = DeviceModel(device_model_value)
        definitions = SENSOR_DEFINITIONS.get(device_model, [])
        entities = [
            RatocSensor(coordinator, entry, definition, device_model)
            for definition in definitions
        ]
        async_add_entities(entities)


class RatocSensorBase(SensorEntity):
    """Base class for RATOC Systems sensors."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        key: str,
        name: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
        icon: str | None,
        device_model: DeviceModel,
        address: str,
        device_name: str,
        precision: int | None,
    ) -> None:
        """Initialize the sensor."""
        self._key = key
        self._device_model = device_model
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_unique_id = _format_unique_id(address, key, device_model)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, address)},
            name=device_name,
            manufacturer="RATOC Systems",
            model=DEVICE_MODELS[device_model]["name"],
        )
        if precision is not None:
            self._attr_suggested_display_precision = precision

    def _get_data_value(self, data: object | None) -> object | None:
        if data is None:
            return None
        return getattr(data, self._key, None)


class RatocSensor(RatocSensorBase):
    """Sensor for single device mode."""

    def __init__(
        self,
        coordinator: BTWATTCH2Coordinator,
        entry: ConfigEntry,
        definition: RatocSensorDefinition,
        device_model: DeviceModel,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            key=definition.key,
            name=definition.name,
            device_class=definition.device_class,
            unit=definition.unit,
            icon=definition.icon,
            device_model=device_model,
            address=coordinator.address,
            device_name=coordinator.name,
            precision=definition.precision,
        )
        self._coordinator = coordinator
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

    @property
    def native_value(self) -> object | None:
        """Return the sensor value."""
        return self._get_data_value(self._coordinator.data)


class RatocSensorAuto(RatocSensorBase):
    """Sensor for auto-discover mode."""

    def __init__(
        self,
        coordinator: BTWATTCH2Coordinator,
        device: BTWATTCH2DeviceData,
        definition: RatocSensorDefinition,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            key=definition.key,
            name=definition.name,
            device_class=definition.device_class,
            unit=definition.unit,
            icon=definition.icon,
            device_model=device.device_model,
            address=device.address,
            device_name=device.name,
            precision=definition.precision,
        )
        self._coordinator = coordinator
        self._device = device
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

    @property
    def native_value(self) -> object | None:
        """Return the sensor value."""
        return self._get_data_value(self._device.data)
