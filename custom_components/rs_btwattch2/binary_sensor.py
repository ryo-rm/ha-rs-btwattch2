"""Binary sensor platform for RATOC Systems devices."""

from __future__ import annotations

import logging
from typing import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CONF_AUTO_DISCOVER, BTWATTCH2Coordinator, BTWATTCH2DeviceData
from .const import DEVICE_MODELS, DOMAIN, DeviceModel

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from a config entry."""
    coordinator: BTWATTCH2Coordinator = hass.data[DOMAIN][entry.entry_id]

    if entry.data.get(CONF_AUTO_DISCOVER, False):
        # Auto-discover mode: create entities for discovered devices dynamically
        added_devices: set[str] = set()

        @callback
        def create_entities_for_device(device: BTWATTCH2DeviceData) -> None:
            """Create binary sensor entities for a newly discovered device."""
            if device.address in added_devices:
                return
            added_devices.add(device.address)

            if device.device_model != DeviceModel.BTWATTCH2:
                return
            async_add_entities([BTWATTCH2RelaySensorAuto(coordinator, device)])
            _LOGGER.info("Added binary sensor entities for device %s", device.address)

        # Add entities for already discovered devices
        for device in coordinator.get_all_devices():
            create_entities_for_device(device)

        # Register callback for new devices
        entry.async_on_unload(coordinator.add_new_device_callback(create_entities_for_device))
    else:
        # Single device mode
        if coordinator.device_model == DeviceModel.BTWATTCH2:
            async_add_entities([BTWATTCH2RelaySensor(coordinator, entry)])


class BTWATTCH2RelaySensor(BinarySensorEntity):
    """Binary sensor for RS-BTWATTCH2 relay state."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.POWER
    _attr_name = "Relay"

    def __init__(
        self,
        coordinator: BTWATTCH2Coordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        self._coordinator = coordinator
        self._attr_unique_id = f"{coordinator.address}_relay"
        self._attr_icon = "mdi:power-plug"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            name=coordinator.name,
            manufacturer="RATOC Systems",
            model=DEVICE_MODELS[DeviceModel.BTWATTCH2]["name"],
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

    @property
    def is_on(self) -> bool | None:
        """Return the relay state."""
        if self._coordinator.data is None:
            return None
        return self._coordinator.data.relay


class BTWATTCH2RelaySensorAuto(BinarySensorEntity):
    """Binary sensor for RS-BTWATTCH2 relay state in auto-discover mode."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.POWER
    _attr_name = "Relay"

    def __init__(
        self,
        coordinator: BTWATTCH2Coordinator,
        device: BTWATTCH2DeviceData,
    ) -> None:
        """Initialize the binary sensor."""
        self._coordinator = coordinator
        self._device = device
        self._attr_unique_id = f"{device.address}_relay"
        self._attr_icon = "mdi:power-plug"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.address)},
            name=device.name,
            manufacturer="RATOC Systems",
            model=DEVICE_MODELS[DeviceModel.BTWATTCH2]["name"],
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

    @property
    def is_on(self) -> bool | None:
        """Return the relay state."""
        if self._device.data is None:
            return None
        return self._device.data.relay
