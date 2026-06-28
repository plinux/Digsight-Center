import unittest
from pathlib import Path


class StaticContractTest(unittest.TestCase):
  def test_required_dom_ids_exist(self):
    html = Path("index.html").read_text(encoding="utf-8")
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
    html = Path("index.html").read_text(encoding="utf-8")
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
    import_action_source = Path("assets/js/import-actions.js").read_text(encoding="utf-8")
    api_source = Path("assets/js/gateway-api.js").read_text(encoding="utf-8")
    html = Path("index.html").read_text(encoding="utf-8")
    self.assertIn("import-format", html)
    self.assertIn("importConfig(", import_action_source)
    self.assertIn("export async function importConfig", api_source)
    self.assertIn("导入配置", html)
    self.assertLess(html.index("import-format"), html.index("导入配置"))

  def test_controller_header_places_status_and_lamp(self):
    html = Path("index.html").read_text(encoding="utf-8")
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
    html = Path("index.html").read_text(encoding="utf-8")
    app_source = Path("assets/js/app.js").read_text(encoding="utf-8")
    self.assertIn('id="controllerKindSelect"', html)
    self.assertIn('class="controller-kind"', html)
    self.assertNotIn('value="digsight_controller"', html)
    self.assertNotIn(">动芯 DXDCNet<", html)
    self.assertLess(html.index('class="controller-kind"'), html.index('id="controllerIp"'))
    self.assertIn("controllerKindSelect", app_source)
    self.assertIn("renderControllerKindOptions", app_source)

  def test_static_entry_does_not_embed_adapter_options(self):
    html = Path("index.html").read_text(encoding="utf-8")
    state_source = Path("assets/js/state-store.js").read_text(encoding="utf-8")
    selector_source = Path("assets/js/capability-selectors.js").read_text(encoding="utf-8")
    import_action_source = Path("assets/js/import-actions.js").read_text(encoding="utf-8")
    for source in (html, state_source, selector_source, import_action_source):
      self.assertNotIn("digsight_controller", source)
      self.assertNotIn("z21_layout_config", source)
      self.assertNotIn("example_controller", source)
      self.assertNotIn("example_layout_config", source)

  def test_controller_read_status_uses_summary_not_raw_warning_list(self):
    source = Path("assets/js/app.js").read_text(encoding="utf-8")
    self.assertIn("function controllerReadStatusMessage(result)", source)
    self.assertIn("function userVisibleWarningMessage(warning)", source)
    self.assertIn('"programming_track_current_limit_unconfirmed": "编程轨限流未确认"', source)
    self.assertIn("userVisibleWarnings(result.warnings || [])", source)
    self.assertNotIn('warnings.join("\\n")', source)
    self.assertNotIn('warnings.join("，")', source)
    self.assertNotIn('nextWarnings.join("，")', source)
    self.assertIn('"控制器信息已读取，CV 安全状态未确认"', source)
    self.assertNotIn('`控制器信息已读取：${warnings.join("，") || "CV 安全状态未确认"}`', source)

  def test_header_styles_define_five_state_lamp(self):
    css = Path("assets/css/app.css").read_text(encoding="utf-8")
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
    html = Path("index.html").read_text(encoding="utf-8")
    self.assertIn('type="module"', html)
    self.assertIn('/assets/js/app.js"', html)
    self.assertNotIn("?v=", html)

  def test_module_imports_use_plain_module_paths(self):
    source = Path("assets/js/app.js").read_text(encoding="utf-8")
    for module_name in [
      "gateway-api.js",
      "state-store.js",
      "controller-view.js",
      "cv-view.js",
      "vehicle-view.js",
    ]:
      self.assertIn(f'./{module_name}"', source)
      self.assertNotIn(f'{module_name}?v=', source)
    self.assertFalse(Path("assets/js/consist-view.js").exists())

  def test_cv_tables_keep_compact_labels_readable(self):
    source = Path("assets/js/cv-view.js").read_text(encoding="utf-8")
    css = Path("assets/css/app.css").read_text(encoding="utf-8")
    self.assertIn("模块型号 (CV127/128)", source)
    self.assertNotIn("模块型号 (CV127/CV128)", source)
    self.assertIn(".cv-list-table th:nth-child(1)", css)
    self.assertIn("min-width: 96px;", css)
    self.assertIn("white-space: nowrap;", css)

  def test_vehicle_cab_uses_responsive_dimensions(self):
    css = Path("assets/css/app.css").read_text(encoding="utf-8")
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
    script = Path("scripts/check_coverage.py").read_text(encoding="utf-8")
    coverage_config = Path(".coveragerc").read_text(encoding="utf-8")
    self.assertIn("FUNCTION_COVERAGE_MINIMUM = 100.0", script)
    self.assertIn("LINE_COVERAGE_MINIMUM = 90.0", script)
    self.assertIn("BRANCH_COVERAGE_MINIMUM = 80.0", script)
    self.assertIn("branch = True", coverage_config)


if __name__ == "__main__":
  unittest.main()
