import {
  cancelCvRead,
  createConsist,
  createVehicle,
  deleteVehicle,
  getControllerInfo,
  getCvMetadata,
  getState,
  importConfig,
  readAllCvValues,
  readAddress,
  readChipInfo as readChipInfoFromController,
  readControllerInfo,
  readCv,
  rememberOperationTokenFromState,
  reorderVehicles,
  saveControllerSettings,
  setDcControl,
  setTrackPower,
  setLocoFunction,
  setLocoSpeed,
  uploadVehicleImage,
  updateConsist,
  updateVehicle,
  writeAddress,
  writeCv
} from "./gateway-api.js?v=20260620-cv-api";
import {appState, replaceState} from "./state-store.js?v=20260620-cv-api";
import {renderControllerHeader, renderControllerSettings} from "./controller-view.js?v=20260620-cv-api";
import {renderCvPanel} from "./cv-view.js?v=20260620-cv-api";
import {
  DEFAULT_FUNCTION_ICON_CATALOG,
  loadFunctionIconCatalog,
  renderDcControl,
  renderLocoControl,
  renderUnsupportedVehicleControl,
  renderVehicleControlWorkspace,
  renderVehicleEditor,
  renderVehicleRegistry
} from "./vehicle-view.js?v=20260620-cv-api";
import {sortedConsistMembers} from "./consist-helpers.js";

const elements = {
  controllerHeader: document.getElementById("controllerHeader"),
  controllerKindSelect: document.getElementById("controllerKindSelect"),
  controllerIp: document.getElementById("controllerIp"),
  programmingTargetSelector: document.getElementById("programmingTargetSelector"),
  programmingTargetButtons: Array.from(document.querySelectorAll("[data-programming-target]")),
  operationModeSelector: document.getElementById("operationModeSelector"),
  operationModeButtons: Array.from(document.querySelectorAll("[data-track-mode]")),
  connectionLamp: document.getElementById("connectionLamp"),
  headerTemperature: document.getElementById("headerTemperature"),
  headerVoltage: document.getElementById("headerVoltage"),
  headerCurrent: document.getElementById("headerCurrent"),
  headerPower: document.getElementById("headerPower"),
  powerOnButton: document.getElementById("powerOnButton"),
  powerOffButton: document.getElementById("powerOffButton"),
  connectionStatus: document.getElementById("connectionStatus"),
  statusDetailButton: document.getElementById("statusDetailButton"),
  statusDetailDialog: document.getElementById("statusDetailDialog"),
  statusDetailCloseButton: document.getElementById("statusDetailCloseButton"),
  statusDetailText: document.getElementById("statusDetailText"),
  navVehicleControl: document.getElementById("navVehicleControl"),
  navCvProgramming: document.getElementById("navCvProgramming"),
  navControllerSettings: document.getElementById("navControllerSettings"),
  z21FileInput: document.getElementById("z21FileInput"),
  importFormatSelect: document.getElementById("importFormatSelect"),
  importZ21Button: document.getElementById("importZ21Button"),
  importStrip: document.querySelector(".import-strip"),
  selectVehiclesButton: document.getElementById("selectVehiclesButton"),
  addVehicleButton: document.getElementById("addVehicleButton"),
  deleteVehiclesButton: document.getElementById("deleteVehiclesButton"),
  vehicleCount: document.getElementById("vehicleCount"),
  vehicleModeHint: document.getElementById("vehicleModeHint"),
  vehicleControlView: document.getElementById("vehicleControlView"),
  vehicleRegistry: document.getElementById("vehicleRegistry"),
  vehicleEditView: document.getElementById("vehicleEditView"),
  vehicleControlDetailView: document.getElementById("vehicleControlDetailView"),
  cvProgrammingView: document.getElementById("cvProgrammingView"),
  chipInfoPanel: document.getElementById("chipInfoPanel"),
  cvListPanel: document.getElementById("cvListPanel"),
  cvEditStackPanel: document.getElementById("cvEditStackPanel"),
  addressPanel: document.getElementById("addressPanel"),
  cvEditorPanel: document.getElementById("cvEditorPanel"),
  cvBitEditor: document.getElementById("cvBitEditor"),
  controllerSettingsView: document.getElementById("controllerSettingsView"),
  controllerInfoPanel: document.getElementById("controllerInfoPanel"),
  trackProfilePanel: document.getElementById("trackProfilePanel"),
  connectionStatusText: document.getElementById("connectionStatusText")
};

