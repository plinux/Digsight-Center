export function buildCabWorkspaceHandlers(context) {
  const {
    operationMode,
    operationModeName,
    leftVehicles,
    rightVehicles,
    appState,
    actions,
    functionIconCatalog
  } = context;
  if (operationMode === "dc") {
    return {
      emptyText: "DC 模式不显示车辆"
    };
  }
  return {
    emptyText: `当前 ${operationModeName(operationMode)} 模式暂无车辆，请导入对应的配置文件`,
    cabVehicles: {left: leftVehicles, right: rightVehicles},
    vehicles: appState.vehicles || [],
    consists: appState.consists || [],
    categories: appState.categories || [],
    functionIconCatalog,
    ...actions
  };
}
