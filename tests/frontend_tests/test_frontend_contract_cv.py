import unittest

from tests.frontend_tests.source_assertions import SourceAssertionsMixin


TOKEN_PROMPT_TEXT = "请输入操作" + "授权令牌"


class FrontendCvContractTest(SourceAssertionsMixin, unittest.TestCase):
  def test_chip_info_uses_two_column_table(self):
    source = self.read_text("assets/js/cv-view.js")
    css = self.read_text("assets/css/app.css")
    self.assertIn('title.textContent = "芯片信息";', source)
    self.assertIn('read.textContent = "读取芯片信息";', source)
    self.assertIn('reset.textContent = "重置芯片";', source)
    self.assertIn("reset.className = \"danger\";", source)
    self.assertIn("onResetDecoder", source)
    self.assertNotIn('title.textContent = "芯片信息读取";', source)
    self.assertIn('document.createElement("table")', source)
    self.assertIn('table.className = "chip-info-table";', source)
    self.assertIn("profile_map", source)
    self.assertIn("vendor_profiles", source)
    self.assertIn("manufacturer_name", source)
    self.assertNotIn('"生产厂家 / CV8"', source)
    self.assertIn('["生产厂家 (CV8)", summary.manufacturer]', source)
    self.assertIn('["模块型号 (CV127/128)", summary.model]', source)
    self.assertIn('["硬件版本 (CV127)", summary.hardware]', source)
    self.assertIn('["软件版本 (CV7)", summary.software]', source)
    self.assertNotIn('"Digsight 模块/硬件高字节"', source)
    self.assertNotIn('"Digsight 模块型号低字节"', source)
    self.assertNotIn('"扩展厂商 ID 高位"', source)
    self.assertNotIn('"扩展厂商 ID 低位"', source)
    self.assertIn(".chip-info-table th,", css)
    self.assertIn(".chip-info-table td", css)

  def test_chip_info_reset_uses_configured_reset_method_after_confirmation(self):
    source = self.read_text("assets/js/cv-runtime-actions.js")
    cv_controller_source = self.read_text("assets/js/cv-controller.js")
    self.assertIn("const resetCommand = `CV${resetMethod.cv}=${resetMethod.value}`;", source)
    self.assertIn("恢复出厂设置", cv_controller_source)
    self.assertIn("厂商 CV 表选择复位方法", source)
    self.assertIn("地址通常会变为 ${resetMethod.defaultAddress || 3}", source)
    self.assertIn('typeof globalScope.confirm === "function" ? globalScope.confirm(message) : false', source)
    self.assertIn('const targetPayload = cvProgrammingRequest("芯片重置");', source)
    self.assertIn('const actionResult = await runPreparedCvAction(', source)
    self.assertIn('"芯片重置",', source)
    self.assertIn('(targetPayload) => writeCv(resetMethod.cv, resetMethod.value, true, targetPayload)', source)

  def test_cv_programming_layout_uses_list_and_editor_stack(self):
    html = self.read_text("index.html")
    source = self.read_text("assets/js/cv-view.js")
    css = self.read_text("assets/css/app.css")
    self.assertIn('id="cvListPanel"', html)
    self.assertIn('id="cvEditStackPanel"', html)
    self.assertIn('class="three-panel cv-programming-layout"', html)
    self.assertLess(html.index('id="chipInfoPanel"'), html.index('id="cvListPanel"'))
    self.assertLess(html.index('id="cvListPanel"'), html.index('id="cvEditStackPanel"'))
    self.assertLess(html.index('id="addressPanel"'), html.index('id="cvEditorPanel"'))
    self.assertIn("renderCvListPanel(elements.cvListPanel, metadata, cvState, handlers);", source)
    self.assertIn('title.textContent = "车辆地址编辑";', source)
    self.assertIn('title.textContent = "CV 地址编辑";', source)
    self.assertIn('title.textContent = "CV值列表";', source)
    self.assertNotIn('title.textContent = "地址设置";', source)
    self.assertNotIn('title.textContent = "CV 编程";', source)
    self.assertIn(".cv-programming-layout", css)
    self.assertIn(".panel-stack", css)

  def test_cv_list_reads_values_incrementally_and_exports(self):
    source = self.read_text("assets/js/cv-view.js")
    app_source = self.read_text("assets/js/app.js")
    runtime_source = self.read_text("assets/js/cv-runtime-actions.js")
    cv_controller_source = self.read_text("assets/js/cv-controller.js")
    cv_export_source = self.read_text("assets/js/cv-export.js")
    combined_app_source = app_source + runtime_source
    read_list_source = runtime_source[
      runtime_source.index("async function readCvListWithMode"):
      runtime_source.index("function downloadTextFile")
    ]
    self.assertIn('readKnown.textContent = "读取已知CV";', source)
    self.assertIn('readFull.textContent = "完整扫描1-1024";', source)
    self.assertIn('cancelRead.textContent = "中止读取";', source)
    self.assertIn('markdown.textContent = "导出 Markdown";', source)
    self.assertIn('csv.textContent = "导出 CSV";', source)
    self.assertIn('table.className = "cv-list-table";', source)
    self.assertIn("row.error_detail", source)
    self.assertIn('detailLink.className = "cv-error-detail-link";', source)
    self.assertIn('detailLink.textContent = "详情";', source)
    self.assertIn('valueCell.append(document.createTextNode(row.error || "读取失败"), " ", detailLink);', source)
    self.assertIn('handlers.onShowCvErrorDetail?.(row.error || "读取失败", row.error_detail);', source)
    self.assertIn("onReadKnownCv", source)
    self.assertIn("onReadFullCv", source)
    self.assertIn("onCancelCvRead", source)
    self.assertIn("onShowCvErrorDetail", source)
    self.assertIn("onExportCvMarkdown", source)
    self.assertIn("onExportCvCsv", source)
    self.assertIn("export function createCvDomainModel", cv_controller_source)
    self.assertIn("const cvNumbers = cvDomain.cvNumbersForReadMode(readMode, manufacturerId);", read_list_source)
    self.assertIn("runCvListRead({", read_list_source)
    self.assertIn("readCv(cvNumber, targetPayload)", read_list_source)
    self.assertIn("cvState.cvList.rows.push(row);", cv_controller_source)
    self.assertIn("cvState.cvList.read_count = cvState.cvList.rows.length;", cv_controller_source)
    self.assertIn("cvState.cvList.ok_count = cvState.cvList.rows.filter((item) => item.ok).length;", cv_controller_source)
    self.assertIn("total_count: cvNumbers.length", cv_controller_source)
    self.assertIn("cvState.cvList.total_count = cvNumbers.length;", cv_controller_source)
    self.assertIn("const progressText = listUpdate.progressText;", read_list_source)
    self.assertIn("setStatus(`${operationName}进行中：${progressText}`);", read_list_source)
    self.assertIn("`CV 读取已中止：${cvDomain.cvListProgressText()}`", runtime_source)
    self.assertIn("`${operationName}完成：${cvDomain.cvListProgressText()}，${manufacturer}`", runtime_source)
    self.assertIn("renderAll();", read_list_source)
    self.assertNotIn("readAllCvValues({", read_list_source)
    for token in [
      "cvState.cvListReading",
      "cvState.cvReadSessionId",
      "cancelCurrentCvRead",
      "onShowCvErrorDetail: showDetailDialog",
    ]:
      self.assertIn(token, combined_app_source)
    self.assertIn("downloadTextFile", combined_app_source)
    self.assertIn("export function buildCvMarkdown(cvList)", cv_export_source)
    self.assertIn("export function buildCvCsv(cvList)", cv_export_source)
    self.assertIn("const totalCount = cvState.cvList?.total_count || cvState.cvList?.read_count || 0;", source)
    self.assertIn("`生产厂家：${manufacturer}，已读取 ${cvState.cvList.read_count || 0}/${totalCount}`", source)

  def test_chip_info_read_uses_cached_controller_safety(self):
    app_source = self.read_text("assets/js/app.js")
    source = self.read_text("assets/js/cv-runtime-actions.js")
    chip_info_source = source[
      source.index("async function readChipInfo()"):
      source.index("async function resetDecoder()")
    ]
    safety_source = source[
      source.index("async function refreshCvSafety(operationName"):
      source.index("async function readChipInfo()")
    ]
    initialize_source = self.read_text("assets/js/app-bootstrap.js")
    self.assertIn('const actionResult = await runTargetedCvAction("芯片信息读取"', chip_info_source)
    self.assertIn("readChipInfoFromController(targetPayload)", chip_info_source)
    self.assertIn("if (!actionResult.completed) {", chip_info_source)
    self.assertNotIn("readControllerInfo()", chip_info_source)
    self.assertIn("appState.controllerInfo?.safe_for_cv", safety_source)
    self.assertIn("const target = normalizeProgrammingTarget(programmingTarget);", safety_source)
    self.assertIn('if (target === "main_track")', safety_source)
    self.assertIn("appState.controllerInfo?.cv_safety_warnings", safety_source)
    self.assertIn("const result = await readControllerInfo();", safety_source)
    self.assertIn("控制器安全状态未确认，正在重新读取控制器信息", safety_source)
    self.assertIn("return Boolean(result.safe_for_cv);", safety_source)
    self.assertIn("const result = await readControllerInfo();", initialize_source)
    self.assertIn("readChipInfoFromController,", app_source)

  def test_cv_operations_retry_once_after_safety_status_errors(self):
    source = self.read_text("assets/js/cv-runtime-actions.js")
    retry_source = source[
      source.index("async function runCvRequestWithSafetyRetry"):
      source.index("function isRetryableCvSafetyError")
    ]
    classifier_source = source[
      source.index("function isRetryableCvSafetyError"):
      source.index("async function readChipInfo()")
    ]
    self.assertIn("try {", retry_source)
    self.assertIn("return await requestFn();", retry_source)
    self.assertIn("refreshCvSafety(operationName, programmingTarget, {force: true})", retry_source)
    self.assertIn("return await requestFn();", retry_source)
    for warning in [
      "programming_track_status_unconfirmed",
      "programming_track_status_stale",
      "booster_status_unconfirmed",
    ]:
      self.assertIn(warning, classifier_source)
    for token in [
      "async function runPreparedCvAction",
      "async function runTargetedCvAction",
      "runTargetedCvAction(\n            \"地址读取\"",
      "runPreparedCvAction(\n            \"地址写入\"",
      "runTargetedCvAction(\n            \"CV 读取\"",
      "runPreparedCvAction(\n            \"CV 写入\"",
    ]:
      self.assertIn(token, source)

  def test_cv_and_address_writes_fail_closed_without_confirm_dialog(self):
    source = self.read_text("assets/js/cv-runtime-actions.js")
    self.assertIn(
      'typeof globalScope.confirm === "function" ? globalScope.confirm(`确认写入车辆地址 ${address}？`) : false',
      source,
    )
    self.assertIn(
      'typeof globalScope.confirm === "function" ? globalScope.confirm(`确认写入 CV${cvNumber}=${value}？`) : false',
      source,
    )
    self.assertNotIn(
      'typeof globalScope.confirm === "function" ? globalScope.confirm(`确认写入车辆地址 ${address}？`) : true',
      source,
    )
    self.assertNotIn(
      'typeof globalScope.confirm === "function" ? globalScope.confirm(`确认写入 CV${cvNumber}=${value}？`) : true',
      source,
    )

  def test_main_track_cv_operations_use_page_vehicle_selector(self):
    html = self.read_text("index.html")
    view_source = self.read_text("assets/js/cv-view.js")
    app_source = self.read_text("assets/js/app.js")
    css = self.read_text("assets/css/app.css")
    request_source = app_source[
      app_source.index("function cvProgrammingRequest"):
      app_source.index("function isDigitalOperationMode")
    ]
    self.assertIn('id="cvTargetPanel"', html)
    self.assertIn("renderCvTargetPanel(elements.cvTargetPanel, cvState, handlers);", view_source)
    self.assertIn('title.textContent = "CV 操作目标";', view_source)
    self.assertIn('labelText.textContent = "主轨操作车号";', view_source)
    self.assertIn('select.disabled = programmingTarget !== "main_track" || !vehicles.length;', view_source)
    self.assertIn('option.textContent = "编程轨不使用车号";', view_source)
    self.assertIn("handlers.onCvProgrammingVehicleChange?.(select.value);", view_source)
    self.assertIn("programmingVehicleId: \"\"", app_source)
    self.assertIn("function syncCvProgrammingVehicle(visibleVehicles)", app_source)
    self.assertIn("function selectedCvProgrammingVehicle()", app_source)
    self.assertIn("const vehicle = selectedCvProgrammingVehicle();", request_source)
    self.assertNotIn("const vehicle = selectedVehicle();", request_source)
    self.assertIn("payload.vehicle_id = vehicle.id;", request_source)
    runtime_source = self.read_text("assets/js/cv-runtime-actions.js")
    self.assertIn("readAddress(targetPayload.vehicle_id, targetPayload)", runtime_source)
    self.assertIn("writeAddress(targetPayload.vehicle_id, address, true, targetPayload)", runtime_source)
    self.assertIn(".cv-target-panel", css)

  def test_address_panel_allows_programming_track_address_without_selected_vehicle(self):
    source = self.read_text("assets/js/cv-view.js")
    runtime_source = self.read_text("assets/js/cv-runtime-actions.js")
    css = self.read_text("assets/css/app.css")
    address_panel_source = source[
      source.index("function renderAddressPanel"):
      source.index("function renderCvEditorPanel")
    ]
    self.assertIn("renderAddressPanel(elements.addressPanel, selectedVehicle, metadata, cvState, handlers);", source)
    self.assertIn("const currentAddress = cvState.address ?? selectedVehicle?.address ?? 3;", address_panel_source)
    self.assertIn('actions.className = "control-row address-actions";', address_panel_source)
    self.assertNotIn("read.disabled = !selectedVehicle;", address_panel_source)
    self.assertNotIn("write.disabled = !selectedVehicle;", address_panel_source)
    self.assertIn("cvState.address = result.address;", runtime_source)
    self.assertIn('runTargetedCvAction(\n            "地址读取"', runtime_source)
    self.assertIn('const targetPayload = cvProgrammingRequest("地址写入");', runtime_source)
    self.assertIn('runPreparedCvAction(\n            "地址写入"', runtime_source)
    self.assertIn("readAddress(targetPayload.vehicle_id, targetPayload)", runtime_source)
    self.assertIn("writeAddress(targetPayload.vehicle_id, address, true, targetPayload)", runtime_source)
    self.assertIn(".address-actions", css)
    self.assertIn("margin-top: 12px;", css)

  def test_cv_editor_allows_programming_track_cv_without_selected_vehicle(self):
    source = self.read_text("assets/js/cv-view.js")
    runtime_source = self.read_text("assets/js/cv-runtime-actions.js")
    css = self.read_text("assets/css/app.css")
    cv_editor_source = source[source.index("function renderCvEditorPanel"):]
    self.assertNotIn("read.disabled = !selectedVehicle;", cv_editor_source)
    self.assertNotIn("write.disabled = !selectedVehicle;", cv_editor_source)
    self.assertIn('runTargetedCvAction(\n            "CV 读取"', runtime_source)
    self.assertIn('const targetPayload = cvProgrammingRequest("CV 写入");', runtime_source)
    self.assertIn('runPreparedCvAction(\n            "CV 写入"', runtime_source)
    self.assertIn("(targetPayload) => readCv(cvNumber, targetPayload)", runtime_source)
    self.assertIn("(targetPayload) => writeCv(cvNumber, value, true, targetPayload)", runtime_source)
    self.assertIn("grid-template-columns: repeat(8, minmax(54px, 1fr));", css)
    self.assertIn("overflow-x: auto;", css)


if __name__ == "__main__":
  unittest.main()
