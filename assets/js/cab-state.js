export function vehicleSelectedByOtherCabState(cabs, cabId, vehicleId) {
  return Object.entries(cabs || {}).some(([otherCabId, otherCab]) => {
    return otherCabId !== cabId && String(otherCab?.vehicleId || "") === String(vehicleId || "");
  });
}
