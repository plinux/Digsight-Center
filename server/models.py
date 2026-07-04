"""Shared domain constants and validators."""

CONTROLLER_DEFAULT_IP = "0.0.0.0"
CONTROLLER_KIND_DIGSIGHT = "digsight_controller"
CONTROLLER_KIND_ECOS_50200 = "ecos_50200_controller"
CONTROLLER_KIND_Z21_STD = "z21_std_controller"
CONTROLLER_KIND_Z21_START = "z21_start_controller"
CONTROLLER_KIND_Z21_XL = "z21_xl_controller"
CONTROLLER_PROTOCOL_DXDCNET = "DXDCNet"
CONTROLLER_PROTOCOL_ECOS = "ECoS"
CONTROLLER_PROTOCOL_Z21_LAN = "Z21LAN"
DXDCNET_DEFAULT_UDP_PORT = 12000
DXDCNET_DEFAULT_LOCAL_UDP_PORT = 6667
DXDCNET_DEFAULT_CHECKSUM_ALGORITHM = "xor"
ECOS_DEFAULT_TCP_PORT = 15471
Z21_DEFAULT_UDP_PORT = 21105
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
CONTROL_PROTOCOL_DCC = "dcc"
CONTROL_PROTOCOL_MOTOROLA = "motorola"
CONTROL_PROTOCOL_M4 = "m4"
DEFAULT_CONTROL_PROTOCOL = CONTROL_PROTOCOL_DCC
DEFAULT_SPEED_STEPS = 128
CONTROL_PROTOCOL_SPEED_STEPS = {
  CONTROL_PROTOCOL_DCC: {14, 28, 128},
  CONTROL_PROTOCOL_MOTOROLA: {1, 2, 28},
  CONTROL_PROTOCOL_M4: {128},
}
CONTROL_PROTOCOL_SPEED_STEP_COUNTS = {
  CONTROL_PROTOCOL_DCC: {14: 14, 28: 28, 128: 126},
  CONTROL_PROTOCOL_MOTOROLA: {1: 14, 2: 27, 28: 28},
  CONTROL_PROTOCOL_M4: {128: 126},
}
SCREEN_DIRECTION_LABELS = {
  0x00: "左",
  0x01: "上",
  0x02: "右",
  0x03: "下",
}


def validate_controller_kind(kind: str) -> str:
  value = str(kind or "").strip().lower()
  if not value or not value.endswith("_controller"):
    raise ValueError(f"controller kind must use xx_controller format: {value}")
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


def validate_control_protocol(control_protocol: str) -> str:
  normalized = str(control_protocol or DEFAULT_CONTROL_PROTOCOL).strip().lower()
  if normalized not in CONTROL_PROTOCOL_SPEED_STEPS:
    allowed = ", ".join(sorted(CONTROL_PROTOCOL_SPEED_STEPS))
    raise ValueError(f"control protocol must be one of: {allowed}")
  return normalized


def validate_speed_steps(control_protocol: str, speed_steps) -> int:
  protocol = validate_control_protocol(control_protocol)
  try:
    normalized = int(speed_steps or DEFAULT_SPEED_STEPS)
  except (TypeError, ValueError) as exc:
    raise ValueError("speed steps must be an integer") from exc
  allowed = CONTROL_PROTOCOL_SPEED_STEPS[protocol]
  if normalized not in allowed:
    allowed_text = ", ".join(str(value) for value in sorted(allowed))
    raise ValueError(f"{protocol} speed steps must be one of: {allowed_text}")
  return normalized


def speed_step_count(control_protocol: str, speed_steps) -> int:
  protocol = validate_control_protocol(control_protocol)
  normalized = validate_speed_steps(protocol, speed_steps)
  return CONTROL_PROTOCOL_SPEED_STEP_COUNTS[protocol][normalized]


def scale_loco_speed_for_steps(speed: int, control_protocol: str, speed_steps: int) -> int:
  speed_value = int(speed)
  if speed_value <= 0:
    return 0
  target_max = speed_step_count(control_protocol, speed_steps)
  if target_max == 126:
    return max(1, min(126, speed_value))
  return max(1, min(target_max, round(speed_value * target_max / 126)))


