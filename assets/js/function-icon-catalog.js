export const FALLBACK_FUNCTION_ICON_CATALOG = {
  version: 1,
  default_icon: "function-generic",
  icons: {
    "function-generic": {
      path: "assets/icons/functions/function-generic.svg",
      label: "功能",
      source: "local-generated",
      license: "project-local",
      keywords: ["功能", "未分类"]
    }
  },
  mappings: {}
};

function uniqueStrings(values) {
  return [...new Set((values || []).filter((value) => typeof value === "string" && value.trim()))];
}

function functionIconMappingFiles(capabilities = {}) {
  const importFormats = Array.isArray(capabilities?.import_formats) ? capabilities.import_formats : [];
  return uniqueStrings(importFormats.flatMap((descriptor) => (
    Array.isArray(descriptor?.function_icon_mapping_files) ? descriptor.function_icon_mapping_files : []
  )));
}

export async function loadFunctionIconCatalog(capabilities = {}, fetchImpl = globalThis.fetch) {
  if (typeof fetchImpl !== "function") {
    return FALLBACK_FUNCTION_ICON_CATALOG;
  }
  try {
    const mappingFiles = functionIconMappingFiles(capabilities);
    const [catalogResponse, ...mappingResponses] = await Promise.all([
      fetchImpl("/config/function-icons.json", {cache: "no-store"}),
      ...mappingFiles.map((path) => fetchImpl(path, {cache: "no-store"}))
    ]);
    if (!catalogResponse.ok) {
      return FALLBACK_FUNCTION_ICON_CATALOG;
    }
    const catalog = await catalogResponse.json();
    if (!catalog || typeof catalog.icons !== "object") {
      return FALLBACK_FUNCTION_ICON_CATALOG;
    }
    const mappings = {};
    for (const response of mappingResponses) {
      if (!response.ok) {
        continue;
      }
      const mapping = await response.json();
      Object.assign(mappings, mapping?.mappings || {});
    }
    return {...catalog, mappings};
  } catch (_error) {
    return FALLBACK_FUNCTION_ICON_CATALOG;
  }
}
