function notifyGatewayBusy(active) {
  if (typeof globalThis.dispatchEvent === "function" && typeof CustomEvent === "function") {
    globalThis.dispatchEvent(new CustomEvent("digsight:gateway-busy", {detail: {active}}));
  }
}

const operationTokenKey = "digsight.operationToken";

function sessionStorageValue(key) {
  try {
    return globalThis.sessionStorage?.getItem(key) || "";
  } catch (_error) {
    return "";
  }
}

export function setOperationToken(token) {
  const normalized = String(token || "").trim();
  try {
    if (normalized) {
      globalThis.sessionStorage?.setItem(operationTokenKey, normalized);
    } else {
      globalThis.sessionStorage?.removeItem(operationTokenKey);
    }
  } catch (_error) {
    // sessionStorage can be disabled by browser privacy settings; API errors remain explicit.
  }
}

export function rememberOperationTokenFromState(_state) {
  // The server intentionally never exposes the real operation token through public state.
}

function requestOperationToken() {
  const promptFn = globalThis.prompt;
  if (typeof promptFn !== "function") {
    return "";
  }
  const token = String(promptFn("请输入操作授权令牌") || "").trim();
  if (token) {
    setOperationToken(token);
  }
  return token;
}

function clearOperationToken() {
  setOperationToken("");
}

function operationHeaders() {
  const token = sessionStorageValue(operationTokenKey) || requestOperationToken();
  return token ? {"X-Digsight-Operation-Token": token} : {};
}

export async function requestJson(path, options = {}) {
  notifyGatewayBusy(true);
  try {
    const response = await fetch(path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {})
      }
    });
    const payload = await response.json();
    if (!payload.ok) {
      if (payload.error?.type === "operation_not_authorized") {
        clearOperationToken();
      }
      const error = new Error(payload.error?.message || "请求失败");
      error.payload = payload;
      throw error;
    }
    return payload.data;
  } finally {
    notifyGatewayBusy(false);
  }
}

function postJson(path, body, options = {}) {
  return requestJson(path, {
    method: "POST",
    ...options,
    body: JSON.stringify(body ?? {})
  });
}

function patchJson(path, body, options = {}) {
  return requestJson(path, {
    method: "PATCH",
    ...options,
    body: JSON.stringify(body ?? {})
  });
}

function deleteJson(path, options = {}) {
  return requestJson(path, {method: "DELETE", ...options});
}

export function getState() {
  return requestJson("/api/state", {method: "GET"});
}

export function getCvMetadata() {
  return requestJson("/api/cv/metadata", {method: "GET"});
}

export function getControllerInfo() {
  return requestJson("/api/controller/info", {method: "GET"});
}

export function readControllerInfo() {
  return postJson("/api/controller/read-info", {});
}

export function saveControllerSettings(changes) {
  return patchJson("/api/controller/settings", changes, {headers: operationHeaders()});
}

export function setTrackPower(powered) {
  return postJson("/api/track-power", {powered}, {headers: operationHeaders()});
}

export function setDcControl(voltageV, direction) {
  return postJson("/api/dc-control", {
    voltage_v: voltageV,
    direction
  }, {headers: operationHeaders()});
}

export async function importConfig(format, file) {
  notifyGatewayBusy(true);
  try {
    const response = await fetch("/api/import/config", {
      method: "POST",
      headers: {
        "Content-Type": "application/octet-stream",
        "X-Import-Format": format,
        "X-File-Name": file.name,
        ...operationHeaders()
      },
      body: await file.arrayBuffer()
    });
    const payload = await response.json();
    if (!payload.ok) {
      if (payload.error?.type === "operation_not_authorized") {
        clearOperationToken();
      }
      const error = new Error(payload.error?.message || "导入失败");
      error.payload = payload;
      throw error;
    }
    return payload.data;
  } finally {
    notifyGatewayBusy(false);
  }
}

export function importZ21(file) {
  return importConfig("z21_layout_config", file);
}

export function readCv(cvNumber, options = {}) {
  return postJson("/api/cv/read", {...options, cv: cvNumber});
}

export function readAllCvValues(options = {}) {
  const body = Array.isArray(options) ? {cv_numbers: options} : {...options};
  return postJson("/api/cv/read-all", body);
}

export function cancelCvRead(sessionId) {
  return postJson("/api/cv/read-all/cancel", {session_id: sessionId});
}

export function readChipInfo(options = {}) {
  return postJson("/api/chip-info/read", {...options});
}

export function writeCv(cvNumber, value, confirmed = false, options = {}) {
  return postJson("/api/cv/write", {...options, cv: cvNumber, value, confirmed}, {headers: operationHeaders()});
}

export function readAddress(vehicleId, options = {}) {
  const body = {...options};
  if (vehicleId) {
    body.vehicle_id = vehicleId;
  }
  return postJson("/api/address/read", body);
}

export function writeAddress(vehicleId, address, confirmed = false, options = {}) {
  const body = {...options, address, confirmed};
  if (vehicleId) {
    body.vehicle_id = vehicleId;
  }
  return postJson("/api/address/write", body, {headers: operationHeaders()});
}

export function updateVehicle(vehicleId, changes) {
  return patchJson(`/api/vehicles/${encodeURIComponent(vehicleId)}`, changes, {headers: operationHeaders()});
}

export function createVehicle(changes) {
  return postJson("/api/vehicles", changes, {headers: operationHeaders()});
}

export function deleteVehicle(vehicleId) {
  return deleteJson(`/api/vehicles/${encodeURIComponent(vehicleId)}`, {headers: operationHeaders()});
}

export function uploadVehicleImage(file) {
  return fileToBase64(file).then((contentBase64) => {
    return postJson("/api/vehicle-images", {
      file_name: file.name || "vehicle-image.png",
      content_base64: contentBase64
    }, {headers: operationHeaders()});
  });
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => {
      const value = String(reader.result || "");
      resolve(value.includes(",") ? value.split(",", 2)[1] : value);
    });
    reader.addEventListener("error", () => reject(reader.error || new Error("图片读取失败")));
    reader.readAsDataURL(file);
  });
}

export function reorderVehicles(vehicleIds) {
  return patchJson("/api/vehicles/order", {vehicle_ids: vehicleIds}, {headers: operationHeaders()});
}

export function createConsist(payload, members) {
  const body = typeof payload === "object" && payload !== null ? payload : {name: payload, members};
  return postJson("/api/consists", body, {headers: operationHeaders()});
}

export function updateConsist(consistId, changes) {
  return patchJson(`/api/consists/${encodeURIComponent(consistId)}`, changes, {headers: operationHeaders()});
}

export function deleteConsist(consistId) {
  return deleteJson(`/api/consists/${encodeURIComponent(consistId)}`, {headers: operationHeaders()});
}

export function setConsistSpeed(consistId, speed, direction) {
  return postJson(`/api/consists/${encodeURIComponent(consistId)}/speed`, {speed, direction}, {headers: operationHeaders()});
}

export function setLocoSpeed(vehicleId, speed, direction) {
  return postJson("/api/loco/speed", {vehicle_id: vehicleId, speed, direction}, {headers: operationHeaders()});
}

export function setLocoFunction(vehicleId, functionNumber, enabled, functionStates = {}) {
  return postJson(
    "/api/loco/function",
    {vehicle_id: vehicleId, function_number: functionNumber, enabled, function_states: functionStates},
    {headers: operationHeaders()}
  );
}
