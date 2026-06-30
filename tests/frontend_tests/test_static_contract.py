import unittest
from pathlib import Path

from tests.frontend_tests.source_assertions import SourceAssertionsMixin


class StaticContractTest(SourceAssertionsMixin, unittest.TestCase):
  def test_required_dom_ids_exist(self):
    html = self.read_text("index.html")
    for element_id in [
      "controllerHeader",
      "headerRuntime",
      "controllerIp",
      "programmingTargetSelector",
      "targetProgrammingTrackButton",
      "targetMainTrackButton",
      "operationModeSelector",
      "modeNButton",
      "modeHoButton",
      "modeGButton",
      "modeDcButton",
      "connectionLamp",
      "headerTemperature",
      "headerVoltage",
      "headerCurrent",
      "headerPower",
      "powerOnButton",
      "powerOffButton",
      "resetControllerConfigButton",
      "connectionStatus",
      "connectionStatusText",
      "navVehicleControl",
      "navCvProgramming",
      "navControllerSettings",
      "importConfigFileInput",
      "importFormatSelect",
      "importConfigButton",
      "selectVehiclesButton",
      "addVehicleButton",
      "deleteVehiclesButton",
      "vehicleControlView",
      "vehicleRegistry",
      "vehicleEditView",
      "vehicleControlDetailView",
      "cvProgrammingView",
      "chipInfoPanel",
      "cvListPanel",
      "cvEditStackPanel",
      "addressPanel",
      "cvEditorPanel",
      "cvBitEditor",
      "controllerSettingsView",
      "controllerInfoPanel",
      "trackProfilePanel",
    ]:
      self.assertIn(f'id="{element_id}"', html)

  def test_z21_import_is_inside_vehicle_control_view_only(self):
    html = self.read_text("index.html")
    vehicle_start = html.index('id="vehicleControlView"')
    cv_start = html.index('id="cvProgrammingView"')
    toolbar_start = html.index('class="vehicle-view-toolbar"')
    import_start = html.index('class="import-strip"')
    title_start = html.index(">车辆控制<", vehicle_start)
    self.assertGreater(toolbar_start, vehicle_start)
    self.assertLess(toolbar_start, cv_start)
    self.assertGreater(import_start, vehicle_start)
    self.assertLess(import_start, cv_start)
    self.assertGreater(import_start, title_start)
    self.assertLess(import_start, html.index('id="vehicleRegistry"'))
    self.assertIn('id="vehicleCount"', html[vehicle_start:cv_start])
    self.assertIn('aria-label="车辆导入"', html[vehicle_start:cv_start])
    self.assertIn("导入配置", html[vehicle_start:cv_start])
    self.assertIn('id="importFormatSelect"', html[vehicle_start:cv_start])
    self.assertNotIn('value="z21_layout_config"', html[vehicle_start:cv_start])
    self.assertNotIn("导入 Z21", html[vehicle_start:cv_start])
    self.assertLess(html.index('id="importFormatSelect"', vehicle_start), html.index('id="importConfigButton"', vehicle_start))
    self.assertNotIn("z21FileInput", html[vehicle_start:cv_start])
    self.assertNotIn("importZ21Button", html[vehicle_start:cv_start])

  def test_vehicle_import_uses_format_selector(self):
    import_workflow_source = self.read_text("assets/js/import-workflow.js")
    api_source = self.read_text("assets/js/gateway-api.js")
    html = self.read_text("index.html")
    self.assertIn("import-format", html)
    self.assertIn("importConfig(", import_workflow_source)
    self.assertIn("export async function importConfig", api_source)
    self.assertIn("导入配置", html)
    self.assertLess(html.index("import-format"), html.index("导入配置"))

  def test_controller_header_places_status_and_lamp(self):
    html = self.read_text("index.html")
    self.assertIn('class="header-status"', html)
    self.assertIn('class="header-runtime"', html)
    self.assertIn('class="brand-line"', html)
    self.assertNotIn('class="mode-label"', html)
    self.assertLess(html.index("Digsight"), html.index("Center"))
    self.assertLess(html.index('id="connectionStatus"'), html.index('id="headerRuntime"'))
    self.assertLess(html.index('id="connectionStatus"'), html.index('id="connectionLamp"'))
    self.assertLess(html.index('id="connectionLamp"'), html.index('id="connectionStatusText"'))
    self.assertLess(html.index('id="headerRuntime"'), html.index('id="operationModeSelector"'))
    self.assertLess(html.index('id="programmingTargetSelector"'), html.index('id="operationModeSelector"'))
    self.assertLess(html.index('id="operationModeSelector"'), html.index('id="headerTemperature"'))
    self.assertLess(html.index('id="connectionLamp"'), html.index('id="headerTemperature"'))

  def test_header_has_controller_kind_selector_before_ip_input(self):
    html = self.read_text("index.html")
    app_source = self.read_text("assets/js/app.js")
    controller_workflow_source = self.read_text("assets/js/controller-workflow.js")
    self.assertIn('id="controllerKindSelect"', html)
    self.assertIn('class="controller-kind"', html)
    self.assertNotIn('value="digsight_controller"', html)
    self.assertNotIn(">动芯 DXDCNet<", html)
    self.assertLess(html.index('class="controller-kind"'), html.index('id="controllerIp"'))
    self.assertIn("controllerKindSelect", app_source)
    self.assertIn("renderControllerKindOptions", controller_workflow_source)

  def test_controller_config_reset_button_follows_power_off(self):
    html = self.read_text("index.html")
    self.assertIn('id="resetControllerConfigButton"', html)
    self.assertLess(html.index('id="powerOffButton"'), html.index('id="resetControllerConfigButton"'))
    self.assertLess(html.index('id="resetControllerConfigButton"'), html.index('id="connectionStatus"'))

  def test_static_entry_does_not_embed_adapter_options(self):
    html = self.read_text("index.html")
    state_source = self.read_text("assets/js/state-store.js")
    selector_source = self.read_text("assets/js/capability-selectors.js")
    import_workflow_source = self.read_text("assets/js/import-workflow.js")
    controller_workflow_source = self.read_text("assets/js/controller-workflow.js")
    for source in (html, state_source, selector_source, import_workflow_source, controller_workflow_source):
      self.assertNotIn("digsight_controller", source)
      self.assertNotIn("z21_layout_config", source)
      self.assertNotIn("example_controller", source)
      self.assertNotIn("example_layout_config", source)

  def test_controller_read_status_uses_summary_not_raw_warning_list(self):
    source = self.read_text("assets/js/app.js")
    self.assertIn("function controllerReadStatusMessage(result)", source)
    self.assertIn("function userVisibleWarningMessage(warning)", source)
    self.assertIn('"controller_ip_unconfigured": "控制器 IP 未配置"', source)
    self.assertIn('"programming_track_current_limit_unconfirmed": "编程轨限流未确认"', source)
    self.assertIn("userVisibleWarnings(result.warnings || [])", source)
    self.assertNotIn('warnings.join("\\n")', source)
    self.assertNotIn('warnings.join("，")', source)
    self.assertNotIn('nextWarnings.join("，")', source)
    self.assertIn('"控制器信息已读取，CV 安全状态未确认"', source)
    self.assertNotIn('`控制器信息已读取：${warnings.join("，") || "CV 安全状态未确认"}`', source)

  def test_header_styles_define_five_state_lamp(self):
    css = self.read_text("assets/css/app.css")
    for token in [
      "grid-template-areas",
      "header-status",
      "header-runtime",
      "header-metrics",
      ".status-text",
      ".brand-line",
      ".ip-field",
      ".mode-buttons",
      "justify-content: center;",
      "place-items: center;",
      "text-align: center;",
      "min-width: 112px;",
      "min-height: 44px;",
      "padding: 6px 10px;",
      "background: var(--soft);",
      "border: 1px solid var(--line);",
      "border-radius: 6px;",
      "--standby",
      "lamp-track-off",
      "lamp-track-on",
      "lamp-busy",
      "lamp-short",
      "@keyframes lampPulse",
      "animation: lampPulse",
      "font-size: 20px;",
      "font-weight: 700;",
      "button.primary",
    ]:
      self.assertIn(token, css)
    self.assertNotIn(".mode-label", css)

  def test_app_uses_module_script(self):
    html = self.read_text("index.html")
    self.assertIn('type="module"', html)
    self.assertIn('/assets/js/app.js"', html)
    self.assertNotIn("?v=", html)

  def test_module_imports_use_plain_module_paths(self):
    source = self.read_text("assets/js/app.js")
    for module_name in [
      "gateway-api.js",
      "state-store.js",
      "controller-view.js",
      "cv-view.js",
      "vehicle-cab-view.js",
      "vehicle-editor-view.js",
    ]:
      self.assertIn(f'./{module_name}"', source)
      self.assertNotIn(f'{module_name}?v=', source)
    self.assertFalse(Path("assets/js/consist-view.js").exists())

  def test_cv_tables_keep_compact_labels_readable(self):
    source = self.read_text("assets/js/cv-view.js")
    css = self.read_text("assets/css/app.css")
    self.assertIn("模块型号 (CV127/128)", source)
    self.assertNotIn("模块型号 (CV127/CV128)", source)
    self.assertIn(".cv-list-table th:nth-child(1)", css)
    self.assertIn("min-width: 96px;", css)
    self.assertIn("white-space: nowrap;", css)

  def test_vehicle_cab_uses_responsive_dimensions(self):
    css = self.read_text("assets/css/app.css")
    for token in [
      "--vehicle-thumb-inline",
      "--vehicle-thumb-block",
      "--control-image-inline",
      "--control-image-block",
      "clamp(",
      "@media (max-width: 760px)",
      ".cab-workspace",
      "grid-template-columns: 1fr;",
    ]:
      self.assertIn(token, css)

  def test_coverage_gate_is_documented_and_scripted(self):
    script = self.read_text("scripts/check_coverage.py")
    coverage_config = self.read_text(".coveragerc")
    self.assertIn("FUNCTION_COVERAGE_MINIMUM = 100.0", script)
    self.assertIn("LINE_COVERAGE_MINIMUM = 90.0", script)
    self.assertIn("BRANCH_COVERAGE_MINIMUM = 80.0", script)
    self.assertIn("branch = True", coverage_config)


if __name__ == "__main__":
  unittest.main()
