import unittest

from tests.frontend_tests.source_assertions import SourceAssertionsMixin


class CapabilityImportFrontendContractTest(SourceAssertionsMixin, unittest.TestCase):
  def test_capability_selectors_are_dedicated_module(self):
    capability_source = self.read_text("assets/js/capability-selectors.js")
    app_source = self.read_text("assets/js/app.js")
    bootstrap_source = self.read_text("assets/js/app-bootstrap.js")
    controller_workflow_source = self.read_text("assets/js/controller-workflow.js")
    import_workflow_source = self.read_text("assets/js/import-workflow.js")

    self.assertIn("export function renderControllerKindOptions", capability_source)
    self.assertIn("export function renderImportFormatOptions", capability_source)
    self.assertIn("getCapabilities()", bootstrap_source)
    self.assertIn("getCapabilities,", app_source)
    self.assertIn("syncControllerDescriptorControls", app_source)
    self.assertIn("renderControllerKindOptions(", controller_workflow_source)
    self.assertIn("renderImportFormatOptions(", import_workflow_source)
    self.assertNotIn("renderImportFormatOptions", app_source)

  def test_import_workflow_is_dedicated_module(self):
    import_workflow_source = self.read_text("assets/js/import-workflow.js")
    app_source = self.read_text("assets/js/app.js")
    bootstrap_source = self.read_text("assets/js/app-bootstrap.js")

    self.assertIn("export function renderImportCapabilities", import_workflow_source)
    self.assertIn("export async function importSelectedConfigFile", import_workflow_source)
    self.assertIn("export async function runImportConfigWorkflow", import_workflow_source)
    self.assertIn("${summary.categories_imported || 0} 个分类", import_workflow_source)
    self.assertIn("runImportConfigWorkflow(", bootstrap_source)
    self.assertIn("runImportConfigWorkflow,", app_source)
    self.assertNotIn("importSelectedConfigFile", app_source)


if __name__ == "__main__":
  unittest.main()
