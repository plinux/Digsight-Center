import {
  VEHICLE_ENERGY_KIND_KEYS,
  VEHICLE_KIND_META,
  VEHICLE_TYPE_LABELS,
  normalizeConsistKind,
  vehicleEnergyGlyph
} from "./vehicle-kind-icons.js";
import {FALLBACK_FUNCTION_ICON_CATALOG} from "./function-icon-catalog.js";
import {renderFunctionIconPicker} from "./function-icon-picker.js";
import {
  findConsistForVehicle,
  vehicleImage
} from "./vehicle-view.js";

export function renderVehicleEditor(container, vehicle, functions, handlers = {}) {
  container.replaceChildren();
  if (!vehicle) {
    container.hidden = true;
    return;
  }
  if (Number(vehicle.type ?? 0) === 3) {
    renderConsistVehicleEditor(container, vehicle, functions, handlers);
    return;
  }
  container.hidden = false;
  const toolbar = subviewToolbar("车辆编辑", handlers.onBack);
  const preview = renderVehicleImageUploader(vehicle, handlers);
  const basicInfoState = renderNormalVehicleBasicInfo(vehicle, handlers);
  const functionEditor = renderFunctionTable(functions, handlers.functionIconCatalog || FALLBACK_FUNCTION_ICON_CATALOG);
  const actionRow = renderVehicleEditorActionRow(handlers);
  const {form} = renderVehicleEditorLayout({
    toolbar,
    preview,
    basicInfo: basicInfoState.basicInfo,
    functionPanel: functionEditor,
    actionRow,
    formClassName: "stack-form vehicle-editor-form",
    leadingContent: basicInfoState.leadingContent
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    handlers.onSave?.(normalVehicleSavePayload(
      basicInfoState.fields,
      vehicle,
      basicInfoState.categoryEditor,
      functionEditor
    ));
  });

  container.append(toolbar, form);
}

