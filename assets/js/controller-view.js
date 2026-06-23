import {labeledInput} from "./ui-helpers.js";

export function renderControllerHeader(elements, controller, state = {}) {
  const telemetry = controller.telemetry || {};
  const programmingTarget = String(controller.programming_target || "programming_track").toLowerCase();
  const trackMode = String(controller.track_mode || "n").toLowerCase();
  const lampState = resolveConnectionLampState(controller, state);
  elements.connectionLamp.className = lampState.className;
  elements.connectionLamp.setAttribute("aria-label", lampState.label);
  elements.headerTemperature.textContent = formatMetric(telemetry.temperature_c, "℃");
  elements.headerVoltage.textContent = formatMetric(telemetry.track_voltage_v, "V");
  elements.headerCurrent.textContent = formatMetric(telemetry.track_current_a, "A");
  elements.headerPower.textContent = formatMetric(telemetry.track_power_w, "W");
  for (const button of elements.programmingTargetButtons || []) {
    const active = button.dataset.programmingTarget === programmingTarget;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  }
  for (const button of elements.operationModeButtons || []) {
    const active = button.dataset.trackMode === trackMode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  }
}

function resolveConnectionLampState(controller, state = {}) {
  const controllerInfo = state.controllerInfo || {};
  const connection = controllerInfo.connection || {};
  const boosterStatus = controller.booster_status || controllerInfo.booster_status || {};
  const controllerReachable = controller.controller_reachable ?? connection.controller_reachable;
  const hasBoosterStatus = Object.prototype.hasOwnProperty.call(boosterStatus, "power_on");
  const connected = controllerReachable === undefined ? hasBoosterStatus : Boolean(controllerReachable);
  if (state.busy) {
    return {
      className: "lamp lamp-busy",
      label: "控制器正在读写操作",
    };
  }
  if (!connected) {
    return {
      className: "lamp lamp-off",
      label: "控制器未能连通",
    };
  }
  if (boosterStatus.short_circuit || boosterStatus.current_alarm) {
    return {
      className: "lamp lamp-short",
      label: "控制器发生短路",
    };
  }
  if (boosterStatus.power_on) {
    return {
      className: "lamp lamp-track-on",
      label: "控制器已连通，轨道已上电",
    };
  }
  return {
    className: "lamp lamp-track-off",
    label: "控制器已连通，轨道未上电",
  };
}

export function renderControllerSettings(elements, controllerInfo, handlers = {}) {
  renderControllerInfo(elements.controllerInfoPanel, controllerInfo, handlers);
  renderTrackProfiles(elements.trackProfilePanel, controllerInfo.track_profiles || {}, handlers);
}

function renderControllerInfo(container, controllerInfo, handlers) {
  container.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = "控制器信息";
  const info = controllerInfo.device_info || {};
  const connection = controllerInfo.connection || {};
  const telemetry = controllerInfo.telemetry || {};
  const table = document.createElement("table");
  table.className = "controller-info-table";
  const rows = [
    ["IP", controllerInfo.ip],
    ["网关状态", connection.gateway_ready || connection.reachable ? "后端就绪" : "后端未就绪"],
    ["设备名称", info.device_name],
    ["出厂编号", info.factory_number],
    ["MAC", formatMac(info.mac_address)],
    ["内核版本", info.core_version],
    ["无线版本", info.wireless_version],
    ["RAILCOM", formatBoolean(info.railcom_enabled)],
    ["屏幕亮度", formatBrightness(info.screen_brightness)],
    ["屏幕方向", formatScreenDirection(info.screen_direction_raw, info.screen_direction_label)],
    ["硬件版本", info.hardware_version],
    ["软件版本", info.software_version],
    ["固件版本", info.firmware_version],
    ["温度", formatMetric(telemetry.temperature_c, "℃")],
    ["电压", formatMetric(telemetry.track_voltage_v, "V")],
    ["电流", formatMetric(telemetry.track_current_a, "A")],
    ["功率", formatMetric(telemetry.track_power_w, "W")]
  ];
  for (let index = 0; index < rows.length; index += 2) {
    appendInfoTableRow(table, rows[index], rows[index + 1]);
  }
  const read = document.createElement("button");
  read.type = "button";
  read.textContent = "读取控制器";
  read.addEventListener("click", () => handlers.onReadInfo?.());
  container.append(title, table, read);
}

function appendInfoTableRow(table, current, next = ["", ""]) {
  const row = document.createElement("tr");
  const labelCell = document.createElement("th");
  labelCell.scope = "row";
  labelCell.textContent = current[0];
  const valueCell = document.createElement("td");
  valueCell.textContent = current[1] || "--";
  const nextLabelCell = document.createElement("th");
  nextLabelCell.scope = "row";
  nextLabelCell.textContent = next[0];
  const nextValueCell = document.createElement("td");
  nextValueCell.textContent = next[1] || "";
  row.append(labelCell, valueCell, nextLabelCell, nextValueCell);
  table.append(row);
}

function renderTrackProfiles(container, profiles, handlers) {
  container.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = "轨道输出参数";
  const form = document.createElement("form");
  form.className = "profile-grid";
  for (const mode of ["n", "ho", "g", "dc"]) {
    if (!profiles[mode]) {
      continue;
    }
    const profile = profiles[mode] || {};
    const fieldset = document.createElement("fieldset");
    fieldset.dataset.mode = mode;
    const legend = document.createElement("legend");
    legend.textContent = profile.name || mode.toUpperCase();
    fieldset.append(
      legend,
      labeledInput("电压 V", "number", profile.voltage_v ?? "", {
        "data-field": "voltage_v",
        min: 0,
        max: profile.max_voltage_v || "",
        step: 0.1,
        disabled: mode === "dc"
      }).label,
      labeledInput("电流 mA", "number", profile.current_limit_ma ?? "", {
        "data-field": "current_limit_ma",
        min: 40,
        max: profile.max_current_limit_ma || 10200,
        step: 40
      }).label
    );
    form.append(fieldset);
  }
  const save = document.createElement("button");
  save.type = "submit";
  save.textContent = "保存参数";
  form.append(save);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const nextProfiles = {};
    for (const fieldset of form.querySelectorAll("fieldset")) {
      const mode = fieldset.dataset.mode;
      nextProfiles[mode] = {
        voltage_v: Number(fieldset.querySelector('[data-field="voltage_v"]').value),
        current_limit_ma: fieldset.querySelector('[data-field="current_limit_ma"]').value
      };
    }
    handlers.onSave?.({track_profiles: nextProfiles});
  });
  container.append(title, form);
}

function formatMetric(value, unit) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  return `${value}${unit}`;
}

function formatBoolean(value) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  return value ? "开启" : "关闭";
}

function formatBrightness(value) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  return `${value}`;
}

function formatScreenDirection(rawValue, label) {
  if (rawValue === null || rawValue === undefined || rawValue === "") {
    return "--";
  }
  return label ? `${label} / 原始值 ${rawValue}` : `原始值 ${rawValue}`;
}

function formatMac(value) {
  if (!value) {
    return "--";
  }
  return String(value).replace(/(..)(?=.)/g, "$1 ");
}
