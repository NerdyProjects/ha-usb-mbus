"""M-Bus serial communication — send commands and receive telegrams.

Handles the low-level M-Bus protocol over a USB serial adapter:
  - SND_NKE (slave initialisation)
  - REQ_UD2 (request user data class 2)
  - Telegram reception with frame validation

Reference: EN 13757-3, IEC 870-5
"""

from __future__ import annotations

import logging
import time

import serial

from .mbus_decoder import MBusDecodeError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# M-Bus frame constants
# ---------------------------------------------------------------------------
MBUS_FRAME_START = 0x68
MBUS_FRAME_STOP = 0x16
MBUS_SHORT_START = 0x10
MBUS_ACK = 0xE5

# Control bytes
MBUS_CTRL_SND_NKE = 0x40
MBUS_CTRL_REQ_UD2 = 0x7B  # FCB=1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _checksum(data: bytes) -> int:
    """Return M-Bus checksum (sum mod 256) over *data*."""
    return sum(data) & 0xFF


def _build_short_frame(ctrl: int, address: int) -> bytes:
    """Build an M-Bus short frame: 10h C A CS 16h."""
    cs = (ctrl + address) & 0xFF
    return bytes([MBUS_SHORT_START, ctrl, address, cs, MBUS_FRAME_STOP])


# ---------------------------------------------------------------------------
# MBusSerial — manages the serial connection
# ---------------------------------------------------------------------------

class MBusSerial:
    """Manages the serial connection to an M-Bus USB adapter."""

    def __init__(
        self,
        port: str,
        baudrate: int = 2400,
        timeout: float = 4.0,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._ser: serial.Serial | None = None

    # -- lifecycle ----------------------------------------------------------

    def open(self) -> None:
        """Open the serial port."""
        logger.info("Opening serial port %s @ %d baud", self._port, self._baudrate)
        self._ser = serial.Serial(
            port=self._port,
            baudrate=self._baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_ONE,
            timeout=self._timeout,
        )
        # Flush any stale data
        self._ser.reset_input_buffer()
        self._ser.reset_output_buffer()

    def close(self) -> None:
        """Close the serial port."""
        if self._ser and self._ser.is_open:
            self._ser.close()
            logger.info("Serial port closed")

    @property
    def is_open(self) -> bool:
        return self._ser is not None and self._ser.is_open

    # -- low-level I/O ------------------------------------------------------

    def _write(self, data: bytes) -> None:
        assert self._ser is not None
        logger.debug("TX: %s", data.hex(" "))
        self._ser.write(data)
        self._ser.flush()

    def _read(self, count: int) -> bytes:
        assert self._ser is not None
        data = self._ser.read(count)
        if data:
            logger.debug("RX: %s", data.hex(" "))
        return data

    def _read_byte(self) -> int | None:
        data = self._read(1)
        if not data:
            return None
        return data[0]

    # -- M-Bus commands -----------------------------------------------------

    def send_nke(self, address: int) -> bool:
        """Send SND_NKE and wait for ACK (0xE5).

        Returns True on success.
        """
        frame = _build_short_frame(MBUS_CTRL_SND_NKE, address)
        self._write(frame)
        resp = self._read_byte()
        if resp == MBUS_ACK:
            logger.debug("SND_NKE to address %d acknowledged", address)
            return True
        logger.warning(
            "SND_NKE to address %d: expected ACK (0xE5), got %s",
            address,
            f"0x{resp:02X}" if resp is not None else "timeout",
        )
        return False

    def request_data(self, address: int) -> bytes | None:
        """Send REQ_UD2 and read the response long frame.

        Returns the complete telegram bytes (including framing) or None on
        failure.
        """
        frame = _build_short_frame(MBUS_CTRL_REQ_UD2, address)
        self._write(frame)

        # Wait a moment for the slave to respond
        time.sleep(0.1)

        return self._receive_long_frame()

    # -- Frame reception ----------------------------------------------------

    def _receive_long_frame(self) -> bytes | None:
        """Read and validate a long-frame M-Bus telegram from the bus.

        Returns the full frame bytes or None on timeout / error.
        """
        # Look for start byte 0x68
        start = self._read_byte()
        if start is None:
            logger.debug("Timeout waiting for response")
            return None
        if start == MBUS_ACK:
            logger.debug("Received single-byte ACK instead of long frame")
            return None
        if start != MBUS_FRAME_START:
            logger.warning("Unexpected start byte: 0x%02X", start)
            return None

        # Read L, L, 0x68
        header = self._read(3)
        if len(header) < 3:
            logger.warning("Incomplete header")
            return None
        length1, length2, start2 = header[0], header[1], header[2]
        if length1 != length2:
            logger.warning("Length mismatch: %d != %d", length1, length2)
            return None
        if start2 != MBUS_FRAME_START:
            logger.warning("Second start byte missing")
            return None

        # Read payload (C + A + CI + user data) + checksum + stop
        remaining = length1 + 2  # payload + CS + stop byte
        body = self._read(remaining)
        if len(body) < remaining:
            logger.warning(
                "Incomplete body: expected %d bytes, got %d", remaining, len(body)
            )
            return None

        # Validate stop byte
        if body[-1] != MBUS_FRAME_STOP:
            logger.warning("Invalid stop byte: 0x%02X", body[-1])
            return None

        # Validate checksum
        payload = body[:length1]
        cs_expected = _checksum(payload)
        cs_actual = body[length1]
        if cs_expected != cs_actual:
            logger.warning(
                "Checksum mismatch: expected 0x%02X, got 0x%02X",
                cs_expected,
                cs_actual,
            )
            return None

        # Assemble complete telegram
        telegram = bytes([MBUS_FRAME_START, length1, length2, MBUS_FRAME_START]) + body
        logger.debug("Received valid telegram (%d bytes)", len(telegram))
        return telegram
