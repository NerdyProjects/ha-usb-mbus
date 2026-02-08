/*
 * Minimal Arduino.h stub for compiling MBusinoLib on a native (Linux) host.
 *
 * We deliberately do NOT define ARDUINO — this lets ArduinoJson operate in
 * its pure-C++ mode (no PROGMEM / Flash / Print / Stream dependencies).
 *
 * Instead we provide a String class with an implicit const-char* conversion
 * so that ArduinoJson can accept String values through its const-char*
 * adapter.
 */

#ifndef ARDUINO_H_STUB
#define ARDUINO_H_STUB

/* Explicitly disable Arduino-specific ArduinoJson features */
#define ARDUINOJSON_ENABLE_ARDUINO_STRING  0
#define ARDUINOJSON_ENABLE_ARDUINO_STREAM  0
#define ARDUINOJSON_ENABLE_ARDUINO_PRINT   0
#define ARDUINOJSON_ENABLE_PROGMEM         0

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <cstdio>
#include <cmath>
#include <string>
#include <algorithm>

/* ---- Arduino integer typedefs ------------------------------------------- */
using std::uint8_t;
using std::uint16_t;
using std::uint32_t;
using std::int8_t;
using std::int16_t;
using std::int32_t;
using std::int64_t;

/* ---- Minimal Arduino String class --------------------------------------- */

#define DEC 10
#define HEX 16
#define OCT  8
#define BIN  2

class String {
public:
    String() : _s() {}
    String(const char *s) : _s(s ? s : "") {}
    String(const String &o) : _s(o._s) {}
    String(String &&o) noexcept : _s(std::move(o._s)) {}

    /* Numeric constructors used by MBusinoLib: String(val, HEX) */
    String(int val, int base = 10)          { _fromLong(val, base); }
    String(unsigned int val, int base = 10) { _fromULong(val, base); }
    String(long val, int base = 10)         { _fromLong(val, base); }
    String(unsigned long val, int base = 10){ _fromULong(val, base); }
    String(double val, int decimalPlaces = 2) {
        char buf[64];
        std::snprintf(buf, sizeof(buf), "%.*f", decimalPlaces, val);
        _s = buf;
    }

    String &operator=(const String &o)  { _s = o._s; return *this; }
    String &operator=(String &&o) noexcept { _s = std::move(o._s); return *this; }
    String &operator=(const char *s)    { _s = s ? s : ""; return *this; }

    /* Concatenation */
    String operator+(const String &o) const { return String((_s + o._s).c_str()); }
    String operator+(const char *s) const   { return String((_s + (s ? s : "")).c_str()); }
    friend String operator+(const char *lhs, const String &rhs) {
        return String((std::string(lhs ? lhs : "") + rhs._s).c_str());
    }
    String &operator+=(const String &o) { _s += o._s; return *this; }
    String &operator+=(const char *s)   { if (s) _s += s; return *this; }

    const char *c_str()   const { return _s.c_str(); }
    unsigned int length() const { return (unsigned int)_s.size(); }

    /* Implicit conversion so ArduinoJson accepts String via const char* */
    operator const char*() const { return _s.c_str(); }

    bool operator==(const String &o) const { return _s == o._s; }
    bool operator==(const char *s)   const { return _s == (s ? s : ""); }
    friend bool operator==(const char *s, const String &o) { return o == s; }

private:
    std::string _s;

    void _fromLong(long val, int base) {
        char buf[68];
        if (base == 16)      std::snprintf(buf, sizeof(buf), "%lx", val);
        else if (base == 8)  std::snprintf(buf, sizeof(buf), "%lo", val);
        else                 std::snprintf(buf, sizeof(buf), "%ld", val);
        _s = buf;
    }
    void _fromULong(unsigned long val, int base) {
        char buf[68];
        if (base == 16)      std::snprintf(buf, sizeof(buf), "%lx", val);
        else if (base == 8)  std::snprintf(buf, sizeof(buf), "%lo", val);
        else                 std::snprintf(buf, sizeof(buf), "%lu", val);
        _s = buf;
    }
};

#endif /* ARDUINO_H_STUB */
