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

export async function loadFunctionIconCatalog(fetchImpl = globalThis.fetch) {
  if (typeof fetchImpl !== "function") {
    return FALLBACK_FUNCTION_ICON_CATALOG;
  }
  try {
    const [catalogResponse, mappingResponse] = await Promise.all([
      fetchImpl("/config/function-icons.json", {cache: "no-store"}),
      fetchImpl("/config/function-icon-mappings/z21.json", {cache: "no-store"})
    ]);
    if (!catalogResponse.ok) {
      return FALLBACK_FUNCTION_ICON_CATALOG;
    }
    const catalog = await catalogResponse.json();
    const mapping = mappingResponse.ok ? await mappingResponse.json() : {};
    if (!catalog || typeof catalog.icons !== "object") {
      return FALLBACK_FUNCTION_ICON_CATALOG;
    }
    return {...catalog, mappings: mapping.mappings || {}};
  } catch (_error) {
    return FALLBACK_FUNCTION_ICON_CATALOG;
  }
}