const cvState = {
  cvNumber: 1,
  value: 0,
  results: {},
  chipInfo: null,
  cvList: {
    manufacturer_id: null,
    manufacturer_name: "",
    rows: [],
    readAt: ""
  },
  cvListReading: false,
  cvReadSessionId: "",
  cvReadCancelling: false,
  address: null
};

let gatewayBusyCount = 0;
let functionIconCatalog = DEFAULT_FUNCTION_ICON_CATALOG;
const pressedFunctionKeys = new Map();
const cabFunctionTimers = new Map();
let draggedVehicleId = "";
const NEW_VEHICLE_ID = "__new_vehicle__";

function isGatewayBusy() {
  return gatewayBusyCount > 0;
}

function setGatewayBusy(active) {
  gatewayBusyCount = Math.max(0, gatewayBusyCount + (active ? 1 : -1));
  renderControllerHeader(elements, appState.controller, {busy: isGatewayBusy(), controllerInfo: appState.controllerInfo});
}

function setStatus(message, detail = "") {
  let summary = message;
  let detailText = detail;
  if (message && typeof message === "object") {
    summary = message.summary || "";
    detailText = message.detail || "";
  }
  elements.connectionStatusText.textContent = String(summary || "");
  if (elements.statusDetailButton && elements.statusDetailText) {
    elements.statusDetailText.textContent = String(detailText || "");
    elements.statusDetailButton.hidden = !detailText;
  }
}

function formatError(error) {
  if (error.payload) {
    return {
      summary: error.payload?.error?.message || error.message,
      detail: JSON.stringify(error.payload, null, 2)
    };
  }
  const detail = error.cause || "";
  return detail ? {summary: error.message, detail: String(detail)} : error.message;
}

function formatErrorSummary(error) {
  const formatted = formatError(error);
  return typeof formatted === "object" ? formatted.summary : String(formatted);
}

const controllerWarningMessages = {
  "booster_dc_mode_reported": "控制器回报为 DC 模式",
  "booster_status_missing": "未收到轨道输出状态回包",
  "command_station_status_missing": "未收到命令站状态回包",
  "operation_mode_not_safe_for_current_decoder": "当前模式不适合当前数码芯片",
  "programming_track_current_limit_unconfirmed": "编程轨限流未确认",
  "programming_track_safety_failed": "编程轨安全校验未通过",
  "programming_track_status_stale": "编程轨状态已过期，请重新读取控制器信息",
  "programming_track_status_unconfirmed": "编程轨状态未确认",
  "udp_checksum_algorithm_unconfirmed": "DXDCNet UDP 校验方式未确认",
  "udp_port_unconfirmed": "DXDCNet UDP 端口未确认",
  "unsafe_track_mode": "当前轨道模式不支持 CV 编程",
  "version_response_missing": "未收到控制器版本信息回包"
};

function userVisibleWarningMessage(warning) {
  const text = String(warning || "");
  if (!text) {
    return "";
  }
  const separatorIndex = text.indexOf(":");
  const code = separatorIndex >= 0 ? text.slice(0, separatorIndex) : text;
  const detail = separatorIndex >= 0 ? text.slice(separatorIndex + 1) : "";
  const message = controllerWarningMessages[code] || `未识别状态：${code}`;
  return detail ? `${message}：${detail}` : message;
}

function userVisibleWarnings(warnings) {
  return (warnings || []).map(userVisibleWarningMessage).filter(Boolean);
}

function controllerReadStatusMessage(result) {
  if (result.safe_for_cv) {
    return "控制器信息已读取，CV 编程安全状态已确认";
  }
  return "控制器信息已读取，CV 安全状态未确认";
}

function controllerReadStatusDetail(result) {
  const visibleWarnings = userVisibleWarnings(result.warnings || []);
  return result.safe_for_cv || !visibleWarnings.length ? "" : visibleWarnings.join("\n");
}

function selectedVehicle() {
  return vehiclesForOperationMode(currentOperationMode()).find((vehicle) => vehicle.id === appState.selectedVehicleId) || null;
}

