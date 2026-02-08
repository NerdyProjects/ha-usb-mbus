# Home Assistant Add-on: M-Bus Reader

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

Read M-Bus (Meter-Bus) sensors via a USB serial adapter and expose them
as Home Assistant sensors through MQTT auto-discovery.

## About

This add-on connects to M-Bus slave devices through a USB-to-M-Bus adapter
(serial converter) and periodically polls configured meter addresses.
Decoded sensor values are published to Home Assistant via MQTT auto-discovery,
so sensors appear automatically in the HA UI.

The M-Bus protocol decoder is ported from the
[MBusinoLib](https://github.com/Zeppelin500/MBusinoLib/) Arduino library.

## Installation

### 1. Copy (or clone) the repository

Place this repository on the machine running Home Assistant OS / Supervised,
or push it to a Git hosting service (GitHub, GitLab, …).

### 2. Add the repository to Home Assistant

1. Open Home Assistant → **Settings** → **Add-ons** → **Add-on Store**.
2. Click the **⋮** menu (top-right) → **Repositories**.
3. Enter the URL of **this** repository (the parent directory that contains
   the `ha/` folder). For a local checkout the path looks like:
   ```
   /addons/ha-mbus
   ```
   For a remote Git repository:
   ```
   https://github.com/<your-user>/ha-mbus
   ```
4. Click **Add** → **Close**.

### 3. Install the add-on

1. Back in the Add-on Store you should now see **M-Bus Reader** listed under
   your local / custom repository.
2. Click on it and press **Install**.

### 4. Configure

1. Go to the **Configuration** tab of the add-on.
2. Set the serial port for your USB-to-M-Bus adapter (e.g. `/dev/ttyUSB0`).
3. Add one or more M-Bus devices with their primary address and a friendly
   name:
   ```yaml
   serial_port: /dev/ttyUSB0
   baud_rate: 2400
   poll_interval: 120
   devices:
     - address: 1
       name: Heat Meter Basement
     - address: 5
       name: Water Meter Kitchen
   ```
4. Click **Save**.

### 5. Start

1. Press **Start** on the **Info** tab.
2. Check the **Log** tab to verify communication with your M-Bus devices.
3. The decoded sensor values appear automatically in Home Assistant via MQTT
   auto-discovery — look for entities named
   `sensor.mbus_<device_name>_<value_name>`.

## Prerequisites

- **USB-to-M-Bus adapter** — a serial converter such as the Mikroe M-Bus
  Slave click wired to one or more M-Bus slave devices.
- **MQTT broker** — the Mosquitto broker add-on or an external MQTT broker
  configured in Home Assistant under **Settings → Devices & Services → MQTT**.

## Documentation

See [DOCS.md](DOCS.md) for the full configuration reference.

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg
