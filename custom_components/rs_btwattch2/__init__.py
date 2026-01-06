"""RATOC Systems Bluetooth devices integration for Home Assistant."""

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

from .const import CONF_DEVICE_MODEL, DEVICE_MODELS, DOMAIN, MANUFACTURER_ID, DeviceModel

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


@dataclass
class BTEVS1Data:
    """Data class for RS-BTEVS1 sensor values."""

    co2: int
    pm1_0: int
    pm2_5: int
    pm4_0: int | None
    temperature: float
    humidity: int
    pm10: int
    tvoc: int | None
    battery_voltage: float | None


def identify_device_model(service_info: BluetoothServiceInfoBleak) -> DeviceModel | None:
    """Identify device model from Bluetooth service info.

    Args:
        service_info: Bluetooth service information

    Returns:
        DeviceModel if identified, None otherwise
    """
    # Check manufacturer ID first
    manufacturer_data = _get_manufacturer_data(service_info)
    if MANUFACTURER_ID not in manufacturer_data:
        return None

    # Method 1: Identify by device name pattern
    if service_info.name:
        name_upper = service_info.name.upper()
        if "BTWATTCH2" in name_upper:
            return DeviceModel.BTWATTCH2
        if "BTEVS1" in name_upper:
            return DeviceModel.BTEVS1
        # Add new device name patterns here:
        # if "OTHER_DEVICE" in name_upper:
        #     return DeviceModel.OTHER_DEVICE

    # Method 2: Identify by data length/format
    data = manufacturer_data[MANUFACTURER_ID]
    if len(data) == 8:
        return DeviceModel.BTWATTCH2
    if len(data) == 9 or len(data) >= 15:
        return DeviceModel.BTEVS1
    # Add new device data length checks here:
    # elif len(data) == 10:
    #     return DeviceModel.OTHER_DEVICE

    return None


def _get_manufacturer_data(service_info: BluetoothServiceInfoBleak) -> dict[int, bytes]:
    """Return manufacturer data from service info with a safe fallback."""
    return getattr(service_info, "manufacturer_data", None) or service_info.advertisement.manufacturer_data


def parse_manufacturer_data(
    manufacturer_data: dict[int, bytes],
    device_model: DeviceModel | None = None,
) -> BTWATTCH2Data | BTEVS1Data | None:
    """Parse manufacturer data based on device model.

    Args:
        manufacturer_data: Dictionary of manufacturer ID to data bytes
        device_model: Device model to use for parsing (None for auto-detect)

    Returns:
        Parsed data if successful, None otherwise
    """
    if MANUFACTURER_ID not in manufacturer_data:
        return None

    data = manufacturer_data[MANUFACTURER_ID]

    # Auto-detect device model if not specified
    if device_model is None:
        if len(data) == 8:
            device_model = DeviceModel.BTWATTCH2
        elif len(data) == 9 or len(data) >= 15:
            device_model = DeviceModel.BTEVS1
        else:
            _LOGGER.debug("Unknown data length: %d", len(data))
            return None

    # Parse based on device model
    if device_model == DeviceModel.BTWATTCH2:
        return _parse_btwattch2_data(data)
    if device_model == DeviceModel.BTEVS1:
        return _parse_btevs1_data(data)
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


def _parse_btevs1_data(data: bytes) -> BTEVS1Data | None:
    """Parse RS-BTEVS1 manufacturer data.

    Args:
        data: Manufacturer data bytes

    Returns:
        BTEVS1Data if parsing successful, None otherwise
    """
    if len(data) not in (9,) and len(data) < 15:
        _LOGGER.debug("Invalid BTEVS1 data length: %d (expected 9 or >= 15)", len(data))
        return None

    try:
        if len(data) == 9:
            co2 = struct.unpack("<H", data[0:2])[0]
            pm1_0 = data[2]
            pm2_5 = data[3]
            pm4_0 = data[4]
            pm10 = data[5]
            temperature_raw = struct.unpack("<h", data[6:8])[0]
            humidity = data[8]

            return BTEVS1Data(
                co2=co2,
                pm1_0=pm1_0,
                pm2_5=pm2_5,
                pm4_0=pm4_0,
                temperature=temperature_raw / 10,
                humidity=humidity,
                pm10=pm10,
                tvoc=None,
                battery_voltage=None,
            )

        co2 = struct.unpack("<H", data[0:2])[0]
        pm1_0 = struct.unpack("<H", data[2:4])[0]
        pm2_5 = struct.unpack("<H", data[4:6])[0]
        temperature_raw = struct.unpack("<H", data[6:8])[0]
        humidity = data[8]
        pm10 = struct.unpack("<H", data[9:11])[0]
        tvoc = struct.unpack("<H", data[11:13])[0]
        battery_raw = struct.unpack("<H", data[13:15])[0]

        return BTEVS1Data(
            co2=co2,
            pm1_0=pm1_0,
            pm2_5=pm2_5,
            pm4_0=None,
            temperature=temperature_raw / 10,
            humidity=humidity,
            pm10=pm10,
            tvoc=tvoc,
            battery_voltage=battery_raw / 100,
        )
    except struct.error as err:
        _LOGGER.debug("Failed to parse BTEVS1 data: %s", err)
        return None


