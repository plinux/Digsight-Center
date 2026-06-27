export function buildLocoRuntimeActions({
  appState,
  controlledVehicle,
  cabVehicle,
  cabFunctionVehicle,
  functionDefinition,
  isDigitalOperationMode,
  syncActiveCabControlState,
  syncControllerEndpoint,
  setLocoSpeed,
  setLocoFunction,
  setStatus,
  formatError,
  renderAll,
  globalScope = globalThis
}) {
  const cabFunctionTimers = new Map();

  async function sendLocoSpeed(speed, direction) {
    const vehicle = controlledVehicle();
    if (!vehicle || !isDigitalOperationMode()) {
      return;
    }
    try {
      await syncControllerEndpoint();
      await setLocoSpeed(vehicle.id, speed, direction);
      setStatus(`速度 ${speed} / ${direction === "reverse" ? "后退" : "前进"}`);
    } catch (error) {
      setStatus(formatError(error));
    } finally {
      renderAll();
    }
  }

  async function sendCabSpeed(cabId, speed, direction) {
    const vehicle = cabVehicle(cabId);
    const cab = appState.cabs[cabId];
    if (!vehicle || !cab || !isDigitalOperationMode()) {
      return;
    }
    appState.activeCabId = cabId;
    appState.selectedVehicleId = vehicle.id;
    syncActiveCabControlState(cabId);
    try {
      await syncControllerEndpoint();
      await setLocoSpeed(vehicle.id, speed, direction);
      setStatus(`${cabStatusLabel(cabId)}：${vehicle.name} 速度 ${speed} / ${direction === "reverse" ? "后退" : "前进"}`);
    } catch (error) {
      setStatus(formatError(error));
    } finally {
      renderAll();
    }
  }

  async function setCabFunctionState(cabId, functionNumber, enabled) {
    const vehicle = cabVehicle(cabId);
    const targetVehicle = cabFunctionVehicle(cabId);
    const cab = appState.cabs[cabId];
    if (!vehicle || !targetVehicle || !cab || !isDigitalOperationMode()) {
      return;
    }
    appState.activeCabId = cabId;
    appState.selectedVehicleId = vehicle.id;
    const functionKey = String(functionNumber);
    const previousEnabled = Boolean(cab.functions[functionKey]);
    cab.functions[functionKey] = Boolean(enabled);
    syncActiveCabControlState(cabId);
    renderAll();
    try {
      await syncControllerEndpoint();
      await setLocoFunction(targetVehicle.id, functionNumber, Boolean(enabled), cab.functions);
      setStatus(`${cabStatusLabel(cabId)}：${targetVehicle.name} F${functionNumber} ${enabled ? "开启" : "关闭"}`);
    } catch (error) {
      cab.functions[functionKey] = previousEnabled;
      syncActiveCabControlState(cabId);
      setStatus(formatError(error));
    } finally {
      renderAll();
    }
  }

  async function sendCabFunction(cabId, functionNumber) {
    const cab = appState.cabs[cabId];
    await setCabFunctionState(cabId, functionNumber, !Boolean(cab?.functions?.[String(functionNumber)]));
  }

  function functionTimerKey(cabId, functionNumber) {
    return `${cabId}:${functionNumber}`;
  }

  function clearCabFunctionTimer(cabId, functionNumber) {
    const key = functionTimerKey(cabId, functionNumber);
    const timer = cabFunctionTimers.get(key);
    if (timer) {
      globalScope.clearTimeout(timer);
      cabFunctionTimers.delete(key);
    }
  }

  async function sendCabFunctionByMode(cabId, functionNumber, eventType = "click") {
    const vehicle = cabVehicle(cabId);
    const targetVehicle = cabFunctionVehicle(cabId);
    const cab = appState.cabs[cabId];
    if (!vehicle || !targetVehicle || !cab || !isDigitalOperationMode()) {
      return;
    }
    const definition = functionDefinition(targetVehicle.id, functionNumber);
    const mode = definition.trigger_mode || "toggle";
    if (mode === "momentary") {
      if (eventType === "down") {
        clearCabFunctionTimer(cabId, functionNumber);
        await setCabFunctionState(cabId, functionNumber, true);
      } else if (eventType === "up") {
        await setCabFunctionState(cabId, functionNumber, false);
      }
      return;
    }
    if (eventType !== "click") {
      return;
    }
    if (mode === "timed") {
      clearCabFunctionTimer(cabId, functionNumber);
      await setCabFunctionState(cabId, functionNumber, true);
      const delay = Math.min(Math.max(Number(definition.duration_ms || 1000), 250), 60000);
      const timer = globalScope.setTimeout(() => {
        cabFunctionTimers.delete(functionTimerKey(cabId, functionNumber));
        setCabFunctionState(cabId, functionNumber, false);
      }, delay);
      cabFunctionTimers.set(functionTimerKey(cabId, functionNumber), timer);
      return;
    }
    clearCabFunctionTimer(cabId, functionNumber);
    await setCabFunctionState(cabId, functionNumber, !Boolean(cab.functions[String(functionNumber)]));
  }

  return {
    sendLocoSpeed,
    sendCabSpeed,
    setCabFunctionState,
    sendCabFunction,
    sendCabFunctionByMode
  };
}

function cabStatusLabel(cabId) {
  return cabId === "left" ? "左控制台" : "右控制台";
}
