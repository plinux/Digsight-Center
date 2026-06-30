import {renderControllerKindOptions} from "./capability-selectors.js";

const GLOBAL_APP_STATE_FILE = "data/app-state.json";

export function controllerDescriptor(capabilities = {}, kind = "") {
  const options = Array.isArray(capabilities.controllers) ? capabilities.controllers : [];
  const controllerKind = kind || capabilities.default_controller_kind || "";
  return options.find((controller) => controller.kind === controllerKind) || {};
}

function transportFieldReady(value) {
  if (typeof value === "number") {
    return Number.isFinite(value) && value > 0;
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) {
      return false;
    }
    const numericValue = Number(trimmed);
    return Number.isFinite(numericValue) ? numericValue > 0 : true;
  }
  return Boolean(value);
}

function controllerEndpointValue(controller = {}, path = "") {
  return String(path).split(".").reduce((value, key) => {
    if (!value || typeof value !== "object") {
      return undefined;
    }
    return value[key];
  }, controller);
}

export function controllerEndpointReady(descriptor = {}, controller = {}) {
  const requiredPaths = descriptor.endpoint_readiness?.required_paths;
  if (!Array.isArray(requiredPaths)) {
    return false;
  }
  return requiredPaths.every((path) => transportFieldReady(controllerEndpointValue(controller, path)));
}

export function persistentConfigurationStatus(appState, kind = "") {
  const lastError = appState.lastError || {};
  if (lastError.type === "controller_config_invalid") {
    const files = controllerConfigResetFiles(appState, null, lastError.controller_kind || kind || appState.controller.kind);
    const manualAction = lastError.manual_action || "请手工修复该 JSON 文件，或点击重置恢复默认配置。";
    const lines = [
      lastError.message || "当前控制器配置文件无效",
      lastError.detail ? `错误详情：${lastError.detail}` : "",
      manualAction,
      "重置只会影响当前选择控制器的配置文件。",
      "本次可重置文件：",
      ...resetFileLines(files)
    ].filter(Boolean);
    return {
      summary: "当前控制器配置文件无效",
      detail: lines.join("\n")
    };
  }
  if (lastError.type === "app_state_corrupt_recovered") {
    return {
      summary: "全局状态文件已恢复为默认状态",
      detail: [
        `${GLOBAL_APP_STATE_FILE} 已恢复为默认状态。`,
        lastError.backup_file ? `损坏文件已备份为：${lastError.backup_file}` : "",
        "如需恢复旧状态，请按详情中的备份文件手工处理。"
      ].filter(Boolean).join("\n")
    };
  }
  return null;
}

export async function resetSelectedControllerConfig({
  appState,
  elements,
  resetControllerConfig,
  refreshState,
  setStatus,
  formatError
}) {
  const kind = selectedControllerKind(appState, elements);
  const files = controllerConfigResetFiles(appState, elements, kind);
  if (!confirmControllerConfigReset(files)) {
    return;
  }
  try {
    const result = await resetControllerConfig(kind);
    const resetFiles = result.reset_files || files;
    setStatus({
      summary: "控制器配置已重置",
      detail: ["已重置文件：", ...resetFileLines(resetFiles)].join("\n")
    });
    await refreshState();
  } catch (error) {
    setStatus(formatError(error));
  }
}

export async function runControllerStatusRetry({
  requiresFreshStatus = false,
  requestFn,
  setStatus,
  readControllerInfo,
  refreshState
}) {
  try {
    return await requestFn();
  } catch (error) {
    if (!requiresFreshStatus || !isRetryableControllerStatusError(error)) {
      throw error;
    }
    setStatus("轨道状态未确认，正在重新读取控制器信息");
    await readControllerInfo();
    await refreshState();
    return await requestFn();
  }
}

function isRetryableControllerStatusError(error) {
  const warningSet = new Set(error.payload?.debug?.warnings || []);
  return error.payload?.error?.type === "protocol_not_ready"
    && (
      warningSet.has("booster_status_unconfirmed")
      || warningSet.has("booster_status_stale")
      || warningSet.has("controller_not_confirmed")
    );
}

export function syncControllerDescriptorControls(elements, appState) {
  renderControllerKindOptions(elements, appState.capabilities);
  const controllerKind = appState.controller.kind || appState.capabilities.default_controller_kind;
  elements.controllerKindSelect.value = controllerKind;
  elements.controllerIp.value = appState.controller.ip || controllerDescriptor(appState.capabilities, controllerKind).default_ip || "";
}

function selectedControllerKind(appState, elements) {
  return elements?.controllerKindSelect?.value || appState.controller.kind || appState.capabilities.default_controller_kind || "";
}

function controllerConfigResetFiles(appState, elements, kind = selectedControllerKind(appState, elements)) {
  const lastError = appState.lastError || {};
  let files = [];
  if (lastError.type === "controller_config_invalid" && Array.isArray(lastError.resettable_files)) {
    files = [...lastError.resettable_files];
  } else {
    const descriptor = controllerDescriptor(appState.capabilities, kind);
    files = descriptor.config_file ? [descriptor.config_file] : ["当前控制器配置文件"];
  }
  if (shouldIncludeGlobalStateInReset(lastError) && !files.includes(GLOBAL_APP_STATE_FILE)) {
    files.push(GLOBAL_APP_STATE_FILE);
  }
  return files;
}

function shouldIncludeGlobalStateInReset(lastError) {
  if (lastError.type === "app_state_corrupt_recovered") {
    return true;
  }
  const globalConfigError = lastError.global_config_error || {};
  return globalConfigError.type === "app_state_corrupt_recovered";
}

function resetFileLines(files = []) {
  return (files || []).map((file) => `- ${file}`);
}

function confirmControllerConfigReset(files) {
  const fileList = resetFileLines(files).join("\n") || "- 当前控制器配置文件";
  const message = [
    "确认重置当前控制器配置？",
    "",
    "本次会重置以下文件：",
    fileList,
    "",
    "不会重置其它控制器配置文件。"
  ].join("\n");
  if (typeof globalThis.confirm !== "function") {
    return false;
  }
  return globalThis.confirm(message);
}
