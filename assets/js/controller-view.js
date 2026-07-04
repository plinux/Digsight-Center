import {labeledInput} from "./ui-helpers.js";

export function renderControllerHeader(elements, controller, state = {}) {
  const telemetry = controller.telemetry || {};
  const programmingTarget = String(controller.programming_target || "programming_track").toLowerCase();
  const trackMode = String(controller.track_mode || "n").toLowerCase();
  const trackProfiles = controller.track_profiles || state.controllerInfo?.track_profiles || {};
  const lampState = resolveConnectionLampState(controller, state);
  elements.connectionLamp.className = lampState.className;
  elements.connectionLamp.setAttribute("aria-label", lampState.label);
  elements.headerTemperature.textContent = formatHeaderMetric(telemetry.temperature_c, "℃");
  elements.headerVoltage.textContent = formatHeaderMetric(telemetry.track_voltage_v, "V");
  elements.headerCurrent.textContent = formatHeaderMetric(telemetry.track_current_a, "A");
  elements.headerPower.textContent = formatHeaderMetric(telemetry.track_power_w, "W");
  syncPressedButtons(elements.programmingTargetButtons, "programmingTarget", programmingTarget);
  syncPressedButtons(elements.operationModeButtons, "trackMode", trackMode, trackProfiles);
}

function syncPressedButtons(buttons, datasetKey, activeValue, trackProfiles = {}) {
  for (const button of buttons || []) {
    const active = button.dataset[datasetKey] === activeValue;
    const profile = datasetKey === "trackMode" ? trackProfiles[button.dataset.trackMode] : null;
    const disabled = Boolean(profile && profile.enabled === false);
    const disabledTitle = disabled && datasetKey === "trackMode" ? unsupportedModeTitle(button.dataset.trackMode) : "";
    button.classList.toggle("active", active);
    button.disabled = disabled;
    button.setAttribute("aria-disabled", disabled ? "true" : "false");
    button.setAttribute("aria-pressed", active ? "true" : "false");
    button.title = disabledTitle;
    if (disabledTitle) {
      button.setAttribute("aria-label", disabledTitle);
    } else {
      button.removeAttribute("aria-label");
    }
  }
}

function unsupportedModeTitle(trackMode) {
  return String(trackMode || "").toLowerCase() === "dc"
    ? "本控制器不支持DC模式"
    : "本控制器不支持该模式";
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
  elements.trackProfilePanel.replaceChildren();
  const deviceWritable = Boolean(controllerInfo.controller_capabilities?.controller_settings);
  const syncOnMode = Boolean(controllerInfo.controller_capabilities?.profile_settings_on_track_mode);
  const trackSection = document.createElement("section");
  trackSection.className = "controller-settings-section";
  const railComSection = document.createElement("section");
  railComSection.className = "controller-settings-section";
  renderTrackProfiles(trackSection, controllerInfo.track_profiles || {}, handlers, {
    disabled: false,
    deviceWritable,
    syncOnMode,
    defaults: controllerInfo.default_track_output_settings || {},
    settings: controllerInfo.settings || {},
    settingSpecs: controllerInfo.track_output_setting_specs || []
  });
  renderRailComSettings(railComSection, controllerInfo.railcom_setting || {}, handlers);
  elements.trackProfilePanel.append(trackSection);
  if (railComSection.childElementCount) {
    elements.trackProfilePanel.append(railComSection);
  }
}

function renderControllerInfo(container, controllerInfo, handlers) {
  container.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = "控制器信息";
  const connection = controllerInfo.connection || {};
  const sections = normalizedControllerInfoSections(controllerInfo, connection);
  container.append(title);
  for (const section of sections) {
    const sectionTitle = document.createElement("h3");
    sectionTitle.textContent = section.title || "控制器信息";
    const table = document.createElement("table");
    table.className = "controller-info-table";
    for (let index = 0; index < section.rows.length; index += 2) {
      appendInfoTableRow(table, section.rows[index], section.rows[index + 1]);
    }
    container.append(sectionTitle, table);
  }
  const read = document.createElement("button");
  read.type = "button";
  read.textContent = "读取控制器";
  read.addEventListener("click", () => handlers.onReadInfo?.());
  container.append(read);
}

