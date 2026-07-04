"""Reply and event block parser for the ESU ECoS PC Interface."""

from dataclasses import dataclass
import re

from esu_ecos.commands import BASIC_INFO_FIELDS, BASIC_OBJECT_ID, BOOSTER_MANAGER_OBJECT_ID


_START_RE = re.compile(r"^<(REPLY|EVENT)\s+(.+)>$")
_END_RE = re.compile(r"^<END\s+(-?\d+)\s+\((.*)\)>$")


@dataclass(frozen=True)
class ECoSBlock:
  """Parsed ECoS reply or event block."""

  kind: str
  command: str
  lines: tuple[str, ...]
  end_code: int
  end_message: str

  @property
  def ok(self) -> bool:
    return self.end_code == 0

  def to_debug_dict(self) -> dict:
    return {
      "kind": self.kind,
      "command": self.command,
      "lines": list(self.lines),
      "end_code": self.end_code,
      "end_message": self.end_message,
      "ok": self.ok,
    }


@dataclass(frozen=True)
class ECoSProgrammerEvent:
  state: str
  cv_number: int | None = None
  value: int | None = None
  object_id: int = 5
  raw_options: dict | None = None

  def to_debug_dict(self) -> dict:
    return {
      "object_id": self.object_id,
      "state": self.state,
      "cv": self.cv_number,
      "value": self.value,
      "options": dict(self.raw_options or {}),
    }


def parse_blocks(text: str) -> list[ECoSBlock]:
  """Parse ECoS text into reply/event blocks."""
  blocks = []
  current_kind = ""
  current_command = ""
  current_lines = []
  for raw_line in str(text or "").splitlines():
    line = raw_line.strip()
    if not line:
      continue
    start = _START_RE.match(line)
    if start:
      if current_kind:
        raise ValueError("ECoS block started before previous block ended")
      current_kind = start.group(1)
      current_command = start.group(2)
      current_lines = []
      continue
    end = _END_RE.match(line)
    if end:
      if not current_kind:
        raise ValueError("ECoS END line without block start")
      blocks.append(ECoSBlock(
        kind=current_kind,
        command=current_command,
        lines=tuple(current_lines),
        end_code=int(end.group(1)),
        end_message=end.group(2),
      ))
      current_kind = ""
      current_command = ""
      current_lines = []
      continue
    if not current_kind:
      raise ValueError(f"ECoS content line without block start: {line}")
    current_lines.append(line)
  if current_kind:
    raise ValueError("ECoS block missing END line")
  return blocks


def parse_object_options(line: str) -> tuple[int, dict]:
  """Parse one ECoS object line into object id and option values."""
  object_text, _, option_text = str(line or "").strip().partition(" ")
  if not object_text:
    raise ValueError("ECoS object line is empty")
  object_id = int(object_text)
  options = {}
  position = 0
  while position < len(option_text):
    while position < len(option_text) and option_text[position].isspace():
      position += 1
    if position >= len(option_text):
      break
    name_start = position
    while position < len(option_text) and option_text[position] not in "[ ":
      position += 1
    name = option_text[name_start:position]
    if not name:
      raise ValueError(f"Invalid ECoS option near: {option_text[name_start:]}")
    if position >= len(option_text) or option_text[position] != "[":
      options[name] = True
      continue
    raw_value, position = _read_bracket_value(option_text, position)
    values = _split_option_values(raw_value)
    options[name] = values[0] if len(values) == 1 else values
  return object_id, options


def parse_basic_info(text_or_blocks) -> dict:
  """Extract controller information fields from a basic object get reply."""
  blocks = parse_blocks(text_or_blocks) if isinstance(text_or_blocks, str) else list(text_or_blocks or [])
  command_prefix = f"get({BASIC_OBJECT_ID},"
  for block in blocks:
    if block.kind != "REPLY" or not block.command.startswith(command_prefix):
      continue
    if not block.ok:
      raise ValueError(f"ECoS get basic info failed: {block.end_code} {block.end_message}")
    merged_options = {}
    for line in block.lines:
      object_id, options = parse_object_options(line)
      if object_id == BASIC_OBJECT_ID:
        merged_options.update(options)
    if merged_options:
      return {field: merged_options.get(field, "") for field in BASIC_INFO_FIELDS}
  return {}