function renderNormalVehicleBasicInfo(vehicle, handlers) {
  const basicInfo = document.createElement("div");
  basicInfo.className = "vehicle-editor-basic-info";
  const name = inputField("车辆名称", "text", vehicle.name || "");
  const address = inputField("车辆编号", "number", vehicle.address || 3, {min: 1, max: 9999});
  const fullName = inputField("完整名称", "text", vehicle.full_name || "");
  const scale = selectField("比例", vehicle.track_mode || "ho", [["ho", "HO"], ["n", "N"]]);
  const vehicleType = selectField("车辆类型", String(vehicle.type ?? 0), vehicleTypeOptions());
  const energyType = renderVehicleKindChoiceField("能源类型", vehicle.energy_type || "electric", ["diesel", "electric", "steam", "hybrid"]);
  const carSubtype = renderVehicleKindChoiceField("车厢子类", vehicle.car_subtype || "passenger", ["passenger", "engineering", "inspection", "crane"]);
  const brand = inputField("模型品牌", "text", vehicle.brand || "");
  const maxSpeed = inputField("最高速度 km/h", "number", vehicle.max_speed || "", {min: 0, max: 999});
  const railway = inputField("铁路公司/局段", "text", vehicle.railway || "");
  const articleNumber = inputField("货号", "text", vehicle.article_number || "");
  const decoderType = inputField("芯片型号", "text", vehicle.decoder_type || "");
  const description = inputField("备注", "text", vehicle.description || "");
  const railwayOptions = createVehicleValueDatalist("vehicle-railway-options", handlers.railwayOptions || []);
  const decoderTypeOptions = createVehicleValueDatalist("vehicle-decoder-type-options", handlers.decoderTypeOptions || []);
  railway.input.setAttribute("list", "vehicle-railway-options");
  decoderType.input.setAttribute("list", "vehicle-decoder-type-options");
  name.label.classList.add("vehicle-field-name");
  fullName.label.classList.add("vehicle-field-full-name");
  scale.label.classList.add("vehicle-field-scale");
  vehicleType.label.classList.add("vehicle-field-type");
  energyType.label.classList.add("vehicle-kind-field", "vehicle-energy-field");
  carSubtype.label.classList.add("vehicle-kind-field", "vehicle-car-subtype-field");
  brand.label.classList.add("vehicle-field-brand");
  maxSpeed.label.classList.add("vehicle-field-max-speed");
  address.label.classList.add("vehicle-field-address");
  railway.label.classList.add("vehicle-field-railway");
  articleNumber.label.classList.add("vehicle-field-article-number");
  decoderType.label.classList.add("vehicle-field-decoder-type");
  const kindDynamicFields = document.createElement("div");
  kindDynamicFields.className = "vehicle-kind-dynamic-fields";
  const updateKindFieldVisibility = () => {
    const selectedType = Number(vehicleType.input.value);
    kindDynamicFields.replaceChildren();
    if (selectedType === 0) {
      energyType.input.disabled = false;
      carSubtype.input.disabled = true;
      kindDynamicFields.append(energyType.label);
    } else if (selectedType === 1) {
      energyType.input.disabled = true;
      carSubtype.input.disabled = false;
      kindDynamicFields.append(carSubtype.label);
    } else {
      energyType.input.disabled = true;
      carSubtype.input.disabled = true;
    }
    kindDynamicFields.hidden = kindDynamicFields.childElementCount === 0;
  };
  vehicleType.input.addEventListener("change", () => {
    updateKindFieldVisibility();
    handlers.onTypeChange?.(Number(vehicleType.input.value));
  });

  const nameRow = document.createElement("div");
  nameRow.className = "vehicle-editor-name-row";
  nameRow.append(name.label, fullName.label);
  const kindRow = document.createElement("div");
  kindRow.className = "vehicle-editor-kind-row";
  kindRow.append(vehicleType.label, kindDynamicFields);
  const runningRow = document.createElement("div");
  runningRow.className = "vehicle-editor-running-row";
  runningRow.append(address.label, scale.label, maxSpeed.label, railway.label);
  const modelRow = document.createElement("div");
  modelRow.className = "vehicle-editor-model-row";
  modelRow.append(brand.label, articleNumber.label, decoderType.label);
  const categoryEditor = renderCategoryEditor(vehicle, handlers.categories || []);
  basicInfo.append(
    nameRow,
    kindRow,
    runningRow,
    modelRow,
    description.label,
    categoryEditor
  );
  updateKindFieldVisibility();
  return {
    basicInfo,
    categoryEditor,
    leadingContent: [railwayOptions, decoderTypeOptions],
    fields: {
      name,
      address,
      fullName,
      scale,
      vehicleType,
      energyType,
      carSubtype,
      brand,
      maxSpeed,
      railway,
      articleNumber,
      decoderType,
      description
    }
  };
}

function normalVehicleSavePayload(fields, vehicle, categoryEditor, functionEditor) {
  const {
    name,
    address,
    fullName,
    scale,
    vehicleType,
    energyType,
    carSubtype,
    brand,
    maxSpeed,
    railway,
    articleNumber,
    decoderType,
    description
  } = fields;
  return {
    name: name.input.value.trim(),
    address: Number(address.input.value),
    full_name: fullName.input.value.trim(),
    track_mode: scale.input.value,
    type: Number(vehicleType.input.value),
    sync_function_control: false,
    energy_type: Number(vehicleType.input.value) === 0 ? energyType.input.value : "",
    car_subtype: Number(vehicleType.input.value) === 1 ? carSubtype.input.value : "",
    brand: brand.input.value.trim(),
    max_speed: Number(maxSpeed.input.value || 0) || null,
    railway: railway.input.value.trim(),
    article_number: articleNumber.input.value.trim(),
    decoder_type: decoderType.input.value.trim(),
    description: description.input.value.trim(),
    image_path: vehicle.image_path || "",
    category_ids: collectCategoryIds(categoryEditor),
    functions: collectFunctions(functionEditor)
  };
}

