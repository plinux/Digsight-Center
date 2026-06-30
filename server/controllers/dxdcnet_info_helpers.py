"""DXDCNet controller information parsing helpers."""


def merge_device_info(controller: dict, **fields) -> None:
  controller["device_info"] = {
    **controller.get("device_info", {}),
    **fields,
  }


def apply_parameter_spec(controller, parsed_parameter, *, expected_param, warning_prefix, fields, warnings) -> bool:
  if parsed_parameter["param_address"] != expected_param:
    warnings.append(f"{warning_prefix}_param_mismatch")
    return False
  merge_device_info(controller, **fields(parsed_parameter))
  return True


def version_fields(version: dict, *, source: str, response_hex: str | None = None) -> dict:
  fields = {**version, "source": source}
  if response_hex is not None:
    fields["response_hex"] = response_hex
  return fields
