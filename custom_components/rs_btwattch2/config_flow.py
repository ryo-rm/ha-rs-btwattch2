"""Config flow for RS-BTWATTCH2 integration."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .const import DEFAULT_NAME, DOMAIN, MANUFACTURER_ID

_LOGGER = logging.getLogger(__name__)

CONF_AUTO_DISCOVER = "auto_discover"


def format_unique_id(address: str) -> str:
    """Format the unique ID from address."""
    return address.replace(":", "").lower()


def normalize_mac_address(address: str) -> str:
    """Normalize MAC address to uppercase with colons."""
    # Remove all non-hex characters
    cleaned = re.sub(r"[^0-9A-Fa-f]", "", address)
    if len(cleaned) != 12:
        return address
    # Insert colons
    return ":".join(cleaned[i : i + 2].upper() for i in range(0, 12, 2))


class BTWATTCH2ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RS-BTWATTCH2."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the Bluetooth discovery step."""
        await self.async_set_unique_id(format_unique_id(discovery_info.address))
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name or DEFAULT_NAME}

        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Bluetooth discovery."""
        assert self._discovery_info is not None

        if user_input is not None:
            name = user_input.get(CONF_NAME, self._discovery_info.name or DEFAULT_NAME)
            return self.async_create_entry(
                title=name,
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                    CONF_NAME: name,
                    CONF_AUTO_DISCOVER: False,
                },
            )

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovery_info.name or DEFAULT_NAME,
                "address": self._discovery_info.address,
            },
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_NAME,
                        default=self._discovery_info.name or DEFAULT_NAME,
                    ): str,
                }
            ),
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial user step - show menu."""
        # Check if auto-discover is already configured
        for entry in self._async_current_entries():
            if entry.data.get(CONF_AUTO_DISCOVER, False):
                # Auto-discover already configured, only allow manual additions
                return self.async_show_menu(
                    step_id="user",
                    menu_options={
                        "pick_device": "検出されたデバイスから選択",
                        "manual": "MACアドレスを手動入力",
                    },
                )

        # Discover RS-BTWATTCH2 devices
        self._discovered_devices.clear()
        for service_info in async_discovered_service_info(self.hass):
            if MANUFACTURER_ID in service_info.manufacturer_data:
                address = service_info.address
                if format_unique_id(address) not in self._async_current_ids():
                    self._discovered_devices[address] = service_info

        # Show menu with options
        return self.async_show_menu(
            step_id="user",
            menu_options={
                "auto_discover": "すべてのデバイスを自動検出（推奨）",
                "pick_device": "検出されたデバイスから選択",
                "manual": "MACアドレスを手動入力",
            },
        )

    async def async_step_auto_discover(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle auto-discover setup."""
        # Check if auto-discover is already configured
        for entry in self._async_current_entries():
            if entry.data.get(CONF_AUTO_DISCOVER, False):
                return self.async_abort(reason="auto_discover_already_configured")

        if user_input is not None:
            # Create entry for auto-discover mode
            return self.async_create_entry(
                title="RS-BTWATTCH2 (自動検出)",
                data={
                    CONF_AUTO_DISCOVER: True,
                },
            )

        return self.async_show_form(
            step_id="auto_discover",
            description_placeholders={},
        )

    async def async_step_pick_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle picking a discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            name = user_input.get(CONF_NAME) or f"{DEFAULT_NAME} {address[-8:]}"

            await self.async_set_unique_id(format_unique_id(address))
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=name,
                data={
                    CONF_ADDRESS: address,
                    CONF_NAME: name,
                    CONF_AUTO_DISCOVER: False,
                },
            )

        # Re-discover devices if needed
        if not self._discovered_devices:
            for service_info in async_discovered_service_info(self.hass):
                if MANUFACTURER_ID in service_info.manufacturer_data:
                    address = service_info.address
                    if format_unique_id(address) not in self._async_current_ids():
                        self._discovered_devices[address] = service_info

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        # Build list of devices for selection
        device_list = {
            address: f"{info.name or DEFAULT_NAME} ({address})"
            for address, info in self._discovered_devices.items()
        }

        return self.async_show_form(
            step_id="pick_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(device_list),
                    vol.Optional(CONF_NAME): str,
                }
            ),
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle manual address entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = normalize_mac_address(user_input[CONF_ADDRESS])
            name = user_input.get(CONF_NAME) or f"{DEFAULT_NAME} {address[-8:]}"

            # Validate MAC address format
            if not self._validate_mac_address(address):
                errors[CONF_ADDRESS] = "invalid_mac"
            else:
                await self.async_set_unique_id(format_unique_id(address))
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_ADDRESS: address,
                        CONF_NAME: name,
                        CONF_AUTO_DISCOVER: False,
                    },
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): str,
                    vol.Optional(CONF_NAME): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    def _validate_mac_address(address: str) -> bool:
        """Validate MAC address format."""
        pattern = r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$"
        return bool(re.match(pattern, address))
