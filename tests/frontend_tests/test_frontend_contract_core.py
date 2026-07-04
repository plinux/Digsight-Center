import unittest
import subprocess
from pathlib import Path

from tests.frontend_tests.source_assertions import SourceAssertionsMixin


TOKEN_PROMPT_TEXT = "请输入操作" + "授权令牌"


class FrontendCoreContractTest(SourceAssertionsMixin, unittest.TestCase):
  def test_source_assertion_helpers_extract_named_function(self):
    source = "function first() {\n  return 1;\n}\n\nasync function second() {\n  return 2;\n}\n\nfunction third(options = {}) {\n  return options;\n}\n"
    self.assertEqual(self.source_function(source, "first").strip(), "function first() {\n  return 1;\n}")
    self.assertEqual(self.source_function(source, "second").strip(), "async function second() {\n  return 2;\n}")
    self.assertEqual(self.source_function(source, "third").strip(), "function third(options = {}) {\n  return options;\n}")

  def test_gateway_and_cv_modules_execute_core_behaviors(self):
    subprocess.run(["node", "tests/frontend_tests/gateway_cv_behavior.mjs"], check=True)

  def test_frontend_uses_shared_helper_modules(self):
    app_source = self.read_text("assets/js/app.js")
    vehicle_source = self.read_text("assets/js/vehicle-view.js")
    ui_helper_source = self.read_text("assets/js/ui-helpers.js")
    consist_helper_path = Path("assets/js/consist-helpers.js")
    self.assertTrue(consist_helper_path.exists(), "assets/js/consist-helpers.js should provide shared consist helpers")
    helper_source = consist_helper_path.read_text(encoding="utf-8")
    self.assert_source_contains_all(app_source, ['from "./consist-helpers.js"'])
    self.assert_source_contains_all(vehicle_source, ['from "./consist-helpers.js"'])
    self.assert_source_contains_all(helper_source, ["export function sortedConsistMembers"])
    self.assert_source_not_contains_any(app_source, ["function sortedConsistMembers(consist)"])
    self.assert_source_not_contains_any(vehicle_source, ["function sortedConsistMembers(consist, vehicles)"])
    self.assert_source_contains_all(ui_helper_source, ["export function labeledInput"])
    self.assert_source_not_contains_any(ui_helper_source, ["export function setText", "export function createButton"])

  def test_vehicle_view_uses_shared_vertical_slider_helper(self):
    cab_source = self.read_text("assets/js/vehicle-cab-view.js")
    vehicle_source = self.read_text("assets/js/vehicle-view.js")
    slider_source = self.read_text("assets/js/vertical-slider.js")
    self.assert_source_contains_all(cab_source, ['from "./vertical-slider.js"'])
    self.assert_source_contains_all(slider_source, [
      "export function verticalValueFromPointer",
      "export function setVerticalSliderFill",
    ])
    self.assert_source_not_contains_any(vehicle_source + cab_source, [
      "function speedFromThrottlePointer",
      "function dcVoltageFromPointer",
    ])

  def test_function_icon_catalog_is_loaded_from_dedicated_module(self):
    vehicle_source = self.read_text("assets/js/vehicle-view.js")
    catalog_source = self.read_text("assets/js/function-icon-catalog.js")
    app_source = self.read_text("assets/js/app.js")
    self.assertIn('from "./function-icon-catalog.js"', vehicle_source + app_source)
    self.assertIn("export const FALLBACK_FUNCTION_ICON_CATALOG", catalog_source)
    self.assertIn('fetchImpl("/config/function-icons.json"', catalog_source)
    self.assertIn("function_icon_mapping_files", catalog_source)
    self.assertIn("capabilities?.import_formats", catalog_source)
    self.assertNotIn('fetchImpl("/config/function-icon-mappings/z21.json"', catalog_source)
    self.assertNotIn('"version": 1,', vehicle_source[:5000])
    self.assertNotIn('"mappings": {', vehicle_source)

  def test_vehicle_kind_icons_are_split_from_vehicle_view(self):
    vehicle_source = self.read_text("assets/js/vehicle-view.js")
    icon_source = self.read_text("assets/js/vehicle-kind-icons.js")
    self.assert_source_contains_all(vehicle_source, ['from "./vehicle-kind-icons.js"'])
    self.assert_source_contains_all(icon_source, [
      "export function vehicleEnergyGlyph",
      "export function vehicleKindIcon",
      "export const VEHICLE_KIND_META",
    ])
    self.assert_source_not_contains_any(vehicle_source, ["function vehicleEnergyGlyph"])

  def test_vehicle_view_delegates_cab_and_editor_modules(self):
    app_source = self.read_text("assets/js/app.js")
    vehicle_source = self.read_text("assets/js/vehicle-view.js")
    cab_source = self.read_text("assets/js/vehicle-cab-view.js")
    editor_source = self.read_text("assets/js/vehicle-editor-view.js")
    self.assert_source_contains_all(cab_source, [
      "export function renderDcControl",
      "export function renderVehicleControlWorkspace",
    ])
    self.assert_source_contains_all(editor_source, ["export function renderVehicleEditor"])
    self.assert_source_contains_all(app_source + vehicle_source, [
      'from "./vehicle-cab-view.js',
      'from "./vehicle-editor-view.js',
    ])
    self.assert_source_not_contains_any(vehicle_source, [
      "export function renderLocoControl",
      "export function renderVehicleEditor",
    ])

  def test_gateway_api_defines_required_calls(self):
    source = self.read_text("assets/js/gateway-api.js")
    self.assert_source_contains_all(source, [
      f"function {name}" for name in [
      "getState",
      "setTrackPower",
      "importConfig",
      "readCv",
      "readAllCvValues",
      "cancelCvRead",
      "writeCv",
      "readChipInfo",
      "readAddress",
      "writeAddress",
      "getCvMetadata",
      "getControllerInfo",
      "readControllerInfo",
      "resetControllerConfig",
      "saveControllerSettings",
      "setControllerTrackMode",
      "setDcControl",
      "createVehicle",
      "updateVehicle",
      "deleteVehicle",
      "uploadVehicleImage",
      "createConsist",
      "updateConsist",
      "deleteConsist",
      "setLocoSpeed",
      "setLocoFunction",
      ]
    ])
    self.assertNotIn("function importZ21", source)

  def test_gateway_api_emits_busy_events(self):
    source = self.read_text("assets/js/gateway-api.js")
    self.assertIn('CustomEvent("digsight:gateway-busy"', source)
    self.assertIn("notifyGatewayBusy(true);", source)
    self.assertIn("notifyGatewayBusy(false);", source)
    self.assertIn("finally", source)

  def test_gateway_api_uses_method_helpers(self):
    gateway_source = self.read_text("assets/js/gateway-api.js")
    self.assertIn("requestJson", gateway_source)
    self.assertIn("postJson(", gateway_source)
    self.assertIn("patchJson(", gateway_source)
    self.assertIn("deleteJson(", gateway_source)

  def test_gateway_mutations_send_client_header(self):
    source = self.read_text("assets/js/gateway-api.js")
    self.assertIn('"X-Digsight-Client": "digsight-web"', source)
    self.assertIn('"Content-Type": "application/json"', source)
    self.assertIn('"Content-Type": "application/octet-stream"', source)

  def test_gateway_api_never_prompts_for_operation_token(self):
    source = self.read_text("assets/js/gateway-api.js")
    self.assertNotIn(TOKEN_PROMPT_TEXT, source)
    self.assertNotIn("X-Digsight-Operation-Token", source)
    self.assertNotIn("operationHeaders", source)
    self.assertNotIn("requestOperationToken", source)
    self.assertNotIn("setOperationToken", source)
    self.assertNotIn("rememberOperationTokenFromState", source)

  def test_operation_mode_switch_does_not_prompt_for_operation_token(self):
    api_source = self.read_text("assets/js/gateway-api.js")
    app_source = self.read_text("assets/js/app.js")
    function_source = self.source_function(api_source, "setControllerTrackMode")
    self.assertIn('patchJson("/api/controller/track-mode"', function_source)
    self.assertIn("setControllerTrackMode(trackMode)", app_source)
    set_mode_source = self.source_function(app_source, "setOperationMode")
    self.assertNotIn("saveControllerSettings({track_mode: trackMode})", set_mode_source)

  def test_gateway_api_writes_do_not_send_operation_token_headers(self):
    source = self.read_text("assets/js/gateway-api.js")
    for function_name in [
      "setTrackPower",
      "setDcControl",
      "saveControllerSettings",
      "resetControllerConfig",
      "importConfig",
      "writeCv",
      "writeAddress",
      "updateVehicle",
      "createVehicle",
      "deleteVehicle",
      "uploadVehicleImage",
      "reorderVehicles",
      "createConsist",
      "updateConsist",
      "deleteConsist",
      "setLocoSpeed",
      "setLocoFunction",
    ]:
      function_source = self.source_function(source, function_name)
      self.assertNotIn("operationHeaders", function_source, function_name)
      self.assertNotIn("X-Digsight-Operation-Token", function_source, function_name)

  def test_track_power_clicks_do_not_confirm_or_prompt_for_token(self):
    source = self.read_text("assets/js/app-bootstrap.js")
    power_on_source = source[source.index("elements.powerOnButton.addEventListener"):]
    power_on_source = power_on_source[:power_on_source.index("elements.powerOffButton.addEventListener")]
    power_off_source = source[source.index("elements.powerOffButton.addEventListener"):]
    power_off_source = power_off_source[:power_off_source.index("elements.importConfigButton.addEventListener")]
    self.assertIn("setTrackPower(true)", power_on_source)
    self.assertIn("setTrackPower(false)", power_off_source)
    self.assertNotIn("confirm(", power_on_source)
    self.assertNotIn("confirm(", power_off_source)
    self.assertNotIn(TOKEN_PROMPT_TEXT, power_on_source)
    self.assertNotIn(TOKEN_PROMPT_TEXT, power_off_source)

  def test_controller_config_reset_confirms_files_before_api_call(self):
    html = self.read_text("index.html")
    gateway_source = self.read_text("assets/js/gateway-api.js")
    app_source = self.read_text("assets/js/app.js")
    bootstrap_source = self.read_text("assets/js/app-bootstrap.js")
    controller_workflow_source = self.read_text("assets/js/controller-workflow.js")

    self.assertIn('id="resetControllerConfigButton"', html)
    self.assertIn('export function resetControllerConfig(kind)', gateway_source)
    self.assertIn('postJson("/api/controller/reset-config"', gateway_source)
    self.assertIn("export async function resetSelectedControllerConfig(", controller_workflow_source)
    self.assertIn("function confirmControllerConfigReset(files)", controller_workflow_source)
    self.assertIn("globalThis.confirm(message)", controller_workflow_source)
    self.assertIn("本次会重置以下文件", controller_workflow_source)
    self.assertIn("reset_files", controller_workflow_source)
    self.assertIn("shouldIncludeGlobalStateInReset", controller_workflow_source)
    self.assertIn("app_state_corrupt_recovered", controller_workflow_source)
    self.assertIn("data/app-state.json", controller_workflow_source)
    self.assertNotIn("async function resetSelectedControllerConfig()", app_source)
    self.assertNotIn("function confirmControllerConfigReset(files)", app_source)
    reset_source = controller_workflow_source[
      controller_workflow_source.index("export async function resetSelectedControllerConfig("):
      controller_workflow_source.index("function confirmControllerConfigReset")
    ]
    self.assertLess(reset_source.index("confirmControllerConfigReset"), reset_source.index("resetControllerConfig("))
    self.assertIn("elements.resetControllerConfigButton.addEventListener", bootstrap_source)

  def test_header_brand_is_right_aligned_outside_primary_controls(self):
    html = self.read_text("index.html")
    css = self.read_text("assets/css/app.css")
    header_controls = html[html.index('<div class="header-controls">'):html.index('<div id="connectionStatus"')]

    self.assertNotIn('class="brand"', header_controls)
    self.assertIn('class="header-brand brand"', html)
    self.assertIn('grid-template-areas: "controls status runtime brand";', css)
    self.assertIn(".header-brand", css)
    self.assertIn("grid-area: brand;", css)

  def test_controller_config_error_status_suggests_manual_repair_or_reset(self):
    app_source = self.read_text("assets/js/app.js")
    source = self.read_text("assets/js/controller-workflow.js")
    self.assertIn("export function persistentConfigurationStatus(", source)
    self.assertIn("当前控制器配置文件无效", source)
    self.assertIn("请手工修复该 JSON 文件，或点击重置恢复默认配置。", source)
    self.assertIn("重置只会影响当前选择控制器的配置文件。", source)
    self.assertIn("persistentConfigurationStatus", source)
    self.assertNotIn("function persistentConfigurationStatus()", app_source)

  def test_track_power_not_ready_message_is_user_actionable(self):
    source = self.read_text("assets/js/controller-workflow.js")
    self.assertIn("轨道状态未确认，正在重新读取控制器信息", source)

  def test_track_power_on_retries_after_stale_booster_status(self):
    source = self.read_text("assets/js/app.js")
    workflow_source = self.read_text("assets/js/controller-workflow.js")
    bootstrap_source = self.read_text("assets/js/app-bootstrap.js")
    self.assertIn("export async function runControllerStatusRetry", workflow_source)
    self.assertIn("function isRetryableControllerStatusError", workflow_source)
    self.assertNotIn("async function runTrackPowerRequestWithStatusRetry", source)
    self.assertNotIn("function isRetryableTrackPowerStatusError", source)
    retry_source = workflow_source[
      workflow_source.index("export async function runControllerStatusRetry"):
      workflow_source.index("function isRetryableControllerStatusError")
    ]
    classifier_source = workflow_source[
      workflow_source.index("function isRetryableControllerStatusError"):
      workflow_source.index("export function syncControllerDescriptorControls")
    ]
    power_on_source = bootstrap_source[bootstrap_source.index("elements.powerOnButton.addEventListener"):]
    power_on_source = power_on_source[:power_on_source.index("elements.powerOffButton.addEventListener")]
    self.assertIn("return await requestFn();", retry_source)
    self.assertIn("if (!requiresFreshStatus || !isRetryableControllerStatusError(error))", retry_source)
    self.assertIn("await readControllerInfo();", retry_source)
    self.assertIn("await refreshState();", retry_source)
    self.assertIn("return await requestFn();", retry_source)
    self.assertIn('error.payload?.error?.type === "protocol_not_ready"', classifier_source)
    for warning in [
      "booster_status_unconfirmed",
      "booster_status_stale",
      "controller_not_confirmed",
    ]:
      self.assertIn(warning, classifier_source)
    self.assertIn("runControllerStatusRetry({", power_on_source)
    self.assertIn("requiresFreshStatus: true", power_on_source)
    self.assertIn("requestFn: () => setTrackPower(true)", power_on_source)

  def test_app_wires_required_panels(self):
    source = self.read_text("assets/js/app.js") + self.read_text("assets/js/app-bootstrap.js")
    self.assert_source_contains_all(source, [
      "setTrackPower",
      "powerOnButton",
      "powerOffButton",
      "syncControllerEndpoint",
      "readControllerInfo",
      "updateVehicle",
      "writeCv",
      "readAddress",
      "writeAddress",
      "renderControllerHeader",
      "programmingTargetButtons",
      "setProgrammingTarget",
      "data-programming-target",
      "operationModeButtons",
      "setOperationMode",
      "isDigitalOperationMode",
      'return trackMode === "n" || trackMode === "ho" || trackMode === "g";',
      "isDccProgrammingMode",
      "isDcOperationMode",
      "dcControl",
      "renderDcControl",
      "setDcControl",
      "isDcOperationMode(operationMode)",
      "renderDcControl(",
      "vehicleControlView.classList.toggle(\"dc-control-mode\"",
      "importStrip.hidden = isDcMode",
      "readChipInfoFromController",
      "data-track-mode",
      "navCvProgramming.disabled",
      "renderVehicleEditor",
      "renderVehicleControlWorkspace",
      "renderControllerSettings",
      "keydown",
      "ArrowUp",
      "ArrowDown",
      "ArrowLeft",
      "ArrowRight",
      " ",
      "setLocoSpeed",
      "renderCvPanel",
      "cvProgrammingRequest",
      "chipInfo",
      "cvList",
      "downloadTextFile",
      "buildCvMarkdown",
      "buildCvCsv",
      "connectionStatusText",
      "statusDetailButton",
      "statusDetailDialog",
      "refreshState",
      "gatewayBusyCount",
      "digsight:gateway-busy",
      "busy: isGatewayBusy()",
    ])
    self.assert_source_contains_all(source, ["setStatus(`已设置为 ${modeName} 模式`);"])
    self.assert_source_not_contains_any(source, [
      "不要执行 G 比例实车 CV、速度或功能控制",
      "renderDcVoltageControl(elements.vehicleRegistry",
      "onDcVoltage",
    ])

  def test_sync_controller_endpoint_uses_transport_readiness_helper(self):
    source = self.read_text("assets/js/app.js")
    controller_workflow_source = self.read_text("assets/js/controller-workflow.js")
    function_source = source[
      source.index("async function syncControllerEndpoint()"):
      source.index("async function setOperationMode")
    ]

    self.assertIn("const descriptor = controllerDescriptor(appState.capabilities, kind);", function_source)
    self.assertIn("controllerEndpointReady(descriptor, appState.controller)", function_source)
    self.assertIn("controllerEndpointReady", source)
    self.assertNotIn("function controllerEndpointReady(descriptor", source)
    self.assertIn("export function controllerEndpointReady(descriptor", controller_workflow_source)
    self.assertNotIn("Number(controllerTransport.udp_port || 0) > 0", function_source)
    self.assertIn("appState.controller.transport = result.transport ?? appState.controller.transport;", function_source)
    self.assertNotIn("result.transport ||", function_source)

  def test_controller_endpoint_ready_uses_descriptor_readiness_contract(self):
    source = self.read_text("assets/js/controller-workflow.js")
    function_source = self.source_function(source, "controllerEndpointReady")

    self.assertIn("endpoint_readiness", function_source)
    self.assertIn("required_paths", function_source)
    self.assertIn("controllerEndpointValue", function_source)
    self.assertIn("every((path)", function_source)
    self.assertNotIn("transport_fields", function_source)
    self.assertNotIn("udp_port", function_source)
    self.assertIn("controllerDescriptor", source)

  def test_app_splits_render_all_handler_builders(self):
    source = self.read_text("assets/js/app.js")
    self.assertIn('from "./cab-controller.js"', source)
    self.assertIn('from "./cv-controller.js"', source)
    self.assertIn("buildCvPanelHandlers, createCvDomainModel", source)
    self.assertIn('from "./vehicle-editor-controller.js"', source)
    self.assertIn('from "./cab-workspace-actions.js"', source)
    self.assertIn('from "./vehicle-editor-actions.js"', source)
    self.assertIn('from "./app-bootstrap.js"', source)
    self.assertNotIn("function buildCabWorkspaceHandlers", source)
    self.assertNotIn("function buildVehicleEditorHandlers", source)
    self.assertNotIn("function buildCvPanelHandlers", source)
    self.assertIn("function buildCvExportHandlers()", source)
    self.assertNotIn("function buildCvAddressHandlers()", source)
    self.assertNotIn("function buildSingleCvHandlers()", source)
    self.assertIn("function buildControllerSettingsHandlers()", source)
    runtime_source = self.read_text("assets/js/cv-runtime-actions.js")
    self.assertIn("function buildCvAddressHandlers()", runtime_source)
    self.assertIn("function buildSingleCvHandlers()", runtime_source)

  def test_controller_header_supports_busy_lamp(self):
    source = self.read_text("assets/js/controller-view.js")
    self.assertIn("state = {}", source)
    self.assertIn("state.busy", source)
    self.assertIn("resolveConnectionLampState", source)
    self.assertIn("state.controllerInfo", source)
    self.assertIn("controller_reachable", source)
    self.assertIn("booster_status", source)
    self.assertIn("power_on", source)
    self.assertIn("short_circuit", source)
    self.assertIn("lamp lamp-track-off", source)
    self.assertIn("lamp lamp-track-on", source)
    self.assertIn("lamp lamp-busy", source)
    self.assertIn("lamp lamp-short", source)
    self.assertIn("控制器已连通，轨道未上电", source)
    self.assertIn("控制器已连通，轨道已上电", source)
    self.assertIn("控制器正在读写操作", source)
    self.assertIn("控制器发生短路", source)
    self.assertIn("控制器未能连通", source)

  def test_app_passes_cached_controller_info_to_header_lamp(self):
    source = self.read_text("assets/js/app.js")
    self.assertIn("controllerInfo: appState.controllerInfo", source)
    self.assertIn("renderControllerHeader(elements, appState.controller, {busy: isGatewayBusy(), controllerInfo: appState.controllerInfo});", source)

  def test_controller_info_uses_four_column_table(self):
    source = self.read_text("assets/js/controller-view.js")
    helper_source = self.read_text("assets/js/ui-helpers.js")
    self.assertIn('document.createElement("table")', source)
    self.assertIn('table.className = "controller-info-table";', source)
    self.assertIn("appendInfoTableRow", source)
    self.assertIn("row.append(labelCell, valueCell, nextLabelCell, nextValueCell);", source)
    self.assertIn('disabled: disabled || mode === "dc"', source)
    self.assertIn("attrValue === false", helper_source)

  def test_track_profiles_use_two_column_grid(self):
    css = self.read_text("assets/css/app.css")
    self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", css)
    self.assertIn("grid-template-columns: minmax(560px, 1fr) minmax(260px, 360px);", css)
    self.assertIn("#trackProfilePanel", css)
    self.assertIn("max-width: 360px;", css)
    self.assertIn("justify-self: end;", css)
    self.assertIn(".profile-grid button", css)
    self.assertIn("grid-column: 1 / -1;", css)

  def test_operation_mode_handles_missing_backend_track_mode(self):
    source = self.read_text("assets/js/app.js")
    self.assertIn("function normalizeTrackMode", source)
    self.assertIn("const nextTrackMode = normalizeTrackMode(result.track_mode || trackMode);", source)
    self.assertNotIn("trackMode.toUpperCase()", source)
    self.assertIn("已设置为 ${modeName} 模式", source)
    self.assertNotIn("已设为操作模式", source)

  def test_header_lamp_keeps_round_shape_when_status_wraps(self):
    css = self.read_text("assets/css/app.css")
    self.assert_source_contains_all(css, [
      ".lamp {",
      "inline-size:",
      "block-size:",
      "aspect-ratio: 1;",
      "flex: 0 0 auto;",
      "border-radius: 999px;",
      "box-shadow:",
    ])

  def test_header_status_shows_long_errors_in_detail_dialog(self):
    html = self.read_text("index.html")
    source = self.read_text("assets/js/app.js") + self.read_text("assets/js/app-bootstrap.js")
    css = self.read_text("assets/css/app.css")
    for token in [
      'id="statusDetailButton"',
      'id="statusDetailDialog"',
      'id="statusDetailText"',
    ]:
      self.assertIn(token, html)
    for token in [
      "function setStatus(message, detail = \"\")",
      "function showDetailDialog(summary, detail)",
      "function openStatusDetailDialog()",
      "elements.connectionStatusText.textContent = String(summary || \"\");",
      "elements.statusDetailButton.hidden",
      "elements.statusDetailText.textContent",
      "JSON.stringify(error.payload, null, 2)",
      "const apiError = error.payload?.error;",
      "summary: apiError?.message || error.message",
      "detail:",
      "elements.statusDetailButton?.addEventListener(\"click\", openStatusDetailDialog)",
      "elements.statusDetailDialog.showModal()",
    ]:
      self.assertIn(token, source)
    self.assertNotIn("status-summary-link", source)
    self.assertNotIn("replaceChildren(statusLink)", source)
    for token in [
      ".status-detail-button",
      ".status-detail-dialog",
      ".status-detail-text",
      ".cv-error-detail-link",
    ]:
      self.assertIn(token, css)
    self.assertNotIn(".status-summary-link", css)

  def test_header_status_is_width_limited_and_two_line_clamped(self):
    css = self.read_text("assets/css/app.css")
    self.assert_source_contains_all(css, [
      ".header-controls button",
      "white-space: nowrap;",
      ".header-status {",
      "width: clamp(240px, 34vw, 420px);",
      "max-width: 420px;",
      "font-size: 0.78rem;",
      "line-height: 1.25;",
      ".status-text {",
      "display: -webkit-box;",
      "-webkit-line-clamp: 2;",
      "-webkit-box-orient: vertical;",
    ])

  def test_header_status_keeps_detail_link_for_generic_fetch_failures(self):
    source = self.read_text("assets/js/app.js")
    format_error_source = self.source_function(source, "formatError")
    self.assert_source_contains_all(format_error_source, [
      "const genericDetail =",
      "error.stack",
      "error.name",
      "return {summary: error.message, detail: genericDetail};",
    ])

  def test_header_status_explicitly_reports_unsupported_controller_protocol(self):
    source = self.read_text("assets/js/app.js")
    self.assert_source_contains_all(source, [
      "if (apiError?.type === \"controller_protocol_not_supported\") {",
      "当前控制器配置了不支持的协议",
      "请检查当前控制器配置文件中的 protocol",
      "JSON.stringify(error.payload, null, 2)",
    ])


if __name__ == "__main__":
  unittest.main()
