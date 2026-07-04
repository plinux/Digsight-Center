import assert from "node:assert/strict";
import {importSourceModule} from "./module_import_helpers.mjs";

async function importControllerView() {
  return importSourceModule("assets/js/controller-view.js", [[
    'import {labeledInput} from "./ui-helpers.js";',
    "const labeledInput = () => ({label: {}});"
  ]]);
}

function headerElements() {
  const operationButtons = ["n", "ho", "g", "dc"].map((trackMode) => ({
    dataset: {trackMode},
    classList: {toggle() {}},
    disabled: false,
    setAttribute() {},
    removeAttribute() {},
    title: "",
  }));
  return {
    connectionLamp: {
      className: "",
      setAttribute() {},
    },
    headerTemperature: {},
    headerVoltage: {},
    headerCurrent: {},
    headerPower: {},
    programmingTargetButtons: [],
    operationModeButtons: operationButtons,
  };
}

const {renderControllerHeader} = await importControllerView();
const elements = headerElements();

renderControllerHeader(elements, {
  track_mode: "n",
  telemetry: {
    temperature_c: 37.46,
    track_voltage_v: 20.026,
    track_current_a: 0.001,
    track_power_w: 0.024,
  },
}, {});

assert.equal(elements.headerTemperature.textContent, "37.5℃");
assert.equal(elements.headerVoltage.textContent, "20V");
assert.equal(elements.headerCurrent.textContent, "0A");
assert.equal(elements.headerPower.textContent, "0W");
