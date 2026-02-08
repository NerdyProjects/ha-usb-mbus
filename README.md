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

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg
