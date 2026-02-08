"""Tests for the M-Bus decoder using the Sensostar U example telegram.

The test data is taken directly from MBusinoLib/examples/MbusinoLibExample.ino.
"""

from __future__ import annotations

import sys
import os
import unittest

# Allow importing from the addon package tree without installing
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "rootfs", "opt")
)

from mbus_reader.mbus_decoder import (
    MBusCode,
    MBusDecodeError,
    MBusRecord,
    decode,
    decode_telegram,
    get_code_name,
    get_code_units,
    get_device_class,
    get_state_class,
)


# ---------------------------------------------------------------------------
# Sensostar U telegram from MbusinoLibExample.ino
# ---------------------------------------------------------------------------

SENSOSTAR_U_TELEGRAM = bytes([
    0x68, 0xC1, 0xC1, 0x68,                         # start + length
    0x08, 0x00,                                       # C, A
    0x72,                                             # CI
    0x09, 0x34, 0x75, 0x73,                           # ID
    0xC5, 0x14,                                       # manufacturer
    0x00, 0x0D,                                       # version, device type
    0x43, 0x00, 0x00, 0x00,                           # access#, status, signature
    # --- Variable data records start here (offset 0x13 = 19) ---
    0x04, 0x78, 0x41, 0x63, 0x65, 0x04,              # fab_number
    0x04, 0x06, 0xAA, 0x29, 0x00, 0x00,              # energy (Wh)
    0x04, 0x13, 0x40, 0xA1, 0x75, 0x00,              # volume (m³)
    0x04, 0x2B, 0x00, 0x00, 0x00, 0x00,              # power (W) current
    0x14, 0x2B, 0x3C, 0xF3, 0x00, 0x00,              # power (W) max
    0x04, 0x3B, 0x48, 0x06, 0x00, 0x00,              # volume_flow (m³/h)
    0x14, 0x3B, 0x4E, 0x0E, 0x00, 0x00,              # volume_flow (m³/h) max
    0x02, 0x5B, 0x19, 0x00,                           # flow_temperature (°C)
    0x02, 0x5F, 0x19, 0x00,                           # return_temperature (°C)
    0x02, 0x61, 0xFA, 0xFF,                           # temperature_diff (K)
    0x02, 0x23, 0xAC, 0x08,                           # on_time (days)
    0x04, 0x6D, 0x03, 0x2A, 0xF1, 0x2A,              # time_point (datetime)
    0x44, 0x06, 0x92, 0x0C, 0x00, 0x00,              # energy (Wh) storage=1
    0x44, 0x13, 0x2D, 0x9B, 0x1C, 0x00,              # volume (m³) storage=1
    0x42, 0x6C, 0xDF, 0x2C,                           # time_point (date) storage=1
    0x01, 0xFD, 0x17, 0x00,                           # error_flags
    0x03, 0xFD, 0x0C, 0x05, 0x00, 0x00,              # model_version
    0x84, 0x10, 0x06, 0x1A, 0x00, 0x00, 0x00,        # energy tariff=1
    0xC4, 0x10, 0x06, 0x05, 0x00, 0x00, 0x00,        # energy tariff=1 storage=1
    0x84, 0x20, 0x06, 0x00, 0x00, 0x00, 0x00,        # energy tariff=2
    0xC4, 0x20, 0x06, 0x00, 0x00, 0x00, 0x00,        # energy tariff=2 storage=1
    0x84, 0x30, 0x06, 0x00, 0x00, 0x00, 0x00,        # energy tariff=3
    0xC4, 0x30, 0x06, 0x00, 0x00, 0x00, 0x00,        # energy tariff=3 storage=1
    0x84, 0x40, 0x13, 0x00, 0x00, 0x00, 0x00,        # volume tariff=1
    0xC4, 0x40, 0x13, 0x00, 0x00, 0x00, 0x00,        # volume tariff=1 storage=1
    0x84, 0x80, 0x40, 0x13, 0x00, 0x00, 0x00, 0x00,  # volume tariff=2
    0xC4, 0x80, 0x40, 0x13, 0x00, 0x00, 0x00, 0x00,  # volume tariff=2 storage=1
    0x84, 0xC0, 0x40, 0x13, 0x00, 0x00, 0x00, 0x00,  # volume tariff=3
    0xC4, 0xC0, 0x40, 0x13, 0x00, 0x00, 0x00, 0x00,  # volume tariff=3 storage=1
    0x75,                                              # checksum
    0x16,                                              # stop
])

START_ADDRESS = 0x13  # offset where variable data records begin


