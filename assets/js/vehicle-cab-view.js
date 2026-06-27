import {sortedConsistMembers} from "./consist-helpers.js";
import {FALLBACK_FUNCTION_ICON_CATALOG} from "./function-icon-catalog.js";
import {bindVerticalSlider, setVerticalSliderFill} from "./vertical-slider.js";
import {
  findConsistForVehicle,
  formatVehicleField,
  resolveFunctionIcon,
  vehicleFunctions,
  vehicleImage,
  vehicleText
} from "./vehicle-view.js";

let draggedVehicleRow = null;

export function renderVehicleControlWorkspace(container, vehicles, functions, cabState, handlers = {}) {
  const previousListScroll = captureCabVehicleListScroll(container);
  container.replaceChildren();

  if (!vehicles.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = handlers.emptyText || "暂无车辆，请先导入 Z21 配置";
    container.append(empty);
    return;
  }

  const workspace = document.createElement("div");
  workspace.className = "cab-workspace";
  const leftVehicles = handlers.cabVehicles?.left || vehicles;
  const rightVehicles = handlers.cabVehicles?.right || vehicles;
  workspace.append(
    renderCabColumn("left", "左控制台", leftVehicles, functions, cabState, handlers),
    renderCabColumn("right", "右控制台", rightVehicles, functions, cabState, handlers)
  );
  container.append(workspace);
  restoreCabVehicleListScroll(workspace, previousListScroll);
}

function captureCabVehicleListScroll(container) {
  const positions = {};
  for (const cabId of ["left", "right"]) {
    const list = container.querySelector(`.cab-column[data-cab-id="${cabId}"] .cab-vehicle-list`);
    if (list) {
      positions[cabId] = list.scrollTop;
    }
  }
  return positions;
}

function restoreCabVehicleListScroll(workspace, positions) {
  for (const [cabId, scrollTop] of Object.entries(positions)) {
    if (!Number.isFinite(scrollTop)) {
      continue;
    }
    const list = workspace.querySelector(`.cab-column[data-cab-id="${cabId}"] .cab-vehicle-list`);
    if (list) {
      list.scrollTop = scrollTop;
    }
  }
}

function renderCabColumn(cabId, titleText, vehicles, functions, cabState, handlers) {
  const cab = cabState.cabs?.[cabId] || {};
  const selectedVehicle = vehicles.find((vehicle) => vehicle.id === cab.vehicleId) || null;
  const showFunctionNumbers = cab.showFunctionNumbers !== false;
  const showFunctionLabels = cab.showFunctionLabels !== false;
  const section = document.createElement("section");
  section.className = `cab-column ${cabState.activeCabId === cabId ? "active-cab" : ""}`;
  section.dataset.cabId = cabId;
  section.addEventListener("pointerdown", (event) => {
    if (!isCabActivationTarget(event.target)) {
      return;
    }
    handlers.onActivateCab?.(cabId);
  });

  const header = document.createElement("div");
  header.className = "cab-header";
  const title = document.createElement("h2");
  title.textContent = titleText;
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "cab-toggle-control";
  toggle.textContent = cab.expanded ? "返回列表" : "展开控制";
  toggle.disabled = !selectedVehicle || !showFunctionLabels;
  toggle.title = showFunctionLabels ? "" : "隐藏功能名称时默认显示全部功能控制";
  toggle.addEventListener("click", (event) => {
    event.stopPropagation();
    handlers.onToggleCabExpanded?.(cabId);
  });
  const headerControls = document.createElement("div");
  headerControls.className = "cab-header-controls";
  headerControls.append(renderCabFilters(cabId, cab, handlers.categories || [], handlers), toggle);
  header.append(title, headerControls);

  section.append(header);
  const context = selectedVehicle ? resolveCabConsistContext(selectedVehicle, cab, functions, handlers) : null;
  const controlPanel = selectedVehicle ? renderCabControlPanel(cabId, selectedVehicle, cab, context.functions, handlers, {
    expanded: Boolean(cab.expanded && showFunctionLabels),
    showFunctionNumbers,
    showFunctionLabels,
    context,
    displayVehicle: context.displayVehicle,
    maxFunctionNumber: context.maxFunctionNumber
  }) : null;
  if (controlPanel) {
    section.append(controlPanel);
  }
  section.append(renderCabVehicleList(cabId, vehicles, cab, cabState, handlers));
  return section;
}