function editingVehicle() {
  if (appState.editingVehicleId === NEW_VEHICLE_ID) {
    return appState.editingVehicleDraft;
  }
  return vehiclesForOperationMode(currentOperationMode()).find((vehicle) => vehicle.id === appState.editingVehicleId) || null;
}

function editingFunctions(vehicle) {
  if (vehicle?.id === NEW_VEHICLE_ID) {
    return vehicle.functions || [];
  }
  return selectedFunctions(vehicle?.id);
}

function activeCab() {
  return appState.cabs[appState.activeCabId] || appState.cabs.left;
}

function cabVehicle(cabId) {
  const cab = appState.cabs[cabId] || {};
  return vehiclesForOperationMode(currentOperationMode()).find((vehicle) => vehicle.id === cab.vehicleId) || null;
}

function cabFunctionVehicle(cabId) {
  const vehicle = cabVehicle(cabId);
  const cab = appState.cabs[cabId] || {};
  if (!vehicle || Number(vehicle.type ?? 0) !== 3 || vehicle.sync_function_control) {
    return vehicle;
  }
  const consist = consistForVehicle(vehicle.id);
  const members = sortedConsistMembers(consist, appState.vehicles || []);
  const member = Number.isInteger(cab.memberIndex) ? members[cab.memberIndex] : null;
  return member?.vehicle || vehicle;
}

function vehicleSelectedByOtherCab(cabId, vehicleId) {
  return Object.entries(appState.cabs || {}).some(([otherCabId, otherCab]) => {
    return otherCabId !== cabId && String(otherCab?.vehicleId || "") === String(vehicleId || "");
  });
}

function controlledVehicle() {
  return vehiclesForOperationMode(currentOperationMode()).find((vehicle) => vehicle.id === appState.control.vehicleId) || selectedVehicle();
}

function selectedFunctions(vehicleId = appState.selectedVehicleId) {
  return appState.functions.filter((fn) => fn.vehicle_id === vehicleId);
}

function functionsByVehicle() {
  const grouped = {};
  for (const fn of appState.functions || []) {
    const vehicleId = String(fn.vehicle_id || "");
    if (!vehicleId) {
      continue;
    }
    grouped[vehicleId] ||= [];
    grouped[vehicleId].push(fn);
  }
  return grouped;
}

function consistForVehicle(vehicleId) {
  return (appState.consists || []).find((consist) => String(consist.control_vehicle_id || "") === String(vehicleId || "")) || null;
}

function vehicleEditorOptions(vehicles) {
  return {
    railwayOptions: uniqueVehicleFieldValues(vehicles, "railway"),
    decoderTypeOptions: uniqueVehicleFieldValues(vehicles, "decoder_type")
  };
}

function uniqueVehicleFieldValues(vehicles, fieldName) {
  return Array.from(new Set((vehicles || [])
    .map((vehicle) => String(vehicle?.[fieldName] || "").trim())
    .filter(Boolean)))
    .sort((left, right) => left.localeCompare(right, "zh-Hans-CN"));
}

function functionDefinition(vehicleId, functionNumber) {
  return appState.functions.find((fn) => fn.vehicle_id === vehicleId && Number(fn.function_number) === Number(functionNumber)) || {};
}

function setActiveView(view) {
  if (view === "cv" && !isDccProgrammingMode()) {
    appState.activeView = "vehicle";
    appState.vehicleSubview = "registry";
    setStatus("CV 编程只支持 N、HO 或 G 的 DCC 数码模式");
    renderAll();
    return;
  }
  appState.activeView = view;
  if (view !== "vehicle") {
    appState.vehicleSubview = "registry";
  }
  renderAll();
}

function showVehicleRegistry() {
  appState.editingVehicleId = "";
  appState.editingVehicleDraft = null;
  appState.vehicleSubview = "registry";
  renderAll();
}

function showVehicleEditor(vehicleId) {
  if (!isDigitalOperationMode()) {
    setStatus("当前模式不支持车辆资料编辑入口，请切换到 N、HO 或 G");
    showVehicleRegistry();
    return;
  }
  appState.editingVehicleId = vehicleId;
  appState.editingVehicleDraft = null;
  appState.vehicleSubview = "edit";
  renderAll();
}

