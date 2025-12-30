# RS-BTWATTCH2 Home Assistant Integration

Home Assistant integration for [RATOC Systems RS-BTWATTCH2](https://www.ratocsystems.com/products/subpage/btwattch2.html) Bluetooth power monitor.

⚠️ This integration is neither RATOC Systems official nor Home Assistant official. **Use at your own risk.** ⚠️

![HACS Badge](https://img.shields.io/badge/HACS-Custom-orange.svg)
## Supported Features

- Power consumption (W)
- Voltage (V)
- Current (mA)
- Relay state (ON/OFF) - Read only
- Auto-discovery of multiple devices

## Requirements

- Bluetooth adapter on Home Assistant host
- Home Assistant Bluetooth integration enabled

## Installation

### Install via HACS (Custom repositories)

https://hacs.xyz/docs/faq/custom_repositories

Enter the following information in the dialog and click `Add` button.

- Repository: `https://github.com/ryo-rm/ha-rs-btwattch2`
- Category: Integration

### Manual Install

1. Download this repository
2. Copy `custom_components/rs_btwattch2` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

```
{path_to_your_config}
├── configuration.yaml
└── custom_components
    └── rs_btwattch2
        ├── __init__.py
        ├── binary_sensor.py
        ├── config_flow.py
        ├── const.py
        ├── manifest.json
        ├── sensor.py
        ├── strings.json
        └── translations/
            ├── en.json
            └── ja.json
```

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **RS-BTWATTCH2**
4. Choose setup method:
   - **Auto-discover all devices** (recommended) - Automatically detect all devices
   - **Select from discovered devices** - Choose specific device
   - **Enter MAC address manually** - Input device MAC address

## Usage

After setup, the integration creates a device with the following entities:

- `sensor.*_power` (W)
- `sensor.*_voltage` (V)
- `sensor.*_current` (mA)
- `binary_sensor.*_relay` (ON/OFF, read-only)

Use these entities in dashboards, automations, or energy monitoring as needed.

## Development

### Prerequisites

- Python 3.12 or higher
- [uv](https://docs.astral.sh/uv/) - Python package manager

### Setup

```bash
# Clone repository
git clone https://github.com/ryo-rm/ha-rs-btwattch2.git
cd ha-rs-btwattch2a

# Install dev dependencies
uv sync --extra dev

# Ruff (lint/format)
uv run ruff check .
uv run ruff check --fix .
uv run ruff format .
```

## License

MIT License