function renderCabFilters(cabId, cab, categories, handlers) {
  const bar = document.createElement("div");
  bar.className = "cab-filter-bar";
  const showFunctionNumbers = cab.showFunctionNumbers !== false;
  const showFunctionLabels = cab.showFunctionLabels !== false;

  const numberToggle = cabToggleButton({
    className: "cab-function-number-toggle",
    active: showFunctionNumbers,
    label: "显示功能编号",
    activeTitle: "功能键显示编号",
    inactiveTitle: "功能键隐藏编号",
    onClick: () => handlers.onToggleCabFunctionNumbers?.(cabId)
  });

  const nameToggle = cabToggleButton({
    className: "cab-function-label-toggle",
    active: showFunctionLabels,
    label: "显示功能名称",
    activeTitle: "功能键显示名称",
    inactiveTitle: "功能键只显示编号和图标",
    onClick: () => handlers.onToggleCabFunctionLabels?.(cabId)
  });

  const category = document.createElement("select");
  category.append(option("", "全部分类"));
  for (const item of categories) {
    category.append(option(item.id, item.name));
  }
  category.value = String(cab.categoryId || "");
  category.addEventListener("change", () => handlers.onCabCategoryFilter?.(cabId, category.value));

  const sort = document.createElement("select");
  for (const [value, label] of [["custom", "自定义排序"], ["created_at", "添加时间"], ["address", "车辆号"], ["name", "车辆名称"], ["railway", "局段"]]) {
    sort.append(option(value, label));
  }
  sort.value = cab.sortKey || "custom";
  sort.addEventListener("change", () => handlers.onCabSortChange?.(cabId, sort.value, cab.sortDirection || "asc"));

  const direction = document.createElement("button");
  direction.type = "button";
  direction.textContent = cab.sortDirection === "desc" ? "降序" : "升序";
  direction.addEventListener("click", () => {
    handlers.onCabSortChange?.(cabId, cab.sortKey || "custom", cab.sortDirection === "desc" ? "asc" : "desc");
  });

  bar.append(numberToggle, nameToggle, category, sort, direction);
  return bar;
}

function cabToggleButton({className, active, label, activeTitle, inactiveTitle, onClick}) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.classList.toggle("active", active);
  button.textContent = label;
  button.setAttribute("aria-pressed", active ? "true" : "false");
  button.title = active ? activeTitle : inactiveTitle;
  button.addEventListener("click", onClick);
  return button;
}

function option(value, label) {
  const item = document.createElement("option");
  item.value = value;
  item.textContent = label;
  return item;
}

function renderCabVehicleList(cabId, vehicles, cab, cabState, handlers) {
  const list = document.createElement("div");
  list.className = "cab-vehicle-list";
  list.addEventListener("dragover", (event) => {
    const targetRow = event.target?.closest?.(".cab-vehicle-row");
    if (!targetRow || targetRow === draggedVehicleRow) {
      return;
    }
    event.preventDefault();
    renderDragInsertionPreview(list, targetRow, event);
    handlers.onVehicleDragOver?.(cabId, targetRow.dataset.vehicleId, event);
  });
  list.addEventListener("drop", (event) => {
    const targetRow = event.target?.closest?.(".cab-vehicle-row");
    if (!targetRow && !draggedVehicleRow) {
      return;
    }
    event.preventDefault();
    const vehicleId = targetRow?.dataset.vehicleId || draggedVehicleRow?.dataset.vehicleId || "";
    const orderedVehicleIds = orderedVehicleIdsFromList(list);
    handlers.onVehicleDrop?.(cabId, vehicleId, event, orderedVehicleIds);
    clearDragPreview();
  });
  for (const vehicle of vehicles) {
    list.append(renderCabVehicleRow(cabId, vehicle, cab, cabState, handlers));
  }
  return list;
}

function renderCabVehicleRow(cabId, vehicle, cab, cabState, handlers) {
  const isSelected = cab.vehicleId === vehicle.id;
  const isMultiSelected = handlers.selectedVehicleIds?.has?.(vehicle.id) || false;
  const selectionMode = Boolean(handlers.selectionMode);
  const disabledByOtherCab = selectedByOtherCab(cabId, cabState, vehicle.id);
  const row = document.createElement("div");
  row.className = `cab-vehicle-row ${isSelected ? "selected" : ""}`;
  row.dataset.vehicleId = String(vehicle.id);
  row.draggable = true;
  row.classList.toggle("multi-selected", isMultiSelected);
  row.classList.toggle("disabled-by-other-cab", disabledByOtherCab && !selectionMode);
  row.setAttribute("aria-disabled", disabledByOtherCab && !selectionMode ? "true" : "false");
  row.addEventListener("click", () => {
    selectCabVehicle({cabId, vehicle, disabledByOtherCab, selectionMode, handlers});
  });
  if (selectionMode) {
    row.append(renderCabVehicleSelectionCheckbox(vehicle, isMultiSelected, handlers));
  }
  const select = document.createElement("button");
  select.type = "button";
  select.className = "cab-vehicle-select";
  select.disabled = disabledByOtherCab && !selectionMode;
  select.setAttribute("aria-disabled", disabledByOtherCab && !selectionMode ? "true" : "false");
  select.setAttribute("aria-pressed", isSelected ? "true" : "false");
  select.title = `选择 ${vehicle.name || "未命名车辆"} 作为${cabId === "left" ? "左控制台" : "右控制台"}当前控制车辆`;
  select.append(vehicleImage(vehicle), vehicleText(vehicle, handlers));
  select.addEventListener("click", (event) => {
    event.stopPropagation();
    selectCabVehicle({cabId, vehicle, disabledByOtherCab, selectionMode, handlers});
  });
  const {statusSlot, disabledBadge} = renderCabVehicleStatusBadges({isSelected, disabledByOtherCab});
  if (disabledBadge) {
    select.append(disabledBadge);
  }
  const {edit, drag} = renderCabVehicleRowActions(vehicle, handlers);
  row.addEventListener("dragstart", (event) => {
    if (disabledByOtherCab) {
      event.preventDefault();
      return;
    }
    draggedVehicleRow = row;
    row.classList.add("dragging");
    event.dataTransfer?.setData("text/plain", vehicle.id);
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = "move";
    }
    handlers.onVehicleDragStart?.(cabId, vehicle.id, event);
  });
  row.addEventListener("dragend", clearDragPreview);
  row.append(select, statusSlot, edit, drag);
  return row;
}