class BTWATTCH2DeviceData:
    """Data holder for a single device."""

    def __init__(self, address: str, name: str, device_model: DeviceModel) -> None:
        """Initialize device data."""
        self.address = address
        self.name = name
        self.device_model = device_model
        self.data: BTWATTCH2Data | BTEVS1Data | None = None
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
        device_model: DeviceModel | None = None,
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
        self.device_model = device_model

        # For single device mode
        self.data: BTWATTCH2Data | BTEVS1Data | None = None
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

        manufacturer_data = _get_manufacturer_data(service_info)
        if not manufacturer_data:
            return

        if self.auto_discover:
            # Auto-discover mode: track multiple devices
            is_new_device = address not in self.devices
            
            # Identify device model
            # For existing devices, try to use default model if identification fails
            device_model = identify_device_model(service_info)
            if device_model is None:
                if is_new_device:
                    # For new devices, we need to identify the model
                    _LOGGER.debug("Could not identify device model for %s", address)
                    return
                else:
                    device_model = self.devices[address].device_model
                    _LOGGER.debug(
                        "Could not identify device model for existing device %s, using stored model %s",
                        address,
                        device_model.value,
                    )

            # Parse data based on device model
            data = parse_manufacturer_data(manufacturer_data, device_model)
            if data is None:
                return

            if is_new_device:
                model_config = DEVICE_MODELS.get(device_model, {})
                default_name = model_config.get("default_name", "RATOC Systems Device")
                device_name = service_info.name or f"{default_name} {address[-8:].upper()}"
                self.devices[address] = BTWATTCH2DeviceData(address, device_name, device_model)
                _LOGGER.info(
                    "Discovered new %s device: %s (%s)",
                    model_config.get("name", "RATOC Systems"),
                    address,
                    device_name,
                )

            self.devices[address].update(data)
            if isinstance(data, BTWATTCH2Data):
                _LOGGER.debug(
                    "Updated data for %s: relay=%s, voltage=%.1fV, current=%dmA, power=%.3fW",
                    address,
                    data.relay,
                    data.voltage,
                    data.current,
                    data.power,
                )
            elif isinstance(data, BTEVS1Data):
                _LOGGER.debug(
                    "Updated data for %s: co2=%dppm, temperature=%.1fC, humidity=%d%%",
                    address,
                    data.co2,
                    data.temperature,
                    data.humidity,
                )

            # Notify about new device after updating data
            if is_new_device:
                for cb in self._new_device_callbacks:
                    cb(self.devices[address])
        else:
            # Single device mode
            device_model = self.device_model or identify_device_model(service_info)
            if device_model is None:
                device_model = DeviceModel.BTWATTCH2
                _LOGGER.debug("Could not identify device model for %s, using default", address)

            # Parse data based on device model
            data = parse_manufacturer_data(manufacturer_data, device_model)
            if data is None:
                return

            self.data = data
            if isinstance(data, BTWATTCH2Data):
                _LOGGER.debug(
                    "Updated data for %s: relay=%s, voltage=%.1fV, current=%dmA, power=%.3fW",
                    self.address,
                    data.relay,
                    data.voltage,
                    data.current,
                    data.power,
                )
            elif isinstance(data, BTEVS1Data):
                _LOGGER.debug(
                    "Updated data for %s: co2=%dppm, temperature=%.1fC, humidity=%d%%",
                    self.address,
                    data.co2,
                    data.temperature,
                    data.humidity,
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
        device_model_value = entry.data.get(CONF_DEVICE_MODEL, DeviceModel.BTWATTCH2.value)
        device_model = DeviceModel(device_model_value)
        default_name = DEVICE_MODELS[device_model]["default_name"]
        name = entry.data.get("name", f"{default_name} {address[-8:]}")
        coordinator = BTWATTCH2Coordinator(
            hass,
            entry,
            address=address,
            name=name,
            device_model=device_model,
        )

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