function createNewVehicle() {
  if (!isDigitalOperationMode()) {
    setStatus("当前模式不支持新增数码车辆，请切换到 N、HO 或 G");
    return;
  }
  appState.editingVehicleId = NEW_VEHICLE_ID;
  appState.editingVehicleDraft = {
    id: NEW_VEHICLE_ID,
    name: "新车辆",
    full_name: "",
    address: 3,
    type: 0,
    sync_function_control: false,
    energy_type: "electric",
    car_subtype: "",
    consist_kind: "",
    brand: "",
    track_mode: currentOperationMode(),
    railway: "",
    article_number: "",
    decoder_type: "",
    description: "",
    image_path: "",
    category_ids: [],
    categories: [],
    functions: [{
      function_number: 0,
      label: "",
      icon_name: "function-generic",
      trigger_mode: "toggle",
      button_type: 0,
      duration_ms: 0,
      position: 0,
      show_function_number: true,
      is_configured: true
    }]
  };
  appState.vehicleSubview = "edit";
  renderAll();
}

function toggleVehicleSelectionMode() {
  appState.vehicleSelectionMode = !appState.vehicleSelectionMode;
  if (!appState.vehicleSelectionMode) {
    appState.selectedVehicleIds.clear();
  }
  renderAll();
}

function toggleVehicleSelection(vehicleId) {
  if (!appState.vehicleSelectionMode) {
    return;
  }
  if (appState.selectedVehicleIds.has(vehicleId)) {
    appState.selectedVehicleIds.delete(vehicleId);
  } else {
    appState.selectedVehicleIds.add(vehicleId);
  }
  renderAll();
}

async function deleteSelectedVehicles() {
  const vehicleIds = Array.from(appState.selectedVehicleIds);
  if (!appState.vehicleSelectionMode || !vehicleIds.length) {
    setStatus("请先点击“选择”并勾选要删除的车辆");
    return;
  }
  const confirmed = typeof globalThis.confirm === "function"
    ? globalThis.confirm(`确认删除 ${vehicleIds.length} 辆车辆？`)
    : false;
  if (!confirmed) {
    return;
  }
  let deletedCount = 0;
  const failures = [];
  for (const vehicleId of vehicleIds) {
    try {
      await deleteVehicle(vehicleId);
      deletedCount += 1;
    } catch (error) {
      failures.push(`${vehicleId}: ${formatErrorSummary(error)}`);
    }
  }
  appState.selectedVehicleIds.clear();
  appState.vehicleSelectionMode = false;
  setStatus(failures.length
    ? `已删除 ${deletedCount} 辆，失败 ${failures.length} 辆：${failures.join("；")}`
    : `已删除 ${deletedCount} 辆车辆`);
  await refreshState();
}

async function saveVehicleConsist(changes, controlVehicleId) {
  const members = changes.consist_members || changes.consist?.members || [];
  if (!members.length) {
    throw new Error("重联/编组至少需要一辆成员车辆");
  }
  const existingConsist = consistForVehicle(controlVehicleId);
  const payload = {
    name: changes.name || changes.consist?.name || "未命名编组",
    control_vehicle_id: controlVehicleId,
    track_mode: changes.track_mode || currentOperationMode(),
    consist_kind: changes.consist_kind || changes.consist?.consist_kind || "consist",
    members
  };
  if (existingConsist) {
    await updateConsist(existingConsist.id, payload);
    return;
  }
  await createConsist({
    ...payload
  });
}

function showLocoControl(vehicleId) {
  if (!isDigitalOperationMode()) {
    setStatus("数码车辆控制只支持 N、HO 或 G 模式");
    showVehicleRegistry();
    return;
  }
  appState.selectedVehicleId = vehicleId;
  appState.control.vehicleId = vehicleId;
  appState.vehicleSubview = "control";
  renderAll();
}

function activateCab(cabId, options = {}) {
  if (!appState.cabs[cabId]) {
    return;
  }
  appState.activeCabId = cabId;
  appState.selectedVehicleId = appState.cabs[cabId].vehicleId || "";
  syncLegacyControlFromCab(cabId);
  if (options.render === false) {
    return;
  }
  renderAll();
}