function renderCabVehicleSelectionCheckbox(vehicle, isMultiSelected, handlers) {
  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.className = "vehicle-multi-select";
  checkbox.checked = isMultiSelected;
  checkbox.addEventListener("click", (event) => {
    event.stopPropagation();
    handlers.onToggleVehicleSelection?.(vehicle.id);
  });
  return checkbox;
}

function selectCabVehicle({cabId, vehicle, disabledByOtherCab, selectionMode, handlers}) {
  if (selectionMode) {
    handlers.onToggleVehicleSelection?.(vehicle.id);
    return;
  }
  if (disabledByOtherCab) {
    return;
  }
  handlers.onSelectVehicle?.(cabId, vehicle.id);
}

function renderCabVehicleStatusBadges({isSelected, disabledByOtherCab}) {
  const statusSlot = document.createElement("span");
  statusSlot.className = "cab-current-badge-slot";
  if (isSelected) {
    const badge = document.createElement("span");
    badge.className = "cab-current-badge";
    badge.textContent = "当前控制";
    statusSlot.append(badge);
  }
  let disabledBadge = null;
  if (disabledByOtherCab) {
    disabledBadge = document.createElement("span");
    disabledBadge.className = "cab-disabled-badge";
    disabledBadge.textContent = "另一侧已选";
  }
  return {statusSlot, disabledBadge};
}

function renderCabVehicleRowActions(vehicle, handlers) {
  const edit = document.createElement("button");
  edit.type = "button";
  edit.className = "cab-vehicle-edit";
  edit.textContent = "编辑";
  edit.addEventListener("click", (event) => {
    event.stopPropagation();
    handlers.onEdit?.(vehicle.id);
  });
  const drag = document.createElement("button");
  drag.type = "button";
  drag.className = "vehicle-drag-handle";
  drag.draggable = true;
  drag.title = "拖动调整自定义排序";
  drag.textContent = "☰";
  drag.addEventListener("click", (event) => event.stopPropagation());
  drag.addEventListener("pointerdown", (event) => event.stopPropagation());
  return {edit, drag};
}

function isCabActivationTarget(target) {
  return !target?.closest?.("button, input, select, textarea, label, .cab-vehicle-row, .cab-control-panel, .cab-filter-bar");
}

function renderDragInsertionPreview(list, targetRow, event) {
  if (!draggedVehicleRow || targetRow === draggedVehicleRow) {
    return;
  }
  const rect = targetRow.getBoundingClientRect();
  const insertAfter = event.clientY > rect.top + rect.height / 2;
  list.insertBefore(draggedVehicleRow, insertAfter ? targetRow.nextSibling : targetRow);
}

function orderedVehicleIdsFromList(list) {
  return Array.from(list.querySelectorAll(".cab-vehicle-row"))
    .map((row) => row.dataset.vehicleId)
    .filter(Boolean);
}

function clearDragPreview() {
  draggedVehicleRow?.classList.remove("dragging");
  draggedVehicleRow = null;
}

