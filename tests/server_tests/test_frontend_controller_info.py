from pathlib import Path
import unittest


class FrontendControllerInfoTest(unittest.TestCase):
  def test_controller_info_view_is_adapter_schema_driven(self):
    source = Path("assets/js/controller-view.js").read_text(encoding="utf-8")

    self.assertIn("normalizedControllerInfoSections", source)
    self.assertIn("controllerInfo.info_sections", source)
    self.assertIn("formatControllerInfoValue", source)
    self.assertNotIn('"设备名称"', source)
    self.assertNotIn('"出厂编号"', source)
    self.assertNotIn("formatBrightness", source)


if __name__ == "__main__":
  unittest.main()
