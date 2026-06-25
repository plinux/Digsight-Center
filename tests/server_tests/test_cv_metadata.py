import json
import tempfile
import unittest
from pathlib import Path

from server.api import ApiRouter
from server.app_state import default_state
from server.cv_catalog import cv_meaning, default_cv_catalog, load_cv_catalog, manufacturer_name


class CvMetadataTest(unittest.TestCase):
  def test_cv_metadata_exposes_chip_info_and_address_rules(self):
    body, status = ApiRouter(None).handle_json("GET", "/api/cv/metadata", b"", default_state())
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["chip_info_cvs"][0]["cv"], 8)
    self.assertEqual(payload["data"]["chip_info_cvs"][1]["cv"], 7)
    self.assertEqual([item["cv"] for item in payload["data"]["chip_info_cvs"]], [8, 7])
    self.assertEqual(payload["data"]["manufacturer_registry"]["known_ids"]["86"], "Wekomm Engineering, GmbH")
    self.assertEqual(payload["data"]["manufacturer_registry"]["known_ids"]["151"], "ESU")
    self.assertEqual(payload["data"]["manufacturer_registry"]["known_ids"]["162"], "PIKO")
    self.assertEqual(payload["data"]["manufacturer_registry"]["known_ids"]["161"], "Roco / Modelleisenbahn GmbH")
    self.assertEqual(payload["data"]["address"]["min"], 1)
    self.assertEqual(payload["data"]["address"]["max"], 9999)
    self.assertEqual(payload["data"]["cv_value"]["max"], 255)
    self.assertEqual(payload["data"]["cv_catalog"]["standard_definitions"]["29"], "DCC 基本配置")
    self.assertEqual(payload["data"]["cv_catalog"]["standard_definitions"]["8"], "生产厂家（只读；写入特定值可触发厂家复位）")
    self.assertIn(1, payload["data"]["cv_catalog"]["standard_explicit_numbers"])
    self.assertIn(8, payload["data"]["cv_catalog"]["standard_explicit_numbers"])
    self.assertNotIn(112, payload["data"]["cv_catalog"]["standard_explicit_numbers"])
    self.assertEqual(payload["data"]["cv_catalog"]["profile_map"]["151"], "esu")
    self.assertEqual(payload["data"]["cv_catalog"]["profile_map"]["86"], "okdcc")
    self.assertNotIn("174", payload["data"]["cv_catalog"]["profile_map"])
    self.assertEqual(payload["data"]["cv_catalog"]["vendor_profiles"]["esu"]["cv_definitions"]["63"], "总音量")
    self.assertEqual(payload["data"]["cv_catalog"]["vendor_profiles"]["esu"]["cv_definitions"]["8"], "生产厂家/复位（写入8恢复出厂）")
    self.assertIn(63, payload["data"]["cv_catalog"]["vendor_explicit_numbers"]["esu"])
    self.assertEqual(payload["data"]["cv_catalog"]["vendor_profiles"]["okdcc"]["reset_method"]["cv"], 8)
    self.assertEqual(payload["data"]["cv_catalog"]["vendor_profiles"]["okdcc"]["reset_method"]["value"], 174)
    self.assertEqual(payload["data"]["cv_catalog"]["vendor_profiles"]["marklin-trix"]["reset_method"]["value"], 8)

  def test_cv_catalog_resolves_vendor_specific_meaning_from_config(self):
    self.assertEqual(manufacturer_name(151), "ESU")
    self.assertEqual(manufacturer_name(162), "PIKO")
    self.assertEqual(manufacturer_name(86), "OKDCC / OK 科技")
    self.assertEqual(manufacturer_name(174), "IMON Corporation")
    self.assertIn("未分配厂家 ID", manufacturer_name(8))
    self.assertEqual(cv_meaning(63, 151), "总音量")
    self.assertEqual(cv_meaning(8, 151), "生产厂家/复位（写入8恢复出厂）")
    self.assertEqual(cv_meaning(8, 162), "生产厂家/复位（写入8恢复出厂）")
    self.assertEqual(cv_meaning(8, 30), "生产厂家/复位（写入8恢复出厂）")
    self.assertEqual(cv_meaning(8, 86), "生产厂家/复位（写入174恢复出厂）")
    self.assertEqual(cv_meaning(8, 131), "生产厂家/复位（写入8恢复出厂）")
    self.assertEqual(cv_meaning(8, None), "生产厂家（只读；写入特定值可触发厂家复位）")
    self.assertEqual(cv_meaning(65, 151), "制动停止微调")
    self.assertEqual(cv_meaning(257, 162), "总音量（需 CV31=16, CV32=0）")
    self.assertEqual(cv_meaning(266, 145), "总音量")
    self.assertEqual(cv_meaning(63, 145), "灯效/制动灯延时")
    self.assertEqual(cv_meaning(113, 30), "总音量")
    self.assertEqual(cv_meaning(33, 30), "AUX_FL 功能分配")
    self.assertEqual(cv_meaning(56, 30), "EMF 算法模式")
    self.assertEqual(cv_meaning(114, 30), "模拟启动电压")
    self.assertEqual(cv_meaning(171, 30), "Slot1 响应功能")
    self.assertEqual(cv_meaning(234, 30), "Slot64 响应功能")
    self.assertEqual(cv_meaning(261, 30), "AUX_FL AND 逻辑")
    self.assertEqual(cv_meaning(317, 30), "Slot1 音量")
    self.assertEqual(cv_meaning(380, 30), "Slot64 音量")
    self.assertEqual(cv_meaning(381, 30), "重联有效 F13-F20")
    self.assertEqual(cv_meaning(388, 30), "自动刹车偏差检测电平")
    self.assertEqual(cv_meaning(401, 30), "低速强制开环倍数")

  def test_cv_catalog_known_numbers_use_explicit_definitions_not_ranges(self):
    catalog = default_cv_catalog()
    known = catalog.known_cv_numbers(86)
    self.assertIn(1, known)
    self.assertIn(8, known)
    self.assertIn(29, known)
    self.assertNotIn(512, known)
    self.assertNotIn(1024, known)

  def test_cv_catalog_can_be_overridden_by_config_files(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      config_dir = Path(temp_dir)
      (config_dir / "profiles").mkdir()
      (config_dir / "manufacturers.json").write_text(
        json.dumps({
          "source": "test",
          "known_ids": {"250": "测试厂家"},
          "unassigned_notes": {"8": "测试未分配"},
        }, ensure_ascii=False),
        encoding="utf-8",
      )
      (config_dir / "profile-map.json").write_text(
        json.dumps({
          "source": "test",
          "manufacturer_profiles": {"250": "custom"},
        }, ensure_ascii=False),
        encoding="utf-8",
      )
      (config_dir / "standard.json").write_text(
        json.dumps({
          "profile_name": "标准",
          "source": "test",
          "cv_definitions": {"42": "标准含义"},
        }, ensure_ascii=False),
        encoding="utf-8",
      )
      (config_dir / "profiles" / "custom.json").write_text(
        json.dumps({
          "profile_name": "Custom",
          "manufacturer_name": "自定义厂家",
          "source": "test",
          "aliases": ["自定义"],
          "cv_definitions": {"42": "厂商含义"},
        }, ensure_ascii=False),
        encoding="utf-8",
      )

      catalog = load_cv_catalog(config_dir)

    self.assertEqual(catalog.manufacturer_name(250), "自定义厂家")
    self.assertEqual(catalog.manufacturer_name(8), "测试未分配")
    self.assertEqual(catalog.cv_meaning(42, 250), "厂商含义")
    self.assertEqual(catalog.cv_meaning(42, 151), "标准含义")


if __name__ == "__main__":
  unittest.main()
