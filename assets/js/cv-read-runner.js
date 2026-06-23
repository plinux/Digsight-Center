export async function runCvListRead({cvNumbers, shouldCancel, readOne, onRow}) {
  for (let index = 0; index < cvNumbers.length; index += 1) {
    if (shouldCancel()) {
      return {cancelled: true};
    }
    const cvNumber = cvNumbers[index];
    const row = await readOne(cvNumber);
    if (row) {
      onRow(row, cvNumber);
    }
  }
  return {cancelled: false};
}
