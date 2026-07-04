import unittest

from tests.frontend_tests.source_assertions import SourceAssertionsMixin


class SoundEditorContractTest(SourceAssertionsMixin, unittest.TestCase):
  def test_sound_editor_dom_and_navigation_exist(self):
    html = self.read_text("index.html")
    app_source = self.read_text("assets/js/app.js")
    bootstrap_source = self.read_text("assets/js/app-bootstrap.js")

    for element_id in [
      "navSoundEditor",
      "soundEditorView",
      "soundDxsdFileInput",
      "soundChipSelect",
      "soundImportDxsdButton",
      "soundGeneratePackageButton",
      "soundSlotList",
      "soundNodeCanvas",
      "soundPropertyPanel",
      "soundFileInventoryPanel",
      "soundLibraryPanel",
      "soundUploadInput",
      "soundPackageWarnings",
    ]:
      self.assertIn(f'id="{element_id}"', html)

    self.assertIn("音效编辑", html)
    self.assertIn("renderSoundEditor", app_source)
    self.assertIn("wireSoundEditorEvents", app_source)
    self.assertIn('elements.navSoundEditor.addEventListener("click"', bootstrap_source)

  def test_sound_editor_uses_dedicated_modules_and_api_helpers(self):
    app_source = self.read_text("assets/js/app.js")
    api_source = self.read_text("assets/js/gateway-api.js")
    view_source = self.read_text("assets/js/sound-editor-view.js")
    controller_source = self.read_text("assets/js/sound-editor-controller.js")

    self.assertIn('./sound-editor-view.js"', app_source)
    self.assertIn('./sound-editor-controller.js"', app_source)
    self.assertIn("export function getSoundChipProfiles", api_source)
    self.assertIn("export function getSoundLibrary", api_source)
    self.assertIn("export async function importSoundDxsd", api_source)
    self.assertIn("export function buildSoundPackage", api_source)
    self.assertIn("renderSoundEditor", view_source)
    self.assertIn("createSoundEditorState", controller_source)
    self.assertNotIn("digsight_8004", " ".join([app_source, view_source]))

  def test_sound_editor_styles_are_not_single_hue_or_card_nested(self):
    css = self.read_text("assets/css/app.css")

    for token in [
      ".sound-editor-layout",
      ".sound-slot-list",
      ".sound-node-canvas",
      ".sound-library-grid",
      ".sound-file-inventory",
      ".sound-property-panel",
      ".sound-warning-list",
      "@media (max-width: 900px)",
    ]:
      self.assertIn(token, css)
    self.assertNotIn(".sound-editor-card .sound-editor-card", css)

  def test_sound_editor_node_file_replacement_controls_exist(self):
    view_source = self.read_text("assets/js/sound-editor-view.js")
    controller_source = self.read_text("assets/js/sound-editor-controller.js")

    self.assertIn("soundNodeFileSelect", view_source)
    self.assertIn("renderSoundFileInventory", view_source)
    self.assertIn("setNodeSoundFile", controller_source)
    self.assertIn("soundUsageForProject", controller_source)

  def test_sound_editor_is_available_only_for_digsight_controller(self):
    app_source = self.read_text("assets/js/app.js")
    availability_source = self.source_function(app_source, "soundEditorAvailableForController")
    active_view_source = self.source_function(app_source, "setActiveView")
    nav_source = self.source_function(app_source, "setNavState")
    visible_state_source = self.source_function(app_source, "syncVisibleState")

    self.assertIn("const descriptor = controllerDescriptor(appState.capabilities, appState.controller?.kind);", availability_source)
    self.assertIn("return Boolean(descriptor.capabilities?.sound_editor);", availability_source)
    self.assertNotIn("digsight_controller", availability_source)
    self.assertIn('if (view === "sound" && !soundEditorAvailableForController()) {', active_view_source)
    self.assertIn("当前控制器不支持音效编辑", active_view_source)
    self.assertIn("elements.navSoundEditor.disabled = !soundEditorAvailableForController();", nav_source)
    self.assertIn('if (appState.activeView === "sound" && !soundEditorAvailableForController()) {', visible_state_source)
    self.assertIn('appState.activeView = "vehicle";', visible_state_source)


if __name__ == "__main__":
  unittest.main()
