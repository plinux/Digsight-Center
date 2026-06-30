import unittest
import re
from pathlib import Path

from tests.frontend_tests.source_assertions import SourceAssertionsMixin


TOKEN_PROMPT_TEXT = "请输入操作" + "授权令牌"


class FrontendVehicleControlContractTest(SourceAssertionsMixin, unittest.TestCase):
  def test_loco_function_api_sends_state_snapshot(self):
    api_source = self.read_text("assets/js/gateway-api.js")
    app_source = self.read_text("assets/js/app.js")
    runtime_source = self.read_text("assets/js/loco-runtime-actions.js")
    self.assertIn("setLocoFunction(vehicleId, functionNumber, enabled, functionStates = {})", api_source)
    self.assertIn("function_states: functionStates", api_source)
    self.assertIn('from "./loco-runtime-actions.js"', app_source)
    self.assertIn("setCabFunctionState", runtime_source)
    self.assertIn("setLocoFunction(targetVehicle.id, functionNumber, Boolean(enabled), cab.functions)", runtime_source)

  def test_dc_control_view_does_not_use_dcc_vehicle_commands(self):
    source = self.read_text("assets/js/vehicle-cab-view.js")
    app_source = self.read_text("assets/js/app.js")
    css = self.read_text("assets/css/app.css")
    self.assert_source_contains_all(source, [
      "export function renderDcControl",
      "dc-voltage-slider",
      "dc-voltage-slider-fill",
      "function clampDcVoltage(",
      "bindVerticalSlider(slider",
      "normalizeDcMaxVoltage(maxVoltage)",
      "(value) => clampDcVoltage(value, maxVoltage)",
      "dc-direction-row",
      "dc-emergency-stop",
    ])
    self.assert_source_contains_all(app_source, [
      "async function sendDcControl",
      "const voltageV = Number(appState.dcControl.voltageV || 0)",
      "const direction = appState.dcControl.direction === \"reverse\" ? \"reverse\" : \"forward\"",
      "runControllerStatusRetry({",
      "requiresFreshStatus: voltageV > 0",
      "requestFn: () => setDcControl(voltageV, direction)",
    ])
    self.assert_source_contains_all(css, [
      ".dc-control-panel",
      "--dc-voltage-fill-percent",
      ".dc-voltage-slider-fill",
      "min-block-size: clamp(18rem, 36vh, 30rem);",
    ])

  def test_vehicle_list_filters_by_operation_mode(self):
    source = self.read_text("assets/js/app.js")
    self.assert_source_contains_all(source, [
      "function vehicleMatchesOperationMode",
      "function vehiclesForOperationMode",
      "function syncCabSelectionForVisibleVehicles",
      "if (mode === \"dc\") {",
      "vehicleTrackMode(vehicle) === mode",
      "const visibleVehicles = vehiclesForOperationMode(operationMode);",
      "visibleFunctions: functionsForVehicles(visibleVehicles),",
      "renderVehicleControlWorkspace(elements.vehicleRegistry, visibleVehicles, visibleFunctions",
      "updateVehicleHeader(visibleVehicles, operationMode);",
    ])

  def test_cab_selection_conflict_predicate_is_shared(self):
    helper_source = self.read_text("assets/js/cab-state.js")
    app_source = self.read_text("assets/js/app.js")
    view_source = self.read_text("assets/js/vehicle-cab-view.js")
    self.assert_source_contains_all(helper_source, [
      "export function vehicleSelectedByOtherCabState",
      "Object.entries(cabs || {}).some",
      "otherCabId !== cabId",
    ])
    self.assertIn('from "./cab-state.js"', app_source)
    self.assertIn('from "./cab-state.js"', view_source)
    self.assertIn("vehicleSelectedByOtherCabState(appState.cabs, cabId, vehicleId)", app_source)
    self.assertIn("vehicleSelectedByOtherCabState(cabState?.cabs, cabId, vehicleId)", view_source)
    self.assertNotIn("Object.entries(appState.cabs || {}).some", app_source)
    self.assertNotIn("Object.entries(cabState?.cabs || {}).some", view_source)

  def test_cab_functions_render_fixed_f0_to_f9_and_expanded_extra_slots(self):
    source = self.read_text("assets/js/vehicle-cab-view.js")
    css = self.read_text("assets/css/app.css")
    self.assert_source_contains_all(source + css, [
      "maxFunctionNumber: showFunctionLabels ? 9 : 31",
      "buildExpandedFunctionSlots(functions)",
      "renderFunctionSlotButton",
      "function-slot-button",
      "function-icon-slot",
      "function-label",
      "function-extra-grid",
      "--cab-function-columns: 5;",
      "grid-template-columns: repeat(var(--cab-function-columns), minmax(0, 1fr));",
    ])
    self.assertIn("for (let functionNumber = 0; functionNumber <= maxFunctionNumber; functionNumber += 1)", source)
    self.assertNotIn("functions.filter((item) => Number(item.function_number) <= 9)", source)

  def test_cab_function_label_wraps_after_four_chars_without_resizing_button(self):
    source = self.read_text("assets/js/vehicle-cab-view.js")
    css = self.read_text("assets/css/app.css")
    self.assert_source_contains_all(source + css, [
      "formatFunctionLabelChunks",
      "appendFunctionLabelContent(label, labelText)",
      "label.dataset.labelLength = String(Array.from(labelText).length);",
      "label.classList.toggle(\"function-label-multiline\", Array.from(labelText).length > 4);",
      "label.classList.toggle(\"function-label-very-long\", Array.from(labelText).length > 8);",
      "label.classList.toggle(\"function-label-extra-long\", Array.from(labelText).length > 12);",
      "--function-label-width:",
      "if (showNumber) {\n    button.append(key);",
      "button.append(iconSlot);",
      "if (showLabel) {\n    button.append(label);",
      "block-size: clamp(38px, 2.7rem, 48px);",
      "grid-template-columns: max-content max-content var(--function-label-width);",
      "justify-content: center;",
      "justify-items: center;",
      "inline-size: var(--function-label-width);",
      "text-align: center;",
      "text-overflow: clip;",
      ".function-label-multiline",
      ".function-label-very-long",
      ".function-label-extra-long",
    ])
    function_label_blocks = re.findall(r"\.function-label\s*\{[^}]*\}", css)
    self.assertTrue(function_label_blocks)
    for block in function_label_blocks:
      self.assertNotIn("-webkit-line-clamp", block)
      self.assertNotIn("-webkit-box-orient", block)
      self.assertNotIn("text-overflow: ellipsis;", block)
    self.assert_source_not_contains_any(css, [
      "minmax(2.2rem, auto)",
      "minmax(var(--function-label-width), 1fr)",
    ])

  def test_vehicle_kind_icons_and_labels_are_available(self):
    view_source = self.read_text("assets/js/vehicle-view.js")
    icon_source = self.read_text("assets/js/vehicle-kind-icons.js")
    editor_source = self.read_text("assets/js/vehicle-editor-view.js")
    source = view_source + icon_source + editor_source
    css = self.read_text("assets/css/app.css")
    expected_icons = [
      "energy-diesel",
      "energy-electric",
      "energy-steam",
      "energy-hybrid",
      "car-passenger",
      "car-engineering",
      "car-inspection",
      "car-crane",
      "consist-multiple-unit",
      "consist-group",
    ]
    for icon_name in expected_icons:
      self.assertTrue(Path(f"assets/icons/vehicle-types/{icon_name}.svg").exists(), icon_name)
      self.assertIn(f"assets/icons/vehicle-types/{icon_name}.svg", source)
    for token in [
      "export const VEHICLE_TYPE_LABELS",
      "const VEHICLE_KIND_META",
      "resolveVehicleKindMeta",
      "vehicle-kind-icon",
      "renderVehicleKindChoiceField",
      "vehicle-kind-choice-image",
      "vehicle-type-icon",
      ".vehicle-kind-icon",
      ".vehicle-type-icon",
      ".vehicle-kind-choice-grid",
      "vehicleEnergyGlyph",
      "vehicle-energy-glyph",
      "vehicle-energy-electric",
      "vehicle-energy-diesel",
      "vehicle-energy-steam",
      "vehicle-energy-hybrid",
      "vehicle-energy-body",
      "vehicle-energy-wheels",
      "vehicle-energy-wheel",
      "vehicle-energy-pantograph",
      "vehicle-energy-pantograph-diamond",
      "vehicle-energy-bolt",
      "vehicle-energy-engine",
      "vehicle-energy-boiler",
      "vehicle-energy-cab",
      "vehicle-energy-smokestack",
      "vehicle-energy-smoke",
      ".vehicle-energy-glyph",
      ".vehicle-energy-body",
      ".vehicle-energy-wheels",
      ".vehicle-energy-electric .vehicle-energy-pantograph",
      ".vehicle-energy-electric .vehicle-energy-pantograph-diamond",
      ".vehicle-energy-electric .vehicle-energy-body > .vehicle-energy-bolt",
      ".vehicle-energy-diesel .vehicle-energy-engine",
      ".vehicle-energy-steam .vehicle-energy-boiler",
      ".vehicle-energy-steam .vehicle-energy-cab",
      ".vehicle-energy-steam .vehicle-energy-smoke",
      ".vehicle-energy-hybrid .vehicle-energy-engine",
      ".vehicle-energy-hybrid .vehicle-energy-pantograph",
      ".vehicle-energy-hybrid .vehicle-energy-pantograph-diamond",
    ]:
      self.assertIn(token, source + css)
    for selector, color in [
      (".vehicle-energy-diesel", "#dc2626"),
      (".vehicle-energy-electric", "#eab308"),
      (".vehicle-energy-steam", "#111827"),
      (".vehicle-energy-hybrid", "#16a34a"),
    ]:
      self.assertIn(selector, css)
      self.assertIn(f"color: {color};", css)
    self.assertRegex(css, r"\.vehicle-energy-body\s*\{[^}]*background:\s*transparent;")
    self.assertNotIn("vehicle-energy-electric-sign", source + css)
    self.assertNotIn("#facc15", css)

  def test_cab_function_name_toggle_controls_all_function_layout_per_cab(self):
    state_source = self.read_text("assets/js/state-store.js")
    app_source = self.read_text("assets/js/app.js") + self.read_text("assets/js/cab-workspace-actions.js")
    view_source = self.read_text("assets/js/vehicle-cab-view.js")
    css = self.read_text("assets/css/app.css")
    for token in [
      "showFunctionNumbers: true",
      "cab.showFunctionNumbers = true;",
      "showFunctionLabels: true",
      "function toggleCabFunctionNumbers(cabId)",
      "cab.showFunctionNumbers = !cab.showFunctionNumbers;",
      "cab.showFunctionLabels = true;",
      "function toggleCabFunctionLabels(cabId)",
      "cab.showFunctionLabels = !cab.showFunctionLabels;",
      "cab.expanded = false;",
      "onToggleCabFunctionNumbers: toggleCabFunctionNumbers",
      "onToggleCabFunctionLabels: toggleCabFunctionLabels",
      "onToggleCabFunctionNumbers?.(cabId)",
      "onToggleCabFunctionLabels?.(cabId)",
      "const numberToggle = cabToggleButton({",
      'className: "cab-function-number-toggle",',
      "active: showFunctionNumbers",
      'label: "显示功能编号",',
      "const nameToggle = cabToggleButton({",
      'className: "cab-function-label-toggle",',
      "active: showFunctionLabels",
      'label: "显示功能名称",',
      "button.setAttribute(\"aria-pressed\", active ? \"true\" : \"false\");",
      "const showFunctionNumbers = cab.showFunctionNumbers !== false;",
      "const showFunctionLabels = cab.showFunctionLabels !== false;",
      "toggle.disabled = !selectedVehicle || !showFunctionLabels;",
      "maxFunctionNumber: showFunctionLabels ? 9 : 31",
      "showNumber: showFunctionNumbers",
      "showFunctionLabels",
      "hide-function-labels",
      "show-all-functions",
      "renderFunctionSlotButton(",
      "state.showNumber !== false",
      "state.showLabel !== false",
      "without-number",
      "with-number",
      ".cab-function-number-toggle",
      ".cab-function-grid.hide-function-labels",
      "--cab-function-columns: 8;",
      ".function-slot-button.with-number.with-label",
      ".function-slot-button.without-number.with-label",
      ".function-slot-button.with-number.without-label",
      ".function-slot-button.without-number.without-label",
      "grid-template-columns: max-content var(--function-label-width);",
      ".function-slot-button.without-label",
      "grid-template-columns: auto auto;",
      "gap: 2px;",
      "padding: 2px;",
      "inline-size: 1.35rem;",
      "width: 21px;",
      "font-size: 0.84rem;",
      ".function-slot-button.without-label .function-label",
      "@media (max-width: 560px)",
      "--cab-function-columns: 2;",
      "--cab-function-columns: 4;",
      "@media (max-width: 360px)",
      "--cab-function-columns: 3;",
    ]:
      self.assertIn(token, state_source + app_source + view_source + css)
    filter_source = view_source[
      view_source.index("function renderCabFilters"):
      view_source.index("function option", view_source.index("function renderCabFilters"))
    ]
    self.assertLess(filter_source.index("numberToggle"), filter_source.index("nameToggle"))
    self.assertIn("bar.append(numberToggle, nameToggle, category", filter_source)

  def test_cab_vehicle_rows_directly_select_and_show_extra_vehicle_details(self):
    source = (
      self.read_text("assets/js/vehicle-cab-view.js")
      + self.read_text("assets/js/vehicle-view.js")
    )
    app_source = self.read_text("assets/js/app.js")
    css = self.read_text("assets/css/app.css")
    for token in [
      'select.addEventListener("click",',
      "event.stopPropagation();",
      "handlers.onSelectVehicle?.(cabId, vehicle.id);",
      "selectedByOtherCab",
      "disabled-by-other-cab",
      "aria-disabled",
      "select.disabled = disabledByOtherCab",
      "vehicleSelectedByOtherCab",
      "该车辆已在另一侧控制区中选择",
      "firstAvailableForRight",
      "vehicle.full_name",
      "vehicle.brand",
      "vehicle.railway",
      "vehicle.article_number",
      "formatVehicleCategories(vehicle)",
      "vehicle-detail-line",
      "vehicle-full-name-tag",
      "vehicle-max-speed-tag",
      "完整名称",
      "局段",
      "品牌",
      "货号",
      "分类",
    ]:
      self.assertIn(token, source + app_source + css)

  def test_vehicle_info_keeps_display_name_plain_and_boxes_full_name(self):
    source = self.read_text("assets/js/vehicle-view.js")
    css = self.read_text("assets/css/app.css")
    for token in [
      "const displayName = document.createElement(\"span\");",
      "displayName.className = \"vehicle-display-name\";",
      "displayName.textContent = vehicle.name || \"未命名车辆\";",
      "vehicle-full-name-tag",
      "fullNameTag.textContent = formatVehicleField(vehicle.full_name);",
      "name.append(addressBadge, displayName, kindIcon, fullNameTag);",
      "if (vehicle.max_speed) {",
      "speedTag.className = \"vehicle-meta-tag vehicle-max-speed-tag\";",
      "speedTag.textContent = `${vehicle.max_speed} km/h`;",
      "formatVehicleCategories(vehicle)",
      'return names.join("、") || "-";',
      ".vehicle-text h2",
      ".vehicle-display-name",
      ".vehicle-full-name-tag",
      ".vehicle-max-speed-tag",
      "font-size: 11px;",
      "border: 1px solid var(--line);",
      "white-space: nowrap;",
    ]:
      self.assertIn(token, source + css)
    self.assertNotIn("vehicle-full-name-line", source + css)
    self.assertNotIn("vehicle-full-name-caption", source + css)

  def test_vehicle_registry_puts_address_before_name_and_shows_full_detail_fields(self):
    source = self.read_text("assets/js/vehicle-view.js")
    css = self.read_text("assets/css/app.css")
    for token in [
      "vehicle-address-badge",
      "const addressBadge = document.createElement(\"strong\");",
      "const addressText = formatVehicleAddressBadgeText(vehicle, context);",
      "addressBadge.textContent = addressText;",
      "function formatVehicleAddressBadgeText(vehicle, context = {})",
      "findConsistForVehicle(vehicle.id, context.consists || [])",
      "sortedConsistMembers(consist, context.vehicles || [])",
      "name.append(addressBadge, displayName, kindIcon, fullNameTag);",
      "vehicle-detail-tag",
      "detail.append(",
      "detailTag(\"局段\", railway)",
      "detailTag(\"货号\", articleNumber)",
      "detailTag(\"分类\", categories)",
      "function detailTag(labelText, valueText)",
      ".vehicle-address-badge",
      ".vehicle-detail-tag",
      "font-weight: 700;",
      "font-size: 11px;",
      "flex-wrap: wrap;",
      "overflow: visible;",
      "overflow-wrap: anywhere;",
    ]:
      self.assertIn(token, source + css)
    self.assertNotIn("vehicle-address-line", source + css)
    self.assertNotIn("addressLabel.textContent = \"编号\";", source)
    self.assertNotIn("address.append(addressLabel, addressBadge);", source)
    self.assertNotIn("block.append(name, address, detail);", source)
    self.assertNotIn("max-width: 33%;", css)
    self.assertNotIn("detail.textContent = `局段 ${railway} · 货号 ${articleNumber} · 分类 ${categories}`;", source)

  def test_cab_mouse_speed_and_function_pressed_state_are_wired(self):
    source = self.read_text("assets/js/vehicle-cab-view.js")
    app_source = self.read_text("assets/js/app.js")
    css = self.read_text("assets/css/app.css")
    slider_source = self.read_text("assets/js/vertical-slider.js")
    self.assert_source_contains_all(source + app_source + css, [
      "bindVerticalSlider(throttle, {",
      "previewThrottleSpeed",
      "commitThrottleSpeed",
      "onSpeedPreview",
      'button.classList.toggle("active", pressed);',
      'button.setAttribute("aria-pressed"',
      ".function-slot-button.active",
      "sendCabFunctionByMode",
    ])
    self.assert_source_contains_all(slider_source, [
      'element.addEventListener("pointerdown"',
      'element.addEventListener("pointermove"',
      'element.addEventListener("pointerup"',
    ])

  def test_keyboard_function_shortcuts_support_momentary_release(self):
    app_source = self.read_text("assets/js/app.js") + self.read_text("assets/js/app-bootstrap.js")
    for token in [
      'document.addEventListener("keydown", handleVehicleKeyboard)',
      'document.addEventListener("keyup", handleVehicleKeyboardRelease)',
      "pressedFunctionKeys",
      'sendCabFunctionByMode(appState.activeCabId, digit, "down")',
      'sendCabFunctionByMode(cabId, digit, "up")',
      "pressedFunctionKeys.delete",
    ]:
      self.assertIn(token, app_source)

  def test_consist_vehicle_control_uses_member_navigation_and_current_badge_slot(self):
    source = self.read_text("assets/js/vehicle-cab-view.js")
    app_source = self.read_text("assets/js/app.js")
    runtime_source = self.read_text("assets/js/loco-runtime-actions.js")
    state_source = self.read_text("assets/js/state-store.js")
    css = self.read_text("assets/css/app.css")
    for token in [
      "memberIndex: null",
      "resolveCabConsistContext(selectedVehicle, cab, functions, handlers)",
      "renderConsistImageSwitcher(cabId, image, context, handlers)",
      "formatCabAddressText(vehicle, context)",
      "slice(0, 3).join(\"|\")",
      "cab-current-badge-slot",
      "select.append(disabledBadge)",
      "row.append(select, statusSlot, edit, drag)",
      "function cabFunctionVehicle(cabId)",
      "functionDefinition(targetVehicle.id, functionNumber)",
      "await setLocoFunction(targetVehicle.id, functionNumber, Boolean(enabled), cab.functions)",
      "function switchCabConsistMember(cabId, step)",
      "const positions = [null, ...members.map((_member, index) => index)]",
      ".cab-consist-image-switcher",
      ".cab-current-badge-slot",
    ]:
      self.assertIn(token, source + app_source + runtime_source + state_source + css)
    self.assertNotIn("renderConsistMemberNavigator(cabId, context, handlers)", source)
    self.assertNotIn(".cab-consist-member-nav", css)

  def test_each_cab_has_category_filter_and_sort_controls(self):
    state_source = self.read_text("assets/js/state-store.js")
    source = self.read_text("assets/js/vehicle-cab-view.js")
    app_source = self.read_text("assets/js/app.js")
    css = self.read_text("assets/css/app.css")
    for token in [
      'categories: []',
      'categoryId: ""',
      'sortKey: "custom"',
      'sortDirection: "asc"',
      "renderCabFilters",
      "cab-filter-bar",
      "handlers.cabVehicles?.left",
      "handlers.cabVehicles?.right",
      "onCabCategoryFilter",
      "onCabSortChange",
      "sortCabVehicles",
      "filterCabVehicles",
      "添加时间",
      "车辆号",
      "车辆名称",
      "局段",
      "自定义排序",
    ]:
      self.assertIn(token, state_source + source + app_source + css)

  def test_vehicle_custom_sort_drag_handle_saves_order(self):
    api_source = self.read_text("assets/js/gateway-api.js")
    view_source = self.read_text("assets/js/vehicle-cab-view.js")
    app_source = self.read_text("assets/js/app.js")
    css = self.read_text("assets/css/app.css")
    for token in [
      "function reorderVehicles",
      '"/api/vehicles/order"',
      "vehicle-drag-handle",
      "draggable = true",
      "onVehicleDragStart",
      "onVehicleDragOver",
      "onVehicleDrop",
      "saveCustomVehicleOrder",
      "reorderVehicles(nextVehicleIds)",
      "cursor: grab;",
    ]:
      self.assertIn(token, api_source + view_source + app_source + css)

  def test_cab_pointerdown_does_not_replace_child_controls_before_click(self):
    view_source = self.read_text("assets/js/vehicle-cab-view.js")
    app_source = self.read_text("assets/js/app.js")
    for token in [
      "function isCabActivationTarget",
      'section.addEventListener("pointerdown", (event) => {',
      "if (!isCabActivationTarget(event.target))",
      'handlers.onActivateCab?.(cabId, {render: false})',
      "function activateCab(cabId, options = {})",
      "if (options.render === false)",
    ]:
      self.assertIn(token, view_source + app_source)

  def test_cab_console_labels_and_control_actions_are_localized(self):
    source = self.read_text("assets/js/vehicle-cab-view.js")
    self.assertIn('"左控制台"', source)
    self.assertIn('"右控制台"', source)
    self.assertNotIn('"左 Cab"', source)
    self.assertNotIn('"右 Cab"', source)
    start = source.index("function renderCabControlPanel")
    end = source.index("function formatCabSpeedValue")
    control_panel_source = source[start:end]
    self.assertIn("cab-control-identity", control_panel_source)
    self.assertIn("cab-control-media", control_panel_source)
    self.assertIn("cab-direction-row", control_panel_source)
    self.assertIn("紧急停车", control_panel_source)
    self.assertNotIn("经济停车", control_panel_source)
    self.assertNotIn('segmentButton("前进"', control_panel_source)
    self.assertNotIn('segmentButton("后退"', control_panel_source)
    self.assertIn('segmentButton("←"', control_panel_source)
    self.assertIn('segmentButton("→"', control_panel_source)

  def test_vehicle_drag_preview_reorders_rows_and_handle_follows_edit_button(self):
    view_source = self.read_text("assets/js/vehicle-cab-view.js")
    app_source = self.read_text("assets/js/app.js")
    css = self.read_text("assets/css/app.css")
    self.assert_source_contains_all(view_source + app_source + css, [
      "let draggedVehicleRow = null",
      "row.draggable = true",
      "renderDragInsertionPreview",
      "orderedVehicleIdsFromList",
      "row.append(select, statusSlot, edit, drag)",
      "saveCustomVehicleOrder(cabId, vehicleId, orderedVehicleIds)",
      "mergeVisibleCustomOrder",
      ".cab-vehicle-row.dragging",
    ])

  def test_long_vehicle_names_do_not_wrap_row_action_buttons(self):
    view_source = self.read_text("assets/js/vehicle-cab-view.js")
    css = self.read_text("assets/css/app.css")
    self.assert_source_contains_all(view_source + css, [
      "select.append(vehicleImage(vehicle), vehicleText(vehicle, handlers));",
      ".cab-vehicle-row .vehicle-text {",
      ".cab-vehicle-row .vehicle-display-name {",
      "max-inline-size: clamp(8rem, 24vw, 18rem);",
      "text-overflow: ellipsis;",
      ".cab-vehicle-edit,",
      ".vehicle-drag-handle {",
      "white-space: nowrap;",
      "flex: 0 0 auto;",
    ])

  def test_vehicle_drop_save_does_not_rerender_before_follow_up_edit_click(self):
    app_source = self.read_text("assets/js/app.js")
    function_source = app_source[
      app_source.index("async function saveCustomVehicleOrder"):
      app_source.index("function fallbackCustomOrder")
    ]
    self.assertIn("await reorderVehicles(nextVehicleIds)", function_source)
    self.assertNotIn("renderAll();", function_source)

  def test_vehicle_order_route_is_checked_before_vehicle_id_patch_route(self):
    source = self.read_text("server/api_support/routes.py")
    self.assertIn('"/api/vehicles/order": "vehicles.reorder"', source)
    self.assertIn('resource_route(route, "vehicles")', source)
    self.assertNotIn('route.startswith("/api/vehicles/")', source)

  def test_state_store_tracks_left_and_right_cabs(self):
    source = self.read_text("assets/js/state-store.js")
    self.assertIn('activeCabId: "left"', source)
    self.assertIn("left: createCabState()", source)
    self.assertIn("right: createCabState()", source)
    self.assertIn("function createCabState()", source)
    self.assertIn("ensureCabVehicles", source)

  def test_vehicle_view_renders_ecos_style_dual_cab_workspace(self):
    source = self.read_text("assets/js/vehicle-cab-view.js")
    css = self.read_text("assets/css/app.css")
    for token in [
      "export function renderVehicleControlWorkspace",
      "renderCabColumn",
      "renderCabVehicleList",
      "renderCabControlPanel",
      "cab-workspace",
      "cab-column",
      "cab-control-panel",
      "展开控制",
      "返回列表",
      "active-cab",
    ]:
      self.assertIn(token, source + css)

  def test_cab_layout_keeps_controls_first_and_vehicle_images_bounded(self):
    source = self.read_text("assets/js/vehicle-cab-view.js")
    css = self.read_text("assets/css/app.css")
    cab_column = source[
      source.index("function renderCabColumn"):
      source.index("function renderCabFilters")
    ]
    self.assertIn("const controlPanel = selectedVehicle ? renderCabControlPanel", cab_column)
    self.assertIn("section.append(renderCabVehicleList(cabId, vehicles, cab, cabState, handlers));", cab_column)
    self.assertLess(cab_column.index("section.append(controlPanel);"), cab_column.index("section.append(renderCabVehicleList"))
    for token in [
      "cab-current-badge",
      'select.setAttribute("aria-pressed"',
      ".vehicle-card > img",
      ".vehicle-card > .vehicle-placeholder",
      ".cab-vehicle-select > img",
      ".cab-vehicle-select > .vehicle-placeholder",
      "inline-size: var(--vehicle-thumb-inline);",
      "block-size: var(--vehicle-thumb-block);",
      "flex: 0 0 var(--vehicle-thumb-inline);",
      "overflow: hidden;",
      "cursor: pointer;",
    ]:
      self.assertIn(token, source + css)

  def test_cab_control_panel_uses_side_actions_speed_scaling_and_function_state(self):
    view_source = self.read_text("assets/js/vehicle-cab-view.js")
    app_source = self.read_text("assets/js/app.js")
    runtime_source = self.read_text("assets/js/loco-runtime-actions.js")
    css = self.read_text("assets/css/app.css")
    self.assert_source_contains_all(view_source + app_source + runtime_source + css, [
      "cab-control-main-row",
      "cab-control-info",
      "cab-control-identity",
      "cab-control-identity-primary",
      "cab-control-address-row",
      "cab-control-address-badge",
      "cab-control-full-name-tag",
      "cab-control-meta-row",
      "cab-control-meta-tag",
      "cab-control-media",
      "cab-speed-control",
      "cab-speed-value",
      "cab-speed-throttle",
      "cab-speed-throttle-fill",
      "cab-control-side-actions",
      "speedValue.textContent = formatCabSpeedValue(speed, vehicle.max_speed);",
      "speedValue.className = \"cab-speed-value\";",
      "speedControl.append(speedValue, throttle);",
      "throttle.className = \"cab-speed-throttle\";",
      "throttle.setAttribute(\"role\", \"slider\");",
      "throttle.setAttribute(\"aria-valuemax\", \"126\");",
      "updateCabSpeedThrottleFill(throttle, speed);",
      "function updateCabSpeedThrottleFill(throttle, speedStep)",
      "setVerticalSliderFill(throttle, \"--speed-fill-percent\", (step / 126) * 100, step);",
      "bindVerticalSlider(throttle, {",
      "normalizeValue: clampCabSpeedStep,",
      "const fullNameTag = cabControlInfoTag(formatVehicleField(vehicle.full_name), \"cab-control-full-name-tag\", \"完整名称\");",
      "const brandTag = cabControlInfoTag(formatVehicleField(vehicle.brand), \"cab-control-meta-tag\", \"品牌\");",
      "const articleNumberTag = cabControlInfoTag(formatVehicleField(vehicle.article_number), \"cab-control-meta-tag\", \"货号\");",
      "identity.append(nameLine, addressLine, metaLine);",
      "media.append(renderConsistImageSwitcher(cabId, image, context, handlers));",
      "infoColumn.className = \"cab-control-info\";",
      "infoColumn.append(identity);",
      "sideActions.append(speedControl, directionRow, stop);",
      "mainRow.append(infoColumn, media, functionGrid, sideActions);",
      "panel.append(mainRow);",
      "button.dataset.triggerMode = fn.trigger_mode || \"toggle\";",
      "button.classList.toggle(\"active\", pressed);",
      ".function-slot-empty",
      "visible: configured?.is_configured !== false,",
      "if (fn.visible === false) {",
      "renderEmptyFunctionSlot(fn.function_number)",
      "return buildFunctionSlots(functions, 31).slice(10);",
      "function formatCabSpeedValue(speedStep, maxSpeed)",
      "const scaled = Math.round((step / 126) * Number(maxSpeed));",
      "return `${scaled} km/h`;",
      ".function-slot-button.active",
      ".cab-control-main-row",
      "grid-template-areas:",
      "\"info media actions\"",
      "\"functions functions actions\"",
      ".cab-control-info",
      "grid-area: info;",
      ".cab-control-identity",
      ".cab-control-identity-primary",
      ".cab-control-address-row",
      ".cab-control-address-badge",
      ".cab-control-full-name-tag",
      ".cab-control-meta-row",
      ".cab-control-meta-tag",
      ".cab-control-full-name-tag {\n  flex: 0 1 auto;",
      ".cab-control-meta-tag {\n  flex: 0 1 auto;",
      ".cab-control-media",
      "grid-area: media;",
      "place-items: center;",
      ".cab-speed-value",
      ".cab-direction-row",
      ".cab-economic-stop",
      "background: #b91c1c;",
      "border-color: #7f1d1d;",
      "color: #fff;",
      "box-shadow: 0 0 0 2px rgba(127, 29, 29, 0.18), 0 2px 8px rgba(127, 29, 29, 0.28);",
      ".cab-control-side-actions",
      "grid-area: actions;",
      "grid-template-rows: minmax(clamp(8rem, 13vw, 10.8rem), 1fr) max-content max-content;",
      "align-content: stretch;",
      ".cab-function-grid",
      "grid-area: functions;",
      "--speed-fill-percent: 0%;",
      ".cab-speed-throttle",
      "place-items: stretch center;",
      "block-size: 100%;",
      "cursor: ns-resize;",
      "touch-action: none;",
      "clip-path: polygon(12% 0, 88% 0, 72% 100%, 28% 100%);",
      "linear-gradient(0deg, #dceaf0 0%, #f6fafb 100%)",
      ".cab-speed-throttle-fill",
      "block-size: var(--speed-fill-percent);",
      "inset-block-end: 0;",
      "linear-gradient(0deg, #e9532d 0%, #ff7a3d 100%)",
      ".cab-filter-bar select",
      "inline-size: max-content;",
      "white-space: nowrap;",
      "font-size: clamp(0.72rem, 2.6vw, 0.9rem);",
      "object-fit: contain;",
      "object-position: center;",
      "--cab-control-image-block-size: clamp(6rem, 10vw, 9.5rem);",
      "block-size: var(--cab-control-image-block-size);",
      "inline-size: 100%;",
      "block-size: 100%;",
      "max-inline-size: 100%;",
      "max-block-size: var(--cab-control-image-block-size);",
      "max-height: var(--cab-control-image-block-size);",
      "width: auto;",
      "height: auto;",
      "display: block;",
      "--cab-control-image-block-size: clamp(4.6rem, 22vw, 6rem);",
      "const cabFunctionTimers = new Map();",
      "function clearCabFunctionTimer(cabId, functionNumber)",
      "if (mode === \"momentary\")",
      "if (mode === \"timed\")",
      "const timer = globalScope.setTimeout(() => {",
      "setCabFunctionState(cabId, functionNumber, false);",
      "await setCabFunctionState(cabId, functionNumber, !Boolean(cab.functions[String(functionNumber)]));",
    ])

  def test_cab_control_panel_is_split_into_named_view_helpers(self):
    source = self.read_text("assets/js/vehicle-cab-view.js")
    view_source = source
    css = self.read_text("assets/css/app.css")
    panel_source = self.source_function(source, "renderCabControlPanel")
    for helper_name in [
      "renderCabIdentity",
      "renderCabSpeedControl",
      "renderCabFunctionGrid",
      "renderCabDirectionActions",
    ]:
      self.assertIn(f"function {helper_name}", source)
      self.assertIn(f"{helper_name}(", panel_source)
    self.assertNotIn("identity.append(nameLine, addressLine, railwayLine, speedControl);", view_source)
    self.assertNotIn("identity.append(nameLine, addressLine, railwayLine, speedValue);", view_source)
    self.assertNotIn("cab-control-railway", view_source)
    self.assertNotIn(".cab-control-railway", css)
    self.assertNotIn("speedControl.append(speedValue, slider);", view_source)
    self.assertNotIn("cab-speed-control input[type=\"range\"].cab-speed-slider", css)
    self.assertNotIn("linear-gradient(90deg, #1f7fa0", css)
    self.assertNotIn("#293840", css)
    self.assertNotIn("#172126", css)
    self.assertNotIn("media.append(image, speedControl);", view_source)
    self.assertNotIn("infoColumn.append(identity, media);", view_source)
    self.assertNotIn(".cab-speed-throttle {\n  writing-mode: vertical-lr;", css)
    self.assertNotIn(".cab-speed-throttle {\n  direction: rtl;", css)
    self.assertNotIn(".dc-voltage-slider {\n  writing-mode: vertical-lr;", css)
    self.assertIn(".dc-voltage-slider-fill", css)

  def test_app_wires_dual_cab_vehicle_control(self):
    source = self.read_text("assets/js/app.js") + self.read_text("assets/js/cab-workspace-actions.js")
    for token in [
      "renderVehicleControlWorkspace",
      "activateCab",
      "selectCabVehicle",
      "toggleCabExpanded",
      "sendCabSpeed",
      "sendCabFunction",
      "cabVehicle",
      "activeCab",
      "onActivateCab",
      "onSelectVehicle",
      "onToggleCabExpanded",
    ]:
      self.assertIn(token, source)

  def test_vehicle_keyboard_routes_to_active_cab(self):
    source = self.read_text("assets/js/app-bootstrap.js") + self.read_text("assets/js/app.js")
    keyboard_source = source[source.index('document.addEventListener("keydown"'):]
    for token in [
      "handleVehicleKeyboard",
      "isEditableKeyboardTarget",
      "appState.activeCabId",
      "sendCabSpeed(appState.activeCabId",
      "sendCabFunctionByMode(appState.activeCabId",
      "Digit0",
      "Numpad0",
      "ArrowUp",
      "ArrowDown",
      "ArrowLeft",
      "ArrowRight",
      "event.key === \" \"",
    ]:
      self.assertIn(token, keyboard_source)


if __name__ == "__main__":
  unittest.main()
