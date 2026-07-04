"""Command builders for the ESU ECoS PC Interface."""

DEFAULT_ECOS_PORT = 15471
BASIC_OBJECT_ID = 1
LOCO_MANAGER_OBJECT_ID = 10
PROGRAMMER_OBJECT_ID = 5
BOOSTER_MANAGER_OBJECT_ID = 27
SYSTEM_BOOSTER_OBJECT_ID = 65000
DCC128_PROTOCOL = "DCC128"
ECOS_PROTOCOL_BY_CONTROL_PROTOCOL_SPEED = {
  ("dcc", 14): "DCC14",
  ("dcc", 28): "DCC28",
  ("dcc", 128): "DCC128",
  ("motorola", 1): "MM14",
  ("motorola", 2): "MM27",
  ("motorola", 28): "MM28",
  ("m4", 128): "M4",
}
BOOSTER_CURRENT_LIMIT_MIN_MA = 1000
BOOSTER_CURRENT_LIMIT_MAX_MA = 6000
BASIC_INFO_FIELDS = (
  "commandstationtype",
  "protocolversion",
  "hardwareversion",
  "applicationversion",
  "applicationversionsuffix",
  "railcom",
  "railcomplus",
  "status",
)
BOOSTER_MONITOR_FIELDS = (
  "name",
  "status",
  "current",
  "voltage",
  "temperature",
  "limit",
)


def build_request_command(object_id: int, permission: str) -> str:
  """Build a request command for view/control permissions."""
  normalized_permission = _normalize_permission(permission)
  return f"request({int(object_id)}, {normalized_permission})"


def build_release_command(object_id: int, permission: str) -> str:
  """Build a release command for view/control permissions."""
  normalized_permission = _normalize_permission(permission)
  return f"release({int(object_id)}, {normalized_permission})"


def _normalize_permission(permission: str) -> str:
  normalized_permission = str(permission or "").strip().lower()
  if normalized_permission not in {"view", "control"}:
    raise ValueError("ECoS request permission must be view or control")
  return normalized_permission


def build_get_command(object_id: int, fields) -> str:
  """Build a get command for an object and field sequence."""
  normalized_fields = tuple(str(field).strip() for field in fields if str(field).strip())
  if not normalized_fields:
    raise ValueError("ECoS get command requires at least one field")
  return f"get({int(object_id)}, {', '.join(normalized_fields)})"


def build_set_command(object_id: int, options) -> str:
  """Build a set command for raw ECoS option expressions."""
  normalized_options = tuple(str(option).strip() for option in options if str(option).strip())
  if not normalized_options:
    raise ValueError("ECoS set command requires at least one option")
  return f"set({int(object_id)}, {', '.join(normalized_options)})"


def build_power_command(powered: bool) -> str:
  return build_set_command(BASIC_OBJECT_ID, ("go" if bool(powered) else "stop",))


def build_railcom_command(enabled: bool) -> str:
  """Build a command that toggles ECoS RailCom on the command station object."""
  return build_set_command(BASIC_OBJECT_ID, (f"railcom[{_bool_option_value(enabled)}]",))


def build_railcomplus_command(enabled: bool) -> str:
  """Build a command that toggles ECoS RailComPlus on the command station object."""
  return build_set_command(BASIC_OBJECT_ID, (f"railcomplus[{_bool_option_value(enabled)}]",))


def build_loco_query_command() -> str:
  return f"queryObjects({LOCO_MANAGER_OBJECT_ID}, addr, name, protocol)"


def ecos_loco_protocol_name(control_protocol: str, speed_steps: int) -> str:
  key = (str(control_protocol or "dcc").strip().lower(), int(speed_steps or 128))
  if key not in ECOS_PROTOCOL_BY_CONTROL_PROTOCOL_SPEED:
    raise ValueError("unsupported ECoS loco protocol and speed-step combination")
  return ECOS_PROTOCOL_BY_CONTROL_PROTOCOL_SPEED[key]


def build_booster_query_command() -> str:
  """Build the command that lists ECoS booster objects."""
  return f"queryObjects({BOOSTER_MANAGER_OBJECT_ID}, name)"


def build_booster_monitor_commands(object_id: int) -> list[str]:
  """Build read-only commands for one ECoS booster monitor object."""
  booster_object_id = int(object_id)
  return [
    build_request_command(booster_object_id, "view"),
    build_get_command(booster_object_id, BOOSTER_MONITOR_FIELDS),
    build_release_command(booster_object_id, "view"),
  ]


