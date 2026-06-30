import unittest

from tests.frontend_tests.source_assertions import SourceAssertionsMixin


class DescriptorDrivenUiTest(SourceAssertionsMixin, unittest.TestCase):
  def test_gateway_api_fetches_capabilities(self):
    source = self.read_text("assets/js/gateway-api.js")
    self.assertIn("export function getCapabilities()", source)
    self.assertIn('requestJson("/api/capabilities"', source)

  def test_app_populates_controller_and_import_selects_from_capabilities(self):
    app_source = self.read_text("assets/js/app.js")
    controller_workflow_source = self.read_text("assets/js/controller-workflow.js")
    import_workflow_source = self.read_text("assets/js/import-workflow.js")
    selector_source = self.read_text("assets/js/capability-selectors.js")
    combined_source = app_source + controller_workflow_source + import_workflow_source
    self.assertIn("appState.capabilities", combined_source)
    self.assertIn("renderControllerKindOptions", controller_workflow_source)
    self.assertIn("renderImportFormatOptions", import_workflow_source)
    self.assertIn("export function controllerDescriptor(", controller_workflow_source)
    self.assertIn(".default_ip || \"\"", controller_workflow_source)
    self.assertIn("item.display_name || item.label || item.kind", selector_source)
    self.assertNotIn("动芯 DXDCNet", selector_source)
    self.assertNotIn("renderImportFormatOptions", app_source)
    self.assertNotIn("function controllerDescriptor(", app_source)
    self.assertNotIn('elements.importFormatSelect.value || "z21_layout_config"', combined_source)
    self.assertNotIn('elements.controllerKindSelect.value || "digsight_controller"', combined_source)
    self.assertNotIn('elements.controllerIp.value = appState.controller.ip || "', combined_source)


if __name__ == "__main__":
  unittest.main()
