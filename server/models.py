"""Shared domain constants and validators."""

CONTROLLER_DEFAULT_IP = "10.10.200.98"
CONTROLLER_KIND_DIGSIGHT = "digsight_controller"
SUPPORTED_CONTROLLER_KINDS = {CONTROLLER_KIND_DIGSIGHT}
DXDCNET_DEFAULT_UDP_PORT = 12000
DXDCNET_DEFAULT_LOCAL_UDP_PORT = 6667
DXDCNET_DEFAULT_CHECKSUM_ALGORITHM = "xor"
CONTROLLER_INFO_STATUS_TIMEOUT_SECONDS = 0.4
CONTROLLER_INFO_POLL_TIMEOUT_SECONDS = 0.25
TRACK_MODE_N = "n"
TRACK_MODE_HO = "ho"
TRACK_MODE_G = "g"
TRACK_MODE_DC = "dc"
DCC_TRACK_MODES = {TRACK_MODE_N, TRACK_MODE_HO, TRACK_MODE_G}
CONTROLLER_PROFILE_MODES = {TRACK_MODE_N, TRACK_MODE_HO, TRACK_MODE_G, TRACK_MODE_DC}
PROGRAMMING_TARGET_PROGRAMMING_TRACK = "programming_track"
PROGRAMMING_TARGET_MAIN_TRACK = "main_track"
PROGRAMMING_TARGETS = {
  PROGRAMMING_TARGET_PROGRAMMING_TRACK,
  PROGRAMMING_TARGET_MAIN_TRACK,
}

DCC_MODE_BIT = 0
DC_MODE_BIT = 1

N_OUTPUT_VALUE = 0x78
HO_OUTPUT_VALUE = 0xA0
G_OUTPUT_VALUE = 0xB4
DC_OUTPUT_VALUE = 0x00
N_CURRENT_PARAM = 0x81
HO_CURRENT_PARAM = 0x82
G_CURRENT_PARAM = 0x83
DC_CURRENT_PARAM = 0x84
CURRENT_STEP_MA = 40
CONTROLLER_CURRENT_LIMIT_MAX_MA = 255 * CURRENT_STEP_MA
SERVICE_MODE_LIMIT_MA = 250
DCC_ADDRESS_MIN = 1
DCC_ADDRESS_MAX = 9999
CONSIST_MAX_MEMBERS = 8
SCREEN_DIRECTION_LABELS = {
  0x00: "左",
  0x01: "上",
  0x02: "右",
  0x03: "下",
}


def validate_controller_kind(kind: str) -> str:
  value = str(kind or CONTROLLER_KIND_DIGSIGHT)
  if value not in SUPPORTED_CONTROLLER_KINDS:
    raise ValueError(f"unsupported controller kind: {value}")
  return value


def screen_direction_label(raw_value) -> str:
  if raw_value is None:
    return ""
  try:
    normalized = int(raw_value)
  except (TypeError, ValueError):
    return ""
  return SCREEN_DIRECTION_LABELS.get(normalized, "")


def validate_track_mode(track_mode: str) -> str:
  normalized = (track_mode or "").strip().lower()
  if normalized not in DCC_TRACK_MODES:
    raise ValueError("track mode must be N, HO or G for DCC digital operation")
  return normalized


def validate_profile_mode(track_mode: str) -> str:
  normalized = (track_mode or "").strip().lower()
  if normalized not in CONTROLLER_PROFILE_MODES:
    raise ValueError("track profile mode must be N, HO, G or DC")
  return normalized


def validate_programming_target(programming_target: str) -> str:
  normalized = str(programming_target or "").strip().lower()
  if normalized not in PROGRAMMING_TARGETS:
    raise ValueError("programming target must be programming_track or main_track")
  return normalized


def default_track_profiles() -> dict:
  return {
    TRACK_MODE_N: {
      "mode": TRACK_MODE_N,
      "name": "N",
      "output_value": N_OUTPUT_VALUE,
      "voltage_v": 12.0,
      "max_voltage_v": 12.0,
      "current_param": N_CURRENT_PARAM,
      "current_limit_ma": None,
      "max_current_limit_ma": CONTROLLER_CURRENT_LIMIT_MAX_MA,
    },
    TRACK_MODE_HO: {
      "mode": TRACK_MODE_HO,
      "name": "HO",
      "output_value": HO_OUTPUT_VALUE,
      "voltage_v": 15.2,
      "max_voltage_v": 15.2,
      "current_param": HO_CURRENT_PARAM,
      "current_limit_ma": None,
      "max_current_limit_ma": CONTROLLER_CURRENT_LIMIT_MAX_MA,
    },
    TRACK_MODE_G: {
      "mode": TRACK_MODE_G,
      "name": "G",
      "output_value": G_OUTPUT_VALUE,
      "voltage_v": 18.0,
      "max_voltage_v": 18.0,
      "current_param": G_CURRENT_PARAM,
      "current_limit_ma": None,
      "max_current_limit_ma": CONTROLLER_CURRENT_LIMIT_MAX_MA,
    },
    TRACK_MODE_DC: {
      "mode": TRACK_MODE_DC,
      "name": "DC",
      "output_value": DC_OUTPUT_VALUE,
      "voltage_v": 12.0,
      "max_voltage_v": 15.2,
      "current_param": DC_CURRENT_PARAM,
      "current_limit_ma": None,
      "max_current_limit_ma": CONTROLLER_CURRENT_LIMIT_MAX_MA,
    },
  }


def validate_track_profile(mode: str, profile: dict) -> dict:
  normalized = validate_profile_mode(mode)
  defaults = default_track_profiles()[normalized]
  result = dict(defaults)
  result.update(profile)
  voltage = float(result["voltage_v"])
  if voltage <= 0 or voltage > defaults["max_voltage_v"]:
    raise ValueError(f"{defaults['name']} voltage must be > 0 and <= {defaults['max_voltage_v']} V")
  current_limit = result.get("current_limit_ma")
  if current_limit in ("", None):
    result["current_limit_ma"] = None
  else:
    current_limit = int(current_limit)
    if current_limit < CURRENT_STEP_MA or current_limit > defaults["max_current_limit_ma"]:
      raise ValueError(f"{defaults['name']} current limit must be {CURRENT_STEP_MA}..{defaults['max_current_limit_ma']} mA")
    if current_limit % CURRENT_STEP_MA != 0:
      raise ValueError(f"{defaults['name']} current limit must use {CURRENT_STEP_MA} mA steps")
    result["current_limit_ma"] = current_limit
  result["voltage_v"] = voltage
  result["output_value"] = defaults["output_value"]
  result["current_param"] = defaults["current_param"]
  return result