function selectCabVehicle(cabId, vehicleId) {
  if (!appState.cabs[cabId]) {
    return;
  }
  if (vehicleSelectedByOtherCab(cabId, vehicleId)) {
    setStatus("该车辆已在另一侧控制区中选择");
    return;
  }
  appState.activeCabId = cabId;
  appState.cabs[cabId].vehicleId = vehicleId;
  appState.cabs[cabId].memberIndex = null;
  appState.selectedVehicleId = vehicleId;
  syncLegacyControlFromCab(cabId);
  renderAll();
}

function switchCabConsistMember(cabId, step) {
  const vehicle = cabVehicle(cabId);
  const cab = appState.cabs[cabId];
  if (!vehicle || !cab || Number(vehicle.type ?? 0) !== 3 || vehicle.sync_function_control) {
    return;
  }
  const members = sortedConsistMembers(consistForVehicle(vehicle.id), appState.vehicles || []);
  if (!members.length) {
    cab.memberIndex = null;
    renderAll();
    return;
  }
  const positions = [null, ...members.map((_member, index) => index)];
  const currentPosition = Number.isInteger(cab.memberIndex)
    ? cab.memberIndex + 1
    : 0;
  const nextPosition = (currentPosition + step + positions.length) % positions.length;
  cab.memberIndex = positions[nextPosition];
  appState.activeCabId = cabId;
  renderAll();
}

function toggleCabExpanded(cabId) {
  const cab = appState.cabs[cabId];
  if (!cab) {
    return;
  }
  if (cab.showFunctionLabels === false) {
    cab.expanded = false;
    return;
  }
  cab.expanded = !cab.expanded;
  appState.activeCabId = cabId;
  appState.selectedVehicleId = cab.vehicleId || "";
  syncLegacyControlFromCab(cabId);
  renderAll();
}

function toggleCabFunctionNumbers(cabId) {
  const cab = appState.cabs[cabId];
  if (!cab) {
    return;
  }
  cab.showFunctionNumbers = !cab.showFunctionNumbers;
  appState.activeCabId = cabId;
  appState.selectedVehicleId = cab.vehicleId || "";
  syncLegacyControlFromCab(cabId);
  renderAll();
}

function toggleCabFunctionLabels(cabId) {
  const cab = appState.cabs[cabId];
  if (!cab) {
    return;
  }
  cab.showFunctionLabels = !cab.showFunctionLabels;
  cab.expanded = false;
  appState.activeCabId = cabId;
  appState.selectedVehicleId = cab.vehicleId || "";
  syncLegacyControlFromCab(cabId);
  renderAll();
}

function syncLegacyControlFromCab(cabId = appState.activeCabId) {
  const cab = appState.cabs[cabId] || activeCab();
  appState.control.vehicleId = cab.vehicleId || "";
  appState.control.speed = cab.speed || 0;
  appState.control.direction = cab.direction || "forward";
  appState.control.functions = cab.functions || {};
}

function vehicleTrackMode(vehicle) {
  return String(vehicle?.track_mode || "").toLowerCase();
}

function vehicleMatchesOperationMode(vehicle, mode) {
  if (mode === "dc") {
    return false;
  }
  return vehicleTrackMode(vehicle) === mode;
}

function vehiclesForOperationMode(mode = currentOperationMode()) {
  return appState.vehicles.filter((vehicle) => vehicleMatchesOperationMode(vehicle, mode));
}

function functionsForVehicles(vehicles) {
  const visibleVehicleIds = new Set(vehicles.map((vehicle) => vehicle.id));
  return appState.functions.filter((fn) => visibleVehicleIds.has(fn.vehicle_id));
}

function filterCabVehicles(vehicles, cab) {
  if (!cab?.categoryId) {
    return vehicles;
  }
  return vehicles.filter((vehicle) => (vehicle.category_ids || []).includes(cab.categoryId));
}

