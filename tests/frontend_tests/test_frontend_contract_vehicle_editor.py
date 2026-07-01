import unittest

from tests.frontend_tests.source_assertions import SourceAssertionsMixin


TOKEN_PROMPT_TEXT = "请输入操作" + "授权令牌"


class FrontendVehicleEditorContractTest(SourceAssertionsMixin, unittest.TestCase):
  def test_vehicle_image_upload_compresses_large_images_before_json_upload(self):
    source = self.read_text("assets/js/gateway-api.js")
    self.assertIn("compressVehicleImageForUpload", source)
    self.assertIn("canvas.toBlob", source)
    self.assertIn("maxVehicleImageUploadBytes", source)
    self.assertIn("image/webp", source)

  def test_vehicle_edit_button_opens_editor_and_saves_function_modes(self):
    source = (
      self.read_text("assets/js/vehicle-view.js")
      + self.read_text("assets/js/vehicle-cab-view.js")
      + self.read_text("assets/js/vehicle-editor-view.js")
      + self.read_text("assets/js/vehicle-editor-controller.js")
    )
    app_source = self.read_text("assets/js/app.js") + self.read_text("assets/js/vehicle-editor-actions.js") + self.read_text("assets/js/cab-workspace-actions.js")
    for token in [
      "showVehicleEditor",
      "renderVehicleEditor",
      'edit.addEventListener("click", (event) => {',
      "handlers.onEdit?.(vehicle.id);",
      'subviewToolbar("车辆编辑", handlers.onBack)',
      'const articleNumber = inputField("货号", "text", vehicle.article_number || "");',
      "article_number: articleNumber.input.value.trim()",
      "const categoryEditor = renderCategoryEditor(vehicle, handlers.categories || []);",
      "category_ids: collectCategoryIds(categoryEditor)",
      "categories: appState.categories || []",
      "vehicle-category-editor",
      "triggerModeSelect",
      "triggerModeToButtonType",
      "collectFunctions",
      "trigger_mode",
      "duration_ms",
      "onSave",
      "updateVehicle",
    ]:
      self.assertIn(token, source + app_source)

  def test_vehicle_editor_extracts_shared_layout_shell(self):
    source = self.read_text("assets/js/vehicle-editor-view.js")
    self.assertIn("function renderVehicleEditorLayout(", source)
    self.assertIn("function renderVehicleEditorActionRow(", source)
    self.assertLessEqual(source.count('const actionRow = document.createElement("div");'), 1)

  def test_vehicle_editor_form_is_split_into_basic_info_helpers(self):
    source = self.read_text("assets/js/vehicle-editor-view.js")
    for helper_name in [
      "renderNormalVehicleBasicInfo",
      "renderConsistBasicInfo",
      "normalVehicleSavePayload",
      "consistVehicleSavePayload",
    ]:
      self.assertIn(f"function {helper_name}", source)

  def test_vehicle_management_toolbar_add_select_delete_and_image_upload_are_wired(self):
    html = self.read_text("index.html")
    api_source = self.read_text("assets/js/gateway-api.js")
    app_source = self.read_text("assets/js/app.js") + self.read_text("assets/js/vehicle-editor-actions.js") + self.read_text("assets/js/cab-workspace-actions.js")
    view_source = self.read_text("assets/js/vehicle-view.js")
    for token in [
      'id="selectVehiclesButton"',
      'id="addVehicleButton"',
      'id="deleteVehiclesButton"',
      "选择",
      "添加",
      "删除",
    ]:
      self.assertIn(token, html)
    for token in [
      "export function createVehicle",
      '"/api/vehicles"',
      "export function deleteVehicle",
      "export function uploadVehicleImage",
      '"/api/vehicle-images"',
    ]:
      self.assertIn(token, api_source)
    for token in [
      "vehicleDeletionSelectionMode",
      "selectedVehicleIds",
      "createNewVehicle",
      "toggleVehicleSelectionMode",
      "deleteSelectedVehicles",
      "deleteVehicle(vehicleId)",
      "createVehicle(changes)",
      "uploadVehicleImage(file)",
      "onDelete",
      "onImageFile",
      "onToggleVehicleSelection",
    ]:
      self.assertIn(token, app_source + view_source)

  def test_vehicle_editor_uses_category_pills_upload_image_and_delete_button(self):
    source = self.read_text("assets/js/vehicle-editor-view.js")
    css = self.read_text("assets/css/app.css")
    for token in [
      "vehicle-image-upload",
      "添加图片",
      "onImageFile",
      "category-pill",
      "category-pill selected",
      "collectCategoryIds(categoryEditor)",
      "deleteVehicleButton",
      "删除车辆",
      "handlers.onDelete",
      ".vehicle-image-upload",
      ".category-pill",
      ".category-pill.selected",
    ]:
      self.assertIn(token, source + css)
    self.assertNotIn("category-check-row", source + css)

  def test_vehicle_editor_image_upload_scales_full_image_without_cropping(self):
    css = self.read_text("assets/css/app.css")
    button_start = css.index(".vehicle-image-upload-button {")
    image_start = css.index(".vehicle-image-upload-button img", button_start)
    end = css.index(".vehicle-image-add", image_start)
    image_upload_css = css[button_start:end]
    for token in [
      "aspect-ratio: 4 / 3;",
      "overflow: hidden;",
      ".vehicle-image-upload-button img,",
      ".vehicle-image-upload-button .vehicle-placeholder",
      "inline-size: 100%;",
      "block-size: 100%;",
      "object-fit: contain;",
      "object-position: center;",
    ]:
      self.assertIn(token, image_upload_css)
    self.assertNotIn("max-height: 120px;", image_upload_css)

  def test_vehicle_editor_function_table_merges_type_into_trigger_mode_and_uses_two_columns(self):
    source = self.read_text("assets/js/vehicle-editor-view.js")
    css = self.read_text("assets/css/app.css")
    for token in [
      "function-editor-grid",
      "function-column",
      "buildEditableFunctionSlots(functions, 31)",
      "renderFunctionColumn(\"F0-F15\"",
      "renderFunctionColumn(\"F16-F31\"",
      "triggerModeToButtonType",
      "button_type: triggerModeToButtonType(triggerMode)",
      ".function-editor-grid",
      "grid-template-columns: repeat(2, minmax(0, 1fr));",
      "function-name-column",
      "function-duration-column",
      "function-enabled-column",
      "<th>功能</th><th>名称</th><th>图标</th><th>触发模式</th><th>持续毫秒</th><th>启用</th>",
      'input.setAttribute("max", "60000")',
      ".function-duration-cell input",
      ".function-enabled-cell",
      "show_function_number: true",
      "is_configured: configured.is_configured ?? true",
      "[[\"toggle\", \"开关\"], [\"momentary\", \"点击\"], [\"timed\", \"延时\"]]",
    ]:
      self.assertIn(token, source + css)
    self.assertNotIn("<th>类型</th>", source)
    self.assertNotIn("<th>显示编号</th>", source)
    self.assertNotIn('tdInput("number", fn.button_type', source)
    self.assertNotIn('field("button_type")', source)
    self.assertNotIn('field("show_function_number")', source)
    self.assertNotIn("Boolean(configured.id || configured.label || configured.icon_name)", source)
    self.assertNotIn("开关式", source)
    self.assertNotIn("点击式", source)
    self.assertNotIn("延时式", source)

  def test_function_icon_picker_uses_chinese_labels_and_top_right_x_close(self):
    source = self.read_text("assets/js/vehicle-editor-view.js")
    picker_source = self.read_text("assets/js/function-icon-picker.js")
    css = self.read_text("assets/css/app.css")
    for token in [
      "function-icon-picker-header",
      "function-icon-picker-close",
      'close.textContent = "×";',
      "label.textContent = icon.label || icon.key;",
      ".function-icon-picker-header",
      ".function-icon-picker-close",
    ]:
      self.assertIn(token, source + picker_source + css)
    self.assertNotIn('close.textContent = "关闭";', picker_source)

  def test_vehicle_editor_uses_compact_metadata_grid_and_field_choices(self):
    source = self.read_text("assets/js/vehicle-editor-view.js")
    app_source = self.read_text("assets/js/app.js") + self.read_text("assets/js/vehicle-editor-actions.js") + self.read_text("assets/js/cab-workspace-actions.js")
    controller_source = self.read_text("assets/js/vehicle-editor-controller.js")
    css = self.read_text("assets/css/app.css")
    for token in [
      "vehicle-editor-form",
      "const scale = selectField(\"比例\", vehicle.track_mode || \"ho\",",
      "[[\"ho\", \"HO\"], [\"n\", \"N\"]]",
      "const vehicleType = selectField(\"车辆类型\", String(vehicle.type ?? 0), vehicleTypeOptions())",
      "const brand = inputField(\"模型品牌\", \"text\", vehicle.brand || \"\")",
      "const maxSpeed = inputField(\"最高速度 km/h\", \"number\", vehicle.max_speed || \"\", {min: 0, max: 999})",
      "const railway = inputField(\"铁路公司/局段\", \"text\", vehicle.railway || \"\")",
      "const decoderType = inputField(\"芯片型号\", \"text\", vehicle.decoder_type || \"\")",
      "nameRow.className = \"vehicle-editor-name-row\";",
      "kindRow.className = \"vehicle-editor-kind-row\";",
      "runningRow.className = \"vehicle-editor-running-row\";",
      "modelRow.className = \"vehicle-editor-model-row\";",
      "nameRow.append(name.label, fullName.label);",
      "kindRow.append(vehicleType.label, kindDynamicFields);",
      "runningRow.append(address.label, scale.label, maxSpeed.label, railway.label);",
      "modelRow.append(brand.label, articleNumber.label, decoderType.label);",
      "const kindDynamicFields = document.createElement(\"div\");",
      "kindDynamicFields.className = \"vehicle-kind-dynamic-fields\";",
      "basicInfo.className = \"vehicle-editor-basic-info\";",
      "basicInfo.append(\n    nameRow,\n    kindRow,\n    runningRow,\n    modelRow,\n    description.label,\n    categoryEditor\n  );",
      "const {form} = renderVehicleEditorLayout({",
      "formClassName: \"stack-form vehicle-editor-form\"",
      "functionPanel: functionEditor",
      "kindDynamicFields.replaceChildren();",
      "kindDynamicFields.append(energyType.label);",
      "kindDynamicFields.append(carSubtype.label);",
      "track_mode: scale.input.value",
      "type: Number(vehicleType.input.value)",
      "sync_function_control: false",
      "brand: brand.input.value.trim()",
      "max_speed: Number(maxSpeed.input.value || 0) || null",
      "createVehicleValueDatalist(\"vehicle-railway-options\", handlers.railwayOptions || [])",
      "createVehicleValueDatalist(\"vehicle-decoder-type-options\", handlers.decoderTypeOptions || [])",
      "railway.input.setAttribute(\"list\", \"vehicle-railway-options\")",
      "decoderType.input.setAttribute(\"list\", \"vehicle-decoder-type-options\")",
      "vehicleType.input.addEventListener(\"change\", () => {",
      "handlers.onTypeChange?.(Number(vehicleType.input.value));",
      "vehicleEditorOptions(appState.vehicles)",
      "railwayOptions: editorOptions.railwayOptions",
      "decoderTypeOptions: editorOptions.decoderTypeOptions",
      ".vehicle-editor-name-row",
      ".vehicle-editor-kind-row",
      ".vehicle-editor-running-row",
      ".vehicle-editor-model-row",
      ".vehicle-editor-layout",
      "grid-template-columns: minmax(260px, 1fr) minmax(0, 2fr);",
      ".vehicle-editor-left-column",
      ".vehicle-editor-function-column",
      ".vehicle-editor-basic-info",
      ".function-name-column",
      "width: 6rem;",
      ".vehicle-kind-dynamic-fields",
      ".vehicle-kind-field",
      ".vehicle-category-editor",
      "font-size: 12px;",
      "line-height: 1.2;",
      "grid-template-columns: minmax(0, 1fr) minmax(0, 2fr);",
    ]:
      self.assertIn(token, source + app_source + controller_source + css)
    normal_editor_source = source[
      source.index("export function renderVehicleEditor"):
      source.index("function renderConsistVehicleEditor")
    ]
    self.assertNotIn("checkboxField(\"同步控制功能\"", normal_editor_source)
    self.assertIn("VEHICLE_TYPE_LABELS", source[:source.index("} from \"./vehicle-kind-icons.js\";")])

  def test_vehicle_editor_separates_normal_vehicle_and_consist_forms(self):
    source = self.read_text("assets/js/vehicle-editor-view.js")
    app_source = self.read_text("assets/js/app.js") + self.read_text("assets/js/vehicle-editor-actions.js") + self.read_text("assets/js/cab-workspace-actions.js")
    gateway_source = self.read_text("assets/js/gateway-api.js")
    css = self.read_text("assets/css/app.css")
    for token in [
      "[\"0\", VEHICLE_TYPE_LABELS.get(0)]",
      "[\"1\", VEHICLE_TYPE_LABELS.get(1)]",
      "[\"2\", VEHICLE_TYPE_LABELS.get(2)]",
      "[\"3\", VEHICLE_TYPE_LABELS.get(3)]",
      "[\"4\", VEHICLE_TYPE_LABELS.get(4)]",
      "const energyType = renderVehicleKindChoiceField(\"能源类型\", vehicle.energy_type || \"electric\", [\"diesel\", \"electric\", \"steam\", \"hybrid\"])",
      "const carSubtype = renderVehicleKindChoiceField(\"车厢子类\", vehicle.car_subtype || \"passenger\", [\"passenger\", \"engineering\", \"inspection\", \"crane\"])",
      "energy_type: Number(vehicleType.input.value) === 0 ? energyType.input.value : \"\"",
      "car_subtype: Number(vehicleType.input.value) === 1 ? carSubtype.input.value : \"\"",
      "renderConsistVehicleEditor(container, vehicle, functions, handlers)",
      "vehicle-consist-editor",
      "const preview = renderVehicleImageUploader(vehicle, handlers)",
      "const consistKind = renderConsistKindChoiceField(vehicle.consist_kind || existingConsist?.consist_kind || \"multiple_unit\")",
      "basicInfo.className = \"vehicle-editor-basic-info vehicle-consist-basic-info\";",
      "consistNameRow.className = \"vehicle-editor-name-row vehicle-consist-name-row\";",
      "consistKindRow.className = \"vehicle-editor-kind-row vehicle-consist-kind-row\";",
      "consistNameRow.append(name.label, scale.label, syncFunctionControl.label);",
      "consistKindRow.append(consistKind.label);",
      "basicInfo.append(\n    consistNameRow,\n    consistKindRow,\n    categoryEditor,\n    memberEditor\n  );",
      "const {form} = renderVehicleEditorLayout({",
      "formClassName: \"stack-form vehicle-consist-editor\"",
      "layoutClassName: \"vehicle-consist-editor-layout\"",
      "leftColumnClassName: \"vehicle-editor-left-column vehicle-consist-editor-left-column\"",
      "functionColumnClassName: \"vehicle-editor-function-column vehicle-consist-editor-function-column\"",
      "[\"multiple_unit\", \"powered_set\", \"train_set\"]",
      "consist_kind: consistKind.input.value",
      "反转运行",
      "同步编组内第一台车功能表",
      "refreshConsistMemberOptions(rows, availableVehicles)",
      "renderConsistMemberImage(member.vehicle_id, availableVehicles)",
      "toggleButtonField(\"反转运行\", member.direction === \"reverse\")",
      "consist_members: collectConsistMembers(memberEditor)",
      "const existingConsist = consistForVehicle(vehicle.id)",
      "await saveVehicleConsist(changes, savedVehicle.id || vehicle.id)",
      "onTypeChange: (type) => {",
      "appState.editingVehicleDraft = {...vehicle, ...(appState.editingVehicleDraft || {}), type};",
      "renderAll();",
      "async function saveVehicleConsist(changes, controlVehicleId)",
      "createConsist({",
      "updateConsist(existingConsist.id,",
      ".vehicle-consist-member-list",
      ".vehicle-consist-member-thumb",
      ".vehicle-consist-reverse-button",
      ".sync-toggle-inline",
      ".vehicle-kind-field",
      ".vehicle-consist-editor-left-column",
      ".vehicle-consist-editor-function-column",
      ".vehicle-consist-basic-info",
      ".vehicle-consist-name-row",
      ".vehicle-consist-kind-row",
      "grid-template-columns: minmax(0, 1fr) minmax(3.8rem, max-content) max-content;",
    ]:
      self.assertIn(token, source + app_source + gateway_source + css)
    consist_editor_source = source[
      source.index("function renderConsistVehicleEditor"):
      source.index("function renderConsistMemberEditor")
    ]
    self.assertNotIn("const address = inputField(\"车辆编号\"", consist_editor_source)
    self.assertNotIn("普通车辆/机车", source + app_source)
    self.assertNotIn("车厢/控制车", source + app_source)
    self.assertNotIn("Accessory/附件", source + app_source)
    self.assertNotIn("摄像车头", source + app_source)

  def test_vehicle_editor_uses_icon_picker_and_fixed_f0_to_f31_rows(self):
    source = self.read_text("assets/js/vehicle-editor-view.js")
    picker_source = self.read_text("assets/js/function-icon-picker.js")
    css = self.read_text("assets/css/app.css")
    for token in [
      "renderFunctionTable(functions, handlers.functionIconCatalog || FALLBACK_FUNCTION_ICON_CATALOG)",
      "buildEditableFunctionSlots(functions, 31)",
      "row.dataset.functionNumber = String(fn.function_number);",
      "key.textContent = `F${fn.function_number}`;",
      "function-icon-picker-button",
      'chooseIcon.setAttribute("aria-label", "选择功能图标");',
      "renderFunctionIconPicker",
      "function-icon-picker-dialog",
      "FUNCTION_ICON_PICKER_GROUPS",
      'label: "灯光控制"',
      'label: "引擎类"',
      'label: "起重机控制"',
      'label: "运行音效"',
      'label: "蒸汽机类"',
      'label: "音效"',
      'label: "控制功能类"',
      'patterns: ["horn", "whistle", "bell", "announcement", "radio", "music", "bugle", "door", "window"',
      'patterns: ["function", "volume", "mute", "brake", "pantograph", "coupler", "load-mode", "weight", "gear", "gear switch", "hump_gear"',
      "resolveFunctionIconPickerGroups",
      "icon-picker-group",
      "icon-picker-group-title",
      "icon-picker-grid",
      "icon-picker-option",
      "function-icon-picker-open",
      'document.documentElement.classList.add("function-icon-picker-open");',
      'document.documentElement.classList.remove("function-icon-picker-open");',
      'document.body.classList.add("function-icon-picker-open");',
      'document.body.classList.remove("function-icon-picker-open");',
      "resolveIconCatalogEntries",
      "icon_name: field(\"icon_name\").value.trim()",
      "function_number: Number(row.dataset.functionNumber || index)",
      ".function-icon-picker-dialog",
      "html.function-icon-picker-open",
      "body.function-icon-picker-open",
      ".icon-picker-group",
      ".icon-picker-group-title",
      ".icon-picker-grid",
      "display: flex;\n  align-items: center;\n  justify-content: center;\n  align-self: stretch;",
      "justify-self: stretch;",
    ]:
      self.assertIn(token, source + picker_source + css)
    self.assertNotIn("选择图标", source + picker_source)
    self.assertNotIn("<th>编号</th><th>名称</th><th>图标</th>", source)
    self.assertNotIn('tdInput("number", fn.function_number', source)
    self.assertNotIn('const addFunction = document.createElement("button");', source)
    self.assertNotIn('remove.textContent = "删除";', source)
    self.assertNotIn('patterns: ["crane", "load", "turntable"', picker_source)
    self.assertNotIn('patterns: ["function", "volume", "mute", "brake", "pantograph", "coupler", "door", "window"', picker_source)

  def test_vehicle_empty_metadata_uses_dash_placeholder(self):
    source = self.read_text("assets/js/vehicle-view.js")
    self.assertNotIn("未填", source)
    for token in [
      "function formatVehicleField",
      'return text || "-";',
      "formatVehicleField(vehicle.railway)",
      "formatVehicleField(vehicle.article_number)",
    ]:
      self.assertIn(token, source)

  def test_vehicle_editor_uses_independent_editing_vehicle_id(self):
    state_source = self.read_text("assets/js/state-store.js")
    app_source = self.read_text("assets/js/app.js") + self.read_text("assets/js/vehicle-editor-actions.js") + self.read_text("assets/js/cab-workspace-actions.js")
    for token in [
      'editingVehicleId: ""',
      "function editingVehicle()",
      "appState.editingVehicleDraft?.id === appState.editingVehicleId",
      "appState.editingVehicleId = vehicleId;",
      "appState.editingVehicleId = \"\";",
      "const vehicle = editingVehicle();",
      "updateVehicle(vehicle.id, changes)",
    ]:
      self.assertIn(token, state_source + app_source)

  def test_function_icon_picker_grid_is_compact(self):
    css = self.read_text("assets/css/app.css")
    self.assertIn("grid-template-columns: repeat(auto-fill, minmax(76px, 1fr));", css)
    self.assertIn("grid-template-columns: 28px minmax(0, 1fr);", css)
    self.assertIn("writing-mode: vertical-rl;", css)
    self.assertIn("min-height: 48px;", css)
    self.assertIn("gap: 3px;", css)
    self.assertIn("padding: 4px;", css)
    self.assertNotIn("grid-template-columns: repeat(auto-fill, minmax(112px, 1fr));", css)
    self.assertNotIn("min-height: 72px;", css)

  def test_vehicle_function_icons_use_local_catalog_with_fallback(self):
    source = (
      self.read_text("assets/js/vehicle-view.js")
      + self.read_text("assets/js/vehicle-cab-view.js")
      + self.read_text("assets/js/function-icon-catalog.js")
      + self.read_text("assets/js/app.js")
    )
    css = self.read_text("assets/css/app.css")
    for token in [
      "FALLBACK_FUNCTION_ICON_CATALOG",
      "loadFunctionIconCatalog",
      "/config/function-icons.json",
      "function_icon_mapping_files",
      "resolveFunctionIcon",
      "renderFunctionSlotButton",
      "function-icon-slot",
      "functionIconCatalog",
      "function-icon",
      "default_icon",
      "mappings",
      "icon_name",
      "shortcut",
      "keywords",
      "F${fn.function_number}",
    ]:
      self.assertIn(token, source + css)


if __name__ == "__main__":
  unittest.main()