def build_booster_current_limit_write_commands(object_id: int, current_limit_ma: int) -> list[str]:
  """Build commands to write and read back one ECoS booster current limit."""
  booster_object_id = int(object_id)
  current_limit = _validate_booster_current_limit_ma(current_limit_ma)
  return [
    build_request_command(booster_object_id, "control"),
    build_set_command(booster_object_id, (f"limit[{current_limit}]",)),
    build_get_command(booster_object_id, ("limit",)),
    build_release_command(booster_object_id, "control"),
  ]


def build_create_loco_command(address: int, name: str, protocol: str = DCC128_PROTOCOL) -> str:
  loco_address = _validate_loco_address(address)
  return (
    f"create({LOCO_MANAGER_OBJECT_ID}, "
    f"addr[{loco_address}], "
    f"name[{_quote_string(name)}], "
    f"protocol[{_protocol_name(protocol)}], append)"
  )


def build_loco_speed_command(object_id: int, speed: int, *, direction: str | None = None) -> str:
  speed_value = _validate_speed_128(speed)
  options = [f"speedstep[{speed_value}]"]
  if direction is not None:
    options.append(f"dir[{_direction_value(direction)}]")
  return build_set_command(object_id, options)


def build_loco_function_command(object_id: int, function_number: int, enabled: bool) -> str:
  function_index = int(function_number)
  if function_index < 0 or function_index > 31:
    raise ValueError("ECoS function number must be in 0..31")
  return build_set_command(object_id, (f"func[{function_index},{1 if bool(enabled) else 0}]",))


def build_programmer_cv_read_commands(cv_number: int) -> list[str]:
  cv = _validate_cv_number(cv_number)
  return [
    build_request_command(PROGRAMMER_OBJECT_ID, "view"),
    build_set_command(PROGRAMMER_OBJECT_ID, (f"mode[readdccdirect]", f"cv[{cv}]")),
  ]


def build_programmer_cv_write_commands(cv_number: int, value: int) -> list[str]:
  cv = _validate_cv_number(cv_number)
  cv_value = _validate_byte(value, "CV value")
  return [
    build_request_command(PROGRAMMER_OBJECT_ID, "view"),
    build_set_command(PROGRAMMER_OBJECT_ID, (f"mode[writedccdirect]", f"cv[{cv},{cv_value}]")),
  ]


def build_basic_info_commands() -> list[str]:
  """Build the read-only commands used to identify an ECoS controller."""
  return [
    build_request_command(BASIC_OBJECT_ID, "view"),
    build_get_command(BASIC_OBJECT_ID, BASIC_INFO_FIELDS),
  ]


def _quote_string(value: str) -> str:
  escaped = str(value or "").replace('"', '""')
  return f'"{escaped}"'


def _protocol_name(value: str) -> str:
  protocol = str(value or DCC128_PROTOCOL).strip().upper()
  if not protocol:
    raise ValueError("ECoS protocol must not be empty")
  return protocol


def _validate_loco_address(address: int) -> int:
  loco_address = int(address)
  if loco_address < 1 or loco_address > 10239:
    raise ValueError("ECoS DCC loco address must be in 1..10239")
  return loco_address


def _validate_speed_128(speed: int) -> int:
  speed_value = int(speed)
  if speed_value < 0 or speed_value > 126:
    raise ValueError("ECoS 128-step speed must be in 0..126")
  return speed_value


def _validate_cv_number(cv_number: int) -> int:
  cv = int(cv_number)
  if cv < 1 or cv > 1024:
    raise ValueError("ECoS CV number must be in 1..1024")
  return cv


def _validate_byte(value: int, label: str) -> int:
  byte_value = int(value)
  if byte_value < 0 or byte_value > 0xFF:
    raise ValueError(f"{label} must be in 0..255")
  return byte_value


def _validate_booster_current_limit_ma(current_limit_ma: int) -> int:
  current_limit = int(current_limit_ma)
  if current_limit < BOOSTER_CURRENT_LIMIT_MIN_MA or current_limit > BOOSTER_CURRENT_LIMIT_MAX_MA:
    raise ValueError(
      "ECoS booster current limit must be "
      f"in {BOOSTER_CURRENT_LIMIT_MIN_MA}..{BOOSTER_CURRENT_LIMIT_MAX_MA} mA"
    )
  return current_limit


def _bool_option_value(enabled: bool) -> int:
  return 1 if bool(enabled) else 0


def _direction_value(direction: str) -> int:
  normalized = str(direction or "forward").strip().lower()
  if normalized not in {"forward", "reverse"}:
    raise ValueError("ECoS direction must be forward or reverse")
  return 0 if normalized == "forward" else 1