function renderConsistVehicleEditor(container, vehicle, functions, handlers = {}) {
  container.hidden = false;
  const toolbar = subviewToolbar("重联/编组编辑", handlers.onBack);
  const preview = renderVehicleImageUploader(vehicle, handlers);
  const existingConsist = findConsistForVehicle(vehicle.id, handlers.consists || []);
  const basicInfoState = renderConsistBasicInfo(vehicle, handlers, existingConsist);

  const functionPanel = document.createElement("div");
  functionPanel.className = "vehicle-consist-function-panel";
  let functionEditor = renderFunctionTable(functions, handlers.functionIconCatalog || FALLBACK_FUNCTION_ICON_CATALOG);
  const syncFirstMember = document.createElement("button");
  syncFirstMember.type = "button";
  syncFirstMember.textContent = "同步编组内第一台车功能表";
  syncFirstMember.addEventListener("click", () => {
    const firstMember = collectConsistMembers(basicInfoState.memberEditor)[0];
    if (!firstMember) {
      return;
    }
    const firstFunctions = functionsForVehicle(handlers.functionsByVehicle, firstMember.vehicle_id);
    functionEditor = renderFunctionTable(firstFunctions, handlers.functionIconCatalog || FALLBACK_FUNCTION_ICON_CATALOG);
    functionPanel.replaceChildren(syncFirstMember, functionEditor);
  });
  functionPanel.append(syncFirstMember, functionEditor);

  const updateConsistFormState = () => {
    functionPanel.hidden = !basicInfoState.fields.syncFunctionControl.input.checked;
  };
  basicInfoState.fields.syncFunctionControl.input.addEventListener("change", updateConsistFormState);
  basicInfoState.memberEditor.addEventListener("change", updateConsistFormState);
  basicInfoState.memberEditor.addEventListener("click", () => globalThis.setTimeout(updateConsistFormState, 0));
  updateConsistFormState();

  const actionRow = renderVehicleEditorActionRow(handlers);
  const {form} = renderVehicleEditorLayout({
    toolbar,
    preview,
    basicInfo: basicInfoState.basicInfo,
    functionPanel,
    actionRow,
    formClassName: "stack-form vehicle-consist-editor",
    layoutClassName: "vehicle-consist-editor-layout",
    leftColumnClassName: "vehicle-editor-left-column vehicle-consist-editor-left-column",
    functionColumnClassName: "vehicle-editor-function-column vehicle-consist-editor-function-column"
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    handlers.onSave?.(consistVehicleSavePayload(
      basicInfoState.fields,
      vehicle,
      existingConsist,
      basicInfoState.memberEditor,
      basicInfoState.categoryEditor,
      functionEditor
    ));
  });
  container.append(toolbar, form);
}

function renderConsistBasicInfo(vehicle, handlers, existingConsist) {
  const basicInfo = document.createElement("div");
  basicInfo.className = "vehicle-editor-basic-info vehicle-consist-basic-info";
  const name = inputField("编组名称", "text", vehicle.name || existingConsist?.name || "");
  const scale = selectField("比例", vehicle.track_mode || "ho", [["ho", "HO"], ["n", "N"]]);
  const consistKind = renderConsistKindChoiceField(vehicle.consist_kind || existingConsist?.consist_kind || "multiple_unit");
  const syncFunctionControl = checkboxField("同步控制功能", Boolean(vehicle.sync_function_control));
  syncFunctionControl.label.classList.add("sync-toggle-inline");
  name.label.classList.add("vehicle-field-name");
  scale.label.classList.add("vehicle-field-scale");
  const categoryEditor = renderCategoryEditor(vehicle, handlers.categories || []);
  const memberEditor = renderConsistMemberEditor(existingConsist, vehicle, handlers.vehicles || []);

  const consistNameRow = document.createElement("div");
  consistNameRow.className = "vehicle-editor-name-row vehicle-consist-name-row";
  consistNameRow.append(name.label, scale.label, syncFunctionControl.label);
  const consistKindRow = document.createElement("div");
  consistKindRow.className = "vehicle-editor-kind-row vehicle-consist-kind-row";
  consistKindRow.append(consistKind.label);
  basicInfo.append(
    consistNameRow,
    consistKindRow,
    categoryEditor,
    memberEditor
  );
  return {
    basicInfo,
    categoryEditor,
    memberEditor,
    fields: {
      name,
      scale,
      consistKind,
      syncFunctionControl
    }
  };
}

