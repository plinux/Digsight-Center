import unittest

from tests.frontend_tests.source_assertions import SourceAssertionsMixin


class CapabilityImportFrontendContractTest(SourceAssertionsMixin, unittest.TestCase):
  def test_capability_selectors_are_dedicated_module(self):
    capability_source = self.read_text("assets/js/capability-selectors.js")
    app_source = self.read_text("assets/js/app.js")
    bootstrap_source = self.read_text("assets/js/app-bootstrap.js")

    self.assertIn("export function renderControllerKindOptions", capability_source)
    self.assertIn("export function renderImportFormatOptions", capability_source)
    self.assertIn("getCapabilities()", bootstrap_source)
    self.assertIn("getCapabilities,", app_source)
    self.assertIn("renderControllerKindOptions(", app_source)

  def test_import_action_is_dedicated_module(self):
    import_action_source = self.read_text("assets/js/import-actions.js")
    app_source = self.read_text("assets/js/app.js")
    bootstrap_source = self.read_text("assets/js/app-bootstrap.js")

    self.assertIn("export async function importSelectedConfigFile", import_action_source)
    self.assertIn("${summary.categories_imported || 0} 个分类", import_action_source)
    self.assertIn("importSelectedConfigFile({", bootstrap_source)
    self.assertIn("importSelectedConfigFile,", app_source)


if __name__ == "__main__":
  unittest.main()