function resolveCabConsistContext(selectedVehicle, cab, functions, handlers) {
  const base = {
    controlVehicle: selectedVehicle,
    displayVehicle: selectedVehicle,
    functionVehicle: selectedVehicle,
    functions: vehicleFunctions(functions, selectedVehicle.id),
    consist: null,
    members: [],
    memberIndex: null,
    maxFunctionNumber: cab.showFunctionLabels === false ? 31 : 9
  };
  if (Number(selectedVehicle.type ?? 0) !== 3) {
    return base;
  }
  const consist = findConsistForVehicle(selectedVehicle.id, handlers.consists || []);
  const members = sortedConsistMembers(consist, handlers.vehicles || []);
  base.consist = consist;
  base.members = members;
  if (selectedVehicle.sync_function_control) {
    return base;
  }
  const memberIndex = Number.isInteger(cab.memberIndex) ? cab.memberIndex : null;
  const member = memberIndex === null ? null : members[memberIndex] || null;
  if (!member) {
    return {
      ...base,
      functions: [{function_number: 0, label: "", icon_name: "function-generic", is_configured: true, position: 0}],
      memberIndex: null,
      maxFunctionNumber: 0
    };
  }
  return {
    ...base,
    displayVehicle: member.vehicle,
    functionVehicle: member.vehicle,
    functions: vehicleFunctions(functions, member.vehicle.id),
    memberIndex
  };
}

function renderConsistImageSwitcher(cabId, image, context, handlers) {
  if (!context?.consist || context.controlVehicle?.sync_function_control || !context.members?.length) {
    return image;
  }
  const switcher = document.createElement("div");
  switcher.className = "cab-consist-image-switcher";
  const previous = document.createElement("button");
  previous.type = "button";
  previous.textContent = "‹";
  previous.title = "上一台成员车";
  previous.addEventListener("click", () => handlers.onSwitchConsistMember?.(cabId, -1));
  const next = document.createElement("button");
  next.type = "button";
  next.textContent = "›";
  next.title = "下一台成员车";
  next.addEventListener("click", () => handlers.onSwitchConsistMember?.(cabId, 1));
  switcher.append(previous, image, next);
  return switcher;
}

function renderCabControlPanel(cabId, vehicle, cab, functions, handlers, options = {}) {
  const panel = document.createElement("section");
  panel.className = "cab-control-panel";
  const showFunctionNumbers = options.showFunctionNumbers !== false;
  const showFunctionLabels = options.showFunctionLabels !== false;
  const displayVehicle = options.displayVehicle || vehicle;
  const context = options.context || {};

  const mainRow = document.createElement("div");
  mainRow.className = "cab-control-main-row";

  const media = document.createElement("div");
  media.className = "cab-control-media";
  const image = document.createElement("div");
  image.className = "cab-control-image";
  image.append(vehicleImage(displayVehicle));
  media.append(renderConsistImageSwitcher(cabId, image, context, handlers));

  const infoColumn = document.createElement("div");
  infoColumn.className = "cab-control-info";
  const identity = renderCabIdentity(vehicle, context);
  infoColumn.append(identity);

  const speedControl = renderCabSpeedControl(cabId, vehicle, cab, handlers);
  const functionGrid = renderCabFunctionGrid(cabId, functions, cab, handlers, {
    maxFunctionNumber: options.maxFunctionNumber,
    showFunctionLabels,
    showFunctionNumbers
  });
  const sideActions = renderCabDirectionActions(cabId, cab, handlers, speedControl);
  mainRow.append(infoColumn, media, functionGrid, sideActions);

  panel.append(mainRow);
  if (options.expanded && showFunctionLabels) {
    const extraGrid = renderCabFunctionGrid(cabId, functions, cab, handlers, {
      expanded: true,
      showFunctionLabels,
      showFunctionNumbers
    });
    if (extraGrid.childElementCount) {
      panel.append(extraGrid);
    }
  }
  return panel;
}

function renderCabIdentity(vehicle, context) {
  const identity = document.createElement("div");
  identity.className = "cab-control-identity";
  const nameLine = document.createElement("strong");
  nameLine.className = "cab-control-identity-line cab-control-identity-primary cab-control-vehicle-name";
  nameLine.textContent = vehicle.name || "未命名车辆";
  const addressLine = document.createElement("span");
  addressLine.className = "cab-control-identity-line cab-control-address-row";
  const addressBadge = document.createElement("span");
  addressBadge.className = "cab-control-address-badge";
  addressBadge.textContent = formatCabAddressText(vehicle, context);
  const fullNameTag = cabControlInfoTag(formatVehicleField(vehicle.full_name), "cab-control-full-name-tag", "完整名称");
  addressLine.append(addressBadge, fullNameTag);
  const metaLine = document.createElement("span");
  metaLine.className = "cab-control-identity-line cab-control-meta-row";
  const brandTag = cabControlInfoTag(formatVehicleField(vehicle.brand), "cab-control-meta-tag", "品牌");
  const articleNumberTag = cabControlInfoTag(formatVehicleField(vehicle.article_number), "cab-control-meta-tag", "货号");
  metaLine.append(brandTag, articleNumberTag);
  identity.append(nameLine, addressLine, metaLine);
  return identity;
}