function consistVehicleSavePayload(fields, vehicle, existingConsist, memberEditor, categoryEditor, functionEditor) {
  const {name, scale, consistKind, syncFunctionControl} = fields;
  const members = collectConsistMembers(memberEditor);
  return {
    name: name.input.value.trim(),
    address: Number(vehicle.address || 3),
    full_name: "",
    track_mode: scale.input.value,
    type: 3,
    sync_function_control: syncFunctionControl.input.checked,
    energy_type: "",
    car_subtype: "",
    consist_kind: consistKind.input.value,
    max_speed: null,
    railway: "",
    article_number: "",
    decoder_type: "",
    description: "",
    image_path: vehicle.image_path || "",
    category_ids: collectCategoryIds(categoryEditor),
    functions: syncFunctionControl.input.checked ? collectFunctions(functionEditor) : [],
    consist_members: collectConsistMembers(memberEditor),
    consist: {
      id: existingConsist?.id || "",
      name: name.input.value.trim(),
      track_mode: scale.input.value,
      consist_kind: consistKind.input.value,
      members
    }
  };
}

function renderVehicleEditorLayout({
  toolbar,
  preview,
  basicInfo,
  functionPanel,
  actionRow,
  leadingContent = [],
  formClassName = "stack-form vehicle-editor-form",
  layoutClassName = "vehicle-editor-layout",
  leftColumnClassName = "vehicle-editor-left-column",
  functionColumnClassName = "vehicle-editor-function-column"
}) {
  const form = document.createElement("form");
  form.className = formClassName;
  const layout = document.createElement("div");
  layout.className = `editor-layout ${layoutClassName}`;
  const leftColumn = document.createElement("div");
  leftColumn.className = leftColumnClassName;
  const functionColumn = document.createElement("section");
  functionColumn.className = functionColumnClassName;
  leftColumn.append(preview, basicInfo, actionRow);
  functionColumn.append(functionPanel);
  layout.append(leftColumn, functionColumn);
  form.append(...leadingContent, layout);
  return {toolbar, form, layout, leftColumn, functionColumn};
}

function renderVehicleEditorActionRow(handlers = {}) {
  const actionRow = document.createElement("div");
  actionRow.className = "vehicle-editor-actions";
  const save = document.createElement("button");
  save.type = "submit";
  save.textContent = "保存车辆";
  const deleteVehicleButton = document.createElement("button");
  deleteVehicleButton.type = "button";
  deleteVehicleButton.className = "danger";
  deleteVehicleButton.textContent = handlers.isNew ? "取消" : "删除车辆";
  deleteVehicleButton.addEventListener("click", () => handlers.onDelete?.());
  actionRow.append(save, deleteVehicleButton);
  return actionRow;
}

function renderConsistMemberEditor(consist, controlVehicle, vehicles) {
  const fieldset = document.createElement("fieldset");
  fieldset.className = "vehicle-consist-member-list";
  const legend = document.createElement("legend");
  legend.textContent = "编组成员";
  const rows = document.createElement("div");
  rows.className = "vehicle-consist-member-rows";
  const availableVehicles = vehicles.filter((vehicle) => {
    return String(vehicle.id) !== String(controlVehicle.id)
      && Number(vehicle.type ?? 0) !== 3
      && String(vehicle.track_mode || "").toLowerCase() === String(controlVehicle.track_mode || "").toLowerCase();
  });
  const appendRow = (member = {}) => {
    const row = document.createElement("div");
    row.className = "vehicle-consist-member-row";
    const vehicleSelect = document.createElement("select");
    vehicleSelect.className = "vehicle-consist-member-select";
    vehicleSelect.dataset.pendingValue = String(member.vehicle_id || "");
    const thumb = renderConsistMemberImage(member.vehicle_id, availableVehicles);
    vehicleSelect.addEventListener("change", () => {
      updateConsistMemberImage(thumb, vehicleSelect.value, availableVehicles);
      refreshConsistMemberOptions(rows, availableVehicles);
      fieldset.dispatchEvent(new Event("change", {bubbles: true}));
    });
    const reverse = toggleButtonField("反转运行", member.direction === "reverse");
    reverse.button.addEventListener("click", () => fieldset.dispatchEvent(new Event("change", {bubbles: true})));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "移除";
    remove.addEventListener("click", () => {
      row.remove();
      refreshConsistMemberOptions(rows, availableVehicles);
      fieldset.dispatchEvent(new Event("change", {bubbles: true}));
    });
    row.append(thumb, vehicleSelect, reverse.button, remove);
    rows.append(row);
    refreshConsistMemberOptions(rows, availableVehicles);
  };
  for (const member of consist?.members || []) {
    appendRow(member);
  }
  const add = document.createElement("button");
  add.type = "button";
  add.textContent = "添加车辆";
  add.addEventListener("click", () => {
    appendRow();
    refreshConsistMemberOptions(rows, availableVehicles);
    fieldset.dispatchEvent(new Event("change", {bubbles: true}));
  });
  if (!rows.childElementCount) {
    appendRow();
  }
  fieldset.append(legend, rows, add);
  return fieldset;
}

