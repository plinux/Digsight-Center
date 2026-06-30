"""Gateway capability descriptor payloads."""

def gateway_capabilities(controller_registry, import_registry) -> dict:
  return {
    "default_controller_kind": controller_registry.default_kind,
    "default_import_format": import_registry.default_format,
    "controllers": controller_registry.descriptors(),
    "import_formats": import_registry.descriptors(),
  }