function sortCabVehicles(vehicles, cab) {
  const key = cab?.sortKey || "custom";
  const direction = cab?.sortDirection === "desc" ? -1 : 1;
  const value = (vehicle) => {
    if (key === "address") {
      return Number(vehicle.address || 0);
    }
    if (key === "name") {
      return vehicle.name || "";
    }
    if (key === "railway") {
      return vehicle.railway || "";
    }
    if (key === "created_at") {
      return vehicle.created_at || "";
    }
    return Number(vehicle.custom_sort_order ?? vehicle.z21_position ?? 0);
  };
  return [...vehicles].sort((left, right) => {
    const leftValue = value(left);
    const rightValue = value(right);
    const result = typeof leftValue === "number" && typeof rightValue === "number"
      ? leftValue - rightValue
      : String(leftValue).localeCompare(String(rightValue), "zh-Hans");
    if (result !== 0) {
      return result * direction;
    }
    return String(left.name || "").localeCompare(String(right.name || ""), "zh-Hans");
  });
}

function syncCabSelectionForVisibleVehicles(visibleVehicles) {
  const visibleIds = new Set(visibleVehicles.map((vehicle) => vehicle.id));
  for (const cab of Object.values(appState.cabs)) {
    if (cab.vehicleId && !visibleIds.has(cab.vehicleId)) {
      cab.vehicleId = "";
      cab.speed = 0;
      cab.functions = {};
      cab.expanded = false;
    }
  }
  if (!appState.cabs.left.vehicleId && visibleVehicles[0]) {
    appState.cabs.left.vehicleId = visibleVehicles[0].id;
  }
  if (appState.cabs.right.vehicleId && appState.cabs.right.vehicleId === appState.cabs.left.vehicleId) {
    appState.cabs.right.vehicleId = "";
    appState.cabs.right.speed = 0;
    appState.cabs.right.functions = {};
    appState.cabs.right.expanded = false;
  }
  const firstAvailableForRight = visibleVehicles.find((vehicle) => {
    return String(vehicle.id) !== String(appState.cabs.left.vehicleId || "");
  });
  if (!appState.cabs.right.vehicleId && firstAvailableForRight) {
    appState.cabs.right.vehicleId = firstAvailableForRight.id;
  }
  if (!appState.cabs[appState.activeCabId]?.vehicleId) {
    appState.activeCabId = appState.cabs.left.vehicleId ? "left" : "right";
  }
  if (!visibleVehicles.length) {
    appState.activeCabId = "left";
  }
  appState.selectedVehicleId = appState.cabs[appState.activeCabId]?.vehicleId || appState.cabs.left.vehicleId || "";
  syncLegacyControlFromCab(appState.activeCabId);
}

function updateVehicleHeader(visibleVehicles, operationMode) {
  elements.vehicleCount.textContent = `${visibleVehicles.length} 辆`;
  elements.vehicleModeHint.textContent = operationMode === "dc"
    ? "DC 模式不显示车辆"
    : `${operationModeName(operationMode)} 模式`;
}

function syncVehicleSelectionToolbar(visibleVehicles) {
  const visibleIds = new Set(visibleVehicles.map((vehicle) => vehicle.id));
  for (const vehicleId of Array.from(appState.selectedVehicleIds)) {
    if (!visibleIds.has(vehicleId)) {
      appState.selectedVehicleIds.delete(vehicleId);
    }
  }
  elements.selectVehiclesButton.disabled = !isDigitalOperationMode();
  elements.selectVehiclesButton.classList.toggle("active", appState.vehicleSelectionMode);
  elements.selectVehiclesButton.textContent = appState.vehicleSelectionMode ? "取消选择" : "选择";
  elements.deleteVehiclesButton.disabled = !appState.vehicleSelectionMode || appState.selectedVehicleIds.size === 0;
  elements.addVehicleButton.disabled = !isDigitalOperationMode();
}

function setNavState() {
  elements.navCvProgramming.disabled = !isDccProgrammingMode();
  for (const [view, button] of [
    ["vehicle", elements.navVehicleControl],
    ["cv", elements.navCvProgramming],
    ["controller", elements.navControllerSettings]
  ]) {
    button.classList.toggle("active", appState.activeView === view);
  }
  elements.vehicleControlView.hidden = appState.activeView !== "vehicle";
  elements.cvProgrammingView.hidden = appState.activeView !== "cv";
  elements.controllerSettingsView.hidden = appState.activeView !== "controller";
}

function setVehicleSubviewState() {
  const registry = appState.vehicleSubview === "registry";
  elements.vehicleRegistry.hidden = !registry;
  elements.vehicleEditView.hidden = appState.vehicleSubview !== "edit";
  elements.vehicleControlDetailView.hidden = appState.vehicleSubview !== "control";
}

