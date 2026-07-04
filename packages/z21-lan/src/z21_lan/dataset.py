"""Z21 LAN dataset encoder and decoder."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Z21Dataset:
  """One Z21 dataset from a UDP datagram."""

  data_len: int
  header: int
  payload: bytes

  def to_bytes(self) -> bytes:
    return encode_dataset(self.header, self.payload)

  def to_debug_dict(self) -> dict:
    return {
      "header": f"0x{self.header:04x}",
      "payload_hex": self.payload.hex(" "),
      "raw_hex": self.to_bytes().hex(" "),
    }


def encode_dataset(header: int, payload: bytes = b"") -> bytes:
  """Encode one Z21 dataset with little-endian length and header."""
  payload = bytes(payload or b"")
  data_len = 4 + len(payload)
  if data_len > 0xFFFF:
    raise ValueError("Z21 dataset is too large")
  return data_len.to_bytes(2, "little") + int(header).to_bytes(2, "little") + payload


def decode_datasets(datagram: bytes) -> list[Z21Dataset]:
  """Decode one UDP datagram into Z21 datasets."""
  data = bytes(datagram or b"")
  datasets = []
  offset = 0
  while offset < len(data):
    if len(data) - offset < 4:
      raise ValueError("Z21 datagram has a truncated dataset header")
    data_len = int.from_bytes(data[offset:offset + 2], "little")
    header = int.from_bytes(data[offset + 2:offset + 4], "little")
    if data_len < 4:
      raise ValueError("Z21 dataset length must be at least 4")
    end = offset + data_len
    if end > len(data):
      raise ValueError("Z21 dataset length exceeds datagram size")
    datasets.append(Z21Dataset(
      data_len=data_len,
      header=header,
      payload=data[offset + 4:end],
    ))
    offset = end
  return datasets
