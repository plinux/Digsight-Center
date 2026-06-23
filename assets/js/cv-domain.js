export function cvNumbersFromSource(source) {
  const values = Array.isArray(source)
    ? source
    : (source && typeof source === "object" ? Object.keys(source) : []);
  return values
    .map((value) => Number(value))
    .filter((value) => Number.isInteger(value) && value >= 1 && value <= 1024);
}

export function sortedUniqueCvNumbers(numbers) {
  return Array.from(new Set(numbers)).sort((left, right) => left - right);
}