function normalizedControllerInfoSections(controllerInfo, connection) {
  const commonRows = [
    ["控制器", controllerInfo.controller_label || "--"],
    ["协议", controllerInfo.controller_protocol || "--"],
    ["IP", controllerInfo.ip],
    ["网关状态", connection.gateway_ready || connection.reachable ? "后端就绪" : "后端未就绪"],
  ];
  const sections = [{
    title: "连接状态",
    rows: commonRows,
  }];
  for (const section of controllerInfo.info_sections || []) {
    const rows = [];
    for (const row of section.rows || []) {
      rows.push([
        row.label || "",
        formatControllerInfoValue(controllerInfo, row),
      ]);
    }
    if (rows.length) {
      sections.push({
        title: section.title || "控制器信息",
        rows,
      });
    }
  }
  return sections;
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

function renderTrackProfiles(container, profiles, handlers, options = {}) {
  const disabled = Boolean(options.disabled);
  const deviceWritable = Boolean(options.deviceWritable);
  container.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = "轨道输出参数";
  const form = document.createElement("form");
  form.className = "profile-grid";
  renderTrackOutputSettingFields(form, options.settings || {}, options.settingSpecs || [], disabled, options.defaults?.settings || {});
  for (const mode of ["n", "ho", "g", "dc"]) {
    if (!profiles[mode]) {
      continue;
    }
    const profile = profiles[mode] || {};
    if (profile.enabled === false) {
      continue;
    }
    const supportsVoltage = Object.prototype.hasOwnProperty.call(profile, "target_voltage_v");
    const supportsCurrentLimit = Object.prototype.hasOwnProperty.call(profile, "target_current_limit_ma");
    const fieldset = document.createElement("fieldset");
    fieldset.dataset.mode = mode;
    const legend = document.createElement("legend");
    legend.textContent = profile.name || mode.toUpperCase();
    const fields = [legend];
    if (supportsVoltage) {
      fields.push(labeledInput("目标电压 V", "number", profile.target_voltage_v ?? "", {
        "data-field": "target_voltage_v",
        min: profile.min_target_voltage_v ?? 0,
        max: profile.max_target_voltage_v || "",
        step: 0.1,
        disabled: disabled || mode === "dc"
      }).label);
    }
    if (supportsCurrentLimit) {
      fields.push(labeledInput("目标限流 mA", "number", profile.target_current_limit_ma ?? "", {
        "data-field": "target_current_limit_ma",
        min: profile.min_target_current_limit_ma || 40,
        max: profile.max_target_current_limit_ma || 10200,
        step: profile.current_step_ma || 40,
        disabled
      }).label);
    }
    fieldset.append(...fields);
    form.append(fieldset);
  }
  const save = document.createElement("button");
  save.type = "submit";
  save.textContent = "保存";
  save.disabled = disabled;
  save.setAttribute("aria-disabled", disabled ? "true" : "false");
  const reset = document.createElement("button");
  reset.type = "button";
  reset.textContent = "重置";
  reset.disabled = disabled || !hasTrackProfileDefaults(options.defaults);
  reset.setAttribute("aria-disabled", reset.disabled ? "true" : "false");
  const note = document.createElement("p");
  note.className = "panel-note";
  note.textContent = options.syncOnMode
    ? "设置相应的比例会同步调整电压值。"
    : deviceWritable
      ? "保存后会写入控制器并读回校验。"
      : "当前控制器适配器尚未实现参数写入控制器，保存只会更新本地配置。";
  const actions = document.createElement("div");
  actions.className = "profile-actions";
  actions.append(save, reset, note);
  form.append(actions);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (disabled) {
      return;
    }
    const nextProfiles = {};
    for (const fieldset of form.querySelectorAll("fieldset[data-mode]")) {
      const mode = fieldset.dataset.mode;
      const voltageInput = fieldset.querySelector('[data-field="target_voltage_v"]');
      const currentInput = fieldset.querySelector('[data-field="target_current_limit_ma"]');
      nextProfiles[mode] = {};
      if (voltageInput) {
        nextProfiles[mode].target_voltage_v = Number(voltageInput.value);
      }
      if (currentInput) {
        nextProfiles[mode].target_current_limit_ma = currentInput.value;
      }
    }
    const nextSettings = collectTrackOutputSettings(form);
    const changes = {track_profiles: nextProfiles};
    if (Object.keys(nextSettings).length) {
      changes.settings = nextSettings;
    }
    handlers.onSave?.(changes);
  });
  reset.addEventListener("click", () => {
    if (reset.disabled) {
      return;
    }
    handlers.onSave?.(trackProfileResetPayload(profiles, options.defaults || {}));
  });
  container.append(title, form);
}

