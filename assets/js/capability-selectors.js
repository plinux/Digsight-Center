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

export function renderControllerKindOptions(elements, capabilities = {}) {
  const options = asArray(capabilities.controllers);
  if (!options.length) {
    appendEmptyOption(elements.controllerKindSelect, "无可用控制器");
    return;
  }

  const defaultKind = options.some((item) => item.kind === capabilities.default_controller_kind)
    ? capabilities.default_controller_kind
    : options[0].kind;
  const currentValue = elements.controllerKindSelect.value;
  elements.controllerKindSelect.disabled = false;
  elements.controllerKindSelect.replaceChildren(...options.map((item) => {
    const option = document.createElement("option");
    option.value = item.kind;
    option.textContent = item.label;
    return option;
  }));
  elements.controllerKindSelect.value = options.some((item) => item.kind === currentValue)
    ? currentValue
    : defaultKind;
}

export function renderImportFormatOptions(elements, capabilities = {}) {
  const options = asArray(capabilities.import_formats);
  if (!options.length) {
    appendEmptyOption(elements.importFormatSelect, "无可用导入格式");
    elements.importConfigFileInput.accept = "";
    return;
  }

  const defaultFormat = options.some((item) => item.format === capabilities.default_import_format)
    ? capabilities.default_import_format
    : options[0].format;
  const currentValue = elements.importFormatSelect.value;
  elements.importFormatSelect.disabled = false;
  elements.importFormatSelect.replaceChildren(...options.map((item) => {
    const option = document.createElement("option");
    option.value = item.format;
    option.textContent = item.label;
    return option;
  }));
  elements.importFormatSelect.value = options.some((item) => item.format === currentValue)
    ? currentValue
    : defaultFormat;
  const selected = options.find((item) => item.format === elements.importFormatSelect.value);
  elements.importConfigFileInput.accept = selected?.extensions?.length ? selected.extensions.join(",") : "";
}