function refreshConsistMemberOptions(rows, availableVehicles) {
  const selects = Array.from(rows.querySelectorAll(".vehicle-consist-member-select"));
  const selectedVehicleIds = new Set(selects.map((select) => select.value || select.dataset.pendingValue || "").filter(Boolean));
  for (const select of selects) {
    const currentValue = select.value || select.dataset.pendingValue || "";
    select.replaceChildren(option("", "选择车辆"));
    for (const candidate of availableVehicles) {
      const candidateId = String(candidate.id);
      if (selectedVehicleIds.has(candidateId) && candidateId !== currentValue) {
        continue;
      }
      select.append(option(candidateId, renderConsistMemberOptionLabel(candidate)));
    }
    select.value = currentValue;
    select.dataset.pendingValue = "";
  }
}

function renderConsistMemberOptionLabel(vehicle) {
  return `${vehicle.name || vehicle.address} / ${vehicle.address || "-"}`;
}

function renderConsistMemberImage(vehicleId, availableVehicles) {
  const thumb = document.createElement("span");
  thumb.className = "vehicle-consist-member-thumb";
  updateConsistMemberImage(thumb, vehicleId, availableVehicles);
  return thumb;
}

function updateConsistMemberImage(thumb, vehicleId, availableVehicles) {
  const vehicle = (availableVehicles || []).find((candidate) => String(candidate.id) === String(vehicleId || ""));
  thumb.replaceChildren();
  if (vehicle) {
    thumb.append(vehicleImage(vehicle));
    thumb.title = vehicle.name || String(vehicle.address || "");
  } else {
    const placeholder = document.createElement("span");
    placeholder.textContent = "-";
    thumb.append(placeholder);
    thumb.removeAttribute("title");
  }
}

function collectConsistMembers(memberEditor) {
  return Array.from(memberEditor.querySelectorAll(".vehicle-consist-member-row"))
    .map((row, index) => {
      const vehicleId = row.querySelector(".vehicle-consist-member-select")?.value || "";
      const reverse = row.querySelector(".vehicle-consist-reverse-button")?.getAttribute("aria-pressed") === "true";
      return vehicleId ? {
        vehicle_id: vehicleId,
        direction: reverse ? "reverse" : "forward",
        order: index + 1
      } : null;
    })
    .filter(Boolean);
}

function renderVehicleImageUploader(vehicle, handlers) {
  const preview = document.createElement("div");
  preview.className = "image-preview vehicle-image-upload";
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = "image/png,image/jpeg,image/webp";
  fileInput.hidden = true;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "vehicle-image-upload-button";
  if (vehicle?.image_path) {
    button.append(vehicleImage(vehicle));
  } else {
    const add = document.createElement("span");
    add.className = "vehicle-image-add";
    add.textContent = "+";
    const text = document.createElement("span");
    text.textContent = "添加图片";
    button.append(add, text);
  }
  button.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (file) {
      handlers.onImageFile?.(file);
    }
    fileInput.value = "";
  });
  preview.append(button, fileInput);
  return preview;
}

function inputField(text, type, value, attrs = {}) {
  const label = document.createElement("label");
  label.textContent = text;
  const input = document.createElement("input");
  input.type = type;
  input.value = value ?? "";
  for (const [key, attrValue] of Object.entries(attrs)) {
    input.setAttribute(key, attrValue);
  }
  label.append(input);
  return {label, input};
}

function selectField(text, value, options, optionMeta = {}) {
  const label = document.createElement("label");
  label.textContent = text;
  const input = document.createElement("select");
  for (const [optionValue, optionText] of options) {
    const option = document.createElement("option");
    option.value = optionValue;
    const meta = optionMeta[optionValue];
    if (meta?.iconText) {
      option.textContent = `${meta.iconText} ${optionText}`;
    } else {
      option.textContent = optionText;
    }
    option.selected = optionValue === String(value || "").toLowerCase();
    input.append(option);
  }
  if (!input.value && options.length) {
    input.value = options[0][0];
  }
  label.append(input);
  return {label, input};
}

