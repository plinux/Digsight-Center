import {labeledInput} from "./ui-helpers.js";

export function renderCvPanel(elements, selectedVehicle, metadata, cvState, handlers = {}) {
  renderCvTargetPanel(elements.cvTargetPanel, cvState, handlers);
  renderChipInfoPanel(elements.chipInfoPanel, metadata, cvState, handlers);
  renderCvListPanel(elements.cvListPanel, metadata, cvState, handlers);
  renderAddressPanel(elements.addressPanel, selectedVehicle, metadata, cvState, handlers);
  renderCvEditorPanel(elements.cvEditorPanel, selectedVehicle, metadata, cvState, handlers);
}

function renderCvTargetPanel(container, cvState, handlers) {
  if (!container) {
    return;
  }
  container.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = "CV 操作目标";
  const programmingTarget = String(cvState.programmingTarget || "programming_track");
  const vehicles = cvState.programmingVehicles || [];
  const selectedVehicleId = vehicles.some((vehicle) => vehicle.id === cvState.programmingVehicleId)
    ? cvState.programmingVehicleId
    : (vehicles[0]?.id || "");

  const label = document.createElement("label");
  label.className = "cv-target-field";
  const labelText = document.createElement("span");
  labelText.textContent = "主轨操作车号";
  const select = document.createElement("select");
  select.disabled = programmingTarget !== "main_track" || !vehicles.length;
  select.value = selectedVehicleId;

  if (programmingTarget !== "main_track") {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "编程轨不使用车号";
    select.append(option);
  } else if (!vehicles.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "当前模式暂无车辆";
    select.append(option);
  } else {
    for (const vehicle of vehicles) {
      const option = document.createElement("option");
      option.value = vehicle.id;
      option.textContent = cvTargetVehicleLabel(vehicle);
      select.append(option);
    }
    select.value = selectedVehicleId;
  }
  select.addEventListener("change", () => {
    handlers.onCvProgrammingVehicleChange?.(select.value);
  });
  label.append(labelText, select);

  const hint = document.createElement("p");
  hint.className = "empty-state cv-target-hint";
  hint.textContent = programmingTarget === "main_track"
    ? "主轨读取和写入会按所选车号发送 POM 命令。"
    : "编程轨模式直接操作编程轨上的芯片，不选择车号。";
  container.append(title, label, hint);
}

function renderChipInfoPanel(container, metadata, cvState, handlers) {
  container.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = "芯片信息";
  const summary = buildChipInfoSummary(metadata, cvState);
  const table = document.createElement("table");
  table.className = "chip-info-table";
  for (const [name, value] of [
    ["生产厂家 (CV8)", summary.manufacturer],
    ["模块型号 (CV127/128)", summary.model],
    ["硬件版本 (CV127)", summary.hardware],
    ["软件版本 (CV7)", summary.software]
  ]) {
    appendChipInfoTableRow(table, name, value);
  }
  const read = document.createElement("button");
  read.type = "button";
  read.textContent = "读取芯片信息";
  read.addEventListener("click", () => handlers.onReadChipInfo?.());
  const reset = document.createElement("button");
  reset.type = "button";
  reset.className = "danger";
  reset.textContent = "重置芯片";
  reset.addEventListener("click", () => handlers.onResetDecoder?.());
  const actions = document.createElement("div");
  actions.className = "control-row";
  actions.append(read, reset);
  container.append(title, table, actions);
}