function renderTrackOutputSettingFields(form, settings, specs, disabled, defaultSettings = {}) {
  if (!Array.isArray(specs) || specs.length === 0) {
    return;
  }
  const fieldset = document.createElement("fieldset");
  fieldset.className = "track-output-common-settings";
  const legend = document.createElement("legend");
  legend.textContent = "通用设置";
  fieldset.append(legend);
  for (const spec of specs) {
    if (!spec || !spec.key) {
      continue;
    }
    const input = labeledInput(spec.label || spec.key, spec.type || "text", trackOutputSettingValue(settings, defaultSettings, spec), {
      "data-setting-key": spec.key,
      min: spec.min,
      max: spec.max,
      step: spec.step,
      title: spec.note || "",
      disabled
    });
    fieldset.append(input.label);
  }
  if (fieldset.childElementCount > 1) {
    form.append(fieldset);
  }
}

function trackOutputSettingValue(settings, defaultSettings, spec) {
  const configuredValue = settings[spec.key];
  if (!isBlankSettingInputValue(configuredValue)) {
    return configuredValue;
  }
  const defaultValue = defaultSettings[spec.key];
  if (!isBlankSettingInputValue(defaultValue)) {
    return defaultValue;
  }
  return spec.type === "number" ? 0 : "";
}

function isBlankSettingInputValue(value) {
  return value === null || value === undefined || value === "";
}

function collectTrackOutputSettings(form) {
  const settings = {};
  for (const input of form.querySelectorAll("[data-setting-key]")) {
    settings[input.dataset.settingKey] = input.type === "number" ? Number(input.value) : input.value;
  }
  return settings;
}

function hasTrackProfileDefaults(defaults = {}) {
  const profiles = defaults.track_profiles || {};
  const settings = defaults.settings || {};
  return Object.keys(profiles).length > 0 || Object.keys(settings).length > 0;
}

function trackProfileResetPayload(currentProfiles, defaults = {}) {
  const defaultProfiles = defaults.track_profiles || {};
  const nextProfiles = {};
  for (const mode of Object.keys(currentProfiles || {})) {
    const currentProfile = currentProfiles[mode] || {};
    const defaultProfile = defaultProfiles[mode];
    if (currentProfile.enabled === false || !defaultProfile) {
      continue;
    }
    nextProfiles[mode] = copyPlain(defaultProfile);
  }
  const changes = {track_profiles: nextProfiles};
  if (defaults.settings && Object.keys(defaults.settings).length) {
    changes.settings = copyPlain(defaults.settings);
  }
  return changes;
}

function copyPlain(value) {
  return JSON.parse(JSON.stringify(value));
}

