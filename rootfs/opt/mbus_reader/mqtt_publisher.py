"""MQTT publisher with Home Assistant auto-discovery.

Publishes sensor discovery configuration and state updates for each decoded
M-Bus data record so that Home Assistant automatically creates sensor
entities.

Discovery topic format:
    homeassistant/sensor/mbus_{device_id}/{object_id}/config

State topic format:
    mbus/{device_name}/state
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import paho.mqtt.client as mqtt

from .mbus_decoder import MBusRecord, get_device_class, get_state_class, MBusCode

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Convert a string to a slug suitable for MQTT topics / HA entity IDs."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9_]+", "_", text)
    text = text.strip("_")
    return text


# ---------------------------------------------------------------------------
# MqttPublisher
# ---------------------------------------------------------------------------

class MqttPublisher:
    """Manages MQTT connection and Home Assistant auto-discovery."""

    def __init__(
        self,
        host: str,
        port: int = 1883,
        username: str | None = None,
        password: str | None = None,
        discovery_prefix: str = "homeassistant",
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._discovery_prefix = discovery_prefix
        self._client: mqtt.Client | None = None
        self._discovered: set[str] = set()

    # -- lifecycle ----------------------------------------------------------

    def connect(self) -> None:
        """Connect to the MQTT broker."""
        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="mbus_reader",
        )
        if self._username:
            self._client.username_pw_set(self._username, self._password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

        logger.info("Connecting to MQTT broker %s:%d", self._host, self._port)
        self._client.connect(self._host, self._port)
        self._client.loop_start()

    def disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            logger.info("MQTT disconnected")

    # -- callbacks ----------------------------------------------------------

    @staticmethod
    def _on_connect(
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        rc: Any,
        properties: Any = None,
    ) -> None:
        if hasattr(rc, "value"):
            code = rc.value
        else:
            code = rc
        if code == 0:
            logger.info("MQTT connected")
        else:
            logger.error("MQTT connection failed: %s", rc)

    @staticmethod
    def _on_disconnect(
        client: mqtt.Client,
        userdata: Any,
        flags: Any = None,
        rc: Any = None,
        properties: Any = None,
    ) -> None:
        logger.warning("MQTT disconnected (rc=%s)", rc)

    # -- publishing ---------------------------------------------------------

    def publish_records(
        self,
        device_name: str,
        address: int,
        records: list[MBusRecord],
    ) -> None:
        """Publish discovery configs and state for all records of one device."""
        if not self._client:
            logger.error("MQTT not connected")
            return

        device_slug = _slugify(device_name)
        device_id = f"mbus_{address}"
        state_topic = f"mbus/{device_slug}/state"

        # Build the state payload (all values in one JSON object)
        state: dict[str, Any] = {}
        for i, rec in enumerate(records):
            key = self._unique_key(rec, i)
            if rec.value_scaled is not None:
                state[key] = round(rec.value_scaled, 6)
            elif rec.value_string is not None:
                state[key] = rec.value_string

        # Publish discovery configs (only once per unique key)
        for i, rec in enumerate(records):
            key = self._unique_key(rec, i)
            if key in self._discovered:
                continue
            self._publish_discovery(
                device_name=device_name,
                device_id=device_id,
                state_topic=state_topic,
                key=key,
                record=rec,
            )
            self._discovered.add(key)

        # Publish state
        payload = json.dumps(state)
        self._client.publish(state_topic, payload, qos=1, retain=True)
        logger.debug("Published state for %s: %s", device_slug, payload)

    def _publish_discovery(
        self,
        device_name: str,
        device_id: str,
        state_topic: str,
        key: str,
        record: MBusRecord,
    ) -> None:
        """Publish an HA MQTT discovery message for one sensor."""
        assert self._client is not None

        object_id = f"{device_id}_{key}"
        config_topic = (
            f"{self._discovery_prefix}/sensor/{device_id}/{key}/config"
        )

        config: dict[str, Any] = {
            "name": record.name.replace("_", " ").title(),
            "state_topic": state_topic,
            "value_template": "{{ " + f"value_json.{key}" + " }}",
            "unique_id": object_id,
            "object_id": object_id,
            "device": {
                "identifiers": [device_id],
                "name": device_name,
                "manufacturer": "M-Bus",
                "model": "M-Bus Device",
            },
        }

        if record.units:
            config["unit_of_measurement"] = record.units

        try:
            code = MBusCode(record.code)
        except ValueError:
            code = MBusCode.UNKNOWN_VIF

        dc = get_device_class(code)
        if dc:
            config["device_class"] = dc

        sc = get_state_class(code)
        if sc:
            config["state_class"] = sc

        payload = json.dumps(config)
        self._client.publish(config_topic, payload, qos=1, retain=True)
        logger.debug("Published discovery for %s: %s", object_id, config_topic)

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _unique_key(record: MBusRecord, index: int) -> str:
        """Build a unique state-dict key from a record."""
        parts = [_slugify(record.name)]
        if record.storage and record.storage > 0:
            parts.append(f"s{record.storage}")
        if record.tariff and record.tariff > 0:
            parts.append(f"t{record.tariff}")
        if record.sub_unit and record.sub_unit > 0:
            parts.append(f"su{record.sub_unit}")
        key = "_".join(parts)
        # Append index to guarantee uniqueness
        return f"{key}_{index}"
