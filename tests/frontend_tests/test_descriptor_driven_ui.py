import unittest

from tests.frontend_tests.source_assertions import SourceAssertionsMixin


class DescriptorDrivenUiTest(SourceAssertionsMixin, unittest.TestCase):
  def test_gateway_api_fetches_capabilities(self):
    source = self.read_text("assets/js/gateway-api.js")
    self.assertIn("export function getCapabilities()", source)
    self.assertIn('requestJson("/api/capabilities"', source)

  def test_app_populates_controller_and_import_selects_from_capabilities(self):
    source = self.read_text("assets/js/app.js")
    self.assertIn("appState.capabilities", source)
    self.assertIn("renderControllerKindOptions", source)
    self.assertIn("renderImportFormatOptions", source)
    self.assertIn("function controllerDescriptor(", source)
    self.assertIn(".default_ip || \"\"", source)
    self.assertNotIn('elements.importFormatSelect.value || "z21_layout_config"', source)
    self.assertNotIn('elements.controllerKindSelect.value || "digsight_controller"', source)
    self.assertNotIn('elements.controllerIp.value = appState.controller.ip || "', source)


if __name__ == "__main__":
  unittest.main()