class TestDecodePayload(unittest.TestCase):
    """Test decode() with the raw payload (starting at DIF bytes)."""

    def setUp(self) -> None:
        payload_start = START_ADDRESS
        payload_end = len(SENSOSTAR_U_TELEGRAM) - 2  # strip CS + stop
        self.payload = SENSOSTAR_U_TELEGRAM[payload_start:payload_end]
        self.records = decode(self.payload)

    def test_record_count(self) -> None:
        """The Sensostar U telegram should yield 29 data records."""
        self.assertEqual(len(self.records), 29)

    # -- individual records -------------------------------------------------

    def test_fab_number(self) -> None:
        """Record 0: fabrication number = 73753409 (0x04656341 LE)."""
        rec = self.records[0]
        self.assertEqual(rec.name, "fab_number")
        # 0x41,0x63,0x65,0x04 little-endian → 0x04656341 = 73753409
        self.assertAlmostEqual(rec.value_scaled, 73753409.0, places=0)

    def test_energy_wh(self) -> None:
        """Record 1: energy = 10666 * 10^3 = 10666000 Wh."""
        rec = self.records[1]
        self.assertEqual(rec.name, "energy")
        self.assertEqual(rec.units, "Wh")
        self.assertAlmostEqual(rec.value_scaled, 10666000.0, places=0)

    def test_volume_m3(self) -> None:
        """Record 2: volume ≈ 7708.992 m³."""
        rec = self.records[2]
        self.assertEqual(rec.name, "volume")
        self.assertEqual(rec.units, "m³")
        self.assertAlmostEqual(rec.value_scaled, 7708.992, places=2)

    def test_power_current(self) -> None:
        """Record 3: power (current) = 0 W."""
        rec = self.records[3]
        self.assertEqual(rec.name, "power")
        self.assertEqual(rec.units, "W")
        self.assertAlmostEqual(rec.value_scaled, 0.0, places=0)

    def test_power_max(self) -> None:
        """Record 4: power (max) = 62268 W."""
        rec = self.records[4]
        self.assertEqual(rec.name, "power_max")
        self.assertEqual(rec.units, "W")
        self.assertAlmostEqual(rec.value_scaled, 62268.0, places=0)

    def test_volume_flow_current(self) -> None:
        """Record 5: volume_flow = 1.608 m³/h."""
        rec = self.records[5]
        self.assertEqual(rec.name, "volume_flow")
        self.assertEqual(rec.units, "m³/h")
        self.assertAlmostEqual(rec.value_scaled, 1.608, places=3)

    def test_volume_flow_max(self) -> None:
        """Record 6: volume_flow max = 3.662 m³/h."""
        rec = self.records[6]
        self.assertEqual(rec.name, "volume_flow_max")
        self.assertAlmostEqual(rec.value_scaled, 3.662, places=3)

    def test_flow_temperature(self) -> None:
        """Record 7: flow_temperature = 25.0 °C."""
        rec = self.records[7]
        self.assertEqual(rec.name, "flow_temperature")
        self.assertEqual(rec.units, "°C")
        self.assertAlmostEqual(rec.value_scaled, 25.0, places=1)

    def test_return_temperature(self) -> None:
        """Record 8: return_temperature = 25.0 °C."""
        rec = self.records[8]
        self.assertEqual(rec.name, "return_temperature")
        self.assertAlmostEqual(rec.value_scaled, 25.0, places=1)

    def test_temperature_diff(self) -> None:
        """Record 9: temperature_diff = -0.06 K."""
        rec = self.records[9]
        self.assertEqual(rec.name, "temperature_diff")
        self.assertEqual(rec.units, "K")
        self.assertAlmostEqual(rec.value_scaled, -0.06, places=2)

    def test_on_time_days(self) -> None:
        """Record 10: on_time = 2220 days."""
        rec = self.records[10]
        self.assertEqual(rec.name, "on_time")
        self.assertEqual(rec.units, "d")
        self.assertAlmostEqual(rec.value_scaled, 2220.0, places=0)

    def test_time_point_datetime(self) -> None:
        """Record 11: time_point datetime = 2023-10-17 10:03:00."""
        rec = self.records[11]
        self.assertEqual(rec.name, "time_point")
        self.assertIsNotNone(rec.value_string)
        self.assertIn("2023", rec.value_string)
        self.assertIn("10:03", rec.value_string)

    def test_energy_storage1(self) -> None:
        """Record 12: energy (storage 1) = 3218000 Wh."""
        rec = self.records[12]
        self.assertEqual(rec.name, "energy")
        self.assertEqual(rec.storage, 1)
        self.assertAlmostEqual(rec.value_scaled, 3218000.0, places=0)

    def test_volume_storage1(self) -> None:
        """Record 13: volume (storage 1) ≈ 1874.733 m³."""
        rec = self.records[13]
        self.assertEqual(rec.name, "volume")
        self.assertEqual(rec.storage, 1)
        self.assertAlmostEqual(rec.value_scaled, 1874.733, places=2)

    def test_time_point_date_storage1(self) -> None:
        """Record 14: time_point date (storage 1) = 2022-12-31."""
        rec = self.records[14]
        self.assertEqual(rec.name, "time_point")
        self.assertEqual(rec.storage, 1)
        self.assertIsNotNone(rec.value_string)
        self.assertIn("2022", rec.value_string)
        self.assertIn("12-31", rec.value_string)

    def test_error_flags(self) -> None:
        """Record 15: error_flags = 0."""
        rec = self.records[15]
        self.assertEqual(rec.name, "error_flags")
        self.assertAlmostEqual(rec.value_scaled, 0.0, places=0)

    def test_model_version(self) -> None:
        """Record 16: model_version = 5."""
        rec = self.records[16]
        self.assertEqual(rec.name, "model_version")
        self.assertAlmostEqual(rec.value_scaled, 5.0, places=0)

    def test_energy_tariff1(self) -> None:
        """Record 17: energy tariff=1 = 26000 Wh."""
        rec = self.records[17]
        self.assertEqual(rec.name, "energy")
        self.assertEqual(rec.tariff, 1)
        self.assertAlmostEqual(rec.value_scaled, 26000.0, places=0)