function renderVehicleKindChoiceField(text, value, keys) {
  const label = document.createElement("label");
  label.className = "vehicle-kind-choice-field";
  const caption = document.createElement("span");
  caption.textContent = text;
  const input = document.createElement("input");
  input.type = "hidden";
  input.value = keys.includes(value) ? value : keys[0];
  const grid = document.createElement("div");
  grid.className = "vehicle-kind-choice-grid";
  const buttons = [];
  const syncPressedState = () => {
    for (const button of buttons) {
      const selected = button.dataset.kindKey === input.value;
      button.classList.toggle("selected", selected);
      button.setAttribute("aria-pressed", selected ? "true" : "false");
    }
  };
  for (const key of keys) {
    const meta = VEHICLE_KIND_META[key];
    const button = document.createElement("button");
    button.type = "button";
    button.className = "vehicle-kind-choice";
    button.dataset.kindKey = key;
    const image = document.createElement(VEHICLE_ENERGY_KIND_KEYS.has(key) ? "span" : "img");
    image.className = "vehicle-kind-choice-image";
    if (VEHICLE_ENERGY_KIND_KEYS.has(key)) {
      image.append(vehicleEnergyGlyph(key));
    } else {
      image.src = meta.path.startsWith("/") ? meta.path : `/${meta.path}`;
      image.alt = "";
      image.loading = "lazy";
    }
    const name = document.createElement("span");
    name.textContent = meta.label;
    button.append(image, name);
    button.addEventListener("click", () => {
      input.value = key;
      syncPressedState();
    });
    buttons.push(button);
    grid.append(button);
  }
  syncPressedState();
  label.append(caption, input, grid);
  return {label, input};
}

function renderConsistKindChoiceField(value) {
  const field = renderVehicleKindChoiceField("编组类型", normalizeConsistKind(value), ["multiple_unit", "powered_set", "train_set"]);
  field.label.classList.add("vehicle-consist-kind-field");
  return field;
}

function checkboxField(text, checked) {
  const label = document.createElement("label");
  label.textContent = text;
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = Boolean(checked);
  label.append(input);
  return {label, input};
}

function toggleButtonField(text, pressed) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "vehicle-consist-reverse-button";
  button.textContent = text;
  const syncPressedState = (nextPressed) => {
    button.setAttribute("aria-pressed", nextPressed ? "true" : "false");
    button.classList.toggle("pressed", nextPressed);
  };
  syncPressedState(Boolean(pressed));
  button.addEventListener("click", () => syncPressedState(button.getAttribute("aria-pressed") !== "true"));
  return {button};
}

function vehicleTypeOptions() {
  return [
    ["0", VEHICLE_TYPE_LABELS.get(0)],
    ["1", VEHICLE_TYPE_LABELS.get(1)],
    ["2", VEHICLE_TYPE_LABELS.get(2)],
    ["3", VEHICLE_TYPE_LABELS.get(3)],
    ["4", VEHICLE_TYPE_LABELS.get(4)]
  ];
}

function createVehicleValueDatalist(id, values) {
  const datalist = document.createElement("datalist");
  datalist.id = id;
  for (const value of values) {
    const option = document.createElement("option");
    option.value = value;
    datalist.append(option);
  }
  return datalist;
}

function renderCategoryEditor(vehicle, categories) {
  const fieldset = document.createElement("fieldset");
  fieldset.className = "vehicle-category-editor";
  const legend = document.createElement("legend");
  legend.textContent = "分类";
  fieldset.append(legend);
  const selectedCategoryIds = new Set(vehicle.category_ids || []);
  for (const category of categories) {
    const label = document.createElement("label");
    label.className = selectedCategoryIds.has(category.id) ? "category-pill selected" : "category-pill";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = category.id;
    input.checked = selectedCategoryIds.has(category.id);
    input.className = "sr-only";
    input.addEventListener("change", () => {
      label.classList.toggle("selected", input.checked);
    });
    const text = document.createElement("span");
    text.textContent = category.name;
    label.append(input, text);
    fieldset.append(label);
  }
  if (!categories.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "暂无分类";
    fieldset.append(empty);
  }
  return fieldset;
}