function renderCabSpeedControl(cabId, vehicle, cab, handlers) {
  const speed = Number(cab.speed || 0);
  const speedControl = document.createElement("div");
  speedControl.className = "cab-speed-control";
  const speedValue = document.createElement("strong");
  speedValue.className = "cab-speed-value";
  speedValue.textContent = formatCabSpeedValue(speed, vehicle.max_speed);
  const throttle = document.createElement("div");
  throttle.className = "cab-speed-throttle";
  throttle.tabIndex = 0;
  throttle.setAttribute("role", "slider");
  throttle.setAttribute("aria-label", "速度");
  throttle.setAttribute("aria-valuemin", "0");
  throttle.setAttribute("aria-valuemax", "126");
  const throttleFill = document.createElement("div");
  throttleFill.className = "cab-speed-throttle-fill";
  throttle.append(throttleFill);
  let pendingSpeed = speed;
  updateCabSpeedThrottleFill(throttle, speed);
  const previewThrottleSpeed = (nextSpeed) => {
    pendingSpeed = clampCabSpeedStep(nextSpeed);
    updateCabSpeedThrottleFill(throttle, pendingSpeed);
    speedValue.textContent = formatCabSpeedValue(pendingSpeed, vehicle.max_speed);
    handlers.onSpeedPreview?.(cabId, pendingSpeed, cab.direction || "forward");
  };
  const commitThrottleSpeed = (nextSpeed) => {
    pendingSpeed = clampCabSpeedStep(nextSpeed);
    updateCabSpeedThrottleFill(throttle, pendingSpeed);
    speedValue.textContent = formatCabSpeedValue(pendingSpeed, vehicle.max_speed);
    handlers.onSpeed?.(cabId, pendingSpeed, cab.direction || "forward");
  };
  bindVerticalSlider(throttle, {
    maxValue: 126,
    normalizeValue: clampCabSpeedStep,
    currentValue: () => pendingSpeed,
    homeValue: 0,
    endValue: 126,
    keySteps: {
      ArrowUp: 1,
      ArrowRight: 1,
      PageUp: 10,
      ArrowDown: -1,
      ArrowLeft: -1,
      PageDown: -10
    },
    onPointerDown: () => handlers.onActivateCab?.(cabId, {render: false}),
    onPreview: previewThrottleSpeed,
    onCommit: commitThrottleSpeed
  });
  speedControl.append(speedValue, throttle);
  return speedControl;
}

function renderCabFunctionGrid(cabId, functions, cab, handlers, options = {}) {
  const showFunctionNumbers = options.showFunctionNumbers !== false;
  const showFunctionLabels = options.showFunctionLabels !== false;
  const functionGrid = document.createElement("div");
  functionGrid.className = options.expanded
    ? "function-grid function-extra-grid"
    : `function-grid cab-function-grid ${showFunctionLabels ? "show-function-labels" : "show-all-functions hide-function-labels"}`;
  if (!options.expanded) {
    functionGrid.dataset.showFunctionLabels = showFunctionLabels ? "true" : "false";
  }
  const functionIconCatalog = handlers.functionIconCatalog || FALLBACK_FUNCTION_ICON_CATALOG;
  const slotOptions = {maxFunctionNumber: showFunctionLabels ? 9 : 31};
  if (Number.isFinite(options.maxFunctionNumber)) {
    slotOptions.maxFunctionNumber = options.maxFunctionNumber;
  }
  const slots = options.expanded ? buildExpandedFunctionSlots(functions) : buildFunctionSlots(functions, slotOptions.maxFunctionNumber);
  for (const fn of slots) {
    if (fn.visible === false) {
      functionGrid.append(renderEmptyFunctionSlot(fn.function_number));
      continue;
    }
    functionGrid.append(renderFunctionSlotButton(
      fn,
      resolveFunctionIcon(fn, functionIconCatalog),
      (eventType) => handlers.onFunction?.(cabId, fn.function_number, eventType),
      {enabled: cab.functions?.[String(fn.function_number)], showLabel: options.expanded ? true : showFunctionLabels, showNumber: showFunctionNumbers}
    ));
  }
  return functionGrid;
}

function renderCabDirectionActions(cabId, cab, handlers, speedControl) {
  const reverse = segmentButton("←", cab.direction === "reverse", () => handlers.onDirection?.(cabId, "reverse"));
  reverse.title = "后退";
  reverse.setAttribute("aria-label", "后退");
  const forward = segmentButton("→", cab.direction !== "reverse", () => handlers.onDirection?.(cabId, "forward"));
  forward.title = "前进";
  forward.setAttribute("aria-label", "前进");
  const directionRow = document.createElement("div");
  directionRow.className = "cab-direction-row";
  directionRow.append(reverse, forward);

  const stop = document.createElement("button");
  stop.type = "button";
  stop.className = "danger cab-economic-stop";
  stop.textContent = "紧急停车";
  stop.addEventListener("click", () => handlers.onEmergencyStop?.(cabId));
  const sideActions = document.createElement("div");
  sideActions.className = "cab-control-side-actions";
  sideActions.append(speedControl, directionRow, stop);
  return sideActions;
}

