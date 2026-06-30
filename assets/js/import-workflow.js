import {renderImportFormatOptions} from "./capability-selectors.js";

export function renderImportCapabilities(elements, capabilities = {}) {
  renderImportFormatOptions(elements, capabilities);
}

export async function runImportConfigWorkflow({
  elements,
  appState,
  importConfig,
  setStatus,
  refreshState,
  formatError
}) {
  return importSelectedConfigFile({
    elements,
    capabilities: appState.capabilities,
    importConfig,
    setStatus,
    refreshState,
    formatError
  });
}

export async function importSelectedConfigFile({
  elements,
  capabilities = {},
  importConfig,
  setStatus,
  refreshState,
  formatError = (error) => error.message || String(error)
}) {
  const file = elements.importConfigFileInput.files[0];
  if (!file) {
    setStatus("请选择配置文件");
    return;
  }
  try {
    const importFormat = elements.importFormatSelect.value || capabilities.default_import_format || "";
    if (!importFormat) {
      setStatus("暂无可用导入格式");
      return;
    }
    const importResult = await importConfig(importFormat, file);
    const summary = importResult.summary || importResult;
    setStatus(`导入完成：${summary.vehicles_imported} 辆车，${summary.functions_imported} 个功能键，${summary.categories_imported || 0} 个分类`);
    await refreshState();
  } catch (error) {
    setStatus(formatError(error));
  }
}
