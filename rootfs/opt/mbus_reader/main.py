"""M-Bus Reader for Home Assistant — main application loop.

Reads configuration, connects to the serial bus and MQTT broker, polls
M-Bus devices at the configured interval, decodes the telegrams and
publishes sensor data via MQTT auto-discovery.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

from .mbus_decoder import MBusDecodeError, decode_telegram
from .mbus_serial import MBusSerial
from .mqtt_publisher import MqttPublisher

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_OPTIONS_PATH = Path("/data/options.json")


def _load_options() -> dict[str, Any]:
    """Load add-on options from the HA Supervisor-provided JSON file."""
    if _OPTIONS_PATH.exists():
        return json.loads(_OPTIONS_PATH.read_text())  # type: ignore[no-any-return]
    # Fallback: environment variables for local testing
    return {
        "serial_port": os.getenv("MBUS_SERIAL_PORT", "/dev/ttyUSB0"),
        "baud_rate": int(os.getenv("MBUS_BAUD_RATE", "2400")),
        "poll_interval": int(os.getenv("MBUS_POLL_INTERVAL", "120")),
        "devices": json.loads(os.getenv("MBUS_DEVICES", "[]")),
    }


def _get_mqtt_config(options: dict[str, Any]) -> dict[str, Any]:
    """Resolve MQTT connection details.

    Tries the HA Supervisor services API first, then falls back to explicit
    addon options, and finally to environment variables.
    """
    # 1. Explicit options
    host = options.get("mqtt_host", "")
    if host:
        return {
            "host": host,
            "port": int(options.get("mqtt_port", 1883)),
            "username": options.get("mqtt_user", ""),
            "password": options.get("mqtt_password", ""),
        }

    # 2. Supervisor service discovery
    supervisor_token = os.getenv("SUPERVISOR_TOKEN")
    if supervisor_token:
        try:
            import urllib.request

            req = urllib.request.Request(
                "http://supervisor/services/mqtt",
                headers={"Authorization": f"Bearer {supervisor_token}"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())["data"]
                return {
                    "host": data["host"],
                    "port": int(data["port"]),
                    "username": data.get("username", ""),
                    "password": data.get("password", ""),
                }
        except Exception:
            logger.warning("Could not discover MQTT via Supervisor API")

    # 3. Environment variables (local testing)
    return {
        "host": os.getenv("MQTT_HOST", "localhost"),
        "port": int(os.getenv("MQTT_PORT", "1883")),
        "username": os.getenv("MQTT_USER", ""),
        "password": os.getenv("MQTT_PASSWORD", ""),
    }


# ---------------------------------------------------------------------------
# Polling loop
# ---------------------------------------------------------------------------

_running = True


def _handle_signal(sig: int, _frame: Any) -> None:
    global _running
    logger.info("Received signal %d — shutting down", sig)
    _running = False


def _poll_device(
    bus: MBusSerial,
    publisher: MqttPublisher,
    address: int,
    name: str,
) -> None:
    """Poll a single M-Bus device: request data, decode, publish."""
    logger.info("Polling device '%s' at address %d", name, address)
    telegram = bus.request_data(address)
    if telegram is None:
        logger.warning("No response from address %d (%s)", address, name)
        return

    try:
        slave_addr, records = decode_telegram(telegram)
    except MBusDecodeError as exc:
        logger.error("Decode error for address %d (%s): %s", address, name, exc)
        return

    if not records:
        logger.warning("No data records decoded from address %d (%s)", address, name)
        return

    logger.info(
        "Decoded %d records from address %d (%s)", len(records), address, name
    )
    publisher.publish_records(name, address, records)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run() -> None:
    """Main entry point — called by the service runner script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Load configuration
    options = _load_options()
    serial_port: str = options["serial_port"]
    baud_rate: int = int(options["baud_rate"])
    poll_interval: int = int(options["poll_interval"])
    devices: list[dict[str, Any]] = options.get("devices", [])

    if not devices:
        logger.error("No M-Bus devices configured — exiting")
        sys.exit(1)

    logger.info(
        "Configuration: port=%s baud=%d interval=%ds devices=%d",
        serial_port,
        baud_rate,
        poll_interval,
        len(devices),
    )

    # Connect MQTT
    mqtt_cfg = _get_mqtt_config(options)
    publisher = MqttPublisher(
        host=mqtt_cfg["host"],
        port=mqtt_cfg["port"],
        username=mqtt_cfg.get("username") or None,
        password=mqtt_cfg.get("password") or None,
    )
    publisher.connect()

    # Open serial port
    bus = MBusSerial(port=serial_port, baudrate=baud_rate)
    try:
        bus.open()
    except Exception as exc:
        logger.error("Failed to open serial port %s: %s", serial_port, exc)
        publisher.disconnect()
        sys.exit(1)

    # Initialise all slaves with SND_NKE
    for dev in devices:
        addr = int(dev["address"])
        if not bus.send_nke(addr):
            logger.warning("SND_NKE failed for address %d — will retry on poll", addr)
        time.sleep(0.5)

    # Main loop
    global _running
    try:
        while _running:
            for dev in devices:
                if not _running:
                    break
                addr = int(dev["address"])
                name = dev.get("name", f"MBus_{addr}")
                try:
                    _poll_device(bus, publisher, addr, name)
                except Exception:
                    logger.exception(
                        "Unexpected error polling address %d (%s)", addr, name
                    )
                # Brief pause between devices to avoid bus contention
                time.sleep(1.0)

            # Wait for the next poll cycle
            logger.info("Sleeping %d seconds until next poll cycle", poll_interval)
            for _ in range(poll_interval):
                if not _running:
                    break
                time.sleep(1)
    finally:
        bus.close()
        publisher.disconnect()
        logger.info("M-Bus Reader stopped")
