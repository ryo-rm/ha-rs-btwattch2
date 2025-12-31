"""RS-BTWATTCH2 Bluetooth Power Monitor integration for Home Assistant."""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from typing import Callable

from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_register_callback,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, MANUFACTURER_ID, DeviceModel

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

# Config entry data keys
CONF_AUTO_DISCOVER = "auto_discover"


@dataclass
class BTWATTCH2Data:
    """Data class for RS-BTWATTCH2 sensor values."""

    relay: bool
    voltage: float
    current: int
    power: float


def identify_device_model(service_info: BluetoothServiceInfoBleak) -> DeviceModel | None:
    """Identify device model from Bluetooth service info.

    Args:
        service_info: Bluetooth service information

    Returns:
        DeviceModel if identified, None otherwise
    """
    # Check manufacturer ID first
    manufacturer_data = service_info.advertisement.manufacturer_data
    if MANUFACTURER_ID not in manufacturer_data:
        return None

    # Method 1: Identify by device name pattern
    if service_info.name:
        name_upper = service_info.name.upper()
        if "BTWATTCH2" in name_upper:
            return DeviceModel.BTWATTCH2
        # Add new device name patterns here:
        # if "OTHER_DEVICE" in name_upper:
        #     return DeviceModel.OTHER_DEVICE

    # Method 2: Identify by data length/format
    data = manufacturer_data[MANUFACTURER_ID]
    if len(data) == 8:
        return DeviceModel.BTWATTCH2
    # Add new device data length checks here:
    # elif len(data) == 10:
    #     return DeviceModel.OTHER_DEVICE

    return None


def parse_manufacturer_data(
    manufacturer_data: dict[int, bytes],
    device_model: DeviceModel | None = None,
) -> BTWATTCH2Data | None:
    """Parse manufacturer data based on device model.

    Args:
        manufacturer_data: Dictionary of manufacturer ID to data bytes
        device_model: Device model to use for parsing (None for auto-detect)

    Returns:
        BTWATTCH2Data if parsing successful, None otherwise
    """
    if MANUFACTURER_ID not in manufacturer_data:
        return None

    data = manufacturer_data[MANUFACTURER_ID]

    # Auto-detect device model if not specified
    if device_model is None:
        if len(data) == 8:
            device_model = DeviceModel.BTWATTCH2
        else:
            _LOGGER.debug("Unknown data length: %d", len(data))
            return None

    # Parse based on device model
    if device_model == DeviceModel.BTWATTCH2:
        return _parse_btwattch2_data(data)
    # Add new device parsers here:
    # elif device_model == DeviceModel.OTHER_DEVICE:
    #     return _parse_other_device_data(data)

    return None


def _parse_btwattch2_data(data: bytes) -> BTWATTCH2Data | None:
    """Parse RS-BTWATTCH2 manufacturer data.

    Args:
        data: Manufacturer data bytes

    Returns:
        BTWATTCH2Data if parsing successful, None otherwise
    """
    if len(data) != 8:
        _LOGGER.debug("Invalid BTWATTCH2 data length: %d (expected 8)", len(data))
        return None

    try:
        relay, voltage, current = struct.unpack("<BHH", data[:5])
        power = int.from_bytes(data[5:8], byteorder="little", signed=False)

        return BTWATTCH2Data(
            relay=relay == 1,
            voltage=voltage / 10,
            current=current,
            power=power / 1000,
        )
    except struct.error as err:
        _LOGGER.debug("Failed to parse BTWATTCH2 data: %s", err)
        return None


class BTWATTCH2DeviceData:
    """Data holder for a single device."""

    def __init__(self, address: str, name: str) -> None:
        """Initialize device data."""
        self.address = address
        self.name = name
        self.data: BTWATTCH2Data | None = None
        self._listeners: list[Callable[[], None]] = []

    def add_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        """Add a listener for updates."""
        self._listeners.append(update_callback)

        def remove_listener() -> None:
            if update_callback in self._listeners:
                self._listeners.remove(update_callback)

        return remove_listener

    def update(self, data: BTWATTCH2Data) -> None:
        """Update data and notify listeners."""
        self.data = data
        for listener in self._listeners:
            listener()


