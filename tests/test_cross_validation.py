"""Cross-validation: compare Python decoder output against the original C++
MBusinoLib decoder compiled natively.

The test compiles ``decode_telegram.cpp`` (which links against the real
MBusinoLib) into a temporary binary, runs it on the Sensostar U telegram, and
compares every decoded record field-by-field with the Python decoder.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest

# Allow importing from the addon package tree
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), "..", "rootfs", "opt")
)

from mbus_reader.mbus_decoder import decode_telegram

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_CROSS_DIR = os.path.join(_HERE, "cross_validation")
_CPP_SOURCE = os.path.join(_CROSS_DIR, "decode_telegram.cpp")
_MBUSINOLIB_SRC = os.path.join(_HERE, "..", "..", "MBusinoLib", "src")
_BINARY = os.path.join(_CROSS_DIR, "decode_telegram")

# The same telegram as in test_mbus_decoder.py
SENSOSTAR_U_TELEGRAM = bytes([
    0x68, 0xC1, 0xC1, 0x68,
    0x08, 0x00,
    0x72,
    0x09, 0x34, 0x75, 0x73,
    0xC5, 0x14,
    0x00, 0x0D,
    0x43, 0x00, 0x00, 0x00,
    0x04, 0x78, 0x41, 0x63, 0x65, 0x04,
    0x04, 0x06, 0xAA, 0x29, 0x00, 0x00,
    0x04, 0x13, 0x40, 0xA1, 0x75, 0x00,
    0x04, 0x2B, 0x00, 0x00, 0x00, 0x00,
    0x14, 0x2B, 0x3C, 0xF3, 0x00, 0x00,
    0x04, 0x3B, 0x48, 0x06, 0x00, 0x00,
    0x14, 0x3B, 0x4E, 0x0E, 0x00, 0x00,
    0x02, 0x5B, 0x19, 0x00,
    0x02, 0x5F, 0x19, 0x00,
    0x02, 0x61, 0xFA, 0xFF,
    0x02, 0x23, 0xAC, 0x08,
    0x04, 0x6D, 0x03, 0x2A, 0xF1, 0x2A,
    0x44, 0x06, 0x92, 0x0C, 0x00, 0x00,
    0x44, 0x13, 0x2D, 0x9B, 0x1C, 0x00,
    0x42, 0x6C, 0xDF, 0x2C,
    0x01, 0xFD, 0x17, 0x00,
    0x03, 0xFD, 0x0C, 0x05, 0x00, 0x00,
    0x84, 0x10, 0x06, 0x1A, 0x00, 0x00, 0x00,
    0xC4, 0x10, 0x06, 0x05, 0x00, 0x00, 0x00,
    0x84, 0x20, 0x06, 0x00, 0x00, 0x00, 0x00,
    0xC4, 0x20, 0x06, 0x00, 0x00, 0x00, 0x00,
    0x84, 0x30, 0x06, 0x00, 0x00, 0x00, 0x00,
    0xC4, 0x30, 0x06, 0x00, 0x00, 0x00, 0x00,
    0x84, 0x40, 0x13, 0x00, 0x00, 0x00, 0x00,
    0xC4, 0x40, 0x13, 0x00, 0x00, 0x00, 0x00,
    0x84, 0x80, 0x40, 0x13, 0x00, 0x00, 0x00, 0x00,
    0xC4, 0x80, 0x40, 0x13, 0x00, 0x00, 0x00, 0x00,
    0x84, 0xC0, 0x40, 0x13, 0x00, 0x00, 0x00, 0x00,
    0xC4, 0xC0, 0x40, 0x13, 0x00, 0x00, 0x00, 0x00,
    0x75, 0x16,
])


def _compile_cpp_decoder() -> str:
    """Compile the C++ decoder if the binary does not exist or is outdated."""
    # Check if rebuild is needed
    sources = [
        _CPP_SOURCE,
        os.path.join(_CROSS_DIR, "Arduino.h"),
        os.path.join(_MBUSINOLIB_SRC, "MBusinoLib.cpp"),
        os.path.join(_MBUSINOLIB_SRC, "MBusinoLib.h"),
    ]
    if os.path.exists(_BINARY):
        bin_mtime = os.path.getmtime(_BINARY)
        if all(os.path.getmtime(s) <= bin_mtime for s in sources if os.path.exists(s)):
            return _BINARY

    cmd = [
        "g++", "-std=c++17",
        "-I" + _CROSS_DIR,
        "-I" + _MBUSINOLIB_SRC,
        _CPP_SOURCE,
        os.path.join(_MBUSINOLIB_SRC, "MBusinoLib.cpp"),
        "-o", _BINARY,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"C++ compilation failed:\n{result.stderr}")
    return _BINARY


def _run_cpp_decoder() -> list[dict]:
    """Compile (if needed) and run the C++ decoder, returning parsed JSON."""
    binary = _compile_cpp_decoder()
    result = subprocess.run([binary], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"C++ decoder failed:\n{result.stderr}")
    return json.loads(result.stdout)


def _run_python_decoder() -> list[dict]:
    """Decode the telegram with the Python decoder and return as dicts."""
    _num_fields, records = decode_telegram(SENSOSTAR_U_TELEGRAM)
    out = []
    for r in records:
        d: dict = {"name": r.name, "value_scaled": r.value_scaled}
        if r.units:
            d["units"] = r.units
        if r.storage is not None and r.storage > 0:
            d["storage"] = r.storage
        if r.tariff is not None and r.tariff > 0:
            d["tariff"] = r.tariff
        if r.sub_unit is not None and r.sub_unit > 0:
            d["subUnit"] = r.sub_unit
        out.append(d)
    return out


class TestCrossValidation(unittest.TestCase):
    """Compare every record from the C++ and Python decoders."""

    @classmethod
    def setUpClass(cls):
        cls.cpp_records = _run_cpp_decoder()
        cls.py_records = _run_python_decoder()

    def test_same_record_count(self):
        self.assertEqual(len(self.cpp_records), len(self.py_records),
                         "C++ and Python decoders produce different number of records")

    def test_record_names_match(self):
        cpp_names = [r["name"] for r in self.cpp_records]
        py_names = [r["name"] for r in self.py_records]
        self.assertEqual(cpp_names, py_names)

    def test_record_units_match(self):
        for i, (cpp, py) in enumerate(zip(self.cpp_records, self.py_records)):
            with self.subTest(i=i, name=cpp.get("name")):
                self.assertEqual(cpp.get("units", ""), py.get("units", ""))

    def test_record_values_match(self):
        """Values must match within a small relative tolerance.

        Note: time_point records encode datetimes as 12-digit integers
        (YYYYMMDDhhmm).  Because C++ ``double`` has ~15-16 significant
        digits, the least-significant digits may be lost.  We therefore
        use a *relative* tolerance (1e-8) for large values.
        """
        for i, (cpp, py) in enumerate(zip(self.cpp_records, self.py_records)):
            with self.subTest(i=i, name=cpp.get("name")):
                cv = float(cpp["value_scaled"])
                pv = float(py["value_scaled"])
                if cv == 0.0 and pv == 0.0:
                    continue
                # Use relative tolerance for large values (e.g. time_point)
                if abs(cv) > 1e6:
                    denom = max(abs(cv), abs(pv))
                    self.assertAlmostEqual(
                        cv / denom, pv / denom, places=5,
                        msg=f"Record {i} ({cpp.get('name')}): "
                            f"C++={cv}, Python={pv}")
                else:
                    self.assertAlmostEqual(
                        cv, pv, places=3,
                        msg=f"Record {i} ({cpp.get('name')})")

    def test_record_storage_match(self):
        for i, (cpp, py) in enumerate(zip(self.cpp_records, self.py_records)):
            with self.subTest(i=i, name=cpp.get("name")):
                self.assertEqual(cpp.get("storage", 0), py.get("storage", 0))

    def test_record_tariff_match(self):
        for i, (cpp, py) in enumerate(zip(self.cpp_records, self.py_records)):
            with self.subTest(i=i, name=cpp.get("name")):
                self.assertEqual(cpp.get("tariff", 0), py.get("tariff", 0))

    def test_record_subunit_match(self):
        for i, (cpp, py) in enumerate(zip(self.cpp_records, self.py_records)):
            with self.subTest(i=i, name=cpp.get("name")):
                self.assertEqual(cpp.get("subUnit", 0), py.get("subUnit", 0))


if __name__ == "__main__":
    unittest.main()
