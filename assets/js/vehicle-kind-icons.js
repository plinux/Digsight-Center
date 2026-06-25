export const VEHICLE_KIND_META = {
  diesel: {
    label: "内燃",
    iconText: "油",
    path: "assets/icons/vehicle-types/energy-diesel.svg"
  },
  electric: {
    label: "电力",
    iconText: "电",
    path: "assets/icons/vehicle-types/energy-electric.svg"
  },
  steam: {
    label: "蒸汽",
    iconText: "汽",
    path: "assets/icons/vehicle-types/energy-steam.svg"
  },
  hybrid: {
    label: "混动",
    iconText: "混",
    path: "assets/icons/vehicle-types/energy-hybrid.svg"
  },
  passenger: {
    label: "客车",
    iconText: "客",
    path: "assets/icons/vehicle-types/car-passenger.svg"
  },
  engineering: {
    label: "工程车",
    iconText: "工",
    path: "assets/icons/vehicle-types/car-engineering.svg"
  },
  inspection: {
    label: "检测车",
    iconText: "检",
    path: "assets/icons/vehicle-types/car-inspection.svg"
  },
  crane: {
    label: "起重机",
    iconText: "吊",
    path: "assets/icons/vehicle-types/car-crane.svg"
  },
  multiple_unit: {
    label: "重连机车",
    iconText: "重",
    path: "assets/icons/vehicle-types/consist-multiple-unit.svg"
  },
  powered_set: {
    label: "动集列车",
    iconText: "动",
    path: "assets/icons/vehicle-types/consist-powered-set.svg"
  },
  train_set: {
    label: "列车编组",
    iconText: "列",
    path: "assets/icons/vehicle-types/consist-train-set.svg"
  },
  consist: {
    label: "列车编组",
    iconText: "编",
    path: "assets/icons/vehicle-types/consist-group.svg"
  }
};

export const VEHICLE_TYPE_LABELS = new Map([
  [0, "机车"],
  [1, "车厢"],
  [2, "附件"],
  [3, "重联/编组"],
  [4, "摄像车"]
]);

export const VEHICLE_ENERGY_KIND_KEYS = new Set(["diesel", "electric", "steam", "hybrid"]);

export function normalizeConsistKind(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (["multiple_unit", "powered_set", "train_set"].includes(normalized)) {
    return normalized;
  }
  return normalized === "consist" ? "train_set" : "multiple_unit";
}

function resolveVehicleKindMeta(vehicle = {}) {
  const vehicleType = Number(vehicle.type ?? 0);
  if (vehicleType === 0) {
    return VEHICLE_KIND_META[vehicle.energy_type || "electric"];
  }
  if (vehicleType === 1) {
    return VEHICLE_KIND_META[vehicle.car_subtype || "passenger"];
  }
  if (vehicleType === 3) {
    return VEHICLE_KIND_META[normalizeConsistKind(vehicle.consist_kind)];
  }
  return null;
}

export function vehicleEnergyGlyph(kind) {
  const glyph = document.createElement("span");
  glyph.className = `vehicle-energy-glyph vehicle-energy-${kind}`;

  if (kind === "steam") {
    const steamBase = document.createElement("span");
    steamBase.className = "vehicle-energy-steam-base";
    const boiler = document.createElement("span");
    boiler.className = "vehicle-energy-boiler";
    const cab = document.createElement("span");
    cab.className = "vehicle-energy-cab";
    const smokestack = document.createElement("span");
    smokestack.className = "vehicle-energy-smokestack";
    const smoke = document.createElement("span");
    smoke.className = "vehicle-energy-smoke";
    steamBase.append(boiler, cab, smokestack, smoke);
    glyph.append(steamBase);
    appendVehicleEnergyWheels(glyph, 4);
    return glyph;
  }

  if (kind === "electric" || kind === "hybrid") {
    const pantograph = document.createElement("span");
    pantograph.className = "vehicle-energy-pantograph";
    const pantographDiamond = document.createElement("span");
    pantographDiamond.className = "vehicle-energy-pantograph-diamond";
    pantograph.append(pantographDiamond);
    glyph.append(pantograph);
  }

  const body = document.createElement("span");
  body.className = "vehicle-energy-body";
  if (kind === "electric") {
    const bolt = document.createElement("span");
    bolt.className = "vehicle-energy-bolt";
    body.append(bolt);
  } else {
    const engine = document.createElement("span");
    engine.className = "vehicle-energy-engine";
    body.append(engine);
  }
  glyph.append(body);
  appendVehicleEnergyWheels(glyph, 3);
  return glyph;
}

function appendVehicleEnergyWheels(glyph, count) {
  const wheels = document.createElement("span");
  wheels.className = "vehicle-energy-wheels";
  for (let index = 0; index < count; index += 1) {
    const wheel = document.createElement("span");
    wheel.className = "vehicle-energy-wheel";
    wheels.append(wheel);
  }
  glyph.append(wheels);
  return wheels;
}

export function vehicleKindIcon(vehicle) {
  const meta = resolveVehicleKindMeta(vehicle);
  const icon = document.createElement("span");
  icon.className = "vehicle-type-icon";
  if (!meta?.path) {
    icon.hidden = true;
    return icon;
  }
  const energyKind = Number(vehicle.type ?? 0) === 0 ? String(vehicle.energy_type || "electric") : "";
  if (VEHICLE_ENERGY_KIND_KEYS.has(energyKind)) {
    icon.append(vehicleEnergyGlyph(energyKind));
    icon.title = meta.label;
    icon.setAttribute("aria-label", meta.label);
    return icon;
  }
  const image = document.createElement("img");
  image.className = "vehicle-kind-icon";
  image.src = meta.path.startsWith("/") ? meta.path : `/${meta.path}`;
  image.alt = meta.label;
  image.title = meta.label;
  image.loading = "lazy";
  icon.append(image);
  return icon;
}