class BTWATTCH2Coordinator:
    """Coordinator for RS-BTWATTCH2 device data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        address: str | None = None,
        name: str | None = None,
        auto_discover: bool = False,
    ) -> None:
        """Initialize the coordinator.

        Args:
            hass: Home Assistant instance
            entry: Config entry
            address: Specific device address (None for auto-discover mode)
            name: Device name (only used for single device mode)
            auto_discover: If True, discover and track all RS-BTWATTCH2 devices
        """
        self.hass = hass
        self.entry = entry
        self.address = address
        self.name = name
        self.auto_discover = auto_discover

        # For single device mode
        self.data: BTWATTCH2Data | None = None
        self._listeners: list[Callable[[], None]] = []

        # For auto-discover mode: track multiple devices
        self.devices: dict[str, BTWATTCH2DeviceData] = {}
        self._new_device_callbacks: list[Callable[[BTWATTCH2DeviceData], None]] = []

    def add_listener(self, update_callback: Callable[[], None]) -> Callable[[], None]:
        """Add a listener for updates (single device mode)."""
        self._listeners.append(update_callback)

        def remove_listener() -> None:
            if update_callback in self._listeners:
                self._listeners.remove(update_callback)

        return remove_listener

    def add_new_device_callback(
        self, callback_func: Callable[[BTWATTCH2DeviceData], None]
    ) -> Callable[[], None]:
        """Add a callback for when new devices are discovered (auto-discover mode)."""
        self._new_device_callbacks.append(callback_func)

        def remove_callback() -> None:
            if callback_func in self._new_device_callbacks:
                self._new_device_callbacks.remove(callback_func)

        return remove_callback

    def _notify_listeners(self) -> None:
        """Notify all listeners of an update."""
        for listener in self._listeners:
            listener()

    def get_device(self, address: str) -> BTWATTCH2DeviceData | None:
        """Get device data by address."""
        return self.devices.get(address.lower())

    def get_all_devices(self) -> list[BTWATTCH2DeviceData]:
        """Get all discovered devices."""
        return list(self.devices.values())

    @callback
    def _handle_bluetooth_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        address = service_info.address.lower()

        # For single device mode, filter by address
        if not self.auto_discover:
            if self.address and address != self.address.lower():
                return

        manufacturer_data = service_info.advertisement.manufacturer_data
        if not manufacturer_data:
            return

        # Identify device model
        device_model = identify_device_model(service_info)
        if device_model is None:
            _LOGGER.debug("Could not identify device model for %s", address)
            return

        # Parse data based on device model
        data = parse_manufacturer_data(manufacturer_data, device_model)
        if data is None:
            return

        if self.auto_discover:
            # Auto-discover mode: track multiple devices
            is_new_device = address not in self.devices
            if is_new_device:
                # Use device model name from config
                from .const import DEVICE_MODELS
                model_config = DEVICE_MODELS.get(device_model, {})
                default_name = model_config.get("default_name", "RATOC Systems Device")
                device_name = service_info.name or f"{default_name} {address[-8:].upper()}"
                self.devices[address] = BTWATTCH2DeviceData(address, device_name)
                _LOGGER.info(
                    "Discovered new %s device: %s (%s)",
                    model_config.get("name", "RATOC Systems"),
                    address,
                    device_name,
                )

            self.devices[address].update(data)
            _LOGGER.debug(
                "Updated data for %s: relay=%s, voltage=%.1fV, current=%dmA, power=%.3fW",
                address,
                data.relay,
                data.voltage,
                data.current,
                data.power,
            )

            # Notify about new device after updating data
            if is_new_device:
                for cb in self._new_device_callbacks:
                    cb(self.devices[address])
        else:
            # Single device mode
            self.data = data
            _LOGGER.debug(
                "Updated data for %s: relay=%s, voltage=%.1fV, current=%dmA, power=%.3fW",
                self.address,
                data.relay,
                data.voltage,
                data.current,
                data.power,
            )
            self._notify_listeners()

    def start(self) -> None:
        """Start listening for Bluetooth advertisements."""
        # Use entry.async_on_unload for proper cleanup as recommended by HA docs
        self.entry.async_on_unload(
            async_register_callback(
                self.hass,
                self._handle_bluetooth_event,
                {"manufacturer_id": MANUFACTURER_ID},
                BluetoothScanningMode.PASSIVE,
            )
        )
        mode = "auto-discover" if self.auto_discover else f"single device ({self.address})"
        _LOGGER.info("Started Bluetooth listener in %s mode", mode)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RS-BTWATTCH2 from a config entry."""
    auto_discover = entry.data.get(CONF_AUTO_DISCOVER, False)

    if auto_discover:
        # Auto-discover mode
        coordinator = BTWATTCH2Coordinator(hass, entry, auto_discover=True)
    else:
        # Single device mode
        address = entry.data["address"]
        name = entry.data.get("name", f"RS-BTWATTCH2 {address[-8:]}")
        coordinator = BTWATTCH2Coordinator(hass, entry, address=address, name=name)

    coordinator.start()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
