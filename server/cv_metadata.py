"""DCC CV metadata used by the programming UI."""

from server.cv_catalog import cv_catalog_payload, default_cv_catalog


def cv_metadata() -> dict:
  """Return standard CV ranges and well-known decoder information CVs."""
  catalog = default_cv_catalog()
  return {
    "chip_info_cvs": [
      {
        "cv": 8,
        "name": "生产厂家",
        "access": "read_only",
        "source": "NMRA S-9.2.2 CV8 Manufacturer ID",
        "auto_read": True,
      },
      {
        "cv": 7,
        "name": "软件版本",
        "access": "read_only",
        "source": "NMRA S-9.2.2 CV7 Decoder version",
        "auto_read": True,
      },
    ],
    "manufacturer_registry": {
      "source": "NMRA S-9.2.2 Appendix A, revised 8-May-2025",
      "url": "https://www.nmra.org/sites/default/files/standards/sandrp/DCC/S/appendix_a_s-9_2_2.pdf",
      "known_ids": dict(sorted(catalog.manufacturer_ids.items(), key=lambda item: int(item[0]))),
      "unassigned_notes": dict(sorted(catalog.unassigned_notes.items(), key=lambda item: int(item[0]))),
    },
    "cv_catalog": cv_catalog_payload(),
    "address": {
      "min": 1,
      "max": 9999,
      "short_address_cv": 1,
      "long_address_cvs": [17, 18],
      "config_cv": 29,
      "long_address_enable_bit": 5,
    },
    "cv_address": {
      "min": 1,
      "max": 1024,
    },
    "cv_value": {
      "min": 0,
      "max": 255,
      "bits": list(range(8)),
    },
  }