function renderFunctionTable(functions, functionIconCatalog = FALLBACK_FUNCTION_ICON_CATALOG) {
  const slots = buildEditableFunctionSlots(functions, 31);
  const grid = document.createElement("div");
  grid.className = "function-editor-grid";
  grid.append(
    renderFunctionColumn("F0-F15", slots.slice(0, 16), functionIconCatalog),
    renderFunctionColumn("F16-F31", slots.slice(16), functionIconCatalog)
  );
  return grid;
}

function renderFunctionColumn(titleText, slots, functionIconCatalog) {
  const column = document.createElement("section");
  column.className = "function-column";
  const title = document.createElement("h3");
  title.textContent = titleText;
  const table = document.createElement("table");
  table.className = "function-table";
  const colgroup = document.createElement("colgroup");
  for (const className of [
    "function-key-column",
    "function-name-column",
    "function-icon-column",
    "function-trigger-column",
    "function-duration-column",
    "function-enabled-column",
  ]) {
    const col = document.createElement("col");
    col.className = className;
    colgroup.append(col);
  }
  const thead = document.createElement("thead");
  thead.innerHTML = "<tr><th>功能</th><th>名称</th><th>图标</th><th>触发模式</th><th>持续毫秒</th><th>启用</th></tr>";
  const tbody = document.createElement("tbody");
  for (const fn of slots) {
    tbody.append(createFunctionRow(fn, functionIconCatalog));
  }
  table.append(colgroup, thead, tbody);
  column.append(title, table);
  return column;
}

function buildEditableFunctionSlots(functions, maxFunctionNumber) {
  const byNumber = new Map(functions.map((fn) => [Number(fn.function_number), fn]));
  const slots = [];
  for (let functionNumber = 0; functionNumber <= maxFunctionNumber; functionNumber += 1) {
    const configured = byNumber.get(functionNumber) || {};
    slots.push({
      function_number: functionNumber,
      label: configured.label || configured.shortcut || "",
      icon_name: configured.icon_name || configured.image_name || "",
      button_type: configured.button_type ?? 0,
      trigger_mode: configured.trigger_mode || "toggle",
      duration_ms: configured.duration_ms ?? configured.time ?? 0,
      position: functionNumber,
      show_function_number: true,
      is_configured: configured.is_configured ?? true
    });
  }
  return slots;
}

function createFunctionRow(fn, functionIconCatalog) {
  const row = document.createElement("tr");
  row.className = "function-row";
  row.dataset.functionNumber = String(fn.function_number);
  const key = document.createElement("td");
  key.className = "function-key-cell";
  key.textContent = `F${fn.function_number}`;
  row.append(
    key,
    tdInput("text", fn.label || "", "label", {}, "function-name-cell"),
    tdIconPicker(fn, functionIconCatalog),
    triggerModeSelect(fn.trigger_mode || "toggle"),
    durationInput(fn.duration_ms ?? fn.time ?? 0, fn.trigger_mode || "toggle"),
    tdCheckbox(Boolean(fn.is_configured), "is_configured", "function-enabled-cell")
  );
  const triggerSelect = row.querySelector('[data-field="trigger_mode"]');
  const duration = row.querySelector('[data-field="duration_ms"]');
  triggerSelect?.addEventListener("change", () => {
    duration.disabled = triggerSelect.value !== "timed";
  });
  return row;
}

function tdIconPicker(fn, functionIconCatalog) {
  const cell = document.createElement("td");
  cell.className = "function-icon-picker-cell";
  const input = document.createElement("input");
  input.type = "hidden";
  input.value = fn.icon_name || "";
  input.dataset.field = "icon_name";
  const chooseIcon = document.createElement("button");
  chooseIcon.type = "button";
  chooseIcon.className = "function-icon-picker-button";
  chooseIcon.setAttribute("aria-label", "选择功能图标");
  chooseIcon.title = "选择功能图标";
  const preview = document.createElement("span");
  preview.className = "function-icon-picker-preview";
  updateFunctionIconPreview(preview, input.value, functionIconCatalog);
  chooseIcon.addEventListener("click", () => {
    renderFunctionIconPicker(functionIconCatalog, input.value, (iconName) => {
      input.value = iconName;
      updateFunctionIconPreview(preview, iconName, functionIconCatalog);
    });
  });
  chooseIcon.append(preview);
  cell.append(input, chooseIcon);
  return cell;
}