class TestDecodeTelegram(unittest.TestCase):
    """Test decode_telegram() with the full framed telegram."""

    def test_address_extraction(self) -> None:
        """Slave address should be extracted from the frame header."""
        addr, records = decode_telegram(SENSOSTAR_U_TELEGRAM)
        self.assertEqual(addr, 0x00)
        self.assertGreater(len(records), 0)

    def test_checksum_validation(self) -> None:
        """A corrupted checksum should raise MBusDecodeError."""
        bad = bytearray(SENSOSTAR_U_TELEGRAM)
        bad[-2] = 0x00  # corrupt checksum
        with self.assertRaises(MBusDecodeError):
            decode_telegram(bad)

    def test_short_telegram(self) -> None:
        """Too-short data should raise MBusDecodeError."""
        with self.assertRaises(MBusDecodeError):
            decode_telegram(b"\x68\x01")


class TestCodeMappings(unittest.TestCase):
    """Verify the code → name / units / device_class / state_class helpers."""

    def test_energy_wh_name(self) -> None:
        self.assertEqual(get_code_name(MBusCode.ENERGY_WH), "energy")

    def test_energy_wh_units(self) -> None:
        self.assertEqual(get_code_units(MBusCode.ENERGY_WH), "Wh")

    def test_energy_wh_device_class(self) -> None:
        self.assertEqual(get_device_class(MBusCode.ENERGY_WH), "energy")

    def test_energy_wh_state_class(self) -> None:
        self.assertEqual(get_state_class(MBusCode.ENERGY_WH), "total")

    def test_flow_temp_measurement(self) -> None:
        self.assertEqual(get_state_class(MBusCode.FLOW_TEMPERATURE_C), "measurement")

    def test_volume_m3_units(self) -> None:
        self.assertEqual(get_code_units(MBusCode.VOLUME_M3), "m³")


class TestRecordToDict(unittest.TestCase):
    """Ensure MBusRecord.to_dict() serialises correctly."""

    def test_basic_record(self) -> None:
        rec = MBusRecord(
            vif_hex="0x6",
            code=int(MBusCode.ENERGY_WH),
            name="energy",
            value_scaled=10666000.0,
            units="Wh",
        )
        d = rec.to_dict()
        self.assertEqual(d["name"], "energy")
        self.assertAlmostEqual(d["value_scaled"], 10666000.0)
        self.assertEqual(d["units"], "Wh")
        self.assertNotIn("storage", d)
        self.assertNotIn("tariff", d)

    def test_record_with_storage_tariff(self) -> None:
        rec = MBusRecord(
            vif_hex="0x6",
            code=int(MBusCode.ENERGY_WH),
            name="energy",
            value_scaled=5000.0,
            units="Wh",
            storage=1,
            tariff=2,
        )
        d = rec.to_dict()
        self.assertEqual(d["storage"], 1)
        self.assertEqual(d["tariff"], 2)


if __name__ == "__main__":
    unittest.main()