function formatCabSpeedValue(speedStep, maxSpeed) {
  const step = clampCabSpeedStep(speedStep);
  if (Number(maxSpeed) > 0) {
    const scaled = Math.round((step / 126) * Number(maxSpeed));
    return `${scaled} km/h`;
  }
  return String(step);
}

function cabControlInfoTag(valueText, className, labelText) {
  const tag = document.createElement("span");
  tag.className = className;
  tag.dataset.label = labelText;
  tag.textContent = labelText === "完整名称" ? valueText : `${labelText} ${valueText}`;
  tag.title = `${labelText} ${valueText}`;
  tag.setAttribute("aria-label", `${labelText} ${valueText}`);
  return tag;
}

function clampCabSpeedStep(speedStep) {
  return Math.max(0, Math.min(126, Math.round(Number(speedStep || 0))));
}

function updateCabSpeedThrottleFill(throttle, speedStep) {
  const step = clampCabSpeedStep(speedStep);
  setVerticalSliderFill(throttle, "--speed-fill-percent", (step / 126) * 100, step);
}

function formatCabAddressText(vehicle, context = {}) {
  if (Number(vehicle?.type ?? 0) === 3 && context.consist) {
    if (context.memberIndex !== null && context.displayVehicle) {
      return String(context.displayVehicle.address || "--");
    }
    const addresses = (context.members || [])
      .map((member) => member.address || member.vehicle?.address)
      .filter((address) => address !== null && address !== undefined && String(address).trim() !== "")
      .map((address) => String(address));
    return addresses.slice(0, 3).join("|") || "--";
  }
  return String(vehicle?.address || "--");
}

export function renderLocoControl(container, vehicle, functions, control, handlers = {}) {
  container.replaceChildren();
  if (!vehicle) {
    container.hidden = true;
    return;
  }
  container.hidden = false;
  const toolbar = subviewToolbar("车辆控制", handlers.onBack);
  const shell = document.createElement("div");
  shell.className = "loco-control";
  const imagePanel = document.createElement("div");
  imagePanel.className = "image-preview large";
  imagePanel.append(vehicleImage(vehicle));

  const speedPanel = document.createElement("section");
  speedPanel.className = "speed-panel";
  const name = document.createElement("h2");
  name.textContent = `${vehicle.name} / ${vehicle.address}`;
  const gauge = document.createElement("meter");
  gauge.className = "speed-gauge";
  gauge.min = "0";
  gauge.max = "126";
  gauge.value = String(control.speed || 0);
  const speedText = document.createElement("strong");
  speedText.textContent = `${control.speed || 0}`;
  const slider = document.createElement("input");
  slider.type = "range";
  slider.min = "0";
  slider.max = "126";
  slider.value = String(control.speed || 0);
  slider.addEventListener("input", () => handlers.onSpeed?.(Number(slider.value), control.direction || "forward"));
  const directionRow = document.createElement("div");
  directionRow.className = "segmented";
  const reverse = segmentButton("←", control.direction === "reverse", () => handlers.onDirection?.("reverse"));
  reverse.title = "后退";
  reverse.setAttribute("aria-label", "后退");
  const forward = segmentButton("→", control.direction !== "reverse", () => handlers.onDirection?.("forward"));
  forward.title = "前进";
  forward.setAttribute("aria-label", "前进");
  directionRow.append(reverse, forward);
  const stop = document.createElement("button");
  stop.type = "button";
  stop.className = "danger";
  stop.textContent = "紧急停车";
  stop.addEventListener("click", () => handlers.onEmergencyStop?.());
  speedPanel.append(name, gauge, speedText, slider, directionRow, stop);

  const functionPanel = document.createElement("section");
  functionPanel.className = "function-grid";
  const functionIconCatalog = handlers.functionIconCatalog || FALLBACK_FUNCTION_ICON_CATALOG;
  for (const fn of functions) {
    const button = document.createElement("button");
    button.type = "button";
    const icon = resolveFunctionIcon(fn, functionIconCatalog);
    appendFunctionButtonContent(button, fn, icon);
    button.addEventListener("click", () => handlers.onFunction?.(fn.function_number, true));
    functionPanel.append(button);
  }
  if (!functions.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "暂无功能键";
    functionPanel.append(empty);
  }
  shell.append(imagePanel, speedPanel, functionPanel);
  container.append(toolbar, shell);
}

