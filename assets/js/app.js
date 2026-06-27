import {
  createConsist,
  createVehicle,
  deleteVehicle,
  getCapabilities,
  getControllerInfo,
  getCvMetadata,
  getState,
  importConfig,
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
} from "./gateway-api.js";
import {appState, replaceState} from "./state-store.js";
import {renderControllerHeader, renderControllerSettings} from "./controller-view.js";
import {renderCvPanel} from "./cv-view.js";
import {buildCabWorkspaceHandlers} from "./cab-controller.js";
import {buildCvPanelHandlers, createCvDomainModel} from "./cv-controller.js";
import {buildCvRuntimeActions, newCvReadSessionId} from "./cv-runtime-actions.js";
import {buildVehicleEditorHandlers} from "./vehicle-editor-controller.js";
import {initializeApp, wireAppEvents} from "./app-bootstrap.js";
import {renderControllerKindOptions, renderImportFormatOptions} from "./capability-selectors.js";
import {buildCabWorkspaceActions} from "./cab-workspace-actions.js";
import {buildLocoRuntimeActions} from "./loco-runtime-actions.js";
import {
  FALLBACK_FUNCTION_ICON_CATALOG,
  loadFunctionIconCatalog
} from "./function-icon-catalog.js";
import {importSelectedConfigFile} from "./import-actions.js";
import {
  renderVehicleRegistry
} from "./vehicle-view.js";
import {buildVehicleEditorActions} from "./vehicle-editor-actions.js";
import {
  renderDcControl,
  renderLocoControl,
  renderUnsupportedVehicleControl,
  renderVehicleControlWorkspace
} from "./vehicle-cab-view.js";
import {renderVehicleEditor} from "./vehicle-editor-view.js";
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
  importConfigFileInput: document.getElementById("importConfigFileInput"),
  importFormatSelect: document.getElementById("importFormatSelect"),
  importConfigButton: document.getElementById("importConfigButton"),
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
    readAt: "",
    total_count: 0
  },
  cvListReading: false,
  cvReadSessionId: "",
  cvReadCancelling: false,
  address: null,
  programmingVehicleId: ""
};

const cvDomain = createCvDomainModel({appState, cvState, formatError, newCvReadSessionId});
const cvRuntimeActions = buildCvRuntimeActions({
  appState,
  cvState,
  cvDomain,
  currentProgrammingTarget,
  normalizeProgrammingTarget,
  userVisibleWarnings,
  syncControllerEndpoint,
  readControllerInfo,
  refreshState,
  readChipInfoFromController,
  cvProgrammingRequest,
  readAddress,
  writeAddress,
  writeCv,
  readCv,
  setStatus,
  formatError,
  renderAll,
  showDetailDialog
});
const {
  downloadTextFile,
  buildCvReadAllHandlers,
  buildCvChipHandlers,
  buildCvAddressHandlers,
  buildSingleCvHandlers
} = cvRuntimeActions;
const locoRuntimeActions = buildLocoRuntimeActions({
  appState,
  controlledVehicle,
  cabVehicle,
  cabFunctionVehicle,
  functionDefinition,
  isDigitalOperationMode,
  syncActiveCabControlState,
  syncControllerEndpoint,
  setLocoSpeed,
  setLocoFunction,
  setStatus,
  formatError,
  renderAll
});
const {
  sendLocoSpeed,
  sendCabSpeed,
  sendCabFunction,
  sendCabFunctionByMode
} = locoRuntimeActions;

let gatewayBusyCount = 0;
let functionIconCatalog = FALLBACK_FUNCTION_ICON_CATALOG;
const pressedFunctionKeys = new Map();
let draggedVehicleId = "";
const NEW_VEHICLE_ID = "__new_vehicle__";

function isGatewayBusy() {
  return gatewayBusyCount > 0;
}

function setGatewayBusy(active) {
  gatewayBusyCount = Math.max(0, gatewayBusyCount + (active ? 1 : -1));
  renderControllerHeader(elements, appState.controller, {busy: isGatewayBusy(), controllerInfo: appState.controllerInfo});
}

function openStatusDetailDialog() {
  if (typeof elements.statusDetailDialog?.showModal === "function") {
    elements.statusDetailDialog.showModal();
  }
}

function showDetailDialog(summary, detail) {
  if (elements.statusDetailText) {
    elements.statusDetailText.textContent = String(detail || summary || "");
  }
  openStatusDetailDialog();
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
  if (!error || typeof error !== "object") {
    return String(error || "操作失败");
  }
  if (error.payload) {
    return {
      summary: error.payload?.error?.message || error.message,
      detail: JSON.stringify(error.payload, null, 2)
    };
  }
  const genericDetail = [
    error.name ? `类型：${error.name}` : "",
    error.message ? `消息：${error.message}` : "",
    error.cause ? `原因：${String(error.cause)}` : "",
    error.stack ? `堆栈：\n${error.stack}` : "",
  ].filter(Boolean).join("\n\n");
  return {summary: error.message, detail: genericDetail};
}

