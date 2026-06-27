export async function initializeApp({
  appState,
  elements,
  getCapabilities,
  renderControllerKindOptions,
  renderImportFormatOptions,
  setFunctionIconCatalog,
  loadFunctionIconCatalog,
  getCvMetadata,
  refreshState,
  readControllerInfo,
  setStatus,
  controllerReadStatusMessage,
  controllerReadStatusDetail,
  formatError
}) {
  appState.capabilities = await getCapabilities();
  renderControllerKindOptions(elements, appState.capabilities);
  renderImportFormatOptions(elements, appState.capabilities);
  setFunctionIconCatalog(await loadFunctionIconCatalog());
  appState.cvMetadata = await getCvMetadata();
  await refreshState();
  setStatus("正在读取控制器信息");
  try {
    const result = await readControllerInfo();
    setStatus(controllerReadStatusMessage(result), controllerReadStatusDetail(result));
    await refreshState();
  } catch (error) {
    const formatted = formatError(error);
    setStatus(
      `本地后端已就绪，控制器信息启动读取失败：${typeof formatted === "object" ? formatted.summary : formatted}`,
      typeof formatted === "object" ? formatted.detail : ""
    );
  }
}

export function wireAppEvents({
  elements,
  appState,
  importConfig,
  setActiveView,
  setOperationMode,
  setProgrammingTarget,
  setGatewayBusy,
  openStatusDetailDialog,
  syncControllerEndpoint,
  runTrackPowerRequestWithStatusRetry,
  setTrackPower,
  setStatus,
  operationModeName,
  refreshState,
  formatError,
  importSelectedConfigFile,
  toggleVehicleSelectionMode,
  createNewVehicle,
  deleteSelectedVehicles,
  handleVehicleKeyboard,
  handleVehicleKeyboardRelease
}) {
  elements.navVehicleControl.addEventListener("click", () => setActiveView("vehicle"));
  elements.navCvProgramming.addEventListener("click", () => setActiveView("cv"));
  elements.navControllerSettings.addEventListener("click", () => setActiveView("controller"));
  for (const button of elements.operationModeButtons) {
    button.addEventListener("click", () => setOperationMode(button.dataset.trackMode));
  }
  for (const button of elements.programmingTargetButtons) {
    button.addEventListener("click", () => setProgrammingTarget(button.dataset.programmingTarget));
  }

  globalThis.addEventListener?.("digsight:gateway-busy", (event) => {
    setGatewayBusy(Boolean(event.detail?.active));
  });

  elements.statusDetailButton?.addEventListener("click", openStatusDetailDialog);

  elements.statusDetailCloseButton?.addEventListener("click", () => {
    elements.statusDetailDialog?.close();
  });

  elements.powerOnButton.addEventListener("click", async () => {
    try {
      await syncControllerEndpoint();
      const result = await runTrackPowerRequestWithStatusRetry(true, () => setTrackPower(true));
      setStatus(`${operationModeName(result.track_mode)} 轨道已通电`);
      await refreshState();
    } catch (error) {
      setStatus(formatError(error));
    }
  });

  elements.powerOffButton.addEventListener("click", async () => {
    try {
      await syncControllerEndpoint();
      const result = await setTrackPower(false);
      setStatus(`${operationModeName(result.track_mode)} 轨道已断电`);
      await refreshState();
    } catch (error) {
      setStatus(formatError(error));
    }
  });

  elements.importConfigButton.addEventListener("click", () => importSelectedConfigFile({
    elements,
    capabilities: appState.capabilities,
    importConfig,
    setStatus,
    refreshState,
    formatError
  }));
  elements.selectVehiclesButton.addEventListener("click", toggleVehicleSelectionMode);
  elements.addVehicleButton.addEventListener("click", createNewVehicle);
  elements.deleteVehiclesButton.addEventListener("click", deleteSelectedVehicles);

  document.addEventListener("keydown", handleVehicleKeyboard);
  document.addEventListener("keyup", handleVehicleKeyboardRelease);
}