function renderCvListPanel(container, metadata, cvState, handlers) {
  container.replaceChildren();
  container.classList.add("cv-list-panel");
  const title = document.createElement("h2");
  title.textContent = "CV值列表";
  const toolbar = document.createElement("div");
  toolbar.className = "cv-list-toolbar";
  const readKnown = document.createElement("button");
  readKnown.type = "button";
  readKnown.textContent = "读取已知CV";
  readKnown.disabled = Boolean(cvState.cvListReading);
  readKnown.addEventListener("click", () => handlers.onReadKnownCv?.());
  const readFull = document.createElement("button");
  readFull.type = "button";
  readFull.textContent = "完整扫描1-1024";
  readFull.disabled = Boolean(cvState.cvListReading);
  readFull.addEventListener("click", () => handlers.onReadFullCv?.());
  const cancelRead = document.createElement("button");
  cancelRead.type = "button";
  cancelRead.textContent = "中止读取";
  cancelRead.disabled = !cvState.cvListReading || Boolean(cvState.cvReadCancelling);
  cancelRead.addEventListener("click", () => handlers.onCancelCvRead?.());
  const markdown = document.createElement("button");
  markdown.type = "button";
  markdown.textContent = "导出 Markdown";
  markdown.disabled = !(cvState.cvList?.rows || []).length;
  markdown.addEventListener("click", () => handlers.onExportCvMarkdown?.());
  const csv = document.createElement("button");
  csv.type = "button";
  csv.textContent = "导出 CSV";
  csv.disabled = !(cvState.cvList?.rows || []).length;
  csv.addEventListener("click", () => handlers.onExportCvCsv?.());
  toolbar.append(readKnown, readFull, cancelRead, markdown, csv);

  const table = document.createElement("table");
  table.className = "cv-list-table";
  const thead = document.createElement("thead");
  const header = document.createElement("tr");
  for (const text of ["CV地址", "含义", "值"]) {
    const cell = document.createElement("th");
    cell.textContent = text;
    header.append(cell);
  }
  thead.append(header);
  const tbody = document.createElement("tbody");
  for (const row of cvState.cvList?.rows || []) {
    appendCvListRow(tbody, row, handlers);
  }
  table.append(thead, tbody);
  const tableWrap = document.createElement("div");
  tableWrap.className = "cv-list-table-wrap";
  tableWrap.append(table);

  const manufacturer = formatManufacturerName(cvState.cvList?.manufacturer_name, cvState.cvList?.manufacturer_id);
  const totalCount = cvState.cvList?.total_count || cvState.cvList?.read_count || 0;
  const summary = document.createElement("p");
  summary.className = "empty-state";
  summary.textContent = (cvState.cvList?.rows || []).length
    ? `生产厂家：${manufacturer}，已读取 ${cvState.cvList.read_count || 0}/${totalCount}`
    : "尚未读取CV值";
  container.append(title, toolbar, summary, tableWrap);
}

function appendCvListRow(tbody, row, handlers) {
  const tr = document.createElement("tr");
  const cvCell = document.createElement("td");
  cvCell.textContent = `CV${row.cv}`;
  const meaningCell = document.createElement("td");
  meaningCell.textContent = row.meaning || "未知/厂家自定义";
  const valueCell = document.createElement("td");
  if (row.ok) {
    valueCell.textContent = String(row.value);
  } else if (row.error_detail) {
    const detailLink = document.createElement("button");
    detailLink.type = "button";
    detailLink.className = "cv-error-detail-link";
    detailLink.textContent = "详情";
    detailLink.addEventListener("click", () => {
      handlers.onShowCvErrorDetail?.(row.error || "读取失败", row.error_detail);
    });
    valueCell.append(document.createTextNode(row.error || "读取失败"), " ", detailLink);
  } else {
    valueCell.textContent = row.error || "读取失败";
  }
  if (!row.ok) {
    valueCell.className = "cv-read-error";
  }
  tr.append(cvCell, meaningCell, valueCell);
  tbody.append(tr);
}

function appendChipInfoTableRow(table, name, value) {
  const row = document.createElement("tr");
  const nameCell = document.createElement("th");
  nameCell.scope = "row";
  nameCell.textContent = name;
  const valueCell = document.createElement("td");
  valueCell.textContent = value || "--";
  row.append(nameCell, valueCell);
  table.append(row);
}

function renderAddressPanel(container, selectedVehicle, metadata, cvState, handlers) {
  container.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = "车辆地址编辑";
  const range = metadata?.address || {min: 1, max: 9999};
  const currentAddress = cvState.address ?? selectedVehicle?.address ?? 3;
  const field = labeledInput("车辆地址", "number", currentAddress, {
    min: range.min,
    max: range.max
  });
  const actions = document.createElement("div");
  actions.className = "control-row address-actions";
  const read = document.createElement("button");
  read.type = "button";
  read.textContent = "读取地址";
  read.addEventListener("click", () => handlers.onReadAddress?.());
  const write = document.createElement("button");
  write.type = "button";
  write.textContent = "写入地址";
  write.addEventListener("click", () => handlers.onWriteAddress?.(Number(field.input.value)));
  actions.append(read, write);
  container.append(title, field.label, actions);
}

