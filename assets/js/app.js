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
  reorderVehicles,
  saveControllerSettings,
  setControllerTrackMode,
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
  cvTargetPanel: document.getElementById("cvTargetPanel"),
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
  address: null,
  programmingVehicleId: ""
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

function selectedCvProgrammingVehicle() {
  return vehiclesForOperationMode(currentOperationMode()).find((vehicle) => vehicle.id === cvState.programmingVehicleId) || null;
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

function syncCvProgrammingVehicle(visibleVehicles) {
  if (visibleVehicles.some((vehicle) => vehicle.id === cvState.programmingVehicleId)) {
    return;
  }
  cvState.programmingVehicleId = visibleVehicles[0]?.id || "";
  if (currentProgrammingTarget() === "main_track") {
    cvState.address = visibleVehicles[0]?.address ?? cvState.address;
  }
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
    const vehicle = selectedCvProgrammingVehicle();
    if (!vehicle?.id) {
      setStatus(`${operationName}选择主轨时需要先选择操作车号`);
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
    const result = await setControllerTrackMode(trackMode);
    const nextTrackMode = normalizeTrackMode(result.track_mode || trackMode);
    const modeName = operationModeName(nextTrackMode);
    if (!isDigitalOperationMode(nextTrackMode)) {
      appState.activeView = "vehicle";
      appState.vehicleSubview = "registry";
    }
    setStatus(`已设置为 ${modeName} 模式`);
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

function buildCabWorkspaceHandlers(operationMode, leftVehicles, rightVehicles) {
  if (isDcOperationMode(operationMode)) {
    return {
      emptyText: "DC 模式不显示车辆"
    };
  }
  return {
    emptyText: `当前 ${operationModeName(operationMode)} 模式暂无车辆，请导入对应的 Z21 配置文件`,
    onActivateCab: activateCab,
    onSelectVehicle: selectCabVehicle,
    selectionMode: appState.vehicleSelectionMode,
    selectedVehicleIds: appState.selectedVehicleIds,
    onToggleVehicleSelection: toggleVehicleSelection,
    onEdit: showVehicleEditor,
    onToggleCabExpanded: toggleCabExpanded,
    onToggleCabFunctionNumbers: toggleCabFunctionNumbers,
    onToggleCabFunctionLabels: toggleCabFunctionLabels,
    onSwitchConsistMember: switchCabConsistMember,
    cabVehicles: {left: leftVehicles, right: rightVehicles},
    vehicles: appState.vehicles || [],
    consists: appState.consists || [],
    categories: appState.categories || [],
    onCabCategoryFilter: (cabId, categoryId) => {
      const cab = appState.cabs[cabId];
      cab.categoryId = categoryId;
      renderAll();
    },
    onCabSortChange: (cabId, sortKey, sortDirection) => {
      const cab = appState.cabs[cabId];
      cab.sortKey = sortKey;
      cab.sortDirection = sortDirection;
      renderAll();
    },
    onVehicleDragStart: (_cabId, vehicleId, event) => {
      draggedVehicleId = vehicleId;
      event.dataTransfer?.setData("text/plain", vehicleId);
    },
    onVehicleDragOver: (_cabId, _vehicleId, event) => {
      event.preventDefault();
    },
    onVehicleDrop: async (cabId, vehicleId, event, orderedVehicleIds = []) => {
      event.preventDefault();
      try {
        await saveCustomVehicleOrder(cabId, vehicleId, orderedVehicleIds);
      } catch (error) {
        setStatus(formatError(error));
      } finally {
        draggedVehicleId = "";
      }
    },
    onDirection: async (cabId, direction) => {
      const cab = appState.cabs[cabId];
      cab.direction = direction;
      await sendCabSpeed(cabId, cab.speed, direction);
    },
    onSpeedPreview: (cabId, speed, direction) => {
      const cab = appState.cabs[cabId];
      if (!cab) {
        return;
      }
      appState.activeCabId = cabId;
      cab.speed = clampSpeed(speed);
      cab.direction = direction;
      syncLegacyControlFromCab(cabId);
    },
    onSpeed: async (cabId, speed, direction) => {
      const cab = appState.cabs[cabId];
      cab.speed = clampSpeed(speed);
      cab.direction = direction;
      await sendCabSpeed(cabId, cab.speed, direction);
    },
    onEmergencyStop: async (cabId) => {
      const cab = appState.cabs[cabId];
      cab.speed = 0;
      await sendCabSpeed(cabId, 0, cab.direction);
    },
    onFunction: async (cabId, functionNumber, eventType = "click") => {
      await sendCabFunctionByMode(cabId, functionNumber, eventType);
    },
    functionIconCatalog
  };
}

function buildVehicleEditorHandlers(vehicle) {
  const editorOptions = vehicleEditorOptions(appState.vehicles);
  return {
    isNew: vehicle?.id === NEW_VEHICLE_ID,
    categories: appState.categories || [],
    vehicles: appState.vehicles || [],
    consists: appState.consists || [],
    functionsByVehicle: functionsByVehicle(),
    railwayOptions: editorOptions.railwayOptions,
    decoderTypeOptions: editorOptions.decoderTypeOptions,
    functionIconCatalog,
    onBack: showVehicleRegistry,
    onSave: async (changes) => {
      try {
        const existingConsist = consistForVehicle(vehicle.id);
        let savedVehicle = null;
        if (vehicle.id === NEW_VEHICLE_ID) {
          savedVehicle = await createVehicle(changes);
          setStatus("车辆已添加");
        } else {
          savedVehicle = await updateVehicle(vehicle.id, changes);
          setStatus("车辆已保存");
        }
        if (Number(changes.type) === 3) {
          await saveVehicleConsist(changes, savedVehicle.id || vehicle.id);
          setStatus(existingConsist ? "重联/编组已保存" : "重联/编组已创建");
        }
        appState.editingVehicleId = "";
        appState.editingVehicleDraft = null;
        appState.vehicleSubview = "registry";
        await refreshState();
      } catch (error) {
        setStatus(formatError(error));
      }
    },
    onDelete: async () => {
      if (vehicle.id === NEW_VEHICLE_ID) {
        showVehicleRegistry();
        return;
      }
      const confirmed = typeof globalThis.confirm === "function"
        ? globalThis.confirm(`确认删除车辆 ${vehicle.name || vehicle.address}？`)
        : false;
      if (!confirmed) {
        return;
      }
      try {
        await deleteVehicle(vehicle.id);
        setStatus("车辆已删除");
        showVehicleRegistry();
        await refreshState();
      } catch (error) {
        setStatus(formatError(error));
      }
    },
    onImageFile: async (file) => {
      try {
        const result = await uploadVehicleImage(file);
        if (vehicle.id === NEW_VEHICLE_ID) {
          appState.editingVehicleDraft.image_path = result.image_path;
          setStatus("车辆图片已上传，保存车辆后生效");
          renderAll();
        } else {
          await updateVehicle(vehicle.id, {image_path: result.image_path});
          setStatus("车辆图片已更新");
          await refreshState();
        }
      } catch (error) {
        setStatus(formatError(error));
      }
    }
  };
}

function buildCvPanelHandlers(vehicle) {
  return {
    onCvProgrammingVehicleChange: (vehicleId) => {
      cvState.programmingVehicleId = vehicleId || "";
      const targetVehicle = selectedCvProgrammingVehicle();
      if (targetVehicle) {
        cvState.address = targetVehicle.address ?? cvState.address;
      }
      renderAll();
    },
    onReadChipInfo: readChipInfo,
    onResetDecoder: resetDecoder,
    onReadKnownCv: readKnownCvList,
    onReadFullCv: readFullCvList,
    onCancelCvRead: cancelCurrentCvRead,
    onExportCvMarkdown: () => {
      downloadTextFile(cvExportFileName("md"), buildCvMarkdown(cvState.cvList), "text/markdown;charset=utf-8");
    },
    onExportCvCsv: () => {
      downloadTextFile(cvExportFileName("csv"), buildCvCsv(cvState.cvList), "text/csv;charset=utf-8");
    },
    onReadAddress: async () => {
      try {
        const targetPayload = cvProgrammingRequest("地址读取");
        if (!targetPayload) {
          return;
        }
        const safetyReady = await refreshCvSafety("地址读取", targetPayload.programming_target);
        if (!safetyReady) {
          return;
        }
        const result = await runCvRequestWithSafetyRetry("地址读取", targetPayload.programming_target, () => readAddress(targetPayload.vehicle_id, targetPayload));
        cvState.address = result.address;
        setStatus(`地址：${result.address}`);
        await refreshState();
      } catch (error) {
        setStatus(formatError(error));
      }
    },
    onWriteAddress: async (address) => {
      try {
        const targetPayload = cvProgrammingRequest("地址写入");
        if (!targetPayload) {
          return;
        }
        const confirmed = globalThis.confirm ? globalThis.confirm(`确认写入车辆地址 ${address}？`) : true;
        if (!confirmed) {
          return;
        }
        const safetyReady = await refreshCvSafety("地址写入", targetPayload.programming_target);
        if (!safetyReady) {
          return;
        }
        const result = await runCvRequestWithSafetyRetry("地址写入", targetPayload.programming_target, () => writeAddress(targetPayload.vehicle_id, address, true, targetPayload));
        cvState.address = result.address;
        setStatus(`地址 ${result.address} 已写入`);
        await refreshState();
      } catch (error) {
        setStatus(formatError(error));
      }
    },
    onReadCv: async (cvNumber) => {
      cvState.cvNumber = cvNumber;
      try {
        const targetPayload = cvProgrammingRequest("CV 读取");
        if (!targetPayload) {
          return;
        }
        const safetyReady = await refreshCvSafety("CV 读取", targetPayload.programming_target);
        if (!safetyReady) {
          return;
        }
        const result = await runCvRequestWithSafetyRetry("CV 读取", targetPayload.programming_target, () => readCv(cvNumber, targetPayload));
        cvState.results[cvNumber] = result.value;
        cvState.value = Number(result.value);
        setStatus(`CV${cvNumber}: ${result.value}`);
        renderAll();
      } catch (error) {
        setStatus(formatError(error));
      }
    },
    onWriteCv: async (cvNumber, value) => {
      cvState.cvNumber = cvNumber;
      cvState.value = value;
      try {
        const targetPayload = cvProgrammingRequest("CV 写入");
        if (!targetPayload) {
          return;
        }
        const confirmed = globalThis.confirm ? globalThis.confirm(`确认写入 CV${cvNumber}=${value}？`) : true;
        if (!confirmed) {
          return;
        }
        const safetyReady = await refreshCvSafety("CV 写入", targetPayload.programming_target);
        if (!safetyReady) {
          return;
        }
        await runCvRequestWithSafetyRetry("CV 写入", targetPayload.programming_target, () => writeCv(cvNumber, value, true, targetPayload));
        setStatus(`CV${cvNumber} 写入完成`);
      } catch (error) {
        setStatus(formatError(error));
      }
    }
  };
}

function buildControllerSettingsHandlers() {
  return {
    onReadInfo: async () => {
      try {
        await syncControllerEndpoint();
        const result = await readControllerInfo();
        setStatus(controllerReadStatusMessage(result), controllerReadStatusDetail(result));
        await refreshState();
      } catch (error) {
        setStatus(formatError(error));
      }
    },
    onSave: async (changes) => {
      try {
        const result = await saveControllerSettings({...changes, apply_to_device: true});
        setStatus(result.applied_to_device ? "参数已保存到控制器" : "参数已保存为本地待应用配置");
        await refreshState();
      } catch (error) {
        setStatus(formatError(error));
      }
    }
  };
}

function renderAll() {
  const operationMode = currentOperationMode();
  const digitalMode = isDigitalOperationMode(operationMode);
  const isDcMode = isDcOperationMode(operationMode);
  const visibleVehicles = vehiclesForOperationMode(operationMode);
  const visibleFunctions = functionsForVehicles(visibleVehicles);
  const leftVehicles = sortCabVehicles(filterCabVehicles(visibleVehicles, appState.cabs.left), appState.cabs.left);
  const rightVehicles = sortCabVehicles(filterCabVehicles(visibleVehicles, appState.cabs.right), appState.cabs.right);
  syncCvProgrammingVehicle(visibleVehicles);
  syncCabSelectionForVisibleVehicles(visibleVehicles);
  updateVehicleHeader(visibleVehicles, operationMode);
  syncVehicleSelectionToolbar(visibleVehicles);
  if (!digitalMode && appState.activeView === "cv") {
    appState.activeView = "vehicle";
  }
  if (!digitalMode && appState.vehicleSubview !== "registry") {
    appState.vehicleSubview = "registry";
  }
  renderControllerHeader(elements, appState.controller, {busy: isGatewayBusy(), controllerInfo: appState.controllerInfo});
  setNavState();
  setVehicleSubviewState();
  elements.vehicleControlView.classList.toggle("dc-control-mode", isDcMode);
  if (elements.importStrip) {
    elements.importStrip.hidden = isDcMode;
  }

  if (isDcMode) {
    appState.vehicleSubview = "registry";
    setVehicleSubviewState();
    elements.vehicleCount.textContent = "DC";
    elements.vehicleModeHint.textContent = "电压控制";
    elements.vehicleEditView.hidden = true;
    elements.vehicleControlDetailView.hidden = true;
    renderDcControl(elements.vehicleRegistry, {
      ...appState.dcControl,
      maxVoltageV: currentTrackProfile("dc").max_voltage_v || 15.2
    }, {
      onVoltagePreview: (voltageV) => {
        appState.dcControl.voltageV = voltageV;
      },
      onVoltage: async (voltageV, direction) => {
        appState.dcControl.voltageV = voltageV;
        appState.dcControl.direction = direction;
        await sendDcControl();
      },
      onDirection: async (direction) => {
        appState.dcControl.direction = direction;
        await sendDcControl();
      },
      onEmergencyStop: async () => {
        appState.dcControl.voltageV = 0;
        await sendDcControl();
      }
    });
    renderControllerSettings(elements, appState.controllerInfo, buildControllerSettingsHandlers());
    return;
  }

  renderVehicleControlWorkspace(elements.vehicleRegistry, visibleVehicles, visibleFunctions, {
    activeCabId: appState.activeCabId,
    cabs: appState.cabs
  }, buildCabWorkspaceHandlers(operationMode, leftVehicles, rightVehicles));

  const vehicle = editingVehicle();
  renderVehicleEditor(elements.vehicleEditView, vehicle, editingFunctions(vehicle), buildVehicleEditorHandlers(vehicle));

  const controlVehicle = controlledVehicle();
  renderLocoControl(
    elements.vehicleControlDetailView,
    controlVehicle,
    selectedFunctions(controlVehicle?.id),
    appState.control,
    {
      onBack: showVehicleRegistry,
      onDirection: async (direction) => {
        appState.control.direction = direction;
        await sendLocoSpeed(appState.control.speed, direction);
      },
      onSpeed: async (speed, direction) => {
        appState.control.speed = clampSpeed(speed);
        appState.control.direction = direction;
        await sendLocoSpeed(appState.control.speed, direction);
      },
      onEmergencyStop: async () => {
        appState.control.speed = 0;
        await sendLocoSpeed(0, appState.control.direction);
      },
      onFunction: async (functionNumber, enabled) => {
        try {
          await syncControllerEndpoint();
          await setLocoFunction(controlVehicle.id, functionNumber, enabled);
          setStatus(`F${functionNumber} 已发送`);
        } catch (error) {
          setStatus(formatError(error));
        }
      },
      functionIconCatalog
    }
  );

  const cvProgrammingTargetVehicle = currentProgrammingTarget() === "main_track" ? selectedCvProgrammingVehicle() : null;
  renderCvPanel(elements, cvProgrammingTargetVehicle, appState.cvMetadata, {
    ...cvState,
    programmingTarget: currentProgrammingTarget(),
    programmingVehicles: visibleVehicles
  }, buildCvPanelHandlers(vehicle));

  renderControllerSettings(elements, appState.controllerInfo, buildControllerSettingsHandlers());
  setVehicleSubviewState();
}

async function refreshCvSafety(operationName, programmingTarget = currentProgrammingTarget(), options = {}) {
  await syncControllerEndpoint();
  const target = normalizeProgrammingTarget(programmingTarget);
  if (target === "main_track") {
    if (options.force) {
      setStatus(`主轨${operationName}状态未确认，正在重新读取控制器信息`);
      await readControllerInfo();
      await refreshState();
    }
    setStatus(`主轨${operationName}已选择车辆，正在等待后端校验 POM 协议状态`);
    return true;
  }
  const warningMessages = userVisibleWarnings(appState.controllerInfo?.cv_safety_warnings || []);
  if (!appState.controllerInfo?.safe_for_cv || options.force) {
    setStatus(`控制器安全状态未确认，正在重新读取控制器信息：${warningMessages.join("，") || "等待 0x23 状态"}`);
    const result = await readControllerInfo();
    await refreshState();
    if (!result.safe_for_cv) {
      const nextWarningMessages = userVisibleWarnings(result.warnings || []);
      setStatus(`控制器安全状态仍未确认：${nextWarningMessages.join("，") || "CV 安全状态未确认"}`);
    }
    return Boolean(result.safe_for_cv);
  }
  setStatus(`控制器安全状态已确认，正在执行${operationName}`);
  return true;
}

async function runCvRequestWithSafetyRetry(operationName, programmingTarget, requestFn) {
  try {
    return await requestFn();
  } catch (error) {
    if (!isRetryableCvSafetyError(error)) {
      throw error;
    }
    const safetyReady = await refreshCvSafety(operationName, programmingTarget, {force: true});
    if (!safetyReady && normalizeProgrammingTarget(programmingTarget) !== "main_track") {
      throw error;
    }
    return await requestFn();
  }
}

function isRetryableCvSafetyError(error) {
  const warningSet = new Set(error.payload?.debug?.warnings || []);
  return error.payload?.error?.type === "protocol_not_ready"
    && (
      warningSet.has("programming_track_status_unconfirmed")
      || warningSet.has("programming_track_status_stale")
      || warningSet.has("booster_status_unconfirmed")
      || warningSet.has("booster_status_stale")
    );
}

async function readChipInfo() {
  cvState.results = {};
  cvState.chipInfo = null;
  try {
    const targetPayload = cvProgrammingRequest("芯片信息读取");
    if (!targetPayload) {
      return;
    }
    const safetyReady = await refreshCvSafety("芯片信息读取", targetPayload.programming_target);
    if (!safetyReady) {
      return;
    }
    const chipInfo = await runCvRequestWithSafetyRetry("芯片信息读取", targetPayload.programming_target, () => readChipInfoFromController(targetPayload));
    for (const [cvNumber, result] of Object.entries(chipInfo.cvs || {})) {
      cvState.results[Number(cvNumber)] = result.value;
    }
    cvState.chipInfo = chipInfo;
    setStatus("芯片信息已读取");
  } catch (error) {
    cvState.chipInfo = null;
    setStatus(formatError(error));
  } finally {
    renderAll();
  }
}

async function resetDecoder() {
  const resetMethod = resolveDecoderResetMethod();
  const resetCommand = `CV${resetMethod.cv}=${resetMethod.value}`;
  const sourceText = resetMethod.source ? `来源：${resetMethod.source}` : "来源：通用 DCC 复位约定";
  const methodText = resetMethod.configured
    ? `已按 ${resetMethod.profileName} 厂商 CV 表选择复位方法：${resetCommand}。`
    : `未读取到可匹配的厂商 CV 表，将使用通用复位方法：${resetCommand}。`;
  const manufacturerText = resetMethod.manufacturerName
    ? `当前芯片厂商：${resetMethod.manufacturerName}${resetMethod.manufacturerId === null ? "" : ` (${resetMethod.manufacturerId})`}`
    : "当前尚未读取芯片厂商信息。";
  const message = [
    "确认重置编程轨上的当前芯片？",
    manufacturerText,
    methodText,
    sourceText,
    `地址通常会变为 ${resetMethod.defaultAddress || 3}，当前 CV、功能映射、速度曲线和声音/厂家设置可能被恢复。`,
    "少数厂家不使用通用复位值，请先确认该芯片手册。"
  ].join("\n");
  const confirmed = typeof globalThis.confirm === "function" ? globalThis.confirm(message) : false;
  if (!confirmed) {
    return;
  }
  try {
    const targetPayload = cvProgrammingRequest("芯片重置");
    if (!targetPayload) {
      return;
    }
    const safetyReady = await refreshCvSafety("芯片重置", targetPayload.programming_target);
    if (!safetyReady) {
      return;
    }
    await runCvRequestWithSafetyRetry("芯片重置", targetPayload.programming_target, () => writeCv(resetMethod.cv, resetMethod.value, true, targetPayload));
    cvState.chipInfo = null;
    cvState.results = {};
    cvState.cvList = {
      manufacturer_id: null,
      manufacturer_name: "",
      rows: [],
      readAt: ""
    };
    cvState.address = null;
    setStatus(`芯片重置命令已发送：${resetCommand}；请按芯片手册等待或重新上下电后再读取地址/芯片信息`);
    renderAll();
  } catch (error) {
    setStatus(formatError(error));
    renderAll();
  }
}

function resolveDecoderResetMethod() {
  const manufacturerId = currentDecoderManufacturerId();
  const catalog = appState.cvMetadata?.cv_catalog || {};
  const profileName = manufacturerId === null || manufacturerId === undefined
    ? null
    : catalog.profile_map?.[String(manufacturerId)];
  const profile = profileName ? catalog.vendor_profiles?.[profileName] : null;
  const configuredMethod = profile?.reset_method || null;
  const registry = appState.cvMetadata?.manufacturer_registry?.known_ids || {};
  const unassigned = appState.cvMetadata?.manufacturer_registry?.unassigned_notes || {};
  const manufacturerKey = manufacturerId === null || manufacturerId === undefined ? "" : String(manufacturerId);
  const manufacturerName = cvState.chipInfo?.manufacturer_name
    || cvState.cvList?.manufacturer_name
    || profile?.manufacturer_name
    || profile?.profile_name
    || registry[manufacturerKey]
    || unassigned[manufacturerKey]
    || null;
  if (isValidResetMethod(configuredMethod)) {
    return {
      cv: Number(configuredMethod.cv),
      value: Number(configuredMethod.value),
      label: configuredMethod.label || "恢复出厂设置",
      source: configuredMethod.source || profile?.source || "",
      defaultAddress: Number(configuredMethod.default_address || 3),
      requiresPowerCycle: Boolean(configuredMethod.requires_power_cycle),
      notes: configuredMethod.notes || [],
      configured: true,
      manufacturerId,
      manufacturerName,
      profileName
    };
  }
  return {
    cv: 8,
    value: 8,
    label: "恢复出厂设置",
    source: "",
    defaultAddress: 3,
    requiresPowerCycle: true,
    notes: [],
    configured: false,
    manufacturerId,
    manufacturerName,
    profileName
  };
}

function currentDecoderManufacturerId() {
  if (cvState.chipInfo?.manufacturer_id !== null && cvState.chipInfo?.manufacturer_id !== undefined) {
    return Number(cvState.chipInfo.manufacturer_id);
  }
  if (cvState.cvList?.manufacturer_id !== null && cvState.cvList?.manufacturer_id !== undefined) {
    return Number(cvState.cvList.manufacturer_id);
  }
  const cv8Value = Number(cvState.results?.[8]);
  return Number.isInteger(cv8Value) ? cv8Value : null;
}

function isValidResetMethod(method) {
  if (!method) {
    return false;
  }
  const cvNumber = Number(method.cv);
  const value = Number(method.value);
  return Number.isInteger(cvNumber)
    && cvNumber >= 1
    && cvNumber <= 1024
    && Number.isInteger(value)
    && value >= 0
    && value <= 255;
}

async function readKnownCvList() {
  await readCvListWithMode("known");
}

async function readFullCvList() {
  const confirmed = typeof globalThis.confirm === "function"
    ? globalThis.confirm("完整扫描会逐个读取 CV1-CV1024，耗时明显更长。确认开始完整扫描？")
    : false;
  if (!confirmed) {
    return;
  }
  await readCvListWithMode("full");
}

function newCvReadSessionId() {
  if (globalThis.crypto?.randomUUID) {
    return globalThis.crypto.randomUUID();
  }
  return `cv-read-${Date.now()}-${Math.round(Math.random() * 1000000)}`;
}

async function cancelCurrentCvRead() {
  if (!cvState.cvReadSessionId || !cvState.cvListReading) {
    return;
  }
  cvState.cvReadCancelling = true;
  setStatus("正在中止 CV 读取");
  renderAll();
  try {
    await cancelCvRead(cvState.cvReadSessionId);
  } catch (error) {
    setStatus(formatError(error));
  }
}

async function readCvListWithMode(readMode) {
  try {
    const operationName = readMode === "full" ? "完整 CV 扫描" : "已知 CV 读取";
    const targetPayload = cvProgrammingRequest(operationName);
    if (!targetPayload) {
      return;
    }
    const safetyReady = await refreshCvSafety(operationName, targetPayload.programming_target);
    if (!safetyReady) {
      return;
    }
    cvState.cvListReading = true;
    cvState.cvReadCancelling = false;
    cvState.cvReadSessionId = newCvReadSessionId();
    renderAll();
    const result = await runCvRequestWithSafetyRetry(operationName, targetPayload.programming_target, () => readAllCvValues({
      ...targetPayload,
      read_mode: readMode,
      session_id: cvState.cvReadSessionId
    }));
    cvState.cvList = {
      ...result,
      rows: result.rows || [],
      readAt: new Date().toISOString()
    };
    for (const row of cvState.cvList.rows) {
      if (row.ok) {
        cvState.results[Number(row.cv)] = Number(row.value);
      }
    }
    const manufacturer = result.manufacturer_id === null || result.manufacturer_id === undefined
      ? result.manufacturer_name
      : `${result.manufacturer_name} (${result.manufacturer_id})`;
    setStatus(result.cancelled
      ? `CV 读取已中止：${result.ok_count}/${result.read_count}`
      : `${operationName}完成：${result.ok_count}/${result.read_count}，${manufacturer}`);
  } catch (error) {
    setStatus(formatError(error));
  } finally {
    cvState.cvListReading = false;
    cvState.cvReadSessionId = "";
    cvState.cvReadCancelling = false;
    renderAll();
  }
}

function cvExportFileName(extension) {
  const manufacturer = (cvState.cvList.manufacturer_name || "decoder").replace(/[^A-Za-z0-9_-]+/g, "-");
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  return `cv-list-${manufacturer}-${stamp}.${extension}`;
}

function buildCvMarkdown(cvList) {
  const rows = cvList.rows || [];
  const manufacturer = cvList.manufacturer_id === null || cvList.manufacturer_id === undefined
    ? (cvList.manufacturer_name || "未知厂家")
    : `${cvList.manufacturer_name} (${cvList.manufacturer_id})`;
  const lines = [
    "# CV值列表",
    "",
    `- 生产厂家：${manufacturer}`,
    `- 读取时间：${cvList.readAt || ""}`,
    "",
    "| CV地址 | 含义 | 值 |",
    "| --- | --- | --- |"
  ];
  for (const row of rows) {
    lines.push(`| ${row.cv} | ${escapeMarkdownCell(row.meaning)} | ${row.ok ? row.value : `读取失败：${escapeMarkdownCell(row.error || "")}`} |`);
  }
  return `${lines.join("\n")}\n`;
}

function buildCvCsv(cvList) {
  const rows = cvList.rows || [];
  const lines = [["CV地址", "含义", "值"].map(csvEscape).join(",")];
  for (const row of rows) {
    lines.push([row.cv, row.meaning, row.ok ? row.value : `读取失败：${row.error || ""}`].map(csvEscape).join(","));
  }
  return `${lines.join("\n")}\n`;
}

function escapeMarkdownCell(value) {
  return String(value ?? "").replaceAll("|", "\\|").replace(/\r?\n/g, " ");
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (/[",\r\n]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}

function downloadTextFile(fileName, content, mimeType) {
  const blob = new Blob([content], {type: mimeType});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function sendDcControl() {
  try {
    await syncControllerEndpoint();
    await setDcControl(appState.dcControl.voltageV, appState.dcControl.direction);
    const voltage = Number(appState.dcControl.voltageV || 0).toFixed(1);
    const direction = appState.dcControl.direction === "reverse" ? "反向" : "正向";
    setStatus(`DC ${voltage} V / ${direction}`);
    await refreshState();
  } catch (error) {
    setStatus(formatError(error));
  }
}

async function sendLocoSpeed(speed, direction) {
  const vehicle = controlledVehicle();
  if (!vehicle || !isDigitalOperationMode()) {
    return;
  }
  try {
    await syncControllerEndpoint();
    await setLocoSpeed(vehicle.id, speed, direction);
    setStatus(`速度 ${speed} / ${direction === "reverse" ? "后退" : "前进"}`);
  } catch (error) {
    setStatus(formatError(error));
  } finally {
    renderAll();
  }
}

async function sendCabSpeed(cabId, speed, direction) {
  const vehicle = cabVehicle(cabId);
  const cab = appState.cabs[cabId];
  if (!vehicle || !cab || !isDigitalOperationMode()) {
    return;
  }
  appState.activeCabId = cabId;
  appState.selectedVehicleId = vehicle.id;
  syncLegacyControlFromCab(cabId);
  try {
    await syncControllerEndpoint();
    await setLocoSpeed(vehicle.id, speed, direction);
    setStatus(`${cabId === "left" ? "左控制台" : "右控制台"}：${vehicle.name} 速度 ${speed} / ${direction === "reverse" ? "后退" : "前进"}`);
  } catch (error) {
    setStatus(formatError(error));
  } finally {
    renderAll();
  }
}

async function setCabFunctionState(cabId, functionNumber, enabled) {
  const vehicle = cabVehicle(cabId);
  const targetVehicle = cabFunctionVehicle(cabId);
  const cab = appState.cabs[cabId];
  if (!vehicle || !targetVehicle || !cab || !isDigitalOperationMode()) {
    return;
  }
  appState.activeCabId = cabId;
  appState.selectedVehicleId = vehicle.id;
  const functionKey = String(functionNumber);
  const previousEnabled = Boolean(cab.functions[functionKey]);
  cab.functions[functionKey] = Boolean(enabled);
  syncLegacyControlFromCab(cabId);
  renderAll();
  try {
    await syncControllerEndpoint();
    await setLocoFunction(targetVehicle.id, functionNumber, Boolean(enabled), cab.functions);
    setStatus(`${cabId === "left" ? "左控制台" : "右控制台"}：${targetVehicle.name} F${functionNumber} ${enabled ? "开启" : "关闭"}`);
  } catch (error) {
    cab.functions[functionKey] = previousEnabled;
    syncLegacyControlFromCab(cabId);
    setStatus(formatError(error));
  } finally {
    renderAll();
  }
}

async function sendCabFunction(cabId, functionNumber) {
  const cab = appState.cabs[cabId];
  await setCabFunctionState(cabId, functionNumber, !Boolean(cab?.functions?.[String(functionNumber)]));
}

function functionTimerKey(cabId, functionNumber) {
  return `${cabId}:${functionNumber}`;
}

function clearCabFunctionTimer(cabId, functionNumber) {
  const key = functionTimerKey(cabId, functionNumber);
  const timer = cabFunctionTimers.get(key);
  if (timer) {
    globalThis.clearTimeout(timer);
    cabFunctionTimers.delete(key);
  }
}

async function sendCabFunctionByMode(cabId, functionNumber, eventType = "click") {
  const vehicle = cabVehicle(cabId);
  const targetVehicle = cabFunctionVehicle(cabId);
  const cab = appState.cabs[cabId];
  if (!vehicle || !targetVehicle || !cab || !isDigitalOperationMode()) {
    return;
  }
  const definition = functionDefinition(targetVehicle.id, functionNumber);
  const mode = definition.trigger_mode || "toggle";
  if (mode === "momentary") {
    if (eventType === "down") {
      clearCabFunctionTimer(cabId, functionNumber);
      await setCabFunctionState(cabId, functionNumber, true);
    } else if (eventType === "up") {
      await setCabFunctionState(cabId, functionNumber, false);
    }
    return;
  }
  if (eventType !== "click") {
    return;
  }
  if (mode === "timed") {
    clearCabFunctionTimer(cabId, functionNumber);
    await setCabFunctionState(cabId, functionNumber, true);
    const delay = Math.min(Math.max(Number(definition.duration_ms || 1000), 250), 60000);
    const timer = globalThis.setTimeout(() => {
      cabFunctionTimers.delete(functionTimerKey(cabId, functionNumber));
      setCabFunctionState(cabId, functionNumber, false);
    }, delay);
    cabFunctionTimers.set(functionTimerKey(cabId, functionNumber), timer);
    return;
  }
  clearCabFunctionTimer(cabId, functionNumber);
  await setCabFunctionState(cabId, functionNumber, !Boolean(cab.functions[String(functionNumber)]));
}

async function saveCustomVehicleOrder(cabId, vehicleId, orderedVehicleIds) {
  const cab = appState.cabs[cabId];
  const vehicles = sortCabVehicles(filterCabVehicles(vehiclesForOperationMode(), cab), {
    ...cab,
    sortKey: "custom",
    sortDirection: "asc"
  });
  const nextVehicleIds = Array.isArray(orderedVehicleIds) && orderedVehicleIds.length
    ? mergeVisibleCustomOrder(cab, orderedVehicleIds)
    : fallbackCustomOrder(vehicles, vehicleId);
  if (!nextVehicleIds.length) {
    return;
  }
  const result = await reorderVehicles(nextVehicleIds);
  appState.vehicles = result.vehicles || appState.vehicles;
  cab.sortKey = "custom";
  cab.sortDirection = "asc";
}

function fallbackCustomOrder(vehicles, targetVehicleId) {
  const from = vehicles.findIndex((vehicle) => vehicle.id === draggedVehicleId);
  const to = vehicles.findIndex((vehicle) => vehicle.id === targetVehicleId);
  if (from < 0 || to < 0 || from === to) {
    return [];
  }
  const nextVehicles = [...vehicles];
  const [moved] = nextVehicles.splice(from, 1);
  nextVehicles.splice(to, 0, moved);
  return nextVehicles.map((vehicle) => vehicle.id);
}

function mergeVisibleCustomOrder(cab, orderedVisibleIds) {
  const visibleSet = new Set(orderedVisibleIds);
  const orderedOperationVehicles = sortCabVehicles(vehiclesForOperationMode(), {
    ...cab,
    categoryId: "",
    sortKey: "custom",
    sortDirection: "asc"
  });
  let nextVisibleIndex = 0;
  return orderedOperationVehicles.map((vehicle) => {
    if (!visibleSet.has(vehicle.id)) {
      return vehicle.id;
    }
    const nextVisibleId = orderedVisibleIds[nextVisibleIndex];
    nextVisibleIndex += 1;
    return nextVisibleId;
  });
}

async function refreshState() {
  const [state, controllerInfo] = await Promise.all([getState(), getControllerInfo()]);
  replaceState(state);
  appState.controllerInfo = controllerInfo;
  elements.controllerKindSelect.value = appState.controller.kind || "digsight_controller";
  elements.controllerIp.value = appState.controller.ip || "0.0.0.0";
  renderAll();
}

async function runTrackPowerRequestWithStatusRetry(powered, requestFn) {
  try {
    return await requestFn();
  } catch (error) {
    if (!powered || !isRetryableTrackPowerStatusError(error)) {
      throw error;
    }
    setStatus("轨道状态未确认，正在重新读取控制器信息");
    await readControllerInfo();
    await refreshState();
    return await requestFn();
  }
}

function isRetryableTrackPowerStatusError(error) {
  const warningSet = new Set(error.payload?.debug?.warnings || []);
  return error.payload?.error?.type === "protocol_not_ready"
    && (
      warningSet.has("booster_status_unconfirmed")
      || warningSet.has("booster_status_stale")
      || warningSet.has("controller_not_confirmed")
    );
}

async function initialize() {
  functionIconCatalog = await loadFunctionIconCatalog();
  appState.cvMetadata = await getCvMetadata();
  await refreshState();
  setStatus("正在读取控制器信息");
  try {
    const result = await readControllerInfo();
    setStatus(controllerReadStatusMessage(result), controllerReadStatusDetail(result));
    await refreshState();
  } catch (error) {
    const formatted = formatError(error);
    setStatus(
      `本地后端已就绪，控制器信息启动读取失败：${typeof formatted === "object" ? formatted.summary : formatted}`,
      typeof formatted === "object" ? formatted.detail : ""
    );
  }
}

elements.navVehicleControl.addEventListener("click", () => setActiveView("vehicle"));
elements.navCvProgramming.addEventListener("click", () => setActiveView("cv"));
elements.navControllerSettings.addEventListener("click", () => setActiveView("controller"));
for (const button of elements.operationModeButtons) {
  button.addEventListener("click", () => setOperationMode(button.dataset.trackMode));
}
for (const button of elements.programmingTargetButtons) {
  button.addEventListener("click", () => setProgrammingTarget(button.dataset.programmingTarget));
}

globalThis.addEventListener?.("digsight:gateway-busy", (event) => {
  setGatewayBusy(Boolean(event.detail?.active));
});

elements.statusDetailButton?.addEventListener("click", () => {
  if (typeof elements.statusDetailDialog?.showModal === "function") {
    elements.statusDetailDialog.showModal();
  }
});

elements.statusDetailCloseButton?.addEventListener("click", () => {
  elements.statusDetailDialog?.close();
});

elements.powerOnButton.addEventListener("click", async () => {
  try {
    await syncControllerEndpoint();
    const result = await runTrackPowerRequestWithStatusRetry(true, () => setTrackPower(true));
    setStatus(`${operationModeName(result.track_mode)} 轨道已通电`);
    await refreshState();
  } catch (error) {
    setStatus(formatError(error));
  }
});

elements.powerOffButton.addEventListener("click", async () => {
  try {
    await syncControllerEndpoint();
    const result = await setTrackPower(false);
    setStatus(`${operationModeName(result.track_mode)} 轨道已断电`);
    await refreshState();
  } catch (error) {
    setStatus(formatError(error));
  }
});

elements.importZ21Button.addEventListener("click", async () => {
  const file = elements.z21FileInput.files[0];
  if (!file) {
    setStatus("请选择配置文件");
    return;
  }
  try {
    const importFormat = elements.importFormatSelect.value || "z21_layout_config";
    const importResult = await importConfig(importFormat, file);
    const summary = importResult.summary || importResult;
    setStatus(`导入完成：${summary.vehicles_imported} 辆车，${summary.functions_imported} 个功能键，${summary.categories_imported || 0} 个分类`);
    await refreshState();
  } catch (error) {
    setStatus(formatError(error));
  }
});
elements.selectVehiclesButton.addEventListener("click", toggleVehicleSelectionMode);
elements.addVehicleButton.addEventListener("click", createNewVehicle);
elements.deleteVehiclesButton.addEventListener("click", deleteSelectedVehicles);

document.addEventListener("keydown", handleVehicleKeyboard);
document.addEventListener("keyup", handleVehicleKeyboardRelease);

const digitShortcutMap = {
  Digit0: 0,
  Digit1: 1,
  Digit2: 2,
  Digit3: 3,
  Digit4: 4,
  Digit5: 5,
  Digit6: 6,
  Digit7: 7,
  Digit8: 8,
  Digit9: 9,
  Numpad0: 0,
  Numpad1: 1,
  Numpad2: 2,
  Numpad3: 3,
  Numpad4: 4,
  Numpad5: 5,
  Numpad6: 6,
  Numpad7: 7,
  Numpad8: 8,
  Numpad9: 9,
};

async function handleVehicleKeyboard(event) {
  if (appState.activeView !== "vehicle" || !isDigitalOperationMode() || isEditableKeyboardTarget(event.target)) {
    return;
  }
  const cab = activeCab();
  if (!cab?.vehicleId) {
    return;
  }
  if (["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", " "].includes(event.key) || digitShortcut(event) !== null) {
    event.preventDefault();
  }
  if (event.key === "ArrowUp") {
    cab.speed = clampSpeed(cab.speed + 5);
    await sendCabSpeed(appState.activeCabId, cab.speed, cab.direction);
  } else if (event.key === "ArrowDown") {
    cab.speed = clampSpeed(cab.speed - 5);
    await sendCabSpeed(appState.activeCabId, cab.speed, cab.direction);
  } else if (event.key === "ArrowLeft") {
    cab.direction = "reverse";
    await sendCabSpeed(appState.activeCabId, cab.speed, "reverse");
  } else if (event.key === "ArrowRight") {
    cab.direction = "forward";
    await sendCabSpeed(appState.activeCabId, cab.speed, "forward");
  } else if (event.key === " ") {
    cab.speed = 0;
    await sendCabSpeed(appState.activeCabId, 0, cab.direction);
  } else {
    const digit = digitShortcut(event);
    if (digit !== null) {
      if (pressedFunctionKeys.has(event.code)) {
        return;
      }
      const cabId = appState.activeCabId;
      pressedFunctionKeys.set(event.code, {cabId, digit});
      if (isMomentaryCabFunction(cabId, digit)) {
        await sendCabFunctionByMode(appState.activeCabId, digit, "down");
      } else {
        await sendCabFunctionByMode(cabId, digit, "click");
      }
    }
  }
}

async function handleVehicleKeyboardRelease(event) {
  if (appState.activeView !== "vehicle" || !isDigitalOperationMode() || isEditableKeyboardTarget(event.target)) {
    return;
  }
  const digit = digitShortcut(event);
  const pressed = digit === null ? null : pressedFunctionKeys.get(event.code);
  if (!pressed) {
    return;
  }
  event.preventDefault();
  const cabId = pressed.cabId;
  pressedFunctionKeys.delete(event.code);
  await sendCabFunctionByMode(cabId, digit, "up");
}

function isMomentaryCabFunction(cabId, functionNumber) {
  const vehicle = cabVehicle(cabId);
  return functionDefinition(vehicle?.id, functionNumber).trigger_mode === "momentary";
}

function isEditableKeyboardTarget(target) {
  const tagName = String(target?.tagName || "").toLowerCase();
  return tagName === "input" || tagName === "textarea" || tagName === "select" || Boolean(target?.isContentEditable);
}

function digitShortcut(event) {
  return digitShortcutMap[event.code] ?? null;
}

function clampSpeed(speed) {
  return Math.max(0, Math.min(126, Number(speed) || 0));
}

initialize().catch((error) => setStatus(formatError(error)));
