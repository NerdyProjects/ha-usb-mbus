# Home Assistant Add-on: M-Bus Reader

## Prerequisites

- A USB-to-M-Bus adapter (serial converter), e.g. Mikroe M-Bus Slave click
- The MQTT integration configured in Home Assistant (Mosquitto broker add-on or external)
- M-Bus slave devices wired to the bus

## Configuration

### Option: `serial_port`

The serial device path for the USB M-Bus adapter.
Common values: `/dev/ttyUSB0`, `/dev/ttyACM0`, `/dev/serial/by-id/...`

### Option: `baud_rate`

Serial baud rate. M-Bus standard is **2400** (default).

### Option: `poll_interval`

Interval in seconds between polling cycles. Default: **120**.

### Option: `devices`

List of M-Bus slave devices to poll:

| Key       | Type   | Description                                    |
|-----------|--------|------------------------------------------------|
| `address` | int    | M-Bus primary address (0–250)                  |
| `name`    | string | Friendly name, used for MQTT topics and HA IDs |

### Example configuration

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

## How it works

1. On start, the add-on sends **SND_NKE** to each configured address to
   initialize communication.
2. Every `poll_interval` seconds it sends **REQ_UD2** to each device and
   reads the response telegram.
3. The telegram payload is decoded (DIF/VIF/data records) into named sensor
   values with units.
4. MQTT auto-discovery messages are published so Home Assistant creates
   sensor entities automatically.
5. Sensor state updates are published on every poll cycle.

## Sensor naming

Sensors are created with entity IDs following the pattern:

```
sensor.mbus_<device_name>_<value_name>
```

For example, a heat meter named "basement" with a flow temperature reading
becomes `sensor.mbus_basement_flow_temperature`.