function renderCvEditorPanel(container, selectedVehicle, metadata, cvState, handlers) {
  container.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = "CV 地址编辑";
  const cvRange = metadata?.cv_address || {min: 1, max: 1024};
  const valueRange = metadata?.cv_value || {min: 0, max: 255};
  const cv = labeledInput("CV 地址", "number", cvState.cvNumber || 1, {
    min: cvRange.min,
    max: cvRange.max
  });
  const value = labeledInput("十进制值", "number", cvState.value || 0, {
    min: valueRange.min,
    max: valueRange.max
  });
  const bitEditor = document.createElement("div");
  bitEditor.id = "cvBitEditor";
  bitEditor.className = "bit-editor";
  const syncBits = () => {
    const nextValue = clampByte(Number(value.input.value));
    value.input.value = String(nextValue);
    for (const checkbox of bitEditor.querySelectorAll("input")) {
      const bit = Number(checkbox.dataset.bit);
      checkbox.checked = Boolean(nextValue & (1 << bit));
    }
  };
  const syncValue = () => {
    let nextValue = 0;
    for (const checkbox of bitEditor.querySelectorAll("input")) {
      if (checkbox.checked) {
        nextValue |= 1 << Number(checkbox.dataset.bit);
      }
    }
    value.input.value = String(nextValue);
  };
  for (let bit = 7; bit >= 0; bit -= 1) {
    const label = document.createElement("label");
    label.textContent = `bit ${bit}`;
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.dataset.bit = String(bit);
    checkbox.addEventListener("change", syncValue);
    label.append(checkbox);
    bitEditor.append(label);
  }
  value.input.addEventListener("input", syncBits);
  syncBits();

  const actions = document.createElement("div");
  actions.className = "control-row";
  const read = document.createElement("button");
  read.type = "button";
  read.textContent = "读取 CV";
  read.addEventListener("click", () => handlers.onReadCv?.(Number(cv.input.value)));
  const write = document.createElement("button");
  write.type = "button";
  write.textContent = "写入 CV";
  write.addEventListener("click", () => handlers.onWriteCv?.(Number(cv.input.value), Number(value.input.value)));
  actions.append(read, write);
  container.append(title, cv.label, value.label, bitEditor, actions);
}

function clampByte(value) {
  if (Number.isNaN(value)) {
    return 0;
  }
  return Math.max(0, Math.min(255, value));
}

function buildChipInfoSummary(metadata, cvState) {
  const results = cvState.results || {};
  const chipInfo = cvState.chipInfo || null;
  const manufacturerId = numericResult(results[8]) ?? numericResult(chipInfo?.manufacturer_id);
  const software = numericResult(results[7]);
  const registry = metadata?.manufacturer_registry?.known_ids || {};
  const unassigned = metadata?.manufacturer_registry?.unassigned_notes || {};
  const profileName = manufacturerId === null ? null : metadata?.cv_catalog?.profile_map?.[String(manufacturerId)];
  const profile = profileName ? metadata?.cv_catalog?.vendor_profiles?.[profileName] : null;
  const manufacturerName = profile?.manufacturer_name || chipInfo?.manufacturer_name || (manufacturerId === null ? "--" : (registry[String(manufacturerId)] || unassigned[String(manufacturerId)] || `厂家 ID ${manufacturerId}`));
  return {
    manufacturer: formatManufacturerName(manufacturerName, manufacturerId),
    model: chipInfo?.model === null || chipInfo?.model === undefined ? "--" : String(chipInfo.model),
    hardware: chipInfo?.hardware_version === null || chipInfo?.hardware_version === undefined ? "--" : String(chipInfo.hardware_version),
    software: chipInfo?.software_version === null || chipInfo?.software_version === undefined
      ? (software === null ? "--" : String(software))
      : String(chipInfo.software_version)
  };
}

function cvTargetVehicleLabel(vehicle) {
  const address = vehicle.address === undefined || vehicle.address === null || vehicle.address === ""
    ? "-"
    : String(vehicle.address);
  const name = vehicle.name || vehicle.full_name || "未命名车辆";
  return `${address} - ${name}`;
}

function formatManufacturerName(name, manufacturerId) {
  if (manufacturerId === null || manufacturerId === undefined || manufacturerId === "") {
    return name || "--";
  }
  return `${name || "未知厂家"} (${manufacturerId})`;
}

function numericResult(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const numeric = Number(value);
  return Number.isInteger(numeric) ? numeric : null;
}
