export function buildVehicleEditorActions({
  vehicle,
  newVehicleId,
  appState,
  functionsByVehicle,
  showVehicleRegistry,
  renderAll,
  consistForVehicle,
  createVehicle,
  updateVehicle,
  saveVehicleConsist,
  setStatus,
  refreshState,
  formatError,
  deleteVehicle,
  uploadVehicleImage
}) {
  return {
    newVehicleId,
    functionsByVehicle,
    onBack: showVehicleRegistry,
    onTypeChange: (type) => {
      appState.editingVehicleDraft = {...vehicle, ...(appState.editingVehicleDraft || {}), type};
      if (type === 3) {
        appState.editingVehicleDraft.sync_function_control = Boolean(appState.editingVehicleDraft.sync_function_control);
        appState.editingVehicleDraft.consist_kind = appState.editingVehicleDraft.consist_kind || "multiple_unit";
        appState.editingVehicleDraft.energy_type = "";
        appState.editingVehicleDraft.car_subtype = "";
      } else {
        appState.editingVehicleDraft.sync_function_control = false;
        appState.editingVehicleDraft.consist_kind = "";
        if (type === 0) {
          appState.editingVehicleDraft.energy_type = appState.editingVehicleDraft.energy_type || "electric";
          appState.editingVehicleDraft.car_subtype = "";
        } else if (type === 1) {
          appState.editingVehicleDraft.energy_type = "";
          appState.editingVehicleDraft.car_subtype = appState.editingVehicleDraft.car_subtype || "passenger";
        } else {
          appState.editingVehicleDraft.energy_type = "";
          appState.editingVehicleDraft.car_subtype = "";
        }
      }
      renderAll();
    },
    onSave: async (changes) => {
      try {
        const existingConsist = consistForVehicle(vehicle.id);
        let savedVehicle = null;
        if (vehicle.id === newVehicleId) {
          savedVehicle = await createVehicle(changes);
          setStatus("车辆已添加");
        } else {
          savedVehicle = await updateVehicle(vehicle.id, changes);
          setStatus("车辆已保存");
        }
        if (Number(changes.type) === 3) {
          await saveVehicleConsist(changes, savedVehicle.id || vehicle.id);
          setStatus(existingConsist ? "重联/编组已保存" : "重联/编组已创建");
        }
        appState.editingVehicleId = "";
        appState.editingVehicleDraft = null;
        appState.vehicleSubview = "registry";
        await refreshState();
      } catch (error) {
        setStatus(formatError(error));
      }
    },
    onDelete: async () => {
      if (vehicle.id === newVehicleId) {
        showVehicleRegistry();
        return;
      }
      const confirmed = typeof globalThis.confirm === "function"
        ? globalThis.confirm(`确认删除车辆 ${vehicle.name || vehicle.address}？`)
        : false;
      if (!confirmed) {
        return;
      }
      try {
        await deleteVehicle(vehicle.id);
        setStatus("车辆已删除");
        showVehicleRegistry();
        await refreshState();
      } catch (error) {
        setStatus(formatError(error));
      }
    },
    onImageFile: async (file) => {
      try {
        const result = await uploadVehicleImage(file);
        if (vehicle.id === newVehicleId) {
          appState.editingVehicleDraft.image_path = result.image_path;
          setStatus("车辆图片已上传，保存车辆后生效");
          renderAll();
        } else {
          await updateVehicle(vehicle.id, {image_path: result.image_path});
          setStatus("车辆图片已更新");
          await refreshState();
        }
      } catch (error) {
        setStatus(formatError(error));
      }
    }
  };
}