def default_track_profiles() -> dict:
  return {
    TRACK_MODE_N: {
      "mode": TRACK_MODE_N,
      "name": "N",
      "output_value": N_OUTPUT_VALUE,
      "target_voltage_v": 12.0,
      "max_target_voltage_v": 12.0,
      "current_param": N_CURRENT_PARAM,
      "target_current_limit_ma": None,
      "max_target_current_limit_ma": CONTROLLER_CURRENT_LIMIT_MAX_MA,
    },
    TRACK_MODE_HO: {
      "mode": TRACK_MODE_HO,
      "name": "HO",
      "output_value": HO_OUTPUT_VALUE,
      "target_voltage_v": 15.2,
      "max_target_voltage_v": 15.2,
      "current_param": HO_CURRENT_PARAM,
      "target_current_limit_ma": None,
      "max_target_current_limit_ma": CONTROLLER_CURRENT_LIMIT_MAX_MA,
    },
    TRACK_MODE_G: {
      "mode": TRACK_MODE_G,
      "name": "G",
      "output_value": G_OUTPUT_VALUE,
      "target_voltage_v": 18.0,
      "max_target_voltage_v": 18.0,
      "current_param": G_CURRENT_PARAM,
      "target_current_limit_ma": None,
      "max_target_current_limit_ma": CONTROLLER_CURRENT_LIMIT_MAX_MA,
    },
    TRACK_MODE_DC: {
      "mode": TRACK_MODE_DC,
      "name": "DC",
      "output_value": DC_OUTPUT_VALUE,
      "target_voltage_v": 12.0,
      "max_target_voltage_v": 15.2,
      "current_param": DC_CURRENT_PARAM,
      "target_current_limit_ma": None,
      "max_target_current_limit_ma": CONTROLLER_CURRENT_LIMIT_MAX_MA,
    },
  }


def validate_track_profile(mode: str, profile: dict, defaults: dict | None = None) -> dict:
  normalized = validate_profile_mode(mode)
  fallback_defaults = default_track_profiles()[normalized]
  defaults = dict(defaults or fallback_defaults)
  result = dict(defaults)
  if "target_voltage_v" in profile:
    result["target_voltage_v"] = profile["target_voltage_v"]
  supports_current_limit = "target_current_limit_ma" in defaults or "max_target_current_limit_ma" in defaults
  if supports_current_limit and "target_current_limit_ma" in profile:
    result["target_current_limit_ma"] = profile["target_current_limit_ma"]
  supports_voltage = "target_voltage_v" in defaults or "max_target_voltage_v" in defaults
  if supports_voltage:
    voltage = float(result["target_voltage_v"])
    min_voltage = float(defaults.get("min_target_voltage_v", 0))
    max_voltage = float(defaults.get("max_target_voltage_v", fallback_defaults["max_target_voltage_v"]))
    if voltage <= 0 or voltage < min_voltage or voltage > max_voltage:
      raise ValueError(f"{defaults['name']} target voltage must be {min_voltage}..{max_voltage} V")
    result["target_voltage_v"] = voltage
  else:
    result.pop("target_voltage_v", None)
    result.pop("min_target_voltage_v", None)
    result.pop("max_target_voltage_v", None)
  if supports_current_limit:
    current_limit = result.get("target_current_limit_ma")
    if current_limit in ("", None):
      result["target_current_limit_ma"] = None
    else:
      current_limit = int(current_limit)
      min_current = int(defaults.get("min_target_current_limit_ma", CURRENT_STEP_MA))
      max_current = int(defaults.get("max_target_current_limit_ma", fallback_defaults["max_target_current_limit_ma"]))
      current_step = int(defaults.get("current_step_ma", CURRENT_STEP_MA))
      if current_limit < min_current or current_limit > max_current:
        raise ValueError(f"{defaults['name']} target current limit must be {min_current}..{max_current} mA")
      if current_limit % current_step != 0:
        raise ValueError(f"{defaults['name']} target current limit must use {current_step} mA steps")
      result["target_current_limit_ma"] = current_limit
  else:
    result.pop("min_target_current_limit_ma", None)
    result.pop("target_current_limit_ma", None)
    result.pop("max_target_current_limit_ma", None)
    result.pop("current_step_ma", None)
  if "output_value" in defaults:
    result["output_value"] = defaults["output_value"]
  else:
    result.pop("output_value", None)
  if "current_param" in defaults:
    result["current_param"] = defaults["current_param"]
  else:
    result.pop("current_param", None)
  return result