function formatErrorSummary(error) {
  const formatted = formatError(error);
  return typeof formatted === "object" ? formatted.summary : String(formatted);
}

const controllerWarningMessages = {
  "booster_dc_mode_reported": "控制器回报为 DC 模式",
  "booster_status_missing": "未收到轨道输出状态回包",
  "booster_status_stale": "请先连接控制器并读取最新状态",
  "booster_status_unconfirmed": "轨道状态未确认",
  "command_station_status_missing": "未收到命令站状态回包",
  "controller_not_confirmed": "控制器连接状态未确认",
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
  if (appState.editingVehicleDraft?.id === appState.editingVehicleId) {
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
  syncActiveCabControlState(cabId);
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
  syncActiveCabControlState(cabId);
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
  syncActiveCabControlState(cabId);
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
  syncActiveCabControlState(cabId);
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
  syncActiveCabControlState(cabId);
  renderAll();
}

function syncActiveCabControlState(cabId = appState.activeCabId) {
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
    return Number(vehicle.custom_sort_order ?? vehicle.source_position ?? 0);
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
  syncActiveCabControlState(appState.activeCabId);
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

function controllerDescriptor(kind = appState.controller.kind || appState.capabilities.default_controller_kind) {
  return (appState.capabilities.controllers || []).find((controller) => controller.kind === kind) || {};
}

async function syncControllerEndpoint() {
  const kind = elements.controllerKindSelect.value || appState.capabilities.default_controller_kind;
  const ip = elements.controllerIp.value.trim();
  if (!ip) {
    throw new Error("控制器 IP 不能为空");
  }
  if (kind === appState.controller.kind && ip === appState.controller.ip && Number(appState.controller.udp_port || 0) > 0) {
    return;
  }
  const result = await saveControllerSettings({kind, ip});
  appState.controller.kind = result.kind ?? kind;
  appState.controller.ip = result.ip ?? ip;
  appState.controller.udp_port = result.udp_port ?? appState.controller.udp_port;
  appState.controller.local_udp_port = result.local_udp_port ?? appState.controller.local_udp_port;
  appState.controller.udp_checksum_algorithm = result.udp_checksum_algorithm ?? appState.controller.udp_checksum_algorithm;
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

function cabWorkspaceActions() {
  return buildCabWorkspaceActions({
    appState,
    activateCab,
    selectCabVehicle,
    toggleVehicleSelection,
    showVehicleEditor,
    toggleCabExpanded,
    toggleCabFunctionNumbers,
    toggleCabFunctionLabels,
    switchCabConsistMember,
    renderAll,
    saveCustomVehicleOrder,
    setStatus,
    formatError,
    setDraggedVehicleId: (vehicleId) => {
      draggedVehicleId = vehicleId;
    },
    sendCabSpeed,
    clampSpeed,
    syncActiveCabControlState,
    sendCabFunctionByMode
  });
}

function vehicleEditorActions(vehicle) {
  return buildVehicleEditorActions({
    vehicle,
    newVehicleId: NEW_VEHICLE_ID,
    appState,
    functionsByVehicle,
    showVehicleRegistry,
    renderAll,
    consistForVehicle,
    createVehicle,
    updateVehicle,
    saveVehicleConsist,
    setStatus,
    refreshState,
    formatError,
    deleteVehicle,
    uploadVehicleImage
  });
}

function buildCvProgrammingVehicleHandlers() {
  return {
    onCvProgrammingVehicleChange: (vehicleId) => {
      cvState.programmingVehicleId = vehicleId || "";
      const targetVehicle = selectedCvProgrammingVehicle();
      if (targetVehicle) {
        cvState.address = targetVehicle.address ?? cvState.address;
      }
      renderAll();
    }
  };
}

function buildCvExportHandlers() {
  return {
    onExportCvMarkdown: () => {
      downloadTextFile(cvDomain.cvExportFileName("md"), cvDomain.buildCvMarkdown(cvState.cvList), "text/markdown;charset=utf-8");
    },
    onExportCvCsv: () => {
      downloadTextFile(cvDomain.cvExportFileName("csv"), cvDomain.buildCvCsv(cvState.cvList), "text/csv;charset=utf-8");
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
  const context = buildRenderContext();
  syncVisibleState(context);
  renderControllerShell(context);
  if (context.isDcMode) {
    renderDcModeView(context);
    return;
  }
  renderActiveVehicleView(context);
  renderActiveCvView(context);
  renderActiveControllerView();
  setVehicleSubviewState();
}

function buildRenderContext() {
  const operationMode = currentOperationMode();
  const visibleVehicles = vehiclesForOperationMode(operationMode);
  return {
    operationMode,
    digitalMode: isDigitalOperationMode(operationMode),
    isDcMode: isDcOperationMode(operationMode),
    visibleVehicles,
    visibleFunctions: functionsForVehicles(visibleVehicles),
    leftVehicles: sortCabVehicles(filterCabVehicles(visibleVehicles, appState.cabs.left), appState.cabs.left),
    rightVehicles: sortCabVehicles(filterCabVehicles(visibleVehicles, appState.cabs.right), appState.cabs.right)
  };
}

function syncVisibleState({digitalMode, visibleVehicles}) {
  syncCvProgrammingVehicle(visibleVehicles);
  syncCabSelectionForVisibleVehicles(visibleVehicles);
  syncVehicleSelectionToolbar(visibleVehicles);
  if (!digitalMode && appState.activeView === "cv") {
    appState.activeView = "vehicle";
  }
  if (!digitalMode && appState.vehicleSubview !== "registry") {
    appState.vehicleSubview = "registry";
  }
}

function renderControllerShell({isDcMode, operationMode, visibleVehicles}) {
  updateVehicleHeader(visibleVehicles, operationMode);
  renderControllerHeader(elements, appState.controller, {busy: isGatewayBusy(), controllerInfo: appState.controllerInfo});
  setNavState();
  setVehicleSubviewState();
  elements.vehicleControlView.classList.toggle("dc-control-mode", isDcMode);
  if (elements.importStrip) {
    elements.importStrip.hidden = isDcMode;
  }
}

function renderDcModeView() {
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
  renderActiveControllerView();
}

function renderActiveVehicleView({operationMode, leftVehicles, rightVehicles, visibleFunctions, visibleVehicles}) {
  renderVehicleControlWorkspace(elements.vehicleRegistry, visibleVehicles, visibleFunctions, {
    activeCabId: appState.activeCabId,
    cabs: appState.cabs
  }, buildCabWorkspaceHandlers({
    operationMode,
    operationModeName,
    leftVehicles,
    rightVehicles,
    appState,
    actions: cabWorkspaceActions(),
    functionIconCatalog
  }));

  const vehicle = editingVehicle();
  renderVehicleEditor(elements.vehicleEditView, vehicle, editingFunctions(vehicle), buildVehicleEditorHandlers({
    vehicle,
    appState,
    editorOptions: vehicleEditorOptions(appState.vehicles),
    actions: vehicleEditorActions(vehicle),
    functionIconCatalog
  }));

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
}

function renderActiveCvView({visibleVehicles}) {
  const vehicle = editingVehicle();
  const cvProgrammingTargetVehicle = currentProgrammingTarget() === "main_track" ? selectedCvProgrammingVehicle() : null;
  renderCvPanel(elements, cvProgrammingTargetVehicle, appState.cvMetadata, {
    ...cvState,
    programmingTarget: currentProgrammingTarget(),
    programmingVehicles: visibleVehicles
  }, buildCvPanelHandlers({
    programmingVehicleHandlers: () => buildCvProgrammingVehicleHandlers(vehicle),
    chipHandlers: buildCvChipHandlers,
    readAllHandlers: buildCvReadAllHandlers,
    exportHandlers: buildCvExportHandlers,
    addressHandlers: buildCvAddressHandlers,
    singleCvHandlers: buildSingleCvHandlers
  }));
}

function renderActiveControllerView() {
  renderControllerSettings(elements, appState.controllerInfo, buildControllerSettingsHandlers());
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
  renderControllerKindOptions(elements, appState.capabilities);
  renderImportFormatOptions(elements, appState.capabilities);
  const controllerKind = appState.controller.kind || appState.capabilities.default_controller_kind;
  elements.controllerKindSelect.value = controllerKind;
  elements.controllerIp.value = appState.controller.ip || controllerDescriptor(controllerKind).default_ip || "";
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
  await initializeApp({
    appState,
    elements,
    getCapabilities,
    renderControllerKindOptions,
    renderImportFormatOptions,
    setFunctionIconCatalog: (catalog) => {
      functionIconCatalog = catalog;
    },
    loadFunctionIconCatalog,
    getCvMetadata,
    refreshState,
    readControllerInfo,
    setStatus,
    controllerReadStatusMessage,
    controllerReadStatusDetail,
    formatError
  });
}

wireAppEvents({
  elements,
  appState,
  importConfig,
  setActiveView,
  setOperationMode,
  setProgrammingTarget,
  setGatewayBusy,
  openStatusDetailDialog,
  syncControllerEndpoint,
  runTrackPowerRequestWithStatusRetry,
  setTrackPower,
  setStatus,
  operationModeName,
  refreshState,
  formatError,
  importSelectedConfigFile,
  toggleVehicleSelectionMode,
  createNewVehicle,
  deleteSelectedVehicles,
  handleVehicleKeyboard,
  handleVehicleKeyboardRelease
});

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
