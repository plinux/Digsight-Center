function notifyGatewayBusy(active) {
  if (typeof globalThis.dispatchEvent === "function" && typeof CustomEvent === "function") {
    globalThis.dispatchEvent(new CustomEvent("digsight:gateway-busy", {detail: {active}}));
  }
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
  return patchJson("/api/controller/settings", changes);
}

export function setControllerTrackMode(trackMode) {
  return patchJson("/api/controller/track-mode", {track_mode: trackMode});
}

export function setTrackPower(powered) {
  return postJson("/api/track-power", {powered});
}

export function setDcControl(voltageV, direction) {
  return postJson("/api/dc-control", {
    voltage_v: voltageV,
    direction
  });
}

export async function importConfig(format, file) {
  notifyGatewayBusy(true);
  try {
    const response = await fetch("/api/import/config", {
      method: "POST",
      headers: {
        "Content-Type": "application/octet-stream",
        "X-Import-Format": format,
        "X-File-Name": file.name
      },
      body: await file.arrayBuffer()
    });
    const payload = await response.json();
    if (!payload.ok) {
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
  return postJson("/api/cv/write", {...options, cv: cvNumber, value, confirmed});
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
  return postJson("/api/address/write", body);
}

export function updateVehicle(vehicleId, changes) {
  return patchJson(`/api/vehicles/${encodeURIComponent(vehicleId)}`, changes);
}

export function createVehicle(changes) {
  return postJson("/api/vehicles", changes);
}

export function deleteVehicle(vehicleId) {
  return deleteJson(`/api/vehicles/${encodeURIComponent(vehicleId)}`);
}

export function uploadVehicleImage(file) {
  return fileToBase64(file).then((contentBase64) => {
    return postJson("/api/vehicle-images", {
      file_name: file.name || "vehicle-image.png",
      content_base64: contentBase64
    });
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
  return patchJson("/api/vehicles/order", {vehicle_ids: vehicleIds});
}

export function createConsist(payload, members) {
  const body = typeof payload === "object" && payload !== null ? payload : {name: payload, members};
  return postJson("/api/consists", body);
}

export function updateConsist(consistId, changes) {
  return patchJson(`/api/consists/${encodeURIComponent(consistId)}`, changes);
}

export function deleteConsist(consistId) {
  return deleteJson(`/api/consists/${encodeURIComponent(consistId)}`);
}

export function setConsistSpeed(consistId, speed, direction) {
  return postJson(`/api/consists/${encodeURIComponent(consistId)}/speed`, {speed, direction});
}

export function setLocoSpeed(vehicleId, speed, direction) {
  return postJson("/api/loco/speed", {vehicle_id: vehicleId, speed, direction});
}

export function setLocoFunction(vehicleId, functionNumber, enabled, functionStates = {}) {
  return postJson(
    "/api/loco/function",
    {vehicle_id: vehicleId, function_number: functionNumber, enabled, function_states: functionStates}
  );
}
