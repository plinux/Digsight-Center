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
    self.assertIn("data-connector-judgment-field", view_source)
    self.assertIn("data-add-connector-judgment", view_source)
    self.assertIn("data-delete-connector-judgment", view_source)
    self.assertIn("addSoundConnectorJudgment", controller_source)
    self.assertIn("updateSoundConnectorJudgmentField", controller_source)
    self.assertIn("deleteSoundConnectorJudgment", controller_source)
    self.assertIn("SOUND_NODE_TYPES", view_source)
    self.assertIn("Play（播放）", view_source)
    self.assertIn("Loop（循环）", view_source)
    self.assertIn('data-node-field="nodeType"', view_source)
    self.assertNotIn('data-node-field="nodeConfig"', view_source)
    self.assertIn('data-node-field="x"', view_source)
    self.assertIn('data-node-field="y"', view_source)
    self.assertIn("connectorJudgments(judgments, connectorId)", view_source)
    self.assertIn("connectorActions(actions)", view_source)
    self.assertIn("Register_Type", self.read_text("server/sound_editor.py"))
    self.assertIn("_judgment_xml", self.read_text("server/sound_editor.py"))
    self.assertIn("data-clear-slot", view_source)
    self.assertIn("data-save-slot-library", view_source)
    self.assertIn("data-slot-library-id", view_source)
    self.assertIn("legacyDxspSlotEditor", view_source)
    self.assertIn("data-legacy-slot-field", view_source)
    self.assertIn("data-legacy-slot-file", view_source)
    self.assertIn("updateLegacyDxspSlotField", controller_source)
    self.assertIn("setLegacyDxspSlotFile", controller_source)
    self.assertIn("legacy_user_files", controller_source)
    self.assertIn("legacy_user_type", controller_source)
    self.assertIn("不使用", view_source)
    self.assertIn("单次发声", view_source)
    self.assertIn("循环发声", view_source)
    self.assertIn("启动段", view_source)
    self.assertIn("循环段", view_source)
    self.assertIn("结束段", view_source)
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
    self.assertIn(".sound-property-number-small", css)
    self.assertIn(".sound-property-number-geometry", css)
    self.assertIn(".sound-connector-judgment-row", css)
    self.assertIn(".legacy-dxsp-panel", css)
    self.assertIn(".legacy-dxsp-canvas", css)

  def test_sound_editor_slot_property_panel_lists_collapsible_nodes(self):
    view_source = self.read_text("assets/js/sound-editor-view.js")
    controller_source = self.read_text("assets/js/sound-editor-controller.js")
    css = self.read_text("assets/css/app.css")
    render_properties = self.source_function(view_source, "renderProperties")
    slot_editor = self.source_function(view_source, "slotEditor")
    connector_details = self.source_function(view_source, "connectorDetails")

    self.assertIn("expandedPropertyItemKeys", controller_source)
    self.assertIn("expandedPropertySectionKeys", controller_source)
    self.assertIn("isSoundPropertyItemExpanded", controller_source)
    self.assertIn("toggleSoundPropertyItemExpansion", controller_source)
    self.assertIn("isSoundPropertySectionExpanded", controller_source)
    self.assertIn("toggleSoundPropertySectionExpansion", controller_source)
    self.assertIn("slotNodeList(slot, state, soundFiles)", render_properties)
    self.assertIn("slotConnectorList(slot, state)", render_properties)
    self.assertIn("slotPropertySection", view_source)
    self.assertIn("data-property-section-toggle", view_source)
    self.assertNotIn("sound-property-file-line", slot_editor)
    self.assertNotIn("音效文件：", slot_editor)
    self.assertIn("sound-connector-endpoint-grid", connector_details)
    self.assert_source_order(connector_details, "源节点", "目标节点")
    self.assertIn("if (node) {", render_properties)
    self.assertIn("nodeDetails(node, state, soundFiles)", render_properties)
    self.assertIn("} else if (connector) {", render_properties)
    self.assertIn("connectorDetails(connector, state)", render_properties)
    self.assertIn("} else if (slot) {", render_properties)
    self.assert_source_order(render_properties, "} else if (connector) {", "} else if (slot) {")
    self.assertIn("if (!isLegacyDxspProject(state)) {\n      content.push(slotNodeList", render_properties)
    self.assertIn("data-property-item-toggle", view_source)
    self.assertIn("Slot 内连接", view_source)
    self.assertIn("sound-slot-connector-list", view_source)
    self.assertIn("sound-slot-connector-item", view_source)
    self.assertIn("connectorDetails(connector, state, {embedded: true})", view_source)
    self.assertIn("▾", view_source)
    self.assertIn("▸", view_source)
    self.assertIn("data-node-edit-key", view_source)
    self.assertIn("data-node-file-select", view_source)
    self.assertNotIn("展开", view_source)
    self.assertNotIn("折叠", view_source)
    self.assertIn(".sound-slot-node-list", css)
    self.assertIn(".sound-slot-section-title", css)
    self.assertIn(".sound-slot-section-arrow", css)
    self.assertIn(".sound-slot-node-toggle", css)
    self.assertIn(".sound-connector-inline-details", css)
    self.assertIn(".sound-property-file-line", css)
    self.assertIn(".sound-connector-endpoint-grid select", css)
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

  def test_sound_editor_is_independent_from_controller_selection(self):
    app_source = self.read_text("assets/js/app.js")
    active_view_source = self.source_function(app_source, "setActiveView")
    nav_source = self.source_function(app_source, "setNavState")
    visible_state_source = self.source_function(app_source, "syncVisibleState")

    self.assertNotIn("soundEditorAvailableForController", app_source)
    self.assertNotIn("capabilities?.sound_editor", app_source)
    self.assertNotIn("当前控制器不支持音效编辑", app_source)
    self.assertNotIn('if (view === "sound"', active_view_source)
    self.assertIn("elements.navSoundEditor.disabled = false;", nav_source)
    self.assertNotIn('appState.activeView === "sound"', visible_state_source)


if __name__ == "__main__":
  unittest.main()