function renderRailComSettings(container, railComSetting, handlers) {
  container.replaceChildren();
  if (!railComSetting.available) {
    return;
  }
  const title = document.createElement("h2");
  title.textContent = "RailCom";
  const form = document.createElement("form");
  form.className = "railcom-settings-form";
  const label = document.createElement("label");
  label.className = "railcom-toggle";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = railComSetting.enabled === true;
  input.disabled = !railComSetting.writable;
  const text = document.createElement("span");
  text.textContent = "启用 RailCom";
  label.append(input, text);
  const railComPlus = railComSetting.railcomplus || {};
  let railComPlusInput = null;
  let railComPlusLabel = null;
  if (railComPlus.available) {
    railComPlusLabel = document.createElement("label");
    railComPlusLabel.className = "railcom-toggle";
    railComPlusInput = document.createElement("input");
    railComPlusInput.type = "checkbox";
    railComPlusInput.checked = railComPlus.enabled === true;
    const railComPlusText = document.createElement("span");
    railComPlusText.textContent = "启用 RailComPlus";
    railComPlusLabel.append(railComPlusInput, railComPlusText);
  }
  const status = document.createElement("p");
  status.className = "panel-note";
  status.textContent = railComStatusText(railComSetting);
  const save = document.createElement("button");
  save.type = "submit";
  save.textContent = "保存 RailCom";
  save.disabled = !railComSetting.writable;
  save.setAttribute("aria-disabled", railComSetting.writable ? "false" : "true");
  form.append(label);
  if (railComPlusLabel) {
    form.append(railComPlusLabel);
  }
  form.append(status, save);
  const syncRailComPlusState = () => {
    if (!railComPlusInput) {
      return;
    }
    if (!input.checked) {
      railComPlusInput.checked = false;
    }
    railComPlusInput.disabled = !railComPlus.writable || !input.checked;
  };
  input.addEventListener("change", syncRailComPlusState);
  syncRailComPlusState();
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!railComSetting.writable) {
      return;
    }
    const settings = {railcom_enabled: input.checked};
    if (railComPlusInput && railComPlus.available) {
      settings.railcomplus_enabled = input.checked && railComPlusInput.checked;
    }
    handlers.onSave?.({settings});
  });
  container.append(title, form);
}

function railComStatusText(railComSetting) {
  if (railComSetting.message) {
    return railComSetting.message;
  }
  if (railComSetting.enabled === true) {
    return "当前状态：已开启。";
  }
  if (railComSetting.enabled === false) {
    return "当前状态：已关闭。";
  }
  return "当前状态尚未读取。";
}

function isBlankDisplayValue(value) {
  return value === null || value === undefined || value === "";
}

function getValueAtPath(source, path) {
  if (!path) {
    return undefined;
  }
  return String(path).split(".").reduce((current, key) => {
    if (current === null || current === undefined) {
      return undefined;
    }
    return current[key];
  }, source);
}

function formatControllerInfoValue(controllerInfo, row) {
  const value = getValueAtPath(controllerInfo, row.path);
  switch (row.format) {
    case "boolean":
      return formatBoolean(value);
    case "power_state":
      return formatPowerState(value);
    case "short_circuit_state":
      return formatShortCircuitState(value);
    case "mac":
      return formatMac(value);
    case "screen_direction":
      return formatScreenDirection(value, getValueAtPath(controllerInfo, row.label_path));
    default:
      if (row.unit) {
        return formatMetric(value, row.unit);
      }
      return isBlankDisplayValue(value) ? "--" : `${value}`;
  }
}

function formatMetric(value, unit) {
  if (isBlankDisplayValue(value)) {
    return "--";
  }
  return `${value}${unit}`;
}

function formatHeaderMetric(value, unit) {
  if (isBlankDisplayValue(value)) {
    return "--";
  }
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return `${value}${unit}`;
  }
  return `${Number(number.toFixed(1))}${unit}`;
}

function formatBoolean(value) {
  if (isBlankDisplayValue(value)) {
    return "--";
  }
  return value ? "开启" : "关闭";
}

function formatPowerState(value) {
  if (isBlankDisplayValue(value)) {
    return "--";
  }
  return value ? "通电" : "断电";
}

function formatShortCircuitState(value) {
  if (isBlankDisplayValue(value)) {
    return "--";
  }
  return value ? "发现短路" : "无短路";
}

function formatScreenDirection(rawValue, label) {
  if (isBlankDisplayValue(rawValue)) {
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