export function renderDcControl(container, dcControl, handlers = {}) {
  container.hidden = false;
  container.replaceChildren();

  const maxVoltage = normalizeDcMaxVoltage(dcControl.maxVoltageV);
  const voltage = clampDcVoltage(dcControl.voltageV, maxVoltage);
  const direction = dcControl.direction || "forward";
  const panel = document.createElement("section");
  panel.className = "dc-control-panel";

  const title = document.createElement("h2");
  title.textContent = "DC 控制";

  const voltageValue = document.createElement("div");
  voltageValue.className = "dc-voltage-value";
  voltageValue.textContent = formatDcVoltage(voltage);

  const slider = document.createElement("div");
  slider.className = "dc-voltage-slider";
  slider.tabIndex = 0;
  slider.setAttribute("role", "slider");
  slider.setAttribute("aria-label", "DC 电压");
  slider.setAttribute("aria-valuemin", "0");
  slider.setAttribute("aria-valuemax", maxVoltage.toFixed(1));
  const sliderFill = document.createElement("div");
  sliderFill.className = "dc-voltage-slider-fill";
  slider.append(sliderFill);
  let pendingVoltage = voltage;
  updateDcVoltageSliderFill(slider, voltage, maxVoltage);
  const previewVoltage = (nextVoltage) => {
    pendingVoltage = clampDcVoltage(nextVoltage, maxVoltage);
    updateDcVoltageSliderFill(slider, pendingVoltage, maxVoltage);
    voltageValue.textContent = formatDcVoltage(pendingVoltage);
    handlers.onVoltagePreview?.(pendingVoltage);
  };
  const commitVoltage = (nextVoltage) => {
    pendingVoltage = clampDcVoltage(nextVoltage, maxVoltage);
    updateDcVoltageSliderFill(slider, pendingVoltage, maxVoltage);
    voltageValue.textContent = formatDcVoltage(pendingVoltage);
    handlers.onVoltage?.(pendingVoltage, direction);
  };
  bindVerticalSlider(slider, {
    maxValue: () => normalizeDcMaxVoltage(maxVoltage),
    normalizeValue: (value) => clampDcVoltage(value, maxVoltage),
    currentValue: () => pendingVoltage,
    homeValue: 0,
    endValue: maxVoltage,
    keySteps: {
      ArrowUp: 0.1,
      ArrowRight: 0.1,
      PageUp: 1,
      ArrowDown: -0.1,
      ArrowLeft: -0.1,
      PageDown: -1
    },
    onPreview: previewVoltage,
    onCommit: commitVoltage
  });

  const directionRow = document.createElement("div");
  directionRow.className = "dc-direction-row";
  for (const [direction, label] of [["reverse", "←"], ["forward", "→"]]) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.className = dcControl.direction === direction ? "active" : "";
    button.addEventListener("click", () => handlers.onDirection?.(direction));
    directionRow.append(button);
  }

  const stop = document.createElement("button");
  stop.type = "button";
  stop.className = "danger dc-emergency-stop";
  stop.textContent = "紧急停车";
  stop.addEventListener("click", () => handlers.onEmergencyStop?.());

  panel.append(title, voltageValue, slider, directionRow, stop);
  container.append(panel);
}

function normalizeDcMaxVoltage(maxVoltage) {
  const numeric = Number(maxVoltage);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : 15.2;
}

function clampDcVoltage(voltage, maxVoltage = 15.2) {
  const max = normalizeDcMaxVoltage(maxVoltage);
  const numeric = Number(voltage);
  const bounded = Math.max(0, Math.min(max, Number.isFinite(numeric) ? numeric : 0));
  return Math.round(bounded * 10) / 10;
}

function formatDcVoltage(voltage) {
  return `${Number(voltage || 0).toFixed(1)} V`;
}

function updateDcVoltageSliderFill(slider, voltage, maxVoltage = 15.2) {
  const max = normalizeDcMaxVoltage(maxVoltage);
  const nextVoltage = clampDcVoltage(voltage, max);
  setVerticalSliderFill(
    slider,
    "--dc-voltage-fill-percent",
    (nextVoltage / max) * 100,
    nextVoltage.toFixed(1),
    formatDcVoltage(nextVoltage)
  );
}

export function renderUnsupportedVehicleControl(container, modeName) {
  container.replaceChildren();
  const header = document.createElement("div");
  header.className = "section-title";
  const title = document.createElement("h1");
  title.textContent = "车辆控制";
  const mode = document.createElement("span");
  mode.textContent = modeName;
  header.append(title, mode);
  const empty = document.createElement("p");
  empty.className = "empty-state";
  empty.textContent = "当前模式不支持数码车辆控制";
  container.append(header, empty);
}

function selectedByOtherCab(cabId, cabState, vehicleId) {
  return Object.entries(cabState?.cabs || {}).some(([otherCabId, otherCab]) => {
    return otherCabId !== cabId && String(otherCab?.vehicleId || "") === String(vehicleId || "");
  });
}

