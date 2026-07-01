export async function initializeApp({
  appState,
  elements,
  getCapabilities,
  renderControllerCapabilities,
  renderImportCapabilities,
  setFunctionIconCatalog,
  loadFunctionIconCatalog,
  getCvMetadata,
  refreshState,
  readControllerInfo,
  setStatus,
  controllerReadStatusMessage,
  controllerReadStatusDetail,
  formatError,
  persistentConfigurationStatus
}) {
  appState.capabilities = await getCapabilities();
  renderControllerCapabilities(elements, appState);
  renderImportCapabilities(elements, appState.capabilities);
  setFunctionIconCatalog(await loadFunctionIconCatalog(appState.capabilities));
  appState.cvMetadata = await getCvMetadata();
  await refreshState();
  const persistentStatus = persistentConfigurationStatus?.();
  if (persistentStatus) {
    setStatus(persistentStatus);
    return;
  }
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
  runImportConfigWorkflow,
  setActiveView,
  setOperationMode,
  setProgrammingTarget,
  setGatewayBusy,
  openStatusDetailDialog,
  syncControllerEndpoint,
  runControllerStatusRetry,
  setTrackPower,
  readControllerInfo,
  resetSelectedControllerConfig,
  setStatus,
  operationModeName,
  refreshState,
  formatError,
  toggleVehicleSelectionMode,
  createNewVehicle,
  deleteSelectedVehicles,
  clearAllVehicles,
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
      const result = await runControllerStatusRetry({
        requiresFreshStatus: true,
        requestFn: () => setTrackPower(true),
        setStatus,
        readControllerInfo,
        refreshState
      });
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

  elements.resetControllerConfigButton.addEventListener("click", resetSelectedControllerConfig);

  elements.importConfigButton.addEventListener("click", () => runImportConfigWorkflow({
    elements,
    appState,
    importConfig,
    setStatus,
    refreshState,
    formatError
  }));
  elements.selectVehiclesButton.addEventListener("click", toggleVehicleSelectionMode);
  elements.addVehicleButton.addEventListener("click", createNewVehicle);
  elements.deleteVehiclesButton.addEventListener("click", deleteSelectedVehicles);
  elements.clearVehiclesButton.addEventListener("click", clearAllVehicles);

  document.addEventListener("keydown", handleVehicleKeyboard);
  document.addEventListener("keyup", handleVehicleKeyboardRelease);
}
