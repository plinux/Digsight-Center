import csv
import json
import unittest
from pathlib import Path


class FunctionIconCatalogTest(unittest.TestCase):
  def setUp(self):
    self.catalog_path = Path("config/function-icons.json")
    self.mapping_path = Path("config/function-icon-mappings/z21.json")
    self.icon_dir = Path("assets/icons/functions")

  def test_catalog_exists_and_uses_only_local_icons(self):
    catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
    self.assertEqual(catalog["version"], 1)
    self.assertIn("icons", catalog)
    self.assertNotIn("aliases", catalog)
    for icon_key, meta in catalog["icons"].items():
      icon_path = Path(meta["path"])
      self.assertFalse(str(icon_path).startswith(("http://", "https://", "//")))
      self.assertEqual(icon_path.suffix, ".svg", icon_key)
      self.assertTrue((Path(".") / icon_path).exists(), icon_key)
      self.assertIn("license", meta)
      self.assertIn("source", meta)

  def test_local_icon_catalog_and_z21_mapping_are_separated(self):
    catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
    mapping = json.loads(self.mapping_path.read_text(encoding="utf-8"))

    self.assertNotIn("aliases", catalog)
    self.assertIn("icons", catalog)
    self.assertEqual(mapping["version"], 1)
    self.assertEqual(mapping["source_system"], "z21")
    self.assertEqual(mapping["target_catalog"], "config/function-icons.json")
    self.assertIn("mappings", mapping)

    self.assertGreaterEqual(len(catalog["icons"]), 60)
    self.assertEqual(catalog["icons"]["window-toggle"]["label"], "车窗开关")
    self.assertEqual(mapping["mappings"]["车窗开关"], "window-toggle")
    self.assertEqual(mapping["mappings"]["车窗"], "window-toggle")

    required = {
      "coach-light": ["车厢灯", "室内灯", "coach_light"],
      "step-light": ["踏脚灯", "脚踏灯", "step_light"],
      "destination-sign": ["方向牌灯", "destination_plate_light", "路牌灯"],
      "parking-brake": ["手制动", "手刹", "parking_brake"],
      "water-pump": ["抽水泵", "给水泵", "water_pump"],
      "firebox": ["火箱", "firebox"],
      "generator": ["发电机", "generator"],
      "preheater": ["内燃机预热", "预热", "preheat"],
      "hood": ["引擎盖", "打开引擎盖", "关闭引擎盖", "hood_open", "hood_close"],
      "turntable": ["转车台", "向左旋转", "向右旋转", "turntable"],
      "load-mode": ["重载", "重车模式", "weight"],
      "load-lift": ["升降货", "超重货上升", "超重货下降", "load_lift"],
      "rpm-up": ["内燃机提速", "rpm_up", "diesel_regulation_step_up"],
      "rpm-down": ["内燃机减速", "rpm_down", "diesel_regulation_step_down"],
      "rail-sound": ["轮轨声", "rail_kick"],
      "crane": ["吊车", "crane", "Kran"],
      "crane-rotate-left": ["吊车左转", "吊臂左转", "crane_rotate_left"],
      "crane-rotate-right": ["吊车右转", "吊臂右转", "crane_rotate_right"],
      "crane-boom-up": ["吊臂升", "吊臂上升", "crane_boom_up"],
      "crane-boom-down": ["吊臂降", "吊臂下降", "crane_boom_down"],
      "crane-boom-extend": ["吊臂伸出", "伸臂", "crane_boom_extend"],
      "crane-boom-retract": ["吊臂缩回", "缩臂", "crane_boom_retract"],
      "crane-hook-up": ["吊钩升", "吊钩上升", "crane_hook_up"],
      "crane-hook-down": ["吊钩降", "吊钩下降", "crane_hook_down"],
      "crane-outrigger": ["支腿", "支撑", "crane_outrigger"],
      "crane-free-run": ["自由拖行", "Freilauf", "crane_free_run"],
      "whistle-short": ["短鸣汽笛", "短鸣笛", "短汽笛", "whistle_short"],
      "whistle-long": ["长鸣汽笛", "长鸣笛", "长汽笛", "whistle_long"],
      "horn-low": ["低音风笛", "低音汽笛", "horn_low"],
      "horn-high": ["高音风笛", "高音汽笛", "horn_high"],
      "horn-mixed": ["混合鸣笛", "混音鸣笛", "双鸣笛", "horn_two_sound"],
      "electric-whistle": ["电笛", "短电笛", "长电笛"],
    }
    for icon_key, aliases in required.items():
      self.assertIn(icon_key, catalog["icons"])
      for alias in aliases:
        self.assertEqual(mapping["mappings"].get(alias), icon_key, alias)

  def test_roco_ek750_0604_ho_function_and_crane_icons_are_fully_covered(self):
    catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
    mapping = json.loads(self.mapping_path.read_text(encoding="utf-8"))
    z21_mappings = mapping["mappings"]
    icons = catalog["icons"]
    default_icon = catalog["default_icon"]

    def resolve(image_name, label=""):
      for candidate in [image_name, label]:
        if not candidate:
          continue
        icon_key = z21_mappings.get(candidate)
        if icon_key in icons:
          return icon_key
        if candidate in icons:
          return candidate
      searchable = f"{image_name} {label}".lower()
      for icon_key, meta in icons.items():
        for keyword in meta.get("keywords", []):
          if str(keyword).lower() in searchable:
            return icon_key
      return default_icon

    expected_function_icons = {
      "main_beam2": "light-front",
      "sound2": "sound-generic",
      "hump_gear": "shunting-mode",
      "light": "light-front",
      "coach_side_light_off": "coach-light",
      "whistle_short": "whistle-short",
      "whistle_long": "whistle-long",
      "mute": "mute",
      "bugle": "horn-mixed",
      "compressor": "compressor",
      "rail_kick": "rail-sound",
      "hood_open": "hood",
      "hood_close": "hood",
      "neutral": "shunting-mode",
    }
    csv_path = Path("tests/fixtures/z21_crane_functions.csv")
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
      rows = list(csv.DictReader(handle))
    seen = {row["图标 image_name"]: resolve(row["图标 image_name"], row["功能名称 shortcut"]) for row in rows}
    self.assertEqual(set(seen), set(expected_function_icons))
    for image_name, expected_icon_key in expected_function_icons.items():
      self.assertEqual(seen[image_name], expected_icon_key, image_name)
      self.assertNotEqual(seen[image_name], default_icon, image_name)

    required_crane_icons = [
      "crane",
      "crane-rotate-left",
      "crane-rotate-right",
      "crane-boom-up",
      "crane-boom-down",
      "crane-boom-extend",
      "crane-boom-retract",
      "crane-hook-up",
      "crane-hook-down",
      "crane-outrigger",
      "crane-free-run",
    ]
    for icon_key in required_crane_icons:
      self.assertIn(icon_key, icons)
      self.assertNotEqual(icon_key, default_icon)
      self.assertTrue((Path(".") / icons[icon_key]["path"]).exists(), icon_key)

  def test_icon_catalog_lists_every_local_icon_identifier(self):
    catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
    for icon_key, meta in catalog["icons"].items():
      self.assertTrue(icon_key)
      self.assertTrue(meta["label"])
      self.assertTrue((Path(".") / meta["path"]).exists(), icon_key)


if __name__ == "__main__":
  unittest.main()
