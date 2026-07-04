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
      "soundReplaceUploadInput",
      "soundFileEditorDialog",
      "soundFileEditorDialogContent",
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
    css = self.read_text("assets/css/app.css")

    self.assertIn("soundNodeFileSelect", view_source)
    self.assertIn("renderSoundFileInventory", view_source)
    self.assertIn("renderSoundFileEditorDialog", view_source)
    self.assertIn("setNodeSoundFile", controller_source)
    self.assertIn("addSoundNode", controller_source)
    self.assertIn("moveSoundNode", controller_source)
    self.assertIn("resizeSoundNode", controller_source)
    self.assertIn("updateSoundNodeField", controller_source)
    self.assertIn("addSoundConnector", controller_source)
    self.assertIn("updateSoundConnectorEndpoint", controller_source)
    self.assertIn("updateSoundConnectorField", controller_source)
    self.assertIn("soundUsageForProject", controller_source)
    self.assertIn("deleteUnusedSoundFile", controller_source)
    self.assertIn("replaceSoundFile", controller_source)
    self.assertIn("openSoundFileEditor", controller_source)
    self.assertIn("closeSoundFileEditor", controller_source)
    self.assertIn("data-sound-file-delete", view_source)
    self.assertIn("data-sound-file-edit", view_source)
    self.assertIn("已被 Slot 或节点引用，不能删除", view_source)
    self.assertIn("data-replacement-sound-id", view_source)
    self.assertIn("soundReplaceUploadInput", controller_source)
    self.assertIn("soundCanvasZoomOut", view_source)
    self.assertIn("soundCanvasZoomIn", view_source)
    self.assertIn("soundCanvasZoomReset", view_source)
    self.assertIn("sound-node-canvas-content", view_source)
    self.assertIn("soundAddNodeButton", view_source)
    self.assertIn("soundAddConnectorButton", view_source)
    self.assertIn("data-node-resize-key", view_source)
    self.assertIn("data-connector-end", view_source)
    self.assertIn("wireConnectorEndpointDragging", view_source)
    self.assertIn("resizeSoundNode", view_source)
    self.assertIn("updateSoundConnectorEndpoint", view_source)
    self.assertIn("soundConnectorSourceSelect", view_source)
    self.assertIn("soundConnectorTargetSelect", view_source)
    self.assertIn("data-node-field", view_source)
    self.assertIn("data-connector-field", view_source)
    self.assertIn("wheel", view_source)
    self.assertIn("pointerdown", view_source)
    self.assertIn("moveSoundNode", view_source)
    self.assertIn("setSoundCanvasZoom", controller_source)
    self.assertIn("panSoundCanvas", controller_source)
    self.assertIn("soundCanvasBoundsForSlot", controller_source)
    self.assertIn("pendingSoundExport", controller_source)
    self.assertIn("hasPendingSoundExport", controller_source)
    self.assertIn("markSoundEditorExportStarted", controller_source)
    self.assertIn("markSoundEditorExported", controller_source)
    self.assertNotIn("editRevision", controller_source)
    self.assertNotIn("lastExportedRevision", controller_source)
    self.assertIn(".sound-node-canvas-scroll", css)
    self.assertIn("overflow: auto;", css)

  def test_sound_editor_visible_labels_use_chinese_terms(self):
    html = self.read_text("index.html")
    view_source = self.read_text("assets/js/sound-editor-view.js")
    readme = self.read_text("README.md")
    manual = self.read_text("manual/MANUAL.html")
    combined_visible_text = "\n".join([html, view_source, readme, manual])

    for text in ["Slot", "添加节点", "添加连接", "节点", "连接"]:
      self.assertIn(text, combined_visible_text)
    for text in ["添加 Node", ">Slots<", ">Node ", ">Connection "]:
      self.assertNotIn(text, combined_visible_text)

  def test_sound_editor_warns_before_closing_with_unexported_changes(self):
    app_source = self.read_text("assets/js/app.js")
    bootstrap_source = self.read_text("assets/js/app-bootstrap.js")
    controller_source = self.read_text("assets/js/sound-editor-controller.js")
    sound_events_source = self.source_function(controller_source, "wireSoundEditorEvents")

    self.assertIn("hasPendingSoundExport", app_source)
    self.assertIn("warnBeforeClosingWithPendingSoundExport", app_source)
    self.assertIn("addEventListener(\"beforeunload\"", app_source)
    self.assertIn("markSoundEditorExportStarted(state)", sound_events_source)
    self.assertIn("markSoundEditorExported(state)", sound_events_source)
    self.assertIn("markSoundEditorExportFailed(state)", sound_events_source)
    self.assertIn("markSoundEditorChanged(state)", sound_events_source)
    self.assertIn("wireSoundEditorEvents?.();", bootstrap_source)

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
