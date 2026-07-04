import assert from "node:assert/strict";
import {importSourceModule} from "./module_import_helpers.mjs";

function jsonBody(request) {
  return JSON.parse(String(request.options.body || "{}"));
}

const requests = [];
globalThis.fetch = async (path, options = {}) => {
  requests.push({path, options});
  return {
    async json() {
      return {ok: true, data: {path}};
    }
  };
};

const gatewayApi = await importSourceModule("assets/js/gateway-api.js");
const cvDomain = await importSourceModule("assets/js/cv-domain.js");
const cvRunner = await importSourceModule("assets/js/cv-read-runner.js");

await gatewayApi.readCv(7, {programming_target: "main_track", vehicle_id: "vehicle-3"});
assert.equal(requests.at(-1).path, "/api/cv/read");
assert.deepEqual(jsonBody(requests.at(-1)), {
  programming_target: "main_track",
  vehicle_id: "vehicle-3",
  cv: 7
});

await gatewayApi.writeCv(8, 86, true, {programming_target: "programming_track"});
assert.equal(requests.at(-1).path, "/api/cv/write");
assert.deepEqual(jsonBody(requests.at(-1)), {
  programming_target: "programming_track",
  cv: 8,
  value: 86,
  confirmed: true
});

await gatewayApi.readAllCvValues([1, 7, 8]);
assert.equal(requests.at(-1).path, "/api/cv/read-all");
assert.deepEqual(jsonBody(requests.at(-1)), {cv_numbers: [1, 7, 8]});

await gatewayApi.cancelCvRead("session-1");
assert.equal(requests.at(-1).path, "/api/cv/read-all/cancel");
assert.deepEqual(jsonBody(requests.at(-1)), {session_id: "session-1"});

await gatewayApi.importConfig("z21_layout_config", {
  name: "HO.z21",
  async arrayBuffer() {
    return new Uint8Array([1, 2, 3]).buffer;
  }
});
const importRequest = requests.at(-1);
assert.equal(importRequest.path, "/api/import/config");
assert.equal(importRequest.options.method, "POST");
assert.equal(importRequest.options.headers["X-Digsight-Client"], "digsight-web");
assert.equal(importRequest.options.headers["X-Import-Format"], "z21_layout_config");
assert.equal(importRequest.options.headers["X-File-Name"], "HO.z21");
assert.equal(importRequest.options.headers["Content-Type"], "application/octet-stream");

assert.deepEqual(cvDomain.cvNumbersFromSource({"7": true, "bad": true, "1025": true, "1": true}), [1, 7]);
assert.deepEqual(cvDomain.cvNumbersFromSource([3, "2", 0, 1025, 3]), [3, 2, 3]);
assert.deepEqual(cvDomain.sortedUniqueCvNumbers([3, 1, 3, 2]), [1, 2, 3]);

const rows = [];
const readResult = await cvRunner.runCvListRead({
  cvNumbers: [1, 2, 3],
  shouldCancel: () => false,
  readOne: async (cvNumber) => ({cv: cvNumber, ok: true}),
  onRow: (row, cvNumber) => rows.push({row, cvNumber})
});
assert.deepEqual(readResult, {cancelled: false});
assert.deepEqual(rows, [
  {row: {cv: 1, ok: true}, cvNumber: 1},
  {row: {cv: 2, ok: true}, cvNumber: 2},
  {row: {cv: 3, ok: true}, cvNumber: 3}
]);

let readAttempts = 0;
const cancelResult = await cvRunner.runCvListRead({
  cvNumbers: [1, 2, 3],
  shouldCancel: () => readAttempts > 0,
  readOne: async (cvNumber) => {
    readAttempts += 1;
    return {cv: cvNumber, ok: true};
  },
  onRow: () => {}
});
assert.deepEqual(cancelResult, {cancelled: true});
assert.equal(readAttempts, 1);