def parse_loco_query_results(text_or_blocks, *, address: int | None = None) -> list[dict]:
  blocks = parse_blocks(text_or_blocks) if isinstance(text_or_blocks, str) else list(text_or_blocks or [])
  locos = []
  for block in blocks:
    if block.kind != "REPLY" or not block.command.startswith("queryObjects(10,"):
      continue
    if not block.ok:
      raise ValueError(f"ECoS loco query failed: {block.end_code} {block.end_message}")
    for line in block.lines:
      object_id, options = parse_object_options(line)
      entry = {"object_id": object_id, **options}
      if address is not None and str(entry.get("addr", "")) != str(int(address)):
        continue
      locos.append(entry)
  return locos


def parse_booster_query_results(text_or_blocks) -> list[dict]:
  """Extract ECoS booster objects returned by the booster manager."""
  blocks = parse_blocks(text_or_blocks) if isinstance(text_or_blocks, str) else list(text_or_blocks or [])
  boosters = []
  command_prefix = f"queryObjects({BOOSTER_MANAGER_OBJECT_ID},"
  for block in blocks:
    if block.kind != "REPLY" or not block.command.startswith(command_prefix):
      continue
    if not block.ok:
      raise ValueError(f"ECoS booster query failed: {block.end_code} {block.end_message}")
    for line in block.lines:
      object_id, options = parse_object_options(line)
      boosters.append({"object_id": object_id, **options})
  return boosters


def parse_booster_monitor_info(text_or_blocks, *, object_id: int | None = None) -> dict:
  """Extract one booster monitor object from get replies."""
  blocks = parse_blocks(text_or_blocks) if isinstance(text_or_blocks, str) else list(text_or_blocks or [])
  target_object_id = int(object_id) if object_id is not None else None
  for block in blocks:
    if block.kind != "REPLY" or not block.command.startswith("get("):
      continue
    if not block.ok:
      raise ValueError(f"ECoS booster monitor read failed: {block.end_code} {block.end_message}")
    merged_options = {}
    matched_object_id = None
    for line in block.lines:
      parsed_object_id, options = parse_object_options(line)
      if target_object_id is not None and parsed_object_id != target_object_id:
        continue
      matched_object_id = parsed_object_id
      merged_options.update(options)
    if matched_object_id is not None and merged_options:
      return {"object_id": matched_object_id, **merged_options}
  return {}


def parse_programmer_event(text_or_blocks) -> ECoSProgrammerEvent:
  blocks = parse_blocks(text_or_blocks) if isinstance(text_or_blocks, str) else list(text_or_blocks or [])
  for block in blocks:
    if block.kind != "EVENT" or block.command.strip() != "5":
      continue
    if not block.ok:
      raise ValueError(f"ECoS programmer event failed: {block.end_code} {block.end_message}")
    for line in block.lines:
      object_id, options = parse_object_options(line)
      if int(object_id) != 5:
        continue
      cv_number, value = _parse_cv_option(options.get("cv"))
      return ECoSProgrammerEvent(
        state=str(options.get("state", "")),
        cv_number=cv_number,
        value=value,
        object_id=object_id,
        raw_options=options,
      )
  raise ValueError("ECoS programmer event for object 5 was missing")


def _read_bracket_value(text: str, open_position: int) -> tuple[str, int]:
  position = open_position + 1
  in_quote = False
  value_chars = []
  while position < len(text):
    char = text[position]
    if char == '"':
      if in_quote and position + 1 < len(text) and text[position + 1] == '"':
        value_chars.append('"')
        position += 2
        continue
      in_quote = not in_quote
      value_chars.append(char)
      position += 1
      continue
    if char == "]" and not in_quote:
      return "".join(value_chars), position + 1
    value_chars.append(char)
    position += 1
  raise ValueError("ECoS option value is missing closing bracket")


def _split_option_values(raw_value: str) -> list:
  values = []
  current = []
  in_quote = False
  for char in raw_value:
    if char == '"':
      in_quote = not in_quote
      current.append(char)
      continue
    if char == "," and not in_quote:
      values.append(_normalize_option_value("".join(current)))
      current = []
      continue
    current.append(char)
  values.append(_normalize_option_value("".join(current)))
  return values


def _normalize_option_value(value: str):
  stripped = value.strip()
  if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
    return stripped[1:-1]
  return stripped


def _parse_cv_option(value) -> tuple[int | None, int | None]:
  if value in ("", None):
    return None, None
  if isinstance(value, list):
    if not value:
      return None, None
    cv_number = int(value[0])
    cv_value = int(value[1]) if len(value) > 1 and str(value[1]).strip() != "" else None
    return cv_number, cv_value
  return int(value), None
