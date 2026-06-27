"""DXDCNet UDP checksum strategies.

The protocol reference does not define the UDP checksum algorithm. The
unconfirmed strategy is the safe default for real device paths.
"""


class NoChecksumAlgorithm:
  name = "unconfirmed"

  def compute(self, frame_body: bytes) -> int:
    raise ValueError("DXDCNet UDP checksum algorithm is not confirmed")


class XORChecksumAlgorithm:
  name = "xor"

  def compute(self, frame_body: bytes) -> int:
    checksum = 0
    for value in frame_body:
      checksum ^= value
    return checksum


def checksum_from_name(name: str):
  normalized = (name or "").strip().lower()
  if normalized == "xor":
    return XORChecksumAlgorithm()
  if normalized in {"", "unconfirmed"}:
    return NoChecksumAlgorithm()
  raise ValueError(f"Unsupported or unconfirmed DXDCNet checksum algorithm: {name}")
