export function sortedConsistMembers(consist, vehicles = []) {
  const byId = new Map((vehicles || []).map((vehicle) => [String(vehicle.id), vehicle]));
  return [...(consist?.members || [])]
    .sort((left, right) => Number(left.order || 0) - Number(right.order || 0))
    .map((member) => ({...member, vehicle: byId.get(String(member.vehicle_id))}))
    .filter((member) => member.vehicle);
}
