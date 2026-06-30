function asArray(value) {
  return Array.isArray(value) ? value : [];
}

function appendEmptyOption(select, label) {
  const option = document.createElement("option");
  option.value = "";
  option.textContent = label;
  select.replaceChildren(option);
  select.value = "";
  select.disabled = true;
}

function selectedDescriptorValue(options, key, currentValue, defaultValue) {
  if (options.some((item) => item[key] === currentValue)) {
    return currentValue;
  }
  if (options.some((item) => item[key] === defaultValue)) {
    return defaultValue;
  }
  return options[0][key];
}

export function renderControllerKindOptions(elements, capabilities = {}) {
  const options = asArray(capabilities.controllers);
  if (!options.length) {
    appendEmptyOption(elements.controllerKindSelect, "无可用控制器");
    return;
  }

  const currentValue = elements.controllerKindSelect.value;
  elements.controllerKindSelect.disabled = false;
  elements.controllerKindSelect.replaceChildren(...options.map((item) => {
    const option = document.createElement("option");
    option.value = item.kind;
    option.textContent = item.display_name || item.label || item.kind;
    return option;
  }));
  elements.controllerKindSelect.value = selectedDescriptorValue(
    options,
    "kind",
    currentValue,
    capabilities.default_controller_kind,
  );
}

export function renderImportFormatOptions(elements, capabilities = {}) {
  const options = asArray(capabilities.import_formats);
  if (!options.length) {
    appendEmptyOption(elements.importFormatSelect, "无可用导入格式");
    elements.importConfigFileInput.accept = "";
    return;
  }

  const currentValue = elements.importFormatSelect.value;
  elements.importFormatSelect.disabled = false;
  elements.importFormatSelect.replaceChildren(...options.map((item) => {
    const option = document.createElement("option");
    option.value = item.format;
    option.textContent = item.label;
    return option;
  }));
  elements.importFormatSelect.value = selectedDescriptorValue(
    options,
    "format",
    currentValue,
    capabilities.default_import_format,
  );
  const selected = options.find((item) => item.format === elements.importFormatSelect.value);
  elements.importConfigFileInput.accept = selected?.extensions?.length ? selected.extensions.join(",") : "";
}