function buildFunctionSlots(functions, maxFunctionNumber) {
  const byNumber = new Map(functions.map((fn) => [Number(fn.function_number), fn]));
  const slots = [];
  for (let functionNumber = 0; functionNumber <= maxFunctionNumber; functionNumber += 1) {
    const configured = byNumber.get(functionNumber);
    slots.push({
      function_number: functionNumber,
      label: configured?.label || configured?.shortcut || "",
      shortcut: configured?.shortcut || "",
      image_name: configured?.image_name || "",
      icon_name: configured?.icon_name || "",
      trigger_mode: configured?.trigger_mode || "toggle",
      duration_ms: configured?.duration_ms ?? configured?.time ?? 0,
      show_function_number: true,
      visible: configured?.is_configured !== false,
      configured: Boolean(configured)
    });
  }
  return slots;
}

function buildExpandedFunctionSlots(functions) {
  return buildFunctionSlots(functions, 31).slice(10);
}

function renderEmptyFunctionSlot(functionNumber) {
  const slot = document.createElement("div");
  slot.className = "function-slot-empty";
  slot.setAttribute("aria-label", `F${functionNumber} 未启用`);
  slot.dataset.functionNumber = String(functionNumber);
  return slot;
}

function formatFunctionLabelChunks(text, chunkSize = 4) {
  const characters = Array.from(String(text || "").trim());
  const chunks = [];
  for (let index = 0; index < characters.length; index += chunkSize) {
    chunks.push(characters.slice(index, index + chunkSize).join(""));
  }
  return chunks;
}

function appendFunctionLabelContent(label, labelText) {
  label.replaceChildren();
  const chunks = formatFunctionLabelChunks(labelText);
  chunks.forEach((chunk, index) => {
    if (index > 0) {
      label.append(document.createElement("br"));
    }
    label.append(document.createTextNode(chunk));
  });
}

function renderFunctionSlotButton(fn, icon, onPress, state = {}) {
  const button = document.createElement("button");
  button.type = "button";
  const showNumber = state.showNumber !== false;
  const showLabel = state.showLabel !== false;
  const labelText = String(fn.label || fn.shortcut || "").trim();
  button.className = [
    "function-slot-button",
    showNumber ? "with-number" : "without-number",
    showLabel ? "with-label" : "without-label"
  ].join(" ");
  button.setAttribute("aria-label", `F${fn.function_number}${labelText ? ` ${labelText}` : ""}`);
  const pressed = Boolean(state.enabled);
  button.classList.toggle("active", pressed);
  button.setAttribute("aria-pressed", pressed ? "true" : "false");
  button.dataset.triggerMode = fn.trigger_mode || "toggle";

  const iconSlot = document.createElement("span");
  iconSlot.className = "function-icon-slot";
  if (fn.configured !== false && icon?.path) {
    const image = document.createElement("img");
    image.className = "function-icon";
    image.src = icon.path.startsWith("/") ? icon.path : `/${icon.path}`;
    image.alt = "";
    image.loading = "lazy";
    iconSlot.append(image);
  }

  const key = document.createElement("span");
  key.className = "function-key";
  key.textContent = `F${fn.function_number}`;

  const label = document.createElement("span");
  label.className = "function-label";
  label.title = labelText;
  label.dataset.labelLength = String(Array.from(labelText).length);
  label.classList.toggle("function-label-multiline", Array.from(labelText).length > 4);
  label.classList.toggle("function-label-very-long", Array.from(labelText).length > 8);
  label.classList.toggle("function-label-extra-long", Array.from(labelText).length > 12);
  appendFunctionLabelContent(label, labelText);

  if (showNumber) {
    button.append(key);
  }
  button.append(iconSlot);
  if (showLabel) {
    button.append(label);
  }
  button.addEventListener("pointerdown", () => onPress?.("down"));
  button.addEventListener("pointerup", () => onPress?.("up"));
  button.addEventListener("pointerleave", () => onPress?.("up"));
  button.addEventListener("click", () => onPress?.("click"));
  return button;
}

function appendFunctionButtonContent(button, fn, icon) {
  button.replaceChildren();
  if (icon?.path) {
    const image = document.createElement("img");
    image.className = "function-icon";
    image.src = icon.path.startsWith("/") ? icon.path : `/${icon.path}`;
    image.alt = "";
    image.loading = "lazy";
    button.append(image);
  }
  const label = document.createElement("span");
  label.textContent = `F${fn.function_number} ${fn.label || fn.shortcut || ""}`.trim();
  button.append(label);
}


function segmentButton(text, active, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = active ? "active" : "";
  button.textContent = text;
  button.addEventListener("click", onClick);
  return button;
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
