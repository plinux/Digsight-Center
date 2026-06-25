export function buildVehicleEditorHandlers(context) {
  const {vehicle, appState, editorOptions, actions, functionIconCatalog} = context;
  return {
    isNew: vehicle?.id === actions.newVehicleId,
    categories: appState.categories || [],
    vehicles: appState.vehicles || [],
    consists: appState.consists || [],
    functionsByVehicle: actions.functionsByVehicle(),
    railwayOptions: editorOptions.railwayOptions,
    decoderTypeOptions: editorOptions.decoderTypeOptions,
    functionIconCatalog,
    onBack: actions.onBack,
    onTypeChange: actions.onTypeChange,
    onSave: actions.onSave,
    onDelete: actions.onDelete,
    onImageFile: actions.onImageFile
  };
}