function updateFunctionIconPreview(preview, iconName, functionIconCatalog) {
  preview.replaceChildren();
  const icon = functionIconCatalog.icons?.[iconName] || functionIconCatalog.icons?.[functionIconCatalog.default_icon];
  if (!icon?.path) {
    preview.textContent = "F";
    return;
  }
  const image = document.createElement("img");
  image.className = "function-icon";
  image.src = icon.path.startsWith("/") ? icon.path : `/${icon.path}`;
  image.alt = iconName || functionIconCatalog.default_icon || "function";
  image.loading = "lazy";
  preview.append(image);
}

function triggerModeSelect(value) {
  const cell = document.createElement("td");
  const select = document.createElement("select");
  select.dataset.field = "trigger_mode";
  for (const [mode, label] of [["toggle", "开关"], ["momentary", "点击"], ["timed", "延时"]]) {
    const option = document.createElement("option");
    option.value = mode;
    option.textContent = label;
    option.selected = mode === value;
    select.append(option);
  }
  cell.append(select);
  return cell;
}

function durationInput(value, triggerMode) {
  const cell = tdInput("number", Math.min(Number(value || 0), 60000), "duration_ms", {min: 0}, "function-duration-cell");
  const input = cell.querySelector("input");
  input.setAttribute("max", "60000");
  input.setAttribute("step", "100");
  input.disabled = triggerMode !== "timed";
  return cell;
}

function triggerModeToButtonType(triggerMode) {
  return {
    toggle: 0,
    momentary: 1,
    timed: 2
  }[triggerMode] ?? 0;
}

function tdInput(type, value, name, attrs = {}, className = "") {
  const cell = document.createElement("td");
  if (className) {
    cell.className = className;
  }
  const input = document.createElement("input");
  input.type = type;
  input.value = value;
  input.dataset.field = name;
  for (const [key, attrValue] of Object.entries(attrs)) {
    input.setAttribute(key, attrValue);
  }
  cell.append(input);
  return cell;
}

function tdCheckbox(value, name, className = "") {
  const cell = document.createElement("td");
  if (className) {
    cell.className = className;
  }
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = value;
  input.dataset.field = name;
  cell.append(input);
  return cell;
}

function collectFunctions(table) {
  return Array.from(table.querySelectorAll(".function-row")).map((row, index) => {
    const field = (name) => row.querySelector(`[data-field="${name}"]`);
    const triggerMode = field("trigger_mode").value || "toggle";
    return {
      function_number: Number(row.dataset.functionNumber || index),
      label: field("label").value.trim(),
      icon_name: field("icon_name").value.trim(),
      button_type: triggerModeToButtonType(triggerMode),
      trigger_mode: triggerMode,
      duration_ms: Math.min(Math.max(Number(field("duration_ms").value || 0), 0), 60000),
      position: index,
      show_function_number: true,
      is_configured: field("is_configured").checked
    };
  });
}

function collectCategoryIds(categoryEditor) {
  return Array.from(categoryEditor.querySelectorAll('input[type="checkbox"]:checked'))
    .map((input) => input.value);
}


function subviewToolbar(titleText, onBack) {
  const toolbar = document.createElement("div");
  toolbar.className = "subview-toolbar";
  const back = document.createElement("button");
  back.type = "button";
  back.textContent = "返回";
  back.addEventListener("click", () => onBack?.());
  const title = document.createElement("h1");
  title.textContent = titleText;
  toolbar.append(back, title);
  return toolbar;
}

function option(value, label) {
  const item = document.createElement("option");
  item.value = value;
  item.textContent = label;
  return item;
}

function functionsForVehicle(functionsByVehicle, vehicleId) {
  if (functionsByVehicle instanceof Map) {
    return functionsByVehicle.get(vehicleId) || functionsByVehicle.get(String(vehicleId)) || [];
  }
  return functionsByVehicle?.[vehicleId] || functionsByVehicle?.[String(vehicleId)] || [];
}
