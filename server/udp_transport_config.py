"""Controller transport configuration validation and normalization."""

UDP_PORT_MIN = 1
UDP_PORT_MAX = 65535
LOCAL_UDP_PORT_MIN = 0


def validate_udp_port(port_value) -> int:
  port = int(port_value)
  if port < UDP_PORT_MIN or port > UDP_PORT_MAX:
    raise ValueError("UDP port must be in range 1..65535")
  return port


def validate_local_udp_port(port_value) -> int:
  port = int(port_value)
  if port < LOCAL_UDP_PORT_MIN or port > UDP_PORT_MAX:
    raise ValueError("local UDP port must be in range 0..65535")
  return port


def transport_port_value(value) -> int:
  try:
    return int(value)
  except (TypeError, ValueError):
    return 0


def udp_transport_default(transport_descriptor, key: str, fallback=0):
  return transport_descriptor.defaults.get(key, fallback)


def udp_transport_default_port(transport_descriptor, key: str) -> int:
  return transport_port_value(udp_transport_default(transport_descriptor, key, 0))


def udp_transport_checksum_algorithm(transport_descriptor) -> str:
  return str(udp_transport_default(transport_descriptor, "udp_checksum_algorithm", "unconfirmed"))


def udp_transport_checksum_algorithms(transport_descriptor) -> tuple[str, ...]:
  algorithms = transport_descriptor.metadata.get("checksum_algorithms")
  if algorithms:
    return tuple(str(algorithm) for algorithm in algorithms if str(algorithm))
  return (udp_transport_checksum_algorithm(transport_descriptor),)


def udp_transport_allows_zero_local_port(transport_descriptor) -> bool:
  return bool(transport_descriptor.metadata.get("allow_zero_local_udp_port", True))


def normalize_local_udp_port(port_value, transport_descriptor) -> int:
  local_port = validate_local_udp_port(port_value)
  if local_port == 0 and not udp_transport_allows_zero_local_port(transport_descriptor):
    return udp_transport_default_port(transport_descriptor, "local_udp_port")
  return local_port


def validate_checksum_algorithm(checksum_algorithm, allowed_algorithms=("xor",)) -> str:
  normalized = str(checksum_algorithm or "").strip().lower()
  allowed = tuple(algorithm for algorithm in allowed_algorithms if algorithm)
  if normalized not in allowed:
    allowed_text = ", ".join(allowed) if allowed else "<none>"
    raise ValueError(f"checksum algorithm must be one of: {allowed_text}")
  return normalized


def _default_or_raise(value, default, validator, *, strict: bool):
  try:
    return validator(value)
  except (TypeError, ValueError):
    if strict:
      raise
    return default


def normalize_transport_config(transport, transport_descriptor, *, strict: bool) -> dict:
  source = transport if isinstance(transport, dict) else {}
  normalized = {
    **transport_descriptor.default_config(),
    **source,
    "kind": str(source.get("kind") or transport_descriptor.kind),
  }
  if "udp_port" in normalized:
    normalized["udp_port"] = _default_or_raise(
      normalized.get("udp_port"),
      udp_transport_default_port(transport_descriptor, "udp_port"),
      validate_udp_port,
      strict=strict,
    )
  if "local_udp_port" in normalized:
    normalized["local_udp_port"] = _default_or_raise(
      normalized.get("local_udp_port"),
      udp_transport_default_port(transport_descriptor, "local_udp_port"),
      lambda value: normalize_local_udp_port(value, transport_descriptor),
      strict=strict,
    )
  if "udp_checksum_algorithm" in normalized:
    normalized["udp_checksum_algorithm"] = _default_or_raise(
      normalized.get("udp_checksum_algorithm"),
      udp_transport_checksum_algorithm(transport_descriptor),
      lambda value: validate_checksum_algorithm(value, udp_transport_checksum_algorithms(transport_descriptor)),
      strict=strict,
    )
  return normalized
