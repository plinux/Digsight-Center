export function buildCabWorkspaceActions({
  appState,
  activateCab,
  selectCabVehicle,
  chooseVehicleFromSelectionGrid,
  toggleVehicleSelection,
  showVehicleEditor,
  toggleCabExpanded,
  toggleCabFunctionNumbers,
  toggleCabFunctionLabels,
  switchCabConsistMember,
  renderAll,
  saveCustomVehicleOrder,
  setStatus,
  formatError,
  setDraggedVehicleId,
  sendCabSpeed,
  clampSpeed,
  sendCabFunctionByMode
}) {
  return {
    onActivateCab: activateCab,
    onSelectVehicle: selectCabVehicle,
    onChooseVehicle: chooseVehicleFromSelectionGrid,
    selectionMode: appState.vehicleDeletionSelectionMode,
    selectedVehicleIds: appState.selectedVehicleIds,
    onToggleVehicleSelection: toggleVehicleSelection,
    onEdit: showVehicleEditor,
    onToggleCabExpanded: toggleCabExpanded,
    onToggleCabFunctionNumbers: toggleCabFunctionNumbers,
    onToggleCabFunctionLabels: toggleCabFunctionLabels,
    onSwitchConsistMember: switchCabConsistMember,
    onCabCategoryFilter: (cabId, categoryId) => {
      const cab = appState.cabs[cabId];
      cab.categoryId = categoryId;
      renderAll();
    },
    onCabSortChange: (cabId, sortKey, sortDirection) => {
      const cab = appState.cabs[cabId];
      cab.sortKey = sortKey;
      cab.sortDirection = sortDirection;
      renderAll();
    },
    onVehicleDragStart: (_cabId, vehicleId, event) => {
      setDraggedVehicleId(vehicleId);
      event.dataTransfer?.setData("text/plain", vehicleId);
    },
    onVehicleDragOver: (_cabId, _vehicleId, event) => {
      event.preventDefault();
    },
    onVehicleDrop: async (cabId, vehicleId, event, orderedVehicleIds = []) => {
      event.preventDefault();
      try {
        await saveCustomVehicleOrder(cabId, vehicleId, orderedVehicleIds);
      } catch (error) {
        setStatus(formatError(error));
      } finally {
        setDraggedVehicleId("");
      }
    },
    onDirection: async (cabId, direction) => {
      const cab = appState.cabs[cabId];
      cab.direction = direction;
      await sendCabSpeed(cabId, cab.speed, direction);
    },
    onSpeedPreview: (cabId, speed, direction) => {
      const cab = appState.cabs[cabId];
      if (!cab) {
        return;
      }
      appState.activeCabId = cabId;
      cab.speed = clampSpeed(speed);
      cab.direction = direction;
    },
    onSpeed: async (cabId, speed, direction) => {
      const cab = appState.cabs[cabId];
      cab.speed = clampSpeed(speed);
      cab.direction = direction;
      await sendCabSpeed(cabId, cab.speed, direction);
    },
    onEmergencyStop: async (cabId) => {
      const cab = appState.cabs[cabId];
      cab.speed = 0;
      await sendCabSpeed(cabId, 0, cab.direction);
    },
    onFunction: async (cabId, functionNumber, eventType = "click") => {
      await sendCabFunctionByMode(cabId, functionNumber, eventType);
    }
  };
}
