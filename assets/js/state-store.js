function createCabState() {
  return {
    vehicleId: "",
    speed: 0,
    direction: "forward",
    functions: {},
    memberIndex: null,
    expanded: false,
    showFunctionNumbers: true,
    showFunctionLabels: true,
    thumbnailMode: false,
    categoryId: "",
    sortKey: "custom",
    sortDirection: "asc"
  };
}

export const appState = {
  capabilities: {
    default_controller_kind: "",
    default_import_format: "",
    controllers: [],
    import_formats: []
  },
  controller: {},
  controllerInfo: {},
  cvMetadata: null,
  vehicles: [],
  functions: [],
  categories: [],
  consists: [],
  lastError: null,
  selectedVehicleId: "",
  editingVehicleId: "",
  editingVehicleDraft: null,
  vehicleDeletionSelectionMode: false,
  selectedVehicleIds: new Set(),
  activeView: "vehicle",
  vehicleSubview: "registry",
  activeCabId: "left",
  cabs: {
    left: createCabState(),
    right: createCabState()
  },
  dcControl: {
    voltageV: 0,
    direction: "forward"
  }
};

export function replaceState(nextState) {
  appState.controller = nextState.controller || {};
  const dcControl = nextState.controller?.dc_control || {};
  appState.dcControl = {
    voltageV: Number(dcControl.voltage_v ?? appState.dcControl?.voltageV ?? 0),
    direction: dcControl.direction === "reverse" ? "reverse" : "forward"
  };
  appState.vehicles = nextState.vehicles || [];
  appState.functions = nextState.functions || [];
  appState.categories = nextState.categories || [];
  appState.consists = nextState.consists || [];
  appState.lastError = nextState.last_error || null;
  ensureCabVehicles();
}

function ensureCabVehicles() {
  const existingIds = new Set(appState.vehicles.map((vehicle) => vehicle.id));
  if (!appState.cabs[appState.activeCabId]) {
    appState.activeCabId = "left";
  }
  for (const cab of Object.values(appState.cabs)) {
    if (typeof cab.showFunctionNumbers !== "boolean") {
      cab.showFunctionNumbers = true;
    }
    if (typeof cab.showFunctionLabels !== "boolean") {
      cab.showFunctionLabels = true;
    }
    if (typeof cab.thumbnailMode !== "boolean") {
      cab.thumbnailMode = false;
    }
    if (!("memberIndex" in cab)) {
      cab.memberIndex = null;
    }
    if (cab.vehicleId && !existingIds.has(cab.vehicleId)) {
      cab.vehicleId = "";
      cab.speed = 0;
      cab.functions = {};
      cab.memberIndex = null;
    }
  }
  if (appState.editingVehicleId && !existingIds.has(appState.editingVehicleId)) {
    if (appState.editingVehicleId !== "__new_vehicle__") {
      appState.editingVehicleId = "";
      appState.editingVehicleDraft = null;
    }
  }
  if (!appState.cabs.left.vehicleId && appState.vehicles[0]) {
    appState.cabs.left.vehicleId = appState.vehicles[0].id;
  }
  if (!appState.cabs.right.vehicleId && appState.vehicles[1]) {
    appState.cabs.right.vehicleId = appState.vehicles[1].id;
  }
  appState.selectedVehicleId = appState.cabs[appState.activeCabId]?.vehicleId || appState.cabs.left.vehicleId || "";
}
