import {sortedConsistMembers} from "./consist-helpers.js";
import {FALLBACK_FUNCTION_ICON_CATALOG} from "./function-icon-catalog.js";
import {
  VEHICLE_TYPE_LABELS,
  vehicleKindIcon
} from "./vehicle-kind-icons.js";

export function renderVehicleRegistry(container, vehicles, handlers = {}) {
  container.replaceChildren();
  const header = document.createElement("div");
  header.className = "section-title";
  const count = document.createElement("span");
  count.textContent = `${vehicles.length} 辆`;
  header.append(count);

  const grid = document.createElement("div");
  grid.className = "vehicle-grid";
  for (const vehicle of vehicles) {
    const card = document.createElement("article");
    card.className = "vehicle-card";
    card.append(vehicleImage(vehicle), vehicleText(vehicle, handlers));
    const actions = document.createElement("div");
    actions.className = "card-actions";
    const edit = document.createElement("button");
    edit.type = "button";
    edit.textContent = "编辑";
    edit.addEventListener("click", () => handlers.onEdit?.(vehicle.id));
    const control = document.createElement("button");
    control.type = "button";
    control.textContent = "控制";
    control.addEventListener("click", () => handlers.onControl?.(vehicle.id));
    actions.append(edit, control);
    card.append(actions);
    grid.append(card);
  }
  if (!vehicles.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "暂无车辆";
    grid.append(empty);
  }
  container.append(header, grid);
}

export function resolveFunctionIcon(functionEntry = {}, catalog = FALLBACK_FUNCTION_ICON_CATALOG) {
  const mappings = catalog.mappings || {};
  const icons = catalog.icons || {};
  const exactCandidates = [
    functionEntry.icon_name,
    functionEntry.image_name,
    functionEntry.label,
    functionEntry.shortcut
  ].filter(Boolean).map((value) => String(value).trim());
  for (const candidate of exactCandidates) {
    const iconKey = mappings[candidate];
    if (iconKey && icons[iconKey]) {
      return {key: iconKey, ...icons[iconKey]};
    }
    if (icons[candidate]) {
      return {key: candidate, ...icons[candidate]};
    }
  }
  const searchable = exactCandidates.join(" ").toLowerCase();
  for (const [iconKey, icon] of Object.entries(icons)) {
    for (const keyword of icon.keywords || []) {
      if (searchable.includes(String(keyword).toLowerCase())) {
        return {key: iconKey, ...icon};
      }
    }
  }
  const defaultKey = catalog.default_icon || "function-generic";
  return {key: defaultKey, ...(icons[defaultKey] || FALLBACK_FUNCTION_ICON_CATALOG.icons["function-generic"])};
}

export function findConsistForVehicle(vehicleId, consists) {
  return (consists || []).find((consist) => String(consist.control_vehicle_id || "") === String(vehicleId || "")) || null;
}

export function vehicleText(vehicle, context = {}) {
  const block = document.createElement("div");
  block.className = "vehicle-text";
  const name = document.createElement("h2");
  const addressBadge = document.createElement("strong");
  addressBadge.className = "vehicle-address-badge";
  const addressText = formatVehicleAddressBadgeText(vehicle, context);
  addressBadge.textContent = addressText;
  addressBadge.title = Number(vehicle?.type ?? 0) === 3 ? `编组成员车号 ${addressText}` : `车辆编号 ${addressText}`;
  addressBadge.setAttribute("aria-label", addressBadge.title);
  const displayName = document.createElement("span");
  displayName.className = "vehicle-display-name";
  displayName.textContent = vehicle.name || "未命名车辆";
  const kindIcon = vehicleKindIcon(vehicle);
  const fullNameTag = document.createElement("span");
  fullNameTag.className = "vehicle-full-name-tag";
  fullNameTag.textContent = formatVehicleField(vehicle.full_name);
  fullNameTag.title = `完整名称 ${formatVehicleField(vehicle.full_name)}`;
  fullNameTag.setAttribute("aria-label", `完整名称 ${formatVehicleField(vehicle.full_name)}`);
  name.append(addressBadge, displayName, kindIcon, fullNameTag);
  if (vehicle.max_speed) {
    const speedTag = document.createElement("span");
    speedTag.className = "vehicle-meta-tag vehicle-max-speed-tag";
    speedTag.textContent = `${vehicle.max_speed} km/h`;
    speedTag.title = `最高速度 ${vehicle.max_speed} km/h`;
    speedTag.setAttribute("aria-label", `最高速度 ${vehicle.max_speed} km/h`);
    name.append(speedTag);
  }
  const detail = document.createElement("p");
  detail.className = "vehicle-detail-line";
  const brand = formatVehicleField(vehicle.brand);
  const railway = formatVehicleField(vehicle.railway);
  const articleNumber = formatVehicleField(vehicle.article_number);
  const categories = formatVehicleCategories(vehicle);
  detail.append(
    detailTag("品牌", brand),
    detailTag("局段", railway),
    detailTag("货号", articleNumber),
    detailTag("分类", categories)
  );
  block.append(name, detail);
  return block;
}

function detailTag(labelText, valueText) {
  const tag = document.createElement("span");
  tag.className = "vehicle-detail-tag";
  const label = document.createElement("span");
  label.className = "vehicle-detail-label";
  label.textContent = labelText;
  const value = document.createElement("span");
  value.className = "vehicle-detail-value";
  value.textContent = valueText;
  tag.title = `${labelText} ${valueText}`;
  tag.append(label, value);
  return tag;
}

export function formatVehicleField(value) {
  const text = String(value ?? "").trim();
  return text || "-";
}

export function formatVehicleAddressBadgeText(vehicle, context = {}) {
  if (Number(vehicle?.type ?? 0) !== 3) {
    return formatVehicleField(vehicle?.address);
  }
  const consist = findConsistForVehicle(vehicle.id, context.consists || []);
  const members = sortedConsistMembers(consist, context.vehicles || []);
  const addresses = members
    .map((member) => member.address || member.vehicle?.address)
    .filter((address) => address !== null && address !== undefined && String(address).trim() !== "")
    .map((address) => String(address));
  return addresses.slice(0, 3).join("|") || "-";
}

function formatVehicleCategories(vehicle) {
  const names = (vehicle.categories || [])
    .map((category) => String(category.name || "").trim())
    .filter(Boolean);
  return names.join("、") || "-";
}

export function vehicleFunctions(functions, vehicleId) {
  return functions
    .filter((fn) => fn.vehicle_id === vehicleId)
    .sort((left, right) => Number(left.position || 0) - Number(right.position || 0));
}

export function vehicleImage(vehicle) {
  if (vehicle?.image_path) {
    const image = document.createElement("img");
    image.src = vehicle.image_path;
    image.alt = vehicle.name || "车辆图片";
    return image;
  }
  const placeholder = document.createElement("div");
  placeholder.className = "vehicle-placeholder";
  placeholder.textContent = "无图";
  return placeholder;
}
