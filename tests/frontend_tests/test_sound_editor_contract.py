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
      "soundLibraryItems",
      "soundSlotLibraryHeader",
      "soundSlotLibraryItems",
      "soundUploadInput",
      "soundReplaceUploadInput",
      "soundFileEditorDialog",
      "soundFileEditorDialogContent",
      "soundPackageWarnings",
    ]:
      self.assertIn(f'id="{element_id}"', html)

    self.assertIn("音效编辑", html)
    self.assertIn('accept=".dxsd,.dxsp"', html)
    self.assertNotIn("application/zip", html)
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
    self.assertIn("export function saveSoundLibrarySound", api_source)
    self.assertIn("export function saveSoundLibrarySlot", api_source)
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
    self.assertIn("deleteUnusedSoundFiles", controller_source)
    self.assertIn("clearSoundSlot", controller_source)
    self.assertIn("copySoundSelection", controller_source)
    self.assertIn("pasteSoundSelection", controller_source)
    self.assertIn("deleteSoundSelection", controller_source)
    self.assertIn("selectSoundItemsInRect", controller_source)
    self.assertIn("saveActiveSlotToLibrary", controller_source)
    self.assertIn("saveSoundFileToLibrary", controller_source)
    self.assertIn("formatBitCount", controller_source)
    self.assertIn("formatMegabitCount", controller_source)
    self.assertIn("replaceSoundFile", controller_source)
    self.assertIn("openSoundFileEditor", controller_source)
    self.assertIn("closeSoundFileEditor", controller_source)
    self.assertIn("data-sound-file-delete", view_source)
    self.assertIn("data-delete-unused-sounds", view_source)
    self.assertIn("data-sound-file-sort", view_source)
    self.assertIn("data-sound-file-save", view_source)
    self.assertIn("data-sound-file-edit", view_source)
    self.assertIn("data-sound-file-play", view_source)
    self.assertIn("soundPreviewUrl", controller_source)
    self.assertIn("soundPreviewUrl", view_source)
    self.assertIn("试听", view_source)
    self.assertIn("pauseActiveSoundPreview", view_source)
    self.assertIn("resumeActiveSoundPreview", view_source)
    self.assertIn("syncSoundPreviewButtons", view_source)
    self.assertIn("activeSoundPreviewFileId", view_source)
    self.assertIn("activeSoundPreview.paused", view_source)
    self.assertIn("⏸", view_source)
    self.assertIn("已被 Slot 或节点引用，不能删除", view_source)
    self.assertIn("data-replacement-sound-id", view_source)
    self.assertIn("soundReplaceUploadInput", controller_source)
    self.assertIn("soundCanvasZoomOut", view_source)
    self.assertIn("soundCanvasZoomIn", view_source)
    self.assertIn("soundCanvasZoomReset", view_source)
    self.assertIn("soundCanvasSelectModeButton", view_source)
    self.assertIn("data-sound-canvas-command", view_source)
    self.assertIn("sound-selection-rect", view_source)
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
    self.assertIn("data-clear-slot", view_source)
    self.assertIn("data-save-slot-library", view_source)
    self.assertIn("data-slot-library-id", view_source)
    self.assertIn("Slot 库", view_source)
    self.assertIn("wheel", view_source)
    self.assertIn("pointerdown", view_source)
    self.assertIn("moveSoundNode", view_source)
    self.assertIn("setSoundCanvasZoom", controller_source)
    self.assertIn("panSoundCanvas", controller_source)
    self.assertIn("soundCanvasBoundsForSlot", controller_source)
    self.assertIn("ensureFixedSoundSlotsForChip", controller_source)
    self.assertIn("soundCapacityUsageForState", controller_source)
    self.assertIn("soundCapacityUsageForState", view_source)
    self.assertIn("soundChipCompatibilityForState", controller_source)
    self.assertIn("changeSoundChipSelection", controller_source)
    self.assertIn("soundExportCapacityProblemForState", controller_source)
    self.assertIn("defaultSlotLibraryCategories", controller_source)
    self.assertIn("data-slot-function-input", view_source)
    self.assertIn('min="0" max="68"', view_source)
    self.assertIn("0 表示 F0", view_source)
    self.assertIn('"functionNumber"', view_source)
    self.assertIn("音效空间", view_source)
    self.assertIn("剩余", view_source)
    self.assertIn("一键删除未使用音效", view_source)
    self.assertIn(">入库</button>", view_source)
    self.assertNotIn("保存到 Slot 库", view_source)
    self.assertIn("pendingSoundExport", controller_source)
    self.assertIn("hasPendingSoundExport", controller_source)
    self.assertIn("markSoundEditorExportStarted", controller_source)
    self.assertIn("markSoundEditorExported", controller_source)
    self.assertNotIn("editRevision", controller_source)
    self.assertNotIn("lastExportedRevision", controller_source)
    self.assertIn(".sound-node-canvas-scroll", css)
    self.assertIn("overflow: auto;", css)
    self.assertIn(".sound-slot-select", css)
    self.assertIn(".sound-slot-function-input", css)
    self.assertIn(".sound-preview-button", css)
    self.assertIn(".sound-preview-button.playing", css)
    self.assertIn(".sound-property-file-line", css)
    self.assertIn(".sound-panel-resizer", css)
    self.assertIn(".sound-canvas-menu", css)
    self.assertIn(".sound-selection-rect", css)
    self.assertIn(".sound-library-column", css)
    self.assertIn(".sound-library-item.compact", css)
    self.assertIn(".sound-library-grid {\n  display: grid;", css)
    self.assertIn(".sound-library-toolbar,\n.sound-slot-library-header {", css)
    self.assertIn("grid-template-rows: auto minmax(0, 1fr);", css)

  def test_sound_editor_layout_stays_inside_viewport(self):
    css = self.read_text("assets/css/app.css")

    self.assertIn("height: clamp(430px, calc(100vh - 250px), 660px);", css)
    self.assertIn(".sound-slot-list,\n.sound-property-panel {", css)
    self.assertIn("overflow: auto;", css)
    self.assertIn(".sound-node-canvas {\n  height: 100%;\n  min-height: 0;", css)
    self.assertIn("@media (max-width: 900px)", css)
    self.assertIn("grid-template-rows: minmax(90px, 0.7fr) minmax(240px, 1.6fr) minmax(110px, 1fr);", css)
    self.assertIn("height: clamp(430px, calc(100vh - 190px), 700px);", css)
    self.assertNotIn(".sound-editor-layout {\n    grid-template-columns: 1fr;\n    height: auto;", css)
    self.assertNotIn(".sound-node-canvas {\n  height: 100%;\n  min-height: 460px;", css)

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
    self.assertIn("changeSoundChipSelection(state", sound_events_source)
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