function normalizeTrackMode(trackMode) {
  return String(trackMode || "n").toLowerCase();
}

function operationModeName(trackMode) {
  const normalizedTrackMode = normalizeTrackMode(trackMode);
  return {
    n: "N",
    ho: "HO",
    g: "G",
    dc: "DC"
  }[normalizedTrackMode] || normalizedTrackMode.toUpperCase();
}

function currentOperationMode() {
  return normalizeTrackMode(appState.controller.track_mode);
}

function normalizeProgrammingTarget(target) {
  return String(target || "programming_track").toLowerCase();
}

function currentProgrammingTarget() {
  return normalizeProgrammingTarget(appState.controller.programming_target);
}

function cvProgrammingRequest(operationName) {
  const programmingTarget = currentProgrammingTarget();
  const payload = {programming_target: programmingTarget};
  if (programmingTarget === "main_track") {
    const vehicle = selectedVehicle();
    if (!vehicle?.id) {
      setStatus(`${operationName}选择主轨时需要先在车辆控制列表选择车辆`);
      return null;
    }
    payload.vehicle_id = vehicle.id;
  }
  return payload;
}

function isDigitalOperationMode(trackMode = currentOperationMode()) {
  return trackMode === "n" || trackMode === "ho" || trackMode === "g";
}

function isDccProgrammingMode(trackMode = currentOperationMode()) {
  return isDigitalOperationMode(trackMode) && !isDcOperationMode(trackMode);
}

function isDcOperationMode(trackMode = currentOperationMode()) {
  return trackMode === "dc";
}

function currentTrackProfile(trackMode = currentOperationMode()) {
  const stateProfiles = appState.controller.track_profiles || {};
  const infoProfiles = appState.controllerInfo.track_profiles || {};
  return stateProfiles[trackMode] || infoProfiles[trackMode] || {};
}

async function syncControllerEndpoint() {
  const kind = elements.controllerKindSelect.value || "digsight_controller";
  const ip = elements.controllerIp.value.trim();
  if (!ip) {
    throw new Error("控制器 IP 不能为空");
  }
  if (kind === appState.controller.kind && ip === appState.controller.ip && Number(appState.controller.udp_port || 0) > 0) {
    return;
  }
  const result = await saveControllerSettings({kind, ip});
  appState.controller.kind = result.kind || kind;
  appState.controller.ip = result.ip || ip;
  appState.controller.udp_port = result.udp_port || appState.controller.udp_port;
  appState.controller.local_udp_port = result.local_udp_port || appState.controller.local_udp_port;
  appState.controller.udp_checksum_algorithm = result.udp_checksum_algorithm || appState.controller.udp_checksum_algorithm;
}

async function setOperationMode(trackMode) {
  if (!trackMode || normalizeTrackMode(trackMode) === currentOperationMode()) {
    return;
  }
  try {
    const result = await saveControllerSettings({track_mode: trackMode});
    const nextTrackMode = normalizeTrackMode(result.track_mode || trackMode);
    const modeName = operationModeName(nextTrackMode);
    const warnings = result.warnings || [];
    const unsafe = warnings.includes("operation_mode_not_safe_for_current_decoder");
    if (!isDigitalOperationMode(nextTrackMode)) {
      appState.activeView = "vehicle";
      appState.vehicleSubview = "registry";
    }
    setStatus(unsafe ? `已设置为 ${modeName} 模式；当前测试夹具不要执行 G 比例实车 CV、速度或功能控制` : `已设置为 ${modeName} 模式`);
    await refreshState();
  } catch (error) {
    setStatus(formatError(error));
  }
}

async function setProgrammingTarget(target) {
  if (!target || normalizeProgrammingTarget(target) === currentProgrammingTarget()) {
    return;
  }
  try {
    const result = await saveControllerSettings({programming_target: target});
    appState.controller.programming_target = normalizeProgrammingTarget(result.programming_target || target);
    setStatus(appState.controller.programming_target === "main_track"
      ? "已切换到主轨编程；CV 操作需要选择车辆"
      : "已切换到编程轨编程");
    await refreshState();
  } catch (error) {
    setStatus(formatError(error));
  }
}

