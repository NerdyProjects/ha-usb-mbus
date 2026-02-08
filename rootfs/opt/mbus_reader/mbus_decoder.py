"""M-Bus telegram decoder — pure-Python port of MBusinoLib.

Decodes M-Bus variable data record blocks (DIF/VIF/data) into a list of
dictionaries suitable for JSON serialisation and Home Assistant sensor
publishing.

Reference: EN 13757-3 / MBusinoLib by Zeppelin500
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


# ---------------------------------------------------------------------------
# M-Bus VIF code identifiers (mirrors the C++ MBUS_CODE enum)
# ---------------------------------------------------------------------------

class MBusCode(IntEnum):
    UNKNOWN_VIF = 0
    ENERGY_WH = 1
    ENERGY_J = 2
    VOLUME_M3 = 3
    MASS_KG = 4
    ON_TIME_S = 5
    ON_TIME_MIN = 6
    ON_TIME_H = 7
    ON_TIME_DAYS = 8
    OPERATING_TIME_S = 9
    OPERATING_TIME_MIN = 10
    OPERATING_TIME_H = 11
    OPERATING_TIME_DAYS = 12
    POWER_W = 13
    POWER_J_H = 14
    VOLUME_FLOW_M3_H = 15
    VOLUME_FLOW_M3_MIN = 16
    VOLUME_FLOW_M3_S = 17
    MASS_FLOW_KG_H = 18
    FLOW_TEMPERATURE_C = 19
    RETURN_TEMPERATURE_C = 20
    TEMPERATURE_DIFF_K = 21
    EXTERNAL_TEMPERATURE_C = 22
    PRESSURE_BAR = 23
    TIME_POINT_DATE = 24
    TIME_POINT_DATETIME = 25
    AVG_DURATION_S = 26
    AVG_DURATION_MIN = 27
    AVG_DURATION_H = 28
    AVG_DURATION_DAYS = 29
    ACTUAL_DURATION_S = 30
    ACTUAL_DURATION_MIN = 31
    ACTUAL_DURATION_H = 32
    ACTUAL_DURATION_DAYS = 33
    FABRICATION_NUMBER = 34
    BUS_ADDRESS = 35
    # VIFE 0xFD
    CREDIT = 36
    DEBIT = 37
    ACCESS_NUMBER = 38
    MANUFACTURER = 39
    PARAMETER_SET_ID = 40
    MODEL_VERSION = 41
    HARDWARE_VERSION = 42
    FIRMWARE_VERSION = 43
    SOFTWARE_VERSION = 44
    CUSTOMER_LOCATION = 45
    CUSTOMER = 46
    ERROR_FLAGS = 47
    ERROR_MASK = 48
    DIGITAL_OUTPUT = 49
    DIGITAL_INPUT = 50
    BAUDRATE_BPS = 51
    RESPONSE_DELAY_TIME = 52
    RETRY = 53
    SIZE_OF_STORAGE_BLOCK = 54
    STORAGE_INTERVAL_MONTH = 55
    GENERIC = 56
    VOLTS = 57
    AMPERES = 58
    RESET_COUNTER = 59
    CUMULATION_COUNTER = 60
    SPECIAL_SUPPLIER_INFO = 61
    # VIFE 0xFDFD
    CURRENT_SELECTED_APL = 62
    SUB_DEVICES = 63
    REMAIN_BAT_LIFE_MONTH = 64
    CARBON_DIOXIDE_PPM = 65
    CARBON_MONOXIDE_PPM = 66
    VOLATILE_ORG_COMP_PPB = 67
    VOLATILE_ORG_COMP_UG_M3 = 68
    PARTICLES_UNSPEC_UG_M3 = 69
    PARTICLES_PM1_UG_M3 = 70
    PARTICLES_PM2_5_UG_M3 = 71
    PARTICLES_PM10_UG_M3 = 72
    PARTICLES_UNSPEC_1M3 = 73
    PARTICLES_PM1_1M3 = 74
    PARTICLES_PM2_5_1M3 = 75
    PARTICLES_PM10_1M3 = 76
    ILLUMINANCE_LUX = 77
    LUMINOUS_IDENSITY_CD = 78
    RADIANT_FLUX_DENS = 79
    WIND_SPEED_M_S = 80
    RAINFALL_L_MM = 81
    FORMAZIN_NEPHELOMETER_U = 82
    POTENTIAL_HYDROGEN_PH = 83
    DISMOUNTS_COUNTER = 84
    TEST_BUTTON_COUNTER = 85
    ALARM_COUNTER = 86
    ALARM_MUTE_COUNTER = 87
    OBSTACLE_DETECT_COUNTER = 88
    SMOKE_ENTRIES_COUNTER = 89
    SMOKE_CHAMBER_DEFECTS = 90
    SELF_TEST_COUNTER = 91
    SOUNDER_DEFECT_COUNTER = 92
    DECIBEL_A = 93
    BATTERY_PERCENTAGE = 94
    CHAMBER_POLLUTION_LEVEL = 95
    DISTANCE_MM = 96
    MOISTURE_LEVEL_PERCENT = 97
    PRESSURE_SENS_STATUS = 98
    SMOKE_ALARM_STATUS = 99
    CO_ALARM_STATUS = 100
    HEAT_ALARM_STATUS = 101
    DOOR_WINDOW_SENS_STATUS = 102
    # VIFE 0xFB
    REACTIVE_ENERGY = 103
    REACTIVE_POWER = 104
    RELATIVE_HUMIDITY = 105
    VOLUME_FT3 = 106
    VOLUME_GAL = 107
    VOLUME_FLOW_GAL_M = 108
    VOLUME_FLOW_GAL_H = 109
    APPARENT_POWER = 110
    FLOW_TEMPERATURE_F = 111
    RETURN_TEMPERATURE_F = 112
    TEMPERATURE_DIFF_F = 113
    EXTERNAL_TEMPERATURE_F = 114
    TEMPERATURE_LIMIT_F = 115
    TEMPERATURE_LIMIT_C = 116
    MAX_POWER_W = 117
    PHASE_VOLT_DEG = 118
    PHASE_CURR_DEG = 119
    FREQUENCY = 120
    # VIFE 0xFC / 0xFF
    CUSTOMIZED_VIF = 121
    MANUFACTURER_SPECIFIC = 122


# ---------------------------------------------------------------------------
# VIF definition table
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VifDef:
    """One row of the VIF definition table."""
    code: MBusCode
    base: int
    size: int
    scalar: int


VIF_DEFS: list[VifDef] = [
    # sentinel for unknown VIF
    VifDef(MBusCode.UNKNOWN_VIF, 0x7E, 1, 0),
    # No VIFE
    VifDef(MBusCode.ENERGY_WH, 0x00, 8, -3),
    VifDef(MBusCode.ENERGY_J, 0x08, 8, 0),
    VifDef(MBusCode.VOLUME_M3, 0x10, 8, -6),
    VifDef(MBusCode.MASS_KG, 0x18, 8, -3),
    VifDef(MBusCode.ON_TIME_S, 0x20, 1, 0),
    VifDef(MBusCode.ON_TIME_MIN, 0x21, 1, 0),
    VifDef(MBusCode.ON_TIME_H, 0x22, 1, 0),
    VifDef(MBusCode.ON_TIME_DAYS, 0x23, 1, 0),
    VifDef(MBusCode.OPERATING_TIME_S, 0x24, 1, 0),
    VifDef(MBusCode.OPERATING_TIME_MIN, 0x25, 1, 0),
    VifDef(MBusCode.OPERATING_TIME_H, 0x26, 1, 0),
    VifDef(MBusCode.OPERATING_TIME_DAYS, 0x27, 1, 0),
    VifDef(MBusCode.POWER_W, 0x28, 8, -3),
    VifDef(MBusCode.POWER_J_H, 0x30, 8, 0),
    VifDef(MBusCode.VOLUME_FLOW_M3_H, 0x38, 8, -6),
    VifDef(MBusCode.VOLUME_FLOW_M3_MIN, 0x40, 8, -7),
    VifDef(MBusCode.VOLUME_FLOW_M3_S, 0x48, 8, -9),
    VifDef(MBusCode.MASS_FLOW_KG_H, 0x50, 8, -3),
    VifDef(MBusCode.FLOW_TEMPERATURE_C, 0x58, 4, -3),
    VifDef(MBusCode.RETURN_TEMPERATURE_C, 0x5C, 4, -3),
    VifDef(MBusCode.TEMPERATURE_DIFF_K, 0x60, 4, -3),
    VifDef(MBusCode.EXTERNAL_TEMPERATURE_C, 0x64, 4, -3),
    VifDef(MBusCode.PRESSURE_BAR, 0x68, 4, -3),
    VifDef(MBusCode.TIME_POINT_DATE, 0x6C, 1, 0),
    VifDef(MBusCode.TIME_POINT_DATETIME, 0x6D, 1, 0),
    VifDef(MBusCode.AVG_DURATION_S, 0x70, 1, 0),
    VifDef(MBusCode.AVG_DURATION_MIN, 0x71, 1, 0),
    VifDef(MBusCode.AVG_DURATION_H, 0x72, 1, 0),
    VifDef(MBusCode.AVG_DURATION_DAYS, 0x73, 1, 0),
    VifDef(MBusCode.ACTUAL_DURATION_S, 0x74, 1, 0),
    VifDef(MBusCode.ACTUAL_DURATION_MIN, 0x75, 1, 0),
    VifDef(MBusCode.ACTUAL_DURATION_H, 0x76, 1, 0),
    VifDef(MBusCode.ACTUAL_DURATION_DAYS, 0x77, 1, 0),
    VifDef(MBusCode.FABRICATION_NUMBER, 0x78, 1, 0),
    VifDef(MBusCode.BUS_ADDRESS, 0x7A, 1, 0),
    # extra volume definitions
    VifDef(MBusCode.VOLUME_M3, 0x933A, 1, -3),
    VifDef(MBusCode.VOLUME_M3, 0x943A, 1, -2),
    # VIFE 0xFD
    VifDef(MBusCode.CREDIT, 0xFD00, 4, -3),
    VifDef(MBusCode.DEBIT, 0xFD04, 4, -3),
    VifDef(MBusCode.ACCESS_NUMBER, 0xFD08, 1, 0),
    VifDef(MBusCode.MANUFACTURER, 0xFD0A, 1, 0),
    VifDef(MBusCode.PARAMETER_SET_ID, 0xFD0B, 1, 0),
    VifDef(MBusCode.MODEL_VERSION, 0xFD0C, 1, 0),
    VifDef(MBusCode.HARDWARE_VERSION, 0xFD0D, 1, 0),
    VifDef(MBusCode.FIRMWARE_VERSION, 0xFD0E, 1, 0),
    VifDef(MBusCode.SOFTWARE_VERSION, 0xFD0F, 1, 0),
    VifDef(MBusCode.CUSTOMER_LOCATION, 0xFD10, 1, 0),
    VifDef(MBusCode.CUSTOMER, 0xFD11, 1, 0),
    VifDef(MBusCode.ERROR_FLAGS, 0xFD17, 1, 0),
    VifDef(MBusCode.ERROR_MASK, 0xFD18, 1, 0),
    VifDef(MBusCode.DIGITAL_OUTPUT, 0xFD1A, 1, 0),
    VifDef(MBusCode.DIGITAL_INPUT, 0xFD1B, 1, 0),
    VifDef(MBusCode.BAUDRATE_BPS, 0xFD1C, 1, 0),
    VifDef(MBusCode.RESPONSE_DELAY_TIME, 0xFD1D, 1, 0),
    VifDef(MBusCode.RETRY, 0xFD1E, 1, 0),
    VifDef(MBusCode.SIZE_OF_STORAGE_BLOCK, 0xFD22, 1, 0),
    VifDef(MBusCode.STORAGE_INTERVAL_MONTH, 0xFD28, 1, 0),
    VifDef(MBusCode.GENERIC, 0xFD3A, 1, 0),
    VifDef(MBusCode.VOLTS, 0xFD40, 16, -9),
    VifDef(MBusCode.AMPERES, 0xFD50, 16, -12),
    VifDef(MBusCode.RESET_COUNTER, 0xFD60, 1, 0),
    VifDef(MBusCode.CUMULATION_COUNTER, 0xFD61, 1, 0),
    VifDef(MBusCode.SPECIAL_SUPPLIER_INFO, 0xFD67, 1, 0),
    # VIFE 0xFDFD
    VifDef(MBusCode.CURRENT_SELECTED_APL, 0xFDFD00, 1, 0),
    VifDef(MBusCode.SUB_DEVICES, 0xFDFD01, 1, 0),
    VifDef(MBusCode.REMAIN_BAT_LIFE_MONTH, 0xFDFD02, 1, 0),
    VifDef(MBusCode.CARBON_DIOXIDE_PPM, 0xFDFD10, 2, 0),
    VifDef(MBusCode.CARBON_MONOXIDE_PPM, 0xFDFD12, 2, 0),
    VifDef(MBusCode.VOLATILE_ORG_COMP_PPB, 0xFDFD14, 2, 0),
    VifDef(MBusCode.VOLATILE_ORG_COMP_UG_M3, 0xFDFD16, 1, 0),
    VifDef(MBusCode.PARTICLES_UNSPEC_UG_M3, 0xFDFD17, 1, 0),
    VifDef(MBusCode.PARTICLES_PM1_UG_M3, 0xFDFD18, 1, 0),
    VifDef(MBusCode.PARTICLES_PM2_5_UG_M3, 0xFDFD19, 1, 0),
    VifDef(MBusCode.PARTICLES_PM10_UG_M3, 0xFDFD1A, 1, 0),
    VifDef(MBusCode.PARTICLES_UNSPEC_1M3, 0xFDFD1B, 1, 5),
    VifDef(MBusCode.PARTICLES_PM1_1M3, 0xFDFD1C, 1, 5),
    VifDef(MBusCode.PARTICLES_PM2_5_1M3, 0xFDFD1D, 1, 5),
    VifDef(MBusCode.PARTICLES_PM10_1M3, 0xFDFD1E, 1, 5),
    VifDef(MBusCode.ILLUMINANCE_LUX, 0xFDFD1F, 1, 0),
    VifDef(MBusCode.LUMINOUS_IDENSITY_CD, 0xFDFD20, 1, 0),
    VifDef(MBusCode.RADIANT_FLUX_DENS, 0xFDFD21, 1, 0),
    VifDef(MBusCode.WIND_SPEED_M_S, 0xFDFD22, 1, 0),
    VifDef(MBusCode.RAINFALL_L_MM, 0xFDFD23, 1, 0),
    VifDef(MBusCode.FORMAZIN_NEPHELOMETER_U, 0xFDFD25, 1, 0),
    VifDef(MBusCode.POTENTIAL_HYDROGEN_PH, 0xFDFD27, 1, 0),
    VifDef(MBusCode.DISMOUNTS_COUNTER, 0xFDFD2C, 1, 0),
    VifDef(MBusCode.TEST_BUTTON_COUNTER, 0xFDFD2D, 1, 0),
    VifDef(MBusCode.ALARM_COUNTER, 0xFDFD2E, 1, 0),
    VifDef(MBusCode.ALARM_MUTE_COUNTER, 0xFDFD2F, 1, 0),
    VifDef(MBusCode.OBSTACLE_DETECT_COUNTER, 0xFDFD30, 1, 0),
    VifDef(MBusCode.SMOKE_ENTRIES_COUNTER, 0xFDFD31, 1, 0),
    VifDef(MBusCode.SMOKE_CHAMBER_DEFECTS, 0xFDFD32, 1, 0),
    VifDef(MBusCode.SELF_TEST_COUNTER, 0xFDFD33, 1, 0),
    VifDef(MBusCode.SOUNDER_DEFECT_COUNTER, 0xFDFD34, 1, 0),
    VifDef(MBusCode.DECIBEL_A, 0xFDFD36, 1, 0),
    VifDef(MBusCode.BATTERY_PERCENTAGE, 0xFDFD38, 1, 0),
    VifDef(MBusCode.CHAMBER_POLLUTION_LEVEL, 0xFDFD39, 1, 0),
    VifDef(MBusCode.DISTANCE_MM, 0xFDFD3A, 2, 0),
    VifDef(MBusCode.MOISTURE_LEVEL_PERCENT, 0xFDFD3E, 1, 0),
    VifDef(MBusCode.PRESSURE_SENS_STATUS, 0xFDFD40, 1, 0),
    VifDef(MBusCode.SMOKE_ALARM_STATUS, 0xFDFD41, 1, 0),
    VifDef(MBusCode.CO_ALARM_STATUS, 0xFDFD42, 1, 0),
    VifDef(MBusCode.HEAT_ALARM_STATUS, 0xFDFD43, 1, 0),
    VifDef(MBusCode.DOOR_WINDOW_SENS_STATUS, 0xFDFD44, 1, 0),
    # VIFE 0xFB
    VifDef(MBusCode.ENERGY_WH, 0xFB00, 2, 5),
    VifDef(MBusCode.REACTIVE_ENERGY, 0xFB02, 2, 0),
    VifDef(MBusCode.ENERGY_J, 0xFB08, 2, 8),
    VifDef(MBusCode.VOLUME_M3, 0xFB10, 2, 2),
    VifDef(MBusCode.REACTIVE_POWER, 0xFB14, 4, -3),
    VifDef(MBusCode.MASS_KG, 0xFB18, 2, 5),
    VifDef(MBusCode.RELATIVE_HUMIDITY, 0xFB1A, 2, -1),
    VifDef(MBusCode.VOLUME_FT3, 0xFB21, 1, -1),
    VifDef(MBusCode.VOLUME_GAL, 0xFB22, 2, -1),
    VifDef(MBusCode.VOLUME_FLOW_GAL_M, 0xFB24, 1, -3),
    VifDef(MBusCode.VOLUME_FLOW_GAL_M, 0xFB25, 1, 0),
    VifDef(MBusCode.VOLUME_FLOW_GAL_H, 0xFB26, 1, 0),
    VifDef(MBusCode.POWER_W, 0xFB28, 2, 5),
    VifDef(MBusCode.PHASE_VOLT_DEG, 0xFB2A, 1, -1),
    VifDef(MBusCode.PHASE_CURR_DEG, 0xFB2B, 1, -1),
    VifDef(MBusCode.FREQUENCY, 0xFB2C, 4, -3),
    VifDef(MBusCode.POWER_J_H, 0xFB30, 2, 8),
    VifDef(MBusCode.APPARENT_POWER, 0xFB34, 4, -3),
    VifDef(MBusCode.FLOW_TEMPERATURE_F, 0xFB58, 4, -3),
    VifDef(MBusCode.RETURN_TEMPERATURE_F, 0xFB5C, 4, -3),
    VifDef(MBusCode.TEMPERATURE_DIFF_F, 0xFB60, 4, -3),
    VifDef(MBusCode.EXTERNAL_TEMPERATURE_F, 0xFB64, 4, -3),
    VifDef(MBusCode.TEMPERATURE_LIMIT_F, 0xFB70, 4, -3),
    VifDef(MBusCode.TEMPERATURE_LIMIT_C, 0xFB74, 4, -3),
    VifDef(MBusCode.MAX_POWER_W, 0xFB78, 8, -3),
    # VIFE 0xFC
    VifDef(MBusCode.CUSTOMIZED_VIF, 0xFC00, 254, 0),
    # VIFE 0xFF
    VifDef(MBusCode.MANUFACTURER_SPECIFIC, 0xFF00, 254, 0),
]


# ---------------------------------------------------------------------------
# Code → human-readable name  (mirrors getCodeName)
# ---------------------------------------------------------------------------

_CODE_NAME: dict[MBusCode, str] = {
    MBusCode.UNKNOWN_VIF: "unknown_vif",
    MBusCode.ENERGY_WH: "energy",
    MBusCode.ENERGY_J: "energy",
    MBusCode.VOLUME_M3: "volume",
    MBusCode.VOLUME_FT3: "volume",
    MBusCode.VOLUME_GAL: "volume",
    MBusCode.MASS_KG: "mass",
    MBusCode.ON_TIME_S: "on_time",
    MBusCode.ON_TIME_MIN: "on_time",
    MBusCode.ON_TIME_H: "on_time",
    MBusCode.ON_TIME_DAYS: "on_time",
    MBusCode.OPERATING_TIME_S: "operating_time",
    MBusCode.OPERATING_TIME_MIN: "operating_time",
    MBusCode.OPERATING_TIME_H: "operating_time",
    MBusCode.OPERATING_TIME_DAYS: "operating_time",
    MBusCode.AVG_DURATION_S: "avg_duration",
    MBusCode.AVG_DURATION_MIN: "avg_duration",
    MBusCode.AVG_DURATION_H: "avg_duration",
    MBusCode.AVG_DURATION_DAYS: "avg_duration",
    MBusCode.ACTUAL_DURATION_S: "actual_duration",
    MBusCode.ACTUAL_DURATION_MIN: "actual_duration",
    MBusCode.ACTUAL_DURATION_H: "actual_duration",
    MBusCode.ACTUAL_DURATION_DAYS: "actual_duration",
    MBusCode.POWER_W: "power",
    MBusCode.MAX_POWER_W: "power",
    MBusCode.POWER_J_H: "power",
    MBusCode.VOLUME_FLOW_M3_H: "volume_flow",
    MBusCode.VOLUME_FLOW_M3_MIN: "volume_flow",
    MBusCode.VOLUME_FLOW_M3_S: "volume_flow",
    MBusCode.VOLUME_FLOW_GAL_M: "volume_flow",
    MBusCode.VOLUME_FLOW_GAL_H: "volume_flow",
    MBusCode.MASS_FLOW_KG_H: "mass_flow",
    MBusCode.FLOW_TEMPERATURE_C: "flow_temperature",
    MBusCode.FLOW_TEMPERATURE_F: "flow_temperature",
    MBusCode.RETURN_TEMPERATURE_C: "return_temperature",
    MBusCode.RETURN_TEMPERATURE_F: "return_temperature",
    MBusCode.EXTERNAL_TEMPERATURE_C: "external_temperature",
    MBusCode.EXTERNAL_TEMPERATURE_F: "external_temperature",
    MBusCode.TEMPERATURE_LIMIT_C: "temperature_limit",
    MBusCode.TEMPERATURE_LIMIT_F: "temperature_limit",
    MBusCode.TEMPERATURE_DIFF_K: "temperature_diff",
    MBusCode.TEMPERATURE_DIFF_F: "temperature_diff",
    MBusCode.PRESSURE_BAR: "pressure",
    MBusCode.TIME_POINT_DATE: "time_point",
    MBusCode.TIME_POINT_DATETIME: "time_point",
    MBusCode.BAUDRATE_BPS: "baudrate",
    MBusCode.VOLTS: "voltage",
    MBusCode.AMPERES: "current",
    MBusCode.FABRICATION_NUMBER: "fab_number",
    MBusCode.BUS_ADDRESS: "bus_address",
    MBusCode.CREDIT: "credit",
    MBusCode.DEBIT: "debit",
    MBusCode.ACCESS_NUMBER: "access_number",
    MBusCode.MANUFACTURER: "manufacturer",
    MBusCode.PARAMETER_SET_ID: "set_id",
    MBusCode.MODEL_VERSION: "model_version",
    MBusCode.HARDWARE_VERSION: "hardware_version",
    MBusCode.FIRMWARE_VERSION: "firmware_version",
    MBusCode.SOFTWARE_VERSION: "software_version",
    MBusCode.CUSTOMER_LOCATION: "customer_location",
    MBusCode.CUSTOMER: "customer",
    MBusCode.ERROR_FLAGS: "error_flags",
    MBusCode.ERROR_MASK: "error_mask",
    MBusCode.DIGITAL_OUTPUT: "digital_output",
    MBusCode.DIGITAL_INPUT: "digital_input",
    MBusCode.RESPONSE_DELAY_TIME: "response_delay",
    MBusCode.RETRY: "retry",
    MBusCode.SIZE_OF_STORAGE_BLOCK: "sizeof_storageblock",
    MBusCode.STORAGE_INTERVAL_MONTH: "storage_interval",
    MBusCode.GENERIC: "generic",
    MBusCode.RESET_COUNTER: "counter",
    MBusCode.CUMULATION_COUNTER: "counter",
    MBusCode.CUSTOMIZED_VIF: "customized_vif",
    MBusCode.MANUFACTURER_SPECIFIC: "manufactur_specific",
    MBusCode.RELATIVE_HUMIDITY: "humidity",
    MBusCode.REACTIVE_ENERGY: "reactive_energy",
    MBusCode.REACTIVE_POWER: "reactive_power",
    MBusCode.APPARENT_POWER: "apparent_power",
    MBusCode.PHASE_VOLT_DEG: "phase_deg_voltage",
    MBusCode.PHASE_CURR_DEG: "phase_deg_current",
    MBusCode.FREQUENCY: "frequency",
    MBusCode.SPECIAL_SUPPLIER_INFO: "special_suppl_info",
    MBusCode.CURRENT_SELECTED_APL: "current_selected_appl.",
    MBusCode.SUB_DEVICES: "sub_devices",
    MBusCode.REMAIN_BAT_LIFE_MONTH: "remain_bat_life",
    MBusCode.CARBON_DIOXIDE_PPM: "CO2",
    MBusCode.CARBON_MONOXIDE_PPM: "CO",
    MBusCode.VOLATILE_ORG_COMP_PPB: "VOC",
    MBusCode.VOLATILE_ORG_COMP_UG_M3: "VOC",
    MBusCode.PARTICLES_UNSPEC_UG_M3: "particels_unspecific",
    MBusCode.PARTICLES_UNSPEC_1M3: "particels_unspecific",
    MBusCode.PARTICLES_PM1_UG_M3: "particles_PM1",
    MBusCode.PARTICLES_PM1_1M3: "particles_PM1",
    MBusCode.PARTICLES_PM2_5_UG_M3: "particles_PM2,5",
    MBusCode.PARTICLES_PM2_5_1M3: "particles_PM2,5",
    MBusCode.PARTICLES_PM10_UG_M3: "particles_PM10",
    MBusCode.PARTICLES_PM10_1M3: "particles_PM10",
    MBusCode.ILLUMINANCE_LUX: "illuminance",
    MBusCode.LUMINOUS_IDENSITY_CD: "luminus_idensity",
    MBusCode.RADIANT_FLUX_DENS: "radiant_flux_density",
    MBusCode.WIND_SPEED_M_S: "wind_speed",
    MBusCode.RAINFALL_L_MM: "rainfall",
    MBusCode.FORMAZIN_NEPHELOMETER_U: "formazin_nephelometric",
    MBusCode.POTENTIAL_HYDROGEN_PH: "PH",
    MBusCode.DISMOUNTS_COUNTER: "dismounts_counter",
    MBusCode.TEST_BUTTON_COUNTER: "test_button_counter",
    MBusCode.ALARM_COUNTER: "alarm_counter",
    MBusCode.ALARM_MUTE_COUNTER: "alarm_mute_counter",
    MBusCode.OBSTACLE_DETECT_COUNTER: "obstacle_detect_counter",
    MBusCode.SMOKE_ENTRIES_COUNTER: "smoke_entries_counter",
    MBusCode.SMOKE_CHAMBER_DEFECTS: "smoke_chamber_defects",
    MBusCode.SELF_TEST_COUNTER: "self_test_counter",
    MBusCode.SOUNDER_DEFECT_COUNTER: "sounder_defect_counter",
    MBusCode.DECIBEL_A: "decibel_A",
    MBusCode.BATTERY_PERCENTAGE: "battery",
    MBusCode.CHAMBER_POLLUTION_LEVEL: "chamber_pollution_level",
    MBusCode.DISTANCE_MM: "distance",
    MBusCode.MOISTURE_LEVEL_PERCENT: "moisture_level",
    MBusCode.PRESSURE_SENS_STATUS: "pressure_sens_status",
    MBusCode.SMOKE_ALARM_STATUS: "smoke_alarm_status",
    MBusCode.CO_ALARM_STATUS: "CO_alarm_status",
    MBusCode.HEAT_ALARM_STATUS: "heat_alarm_status",
    MBusCode.DOOR_WINDOW_SENS_STATUS: "door_window_sens_status",
}


# ---------------------------------------------------------------------------
# Code → unit string  (mirrors getCodeUnits)
# ---------------------------------------------------------------------------

_CODE_UNITS: dict[MBusCode, str] = {
    MBusCode.ENERGY_WH: "Wh",
    MBusCode.ENERGY_J: "J",
    MBusCode.VOLUME_M3: "m³",
    MBusCode.MASS_KG: "kg",
    MBusCode.ON_TIME_S: "s",
    MBusCode.ON_TIME_MIN: "min",
    MBusCode.ON_TIME_H: "h",
    MBusCode.ON_TIME_DAYS: "d",
    MBusCode.OPERATING_TIME_S: "s",
    MBusCode.OPERATING_TIME_MIN: "min",
    MBusCode.OPERATING_TIME_H: "h",
    MBusCode.OPERATING_TIME_DAYS: "d",
    MBusCode.AVG_DURATION_S: "s",
    MBusCode.AVG_DURATION_MIN: "min",
    MBusCode.AVG_DURATION_H: "h",
    MBusCode.AVG_DURATION_DAYS: "d",
    MBusCode.ACTUAL_DURATION_S: "s",
    MBusCode.ACTUAL_DURATION_MIN: "min",
    MBusCode.ACTUAL_DURATION_H: "h",
    MBusCode.ACTUAL_DURATION_DAYS: "d",
    MBusCode.POWER_W: "W",
    MBusCode.MAX_POWER_W: "W",
    MBusCode.POWER_J_H: "J/h",
    MBusCode.VOLUME_FLOW_M3_H: "m³/h",
    MBusCode.VOLUME_FLOW_M3_MIN: "m³/min",
    MBusCode.VOLUME_FLOW_M3_S: "m³/s",
    MBusCode.MASS_FLOW_KG_H: "kg/h",
    MBusCode.FLOW_TEMPERATURE_C: "°C",
    MBusCode.RETURN_TEMPERATURE_C: "°C",
    MBusCode.EXTERNAL_TEMPERATURE_C: "°C",
    MBusCode.TEMPERATURE_LIMIT_C: "°C",
    MBusCode.TEMPERATURE_DIFF_K: "K",
    MBusCode.PRESSURE_BAR: "bar",
    MBusCode.TIME_POINT_DATE: "YYYYMMDD",
    MBusCode.TIME_POINT_DATETIME: "YYYYMMDDhhmm",
    MBusCode.BAUDRATE_BPS: "bit/s",
    MBusCode.VOLTS: "V",
    MBusCode.AMPERES: "A",
    MBusCode.VOLUME_FT3: "ft³",
    MBusCode.VOLUME_GAL: "gal",
    MBusCode.VOLUME_FLOW_GAL_M: "gal/min",
    MBusCode.VOLUME_FLOW_GAL_H: "gal/h",
    MBusCode.FLOW_TEMPERATURE_F: "°F",
    MBusCode.RETURN_TEMPERATURE_F: "°F",
    MBusCode.TEMPERATURE_DIFF_F: "°F",
    MBusCode.EXTERNAL_TEMPERATURE_F: "°F",
    MBusCode.TEMPERATURE_LIMIT_F: "°F",
    MBusCode.STORAGE_INTERVAL_MONTH: "month",
    MBusCode.REMAIN_BAT_LIFE_MONTH: "month",
    MBusCode.RELATIVE_HUMIDITY: "%",
    MBusCode.BATTERY_PERCENTAGE: "%",
    MBusCode.CHAMBER_POLLUTION_LEVEL: "%",
    MBusCode.MOISTURE_LEVEL_PERCENT: "%",
    MBusCode.REACTIVE_ENERGY: "kvarh",
    MBusCode.REACTIVE_POWER: "kvar",
    MBusCode.APPARENT_POWER: "kVA",
    MBusCode.PHASE_VOLT_DEG: "°",
    MBusCode.PHASE_CURR_DEG: "°",
    MBusCode.FREQUENCY: "Hz",
    MBusCode.CARBON_DIOXIDE_PPM: "ppm",
    MBusCode.CARBON_MONOXIDE_PPM: "ppm",
    MBusCode.VOLATILE_ORG_COMP_PPB: "ppb",
    MBusCode.VOLATILE_ORG_COMP_UG_M3: "µg/m³",
    MBusCode.PARTICLES_UNSPEC_UG_M3: "µg/m³",
    MBusCode.PARTICLES_PM1_UG_M3: "µg/m³",
    MBusCode.PARTICLES_PM2_5_UG_M3: "µg/m³",
    MBusCode.PARTICLES_PM10_UG_M3: "µg/m³",
    MBusCode.PARTICLES_UNSPEC_1M3: "1/m³",
    MBusCode.PARTICLES_PM1_1M3: "1/m³",
    MBusCode.PARTICLES_PM2_5_1M3: "1/m³",
    MBusCode.PARTICLES_PM10_1M3: "1/m³",
    MBusCode.ILLUMINANCE_LUX: "lx",
    MBusCode.LUMINOUS_IDENSITY_CD: "cd",
    MBusCode.RADIANT_FLUX_DENS: "W/m²",
    MBusCode.WIND_SPEED_M_S: "m/s",
    MBusCode.RAINFALL_L_MM: "l/mm²",
    MBusCode.FORMAZIN_NEPHELOMETER_U: "FNU",
    MBusCode.DECIBEL_A: "dB",
    MBusCode.DISTANCE_MM: "mm",
}


# ---------------------------------------------------------------------------
# Code → HA device_class  (mirrors getDeviceClass)
# ---------------------------------------------------------------------------

_CODE_DEVICE_CLASS: dict[MBusCode, str] = {
    MBusCode.ENERGY_WH: "energy",
    MBusCode.ENERGY_J: "energy",
    MBusCode.VOLUME_M3: "volume",
    MBusCode.VOLUME_FT3: "volume",
    MBusCode.VOLUME_GAL: "volume",
    MBusCode.MASS_KG: "weight",
    MBusCode.ON_TIME_S: "duration",
    MBusCode.ON_TIME_MIN: "duration",
    MBusCode.ON_TIME_H: "duration",
    MBusCode.ON_TIME_DAYS: "duration",
    MBusCode.OPERATING_TIME_S: "duration",
    MBusCode.OPERATING_TIME_MIN: "duration",
    MBusCode.OPERATING_TIME_H: "duration",
    MBusCode.OPERATING_TIME_DAYS: "duration",
    MBusCode.AVG_DURATION_S: "duration",
    MBusCode.AVG_DURATION_MIN: "duration",
    MBusCode.AVG_DURATION_H: "duration",
    MBusCode.AVG_DURATION_DAYS: "duration",
    MBusCode.ACTUAL_DURATION_S: "duration",
    MBusCode.ACTUAL_DURATION_MIN: "duration",
    MBusCode.ACTUAL_DURATION_H: "duration",
    MBusCode.ACTUAL_DURATION_DAYS: "duration",
    MBusCode.POWER_W: "power",
    MBusCode.MAX_POWER_W: "power",
    MBusCode.POWER_J_H: "power",
    MBusCode.VOLUME_FLOW_M3_H: "volume_flow_rate",
    MBusCode.VOLUME_FLOW_M3_MIN: "volume_flow_rate",
    MBusCode.VOLUME_FLOW_M3_S: "volume_flow_rate",
    MBusCode.VOLUME_FLOW_GAL_M: "volume_flow_rate",
    MBusCode.VOLUME_FLOW_GAL_H: "volume_flow_rate",
    MBusCode.FLOW_TEMPERATURE_C: "temperature",
    MBusCode.FLOW_TEMPERATURE_F: "temperature",
    MBusCode.RETURN_TEMPERATURE_C: "temperature",
    MBusCode.RETURN_TEMPERATURE_F: "temperature",
    MBusCode.EXTERNAL_TEMPERATURE_C: "temperature",
    MBusCode.EXTERNAL_TEMPERATURE_F: "temperature",
    MBusCode.TEMPERATURE_LIMIT_C: "temperature",
    MBusCode.TEMPERATURE_LIMIT_F: "temperature",
    MBusCode.TEMPERATURE_DIFF_K: "temperature",
    MBusCode.TEMPERATURE_DIFF_F: "temperature",
    MBusCode.PRESSURE_BAR: "pressure",
    MBusCode.BAUDRATE_BPS: "data_rate",
    MBusCode.VOLTS: "voltage",
    MBusCode.AMPERES: "current",
    MBusCode.RELATIVE_HUMIDITY: "humidity",
    MBusCode.FREQUENCY: "frequency",
}


# ---------------------------------------------------------------------------
# Code → HA state_class  (mirrors getStateClass)
# ---------------------------------------------------------------------------

_MEASUREMENT_CODES: frozenset[MBusCode] = frozenset({
    MBusCode.AMPERES,
    MBusCode.MASS_KG,
    MBusCode.POWER_W,
    MBusCode.MAX_POWER_W,
    MBusCode.POWER_J_H,
    MBusCode.VOLUME_FLOW_M3_H,
    MBusCode.VOLUME_FLOW_M3_MIN,
    MBusCode.VOLUME_FLOW_M3_S,
    MBusCode.VOLUME_FLOW_GAL_M,
    MBusCode.VOLUME_FLOW_GAL_H,
    MBusCode.MASS_FLOW_KG_H,
    MBusCode.FLOW_TEMPERATURE_C,
    MBusCode.FLOW_TEMPERATURE_F,
    MBusCode.RETURN_TEMPERATURE_C,
    MBusCode.RETURN_TEMPERATURE_F,
    MBusCode.EXTERNAL_TEMPERATURE_C,
    MBusCode.EXTERNAL_TEMPERATURE_F,
    MBusCode.TEMPERATURE_LIMIT_C,
    MBusCode.TEMPERATURE_LIMIT_F,
    MBusCode.TEMPERATURE_DIFF_K,
    MBusCode.TEMPERATURE_DIFF_F,
    MBusCode.PRESSURE_BAR,
    MBusCode.BAUDRATE_BPS,
    MBusCode.VOLTS,
    MBusCode.RELATIVE_HUMIDITY,
    MBusCode.PHASE_VOLT_DEG,
    MBusCode.PHASE_CURR_DEG,
})


def get_code_name(code: MBusCode) -> str:
    return _CODE_NAME.get(code, "")


def get_code_units(code: MBusCode) -> str | None:
    return _CODE_UNITS.get(code)


def get_device_class(code: MBusCode) -> str:
    return _CODE_DEVICE_CLASS.get(code, "")


def get_state_class(code: MBusCode) -> str:
    if code in _MEASUREMENT_CODES:
        return "measurement"
    return "total"


# ---------------------------------------------------------------------------
# VIF lookup
# ---------------------------------------------------------------------------

def _find_definition(vif: int) -> int:
    """Return index into VIF_DEFS or -1 if not found."""
    for i, vd in enumerate(VIF_DEFS):
        if vd.base <= vif < vd.base + vd.size:
            return i
    return -1


# ---------------------------------------------------------------------------
# Data-coding helpers
# ---------------------------------------------------------------------------

# dataCodingType constants
_DCT_NONE = 0
_DCT_INTEGER = 1
_DCT_BCD = 2
_DCT_REAL = 3
_DCT_VARIABLE = 4
_DCT_SPECIAL = 5
_DCT_DATETIME_F = 6  # Date & Time  (Type F, 4 bytes)
_DCT_DATE_G = 7       # Date only    (Type G, 2 bytes)

# DIF least-4-bit → (byte_length, dataCodingType)
_DIF_LENGTH_MAP: dict[int, tuple[int, int]] = {
    0x00: (0, _DCT_NONE),
    0x01: (1, _DCT_INTEGER),
    0x02: (2, _DCT_INTEGER),
    0x03: (3, _DCT_INTEGER),
    0x04: (4, _DCT_INTEGER),
    0x05: (4, _DCT_REAL),
    0x06: (6, _DCT_INTEGER),
    0x07: (8, _DCT_INTEGER),
    0x08: (0, _DCT_NONE),
    0x09: (1, _DCT_BCD),
    0x0A: (2, _DCT_BCD),
    0x0B: (3, _DCT_BCD),
    0x0C: (4, _DCT_BCD),
    0x0D: (0, _DCT_VARIABLE),
    0x0E: (6, _DCT_BCD),
    0x0F: (0, _DCT_SPECIAL),
}

_FUNCTION_FIELD_SUFFIX = {0: "", 1: "_max", 2: "_min", 3: "_err"}


# ---------------------------------------------------------------------------
# Decoder error
# ---------------------------------------------------------------------------

class MBusDecodeError(Exception):
    """Raised when a telegram cannot be decoded."""


# ---------------------------------------------------------------------------
# Public decoder
# ---------------------------------------------------------------------------

@dataclass
class MBusRecord:
    """One decoded data record from an M-Bus telegram."""
    vif_hex: str
    code: int
    name: str
    value_scaled: float | None = None
    value_string: str | None = None
    units: str | None = None
    storage: int | None = None
    sub_unit: int | None = None
    tariff: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "vif": self.vif_hex,
            "code": self.code,
            "name": self.name,
        }
        if self.value_scaled is not None:
            d["value_scaled"] = self.value_scaled
        if self.value_string is not None:
            d["value_string"] = self.value_string
        if self.units is not None:
            d["units"] = self.units
        if self.storage is not None and self.storage > 0:
            d["storage"] = self.storage
        if self.sub_unit is not None and self.sub_unit > 0:
            d["subUnit"] = self.sub_unit
        if self.tariff is not None and self.tariff > 0:
            d["tariff"] = self.tariff
        return d


def _read_integer(buf: bytes, offset: int, length: int) -> int:
    """Read a little-endian signed integer of *length* bytes."""
    raw = buf[offset:offset + length]
    val = int.from_bytes(raw, byteorder="little", signed=False)
    # Sign-extend based on byte length
    if length <= 2:
        if val >= (1 << (8 * length - 1)):
            val -= 1 << (8 * length)
    elif length <= 4:
        if val >= (1 << (8 * length - 1)):
            val -= 1 << (8 * length)
    else:
        if val >= (1 << (8 * length - 1)):
            val -= 1 << (8 * length)
    return val


def _read_bcd(buf: bytes, offset: int, length: int) -> tuple[int, bool]:
    """Read a BCD-encoded value (little-endian), return (value, negative)."""
    negative = False
    result = 0
    for i in range(length):
        byte = buf[offset + length - i - 1]
        if i == 0 and (byte & 0xF0) == 0xF0:
            byte = byte & 0x0F
            negative = True
        result = result * 100 + ((byte >> 4) * 10) + (byte & 0x0F)
    return result, negative


def _read_real(buf: bytes, offset: int) -> float:
    """Read an IEEE 754 single-precision float (little-endian)."""
    return struct.unpack_from("<f", buf, offset)[0]


def _decode_datetime_f(buf: bytes, offset: int) -> tuple[float, str]:
    """Decode a Type F date/time (4 bytes) → (numeric, formatted string)."""
    d = buf[offset:offset + 4]
    if d[0] & 0x80:
        return 0.0, "invalid"
    minute = d[0] & 0x3F
    hour = d[1] & 0x1F
    day = d[2] & 0x1F
    month = d[3] & 0x0F
    year = ((d[2] & 0xE0) >> 5) | ((d[3] & 0xF0) >> 1)
    numeric_str = f"20{year:02d}{month:02d}{day:02d}{hour:02d}{minute:02d}"
    formatted = f"20{year:02d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:00"
    return float(numeric_str), formatted


def _decode_date_g(buf: bytes, offset: int) -> tuple[float, str]:
    """Decode a Type G date (2 bytes) → (numeric, formatted string)."""
    d = buf[offset:offset + 2]
    month = d[1] & 0x0F
    if month > 12:
        return 0.0, "invalid"
    day = d[0] & 0x1F
    year = ((d[0] & 0xE0) >> 5) | ((d[1] & 0xF0) >> 1)
    numeric_str = f"20{year:02d}{month:02d}{day:02d}"
    formatted = f"20{year:02d}-{month:02d}-{day:02d}"
    return float(numeric_str), formatted


def decode(buffer: bytes | bytearray, size: int | None = None) -> list[MBusRecord]:
    """Decode variable data records from an M-Bus telegram payload.

    *buffer* should start at the first DIF byte (after the fixed data header,
    typically offset 0x13 from the beginning of the long frame).

    Returns a list of `MBusRecord` objects.
    """
    if size is None:
        size = len(buffer)
    buf = bytes(buffer[:size])
    records: list[MBusRecord] = []
    index = 0

    while index < size:
        # ---- DIF ----
        dif = buf[index]
        index += 1
        dif_least4 = dif & 0x0F
        dif_function = (dif & 0x30) >> 4
        length, data_coding = _DIF_LENGTH_MAP.get(dif_least4, (0, _DCT_NONE))
        func_suffix = _FUNCTION_FIELD_SUFFIX.get(dif_function, "")

        # ---- DIFE ----
        storage_number = 1 if (dif & 0x40) else 0
        dife_list: list[int] = []
        has_dife = bool(dif & 0x80)
        while has_dife:
            if index >= size:
                raise MBusDecodeError("Buffer overflow reading DIFE")
            dife_byte = buf[index]
            index += 1
            dife_list.append(dife_byte)
            has_dife = bool(dife_byte & 0x80)

        sub_unit = 0
        tariff = 0
        for i, dife_byte in enumerate(dife_list):
            if i == 0:
                storage_number |= (dife_byte & 0x0F) << 1
            else:
                storage_number |= (dife_byte & 0x0F) << (4 * i)
            sub_unit |= ((dife_byte & 0x40) >> 6) << i
            tariff |= ((dife_byte & 0x30) >> 4) << (2 * i)

        # ---- VIF / VIFE ----
        vif_value = 0
        vif_array: list[int] = []
        custom_vif = ""
        is_custom_vif = False
        custom_vif_len = 0

        while True:
            if index >= size:
                raise MBusDecodeError("Buffer overflow reading VIF")
            vif_byte = buf[index]
            index += 1
            vif_array.append(vif_byte)

            # Handle customised ASCII VIF marker
            if len(vif_array) == 1 and (vif_byte & 0x7F) == 0x7C:
                if index >= size:
                    raise MBusDecodeError("Buffer overflow reading custom VIF length")
                custom_vif_len = buf[index]
                if vif_byte == 0xFC:
                    # Skip the ASCII string for now; we'll come back
                    index += custom_vif_len + 1

            vc = len(vif_array) - 1
            if vc < 2:
                vif_value = (vif_value << 8) + vif_byte
            elif vc == 2 and vif_value == 0xFDFD:
                vif_value = (vif_value << 8) + vif_byte

            if not (vif_byte & 0x80):
                break

        # Resolve true VIF
        if (
            (vif_array[0] & 0x80)
            and vif_array[0] not in (0xFD, 0xFC, 0xFB, 0xFF)
        ):
            vif_value = vif_array[0] & 0x7F

        if vif_array[0] == 0x7C:
            vif_value = 0x7C00

        if (vif_value & 0x7F) == 0x6D:
            data_coding = _DCT_DATETIME_F
        elif (vif_value & 0x7F) == 0x6C:
            data_coding = _DCT_DATE_G
        elif (vif_value & 0x7F00) == 0x7C00:
            vif_value = 0xFC00
            if vif_array[0] == 0xFC:
                # Go back to read the ASCII string we skipped earlier
                index -= custom_vif_len + 1 + (len(vif_array) - 1)
                # re-advance past vif_array bytes
                index += len(vif_array) - 1
                # Actually let's recompute properly:
                # We need to back up to just after the length byte and read
                # the ASCII chars.
                pass

            # Read custom VIF ASCII string
            if vif_array[0] == 0xFC and custom_vif_len > 0:
                # Position: index is currently past all VIF/VIFE bytes.
                # The ASCII string is embedded after the first VIF byte + length byte.
                # For 0xFC, we skipped earlier; now rewind to read.
                # The structure is: FC <len> <ascii_bytes...> [VIFEs...]
                # We need to find the ascii_bytes.
                # When vif_array[0]==0xFC, the bytes after it were:
                #   buf[original_vif_start+1] = length
                #   buf[original_vif_start+2 .. +2+length-1] = ASCII (reversed)
                #   then VIFEs
                # Since we already consumed all VIF/VIFEs, let's compute the
                # start of the ASCII data.
                ascii_start = index - len(vif_array) + 1  # after the 0xFC byte
                # ascii_start points to the length byte
                ascii_data_start = ascii_start + 1
                chars = []
                for i in range(custom_vif_len):
                    chars.append(chr(buf[ascii_data_start + custom_vif_len - i - 1]))
                custom_vif = "".join(chars)
                is_custom_vif = True
            elif vif_array[0] == 0x7C and custom_vif_len > 0:
                ascii_start = index - len(vif_array) + 1
                ascii_data_start = ascii_start + 1
                chars = []
                for i in range(custom_vif_len):
                    chars.append(chr(buf[ascii_data_start + custom_vif_len - i - 1]))
                custom_vif = "".join(chars)
                is_custom_vif = True

        # Strip leading bit of last VIF byte for definition lookup
        vif_value = vif_value & 0xFFFFFF7F

        # Find VIF definition
        def_idx = _find_definition(vif_value)
        if def_idx < 0:
            def_idx = 0  # fall back to UNKNOWN_VIF

        vif_def = VIF_DEFS[def_idx]

        # ---- VIFE extensions (table 8.4.5) ----
        extension_scaler = 0
        extension_additive = 0.0
        name_extension = ""
        no_unit = False

        vif_count = len(vif_array)
        if vif_count > 1:
            if vif_array[0] in (0xFB,) or (
                vif_array[0] == 0xFD and (len(vif_array) < 2 or vif_array[1] != 0xFD)
            ) or vif_array[0] == 0xFF:
                first_ext = 2
            elif vif_array[0] == 0xFD and len(vif_array) > 1 and vif_array[1] == 0xFD:
                first_ext = 3
            else:
                first_ext = 1

            ext_i = first_ext
            while ext_i < vif_count:
                ext_byte = vif_array[ext_i]
                masked = ext_byte & 0x7F

                if masked == 0x7D:
                    extension_scaler = 3
                elif (ext_byte & 0x78) == 0x70:
                    extension_scaler = (ext_byte & 0x07) - 6
                elif (ext_byte & 0x7C) == 0x78:
                    exp = (ext_byte & 0x03) - 3
                    extension_additive = 10.0 ** exp
                elif (ext_byte & 0x7A) == 0x6A:
                    if dif_least4 == 4:
                        data_coding = _DCT_DATETIME_F
                    elif dif_least4 == 2:
                        data_coding = _DCT_DATE_G
                    name_extension = "_TimeSt"
                    no_unit = True
                elif ext_byte in (0xFC, 0xFF) and ext_i + 1 < vif_count:
                    next_byte = vif_array[ext_i + 1] & 0x7F
                    _phase_map = {
                        1: "_L1", 2: "_L2", 3: "_L3", 4: "_N",
                        5: "_L1-L2", 6: "_L2-L3", 7: "_L3-L1",
                        10: "_abs.", 12: "_delta",
                    }
                    if next_byte in _phase_map:
                        name_extension = _phase_map[next_byte]
                        ext_i += 1
                ext_i += 1

        # ---- Read data value ----
        if index + length > size:
            raise MBusDecodeError("Buffer overflow reading data value")

        value_int: int = 0
        value_float: float = 0.0
        value_string: str | None = None
        ascii_value = 0  # 0=double, 1=ASCII, 2=both
        negative = False

        keep_going = True
        while keep_going:
            keep_going = False
            if data_coding == _DCT_NONE:
                pass

            elif data_coding == _DCT_INTEGER:
                value_int = _read_integer(buf, index, length)

            elif data_coding == _DCT_BCD:
                value_int, negative = _read_bcd(buf, index, length)
                if negative:
                    value_int = -value_int

            elif data_coding == _DCT_REAL:
                value_float = _read_real(buf, index)

            elif data_coding == _DCT_VARIABLE:
                if index >= size:
                    raise MBusDecodeError("Buffer overflow reading variable length")
                lvar = buf[index]
                if 0x00 <= lvar <= 0xBF:
                    # ASCII string
                    length = lvar
                    index += 1
                    if index + length > size:
                        raise MBusDecodeError("Buffer overflow reading ASCII data")
                    chars = []
                    for i in range(length):
                        chars.append(chr(buf[index + length - i - 1]))
                    value_string = "".join(chars)
                    ascii_value = 1
                elif 0xC0 <= lvar <= 0xCF:
                    # Positive BCD
                    length = lvar - 0xC0
                    index += 1
                    data_coding = _DCT_BCD
                    keep_going = True
                    continue
                elif 0xD0 <= lvar <= 0xDF:
                    # Negative BCD
                    length = lvar - 0xD0
                    index += 1
                    data_coding = _DCT_BCD
                    negative = True
                    keep_going = True
                    continue
                elif 0xE0 <= lvar <= 0xEF:
                    # Binary integer
                    length = lvar - 0xE0
                    index += 1
                    data_coding = _DCT_INTEGER
                    keep_going = True
                    continue
                elif 0xF0 <= lvar <= 0xFA:
                    # Floating point
                    length = lvar - 0xF0
                    index += 1
                    data_coding = _DCT_REAL
                    keep_going = True
                    continue

            elif data_coding == _DCT_SPECIAL:
                pass

            elif data_coding == _DCT_DATETIME_F:
                numeric, formatted = _decode_datetime_f(buf, index)
                value_int = int(numeric)
                value_float = numeric
                value_string = formatted
                ascii_value = 2

            elif data_coding == _DCT_DATE_G:
                numeric, formatted = _decode_date_g(buf, index)
                value_int = int(numeric)
                value_float = numeric
                value_string = formatted
                ascii_value = 2

        index += length

        # ---- Compute scaled value ----
        scalar = 0
        if def_idx != 0:
            scalar = vif_def.scalar + vif_value - vif_def.base + extension_scaler

        if data_coding == _DCT_REAL:
            scaled = value_float
            if vif_array[0] != 0xFF:
                scaled = scaled * (10.0 ** scalar) + extension_additive
        elif vif_array[0] == 0xFF:
            scaled = float(value_int)
        elif data_coding in (_DCT_DATETIME_F, _DCT_DATE_G):
            scaled = value_float
        else:
            scaled = float(value_int)
            if vif_array[0] != 0xFF:
                scaled = scaled * (10.0 ** scalar) + extension_additive

        # ---- Build result name ----
        code = vif_def.code
        base_name = get_code_name(code)
        full_name = f"{base_name}{name_extension}{func_suffix}"

        # ---- Build units ----
        units: str | None = None
        if is_custom_vif:
            units = custom_vif
        elif not no_unit:
            units = get_code_units(code)

        # ---- Assemble record ----
        rec = MBusRecord(
            vif_hex=f"0x{vif_value:x}",
            code=int(code),
            name=full_name,
            units=units,
            storage=storage_number if storage_number > 0 else None,
            sub_unit=sub_unit if sub_unit > 0 else None,
            tariff=tariff if tariff > 0 else None,
        )
        if ascii_value != 1:
            rec.value_scaled = scaled
        if ascii_value >= 1:
            rec.value_string = value_string

        records.append(rec)

        # ---- Check for manufacturer-specific / continuation markers ----
        if index < size and buf[index] == 0x0F:
            break
        if index < size and buf[index] == 0x1F:
            rec.to_dict()  # ensure data is valid
            break

    return records


# ---------------------------------------------------------------------------
# Convenience: decode a full long-frame telegram
# ---------------------------------------------------------------------------

# Standard offsets in M-Bus long frame
FRAME_HEADER_SIZE = 19  # 0x13 — start of variable data records
FRAME_OVERHEAD = 2      # checksum + stop byte at end


def decode_telegram(telegram: bytes | bytearray) -> tuple[int, list[MBusRecord]]:
    """Decode a full M-Bus long-frame telegram.

    Returns ``(slave_address, records)``.

    Raises `MBusDecodeError` on invalid framing.
    """
    if len(telegram) < 10:
        raise MBusDecodeError("Telegram too short")
    if telegram[0] != 0x68 or telegram[3] != 0x68:
        raise MBusDecodeError("Invalid start bytes")
    if telegram[-1] != 0x16:
        raise MBusDecodeError("Invalid stop byte")

    declared_len = telegram[1]
    if telegram[2] != declared_len:
        raise MBusDecodeError("Length bytes mismatch")

    # Checksum: sum of bytes between second 0x68 (exclusive) and CS byte
    payload_start = 4
    payload_end = 4 + declared_len
    if payload_end + 2 > len(telegram):
        raise MBusDecodeError("Telegram shorter than declared length")
    cs_expected = sum(telegram[payload_start:payload_end]) & 0xFF
    cs_actual = telegram[payload_end]
    if cs_expected != cs_actual:
        raise MBusDecodeError(
            f"Checksum mismatch: expected 0x{cs_expected:02X}, got 0x{cs_actual:02X}"
        )

    slave_address = telegram[5]
    # Variable data records start at offset 19 (0x13)
    data_start = FRAME_HEADER_SIZE
    data_end = payload_end  # exclusive
    records = decode(telegram[data_start:data_end], data_end - data_start)
    return slave_address, records
