import {spawn} from "node:child_process";
import {mkdtempSync, rmSync} from "node:fs";
import {tmpdir} from "node:os";
import {join} from "node:path";

import {assertNamedChecks, getBox, nextFrame as waitForAnimationFrame} from "./browser_helpers.mjs";

const chromePath = process.env.CHROME_BIN || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const targetUrl = process.env.DIGSIGHT_SMOKE_URL || "http://127.0.0.1:8765/";
const targetOrigin = new URL(targetUrl).origin;
const userDataDir = mkdtempSync(join(tmpdir(), "digsight-cab-smoke-"));

let chrome = null;
let socket = null;
let nextMessageId = 1;
let pageSessionId = "";
const pendingMessages = new Map();

function fail(message) {
  throw new Error(message);
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    fail(`HTTP ${response.status} for ${url}`);
  }
  return response.json();
}

async function readPreferredVehicleIds() {
  const payload = await fetchJson(`${targetOrigin}/api/state`);
  if (!payload.ok) {
    fail(payload.error?.message || "state API returned ok=false");
  }
  const state = payload.data || {};
  const mode = String(state.controller?.track_mode || "n").toLowerCase();
  const visibleVehicles = (state.vehicles || []).filter((vehicle) => {
    return mode !== "dc" && String(vehicle.track_mode || "").toLowerCase() === mode;
  });
  const functionsByVehicle = new Map();
  for (const fn of state.functions || []) {
    if (!functionsByVehicle.has(fn.vehicle_id)) {
      functionsByVehicle.set(fn.vehicle_id, []);
    }
    functionsByVehicle.get(fn.vehicle_id).push(fn);
  }
  const withExtra = visibleVehicles.filter((vehicle) => {
    return (functionsByVehicle.get(vehicle.id) || []).some((fn) => Number(fn.function_number) > 9);
  });
  const ordered = [...withExtra, ...visibleVehicles.filter((vehicle) => !withExtra.includes(vehicle))];
  if (ordered.length < 2) {
    fail("vehicle cab smoke requires at least two visible digital vehicles");
  }
  return ordered.map((vehicle) => String(vehicle.id));
}

function waitForChromeWebSocket(child) {
  return new Promise((resolve, reject) => {
    let stderr = "";
    const timer = setTimeout(() => reject(new Error(`Chrome DevTools endpoint timeout: ${stderr}`)), 15000);
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
      const match = stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) {
        clearTimeout(timer);
        resolve(match[1]);
      }
    });
    child.on("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`Chrome exited before DevTools endpoint was ready: ${code}\n${stderr}`));
    });
  });
}

function connectDevTools(webSocketUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(webSocketUrl);
    ws.addEventListener("open", () => resolve(ws), {once: true});
    ws.addEventListener("error", () => reject(new Error("DevTools WebSocket connection failed")), {once: true});
    ws.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (!message.id || !pendingMessages.has(message.id)) {
        return;
      }
      const {resolve: resolveMessage, reject: rejectMessage} = pendingMessages.get(message.id);
      pendingMessages.delete(message.id);
      if (message.error) {
        rejectMessage(new Error(`${message.error.message}: ${message.error.data || ""}`));
      } else {
        resolveMessage(message.result || {});
      }
    });
  });
}

function cdp(method, params = {}, sessionId = "") {
  const id = nextMessageId;
  nextMessageId += 1;
  const message = {id, method, params};
  if (sessionId) {
    message.sessionId = sessionId;
  }
  socket.send(JSON.stringify(message));
  return new Promise((resolve, reject) => {
    pendingMessages.set(id, {resolve, reject});
  });
}

async function evaluate(expression) {
  const result = await cdp("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true
  }, pageSessionId);
  if (result.exceptionDetails) {
    fail(result.exceptionDetails.text || "Runtime.evaluate failed");
  }
  return result.result?.value;
}

async function waitForExpression(expression, timeoutMs = 12000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    if (await evaluate(expression)) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 150));
  }
  fail(`Timed out waiting for expression: ${expression}`);
}

async function assertCabSelection({data}) {
  assertNamedChecks("vehicle cab selection smoke", [
    ["selectionChanged", data.selectionChanged === true],
    ["otherCabSelectedVehicleDisabled", data.otherCabSelectedVehicleDisabled === true],
    ["blockedSelectionDidNotChange", data.blockedSelectionDidNotChange === true],
    ["selectionKeepsScrollPosition", data.selectionKeepsScrollPosition === true],
    ["mouseSelectionChanged", data.afterMouseSelection && data.afterMouseSelection !== data.beforeMouseSelection],
    ["normalVehicleEditTargetFound", Boolean(data.editTarget?.id)],
    ["normalVehicleEditorOpened", data.normalEditorOpened === true],
    ["mouseEditOpensClickedVehicle", !data.editTarget || data.editOpenedName === data.editTarget.name],
    ["consistVehicleEditTargetFound", Boolean(data.consistEditTarget?.id)],
    ["consistVehicleEditorOpened", data.consistEditorOpened === true]
  ], data);
}

async function assertFunctionButtonState({data, mobileFunctionLayoutData}) {
  assertNamedChecks("vehicle cab function smoke", [
    ["collapsedHasTenButtons", data.collapsedButtonCount === 10],
    ["collapsedFunctionContentCentered", data.collapsedFunctionContentCentered === true],
    ["expandedShowsMoreButtons", data.expandedButtonCount > data.collapsedButtonCount],
    ["expandedKeepsVehicleListVisible", data.expandedListVisible === true],
    ["expandedVehicleListBelowPanel", data.expandedListBelowPanel === true],
    ["mainFunctionSlotsFixed", data.mainFunctionSlots === 10],
    ["toggleFunctionHasTriggerMode", data.toggleFunctionHasTriggerMode === true],
    ["gridFiveColumns", data.gridColumns === 5],
    ["functionNumberToggleDefaultsPressed", data.defaultFunctionNumberTogglePressed === true],
    ["functionNameToggleDefaultsPressed", data.defaultFunctionNameTogglePressed === true],
    ["functionNumberToggleBeforeName", data.functionNumberToggleBeforeName === true],
    ["functionNameToggleBeforeCategory", data.functionNameToggleBeforeCategory === true],
    ["functionNumberToggleOffPressedState", data.noNumberTogglePressed === true],
    ["functionNumberToggleHidesFunctionKey", data.visibleFunctionNumbersWithoutNumbers === 0],
    ["functionNumberToggleKeepsIconAndLabel", data.noNumberButtonsKeepIconAndLabel === true],
    ["functionNumberToggleContentCentered", data.noNumberContentCentered === true],
    ["functionNumberToggleIsPerCab", data.rightFunctionNumberToggleIndependent === true && data.rightFunctionNumbersStillVisible === true],
    ["functionNameToggleOffPressedState", data.noLabelTogglePressed === true],
    ["functionNameToggleDisablesExpand", data.noLabelExpandDisabled === true],
    ["functionNameToggleShowsThirtyTwoSlots", data.noLabelMainFunctionSlots === 32],
    ["functionNameToggleUsesEightColumns", data.noLabelGridColumns === 8],
    ["functionNameToggleGrowsThrottleWithFullPanel", data.noLabelSpeedThrottleHeight >= data.speedThrottleHeight + 12],
    ["functionNameToggleActionStackUsesFullHeight", data.noLabelActionStackUsesFullHeight === true],
    ["functionNameToggleHidesTextLabels", data.visibleFunctionLabelsWithoutNames === 0],
    ["functionNameToggleKeepsIconAndKey", data.noLabelButtonsOnlyUseIconAndKey === true],
    ["functionNameToggleUsesHorizontalKeyIconLayout", data.noLabelButtonsHorizontal === true],
    ["functionNameToggleUsesLargerKeyText", data.noLabelKeyFontSize >= 13],
    ["functionNameToggleUsesLargerIcons", data.noLabelIconSize >= 20],
    ["functionNameToggleDoesNotGrowButtonFrame", data.noLabelButtonHeight <= 42.5],
    ["functionNameToggleIsPerCab", data.rightFunctionNameToggleIndependent === true && data.rightGridColumnsAfterLeftToggle === 5],
    ["mouseFunctionClickWorks", data.functionClicked === true],
    ["toggleFunctionStayedActive", data.toggleFunctionStayedActive === true],
    ["toggleFunctionClearedAfterSecondClick", data.toggleFunctionClearedAfterSecondClick === true],
    ["mobileDefaultColumnsAdaptToWidth", mobileFunctionLayoutData.defaultColumns > 1 && mobileFunctionLayoutData.defaultColumns <= 3],
    ["mobileDefaultButtonContentFits", mobileFunctionLayoutData.defaultButtonsFit === true],
    ["mobileDefaultLabelsFitButtonBox", mobileFunctionLayoutData.defaultLabelsFitButtonBox === true],
    ["mobileDefaultButtonHeightsFixed", mobileFunctionLayoutData.defaultButtonHeightsFixed === true],
    ["mobileDefaultContentCentered", mobileFunctionLayoutData.defaultContentCentered === true],
    ["mobileCompactModeEnabled", mobileFunctionLayoutData.compactMode === true],
    ["mobileCompactColumnsAdaptToWidth", mobileFunctionLayoutData.compactColumns > 1 && mobileFunctionLayoutData.compactColumns <= 4],
    ["mobileCompactButtonContentFits", mobileFunctionLayoutData.compactButtonsFit === true],
    ["mobileCompactButtonsStayHorizontal", mobileFunctionLayoutData.compactButtonsHorizontal === true]
  ], {data, mobileFunctionLayoutData});
}

async function assertCvTargetSwitching() {
  const result = await evaluate(`(async () => {
    const delay = () => new Promise((resolve) => setTimeout(resolve, 50));
    const waitFor = async (predicate) => {
      for (let attempt = 0; attempt < 100; attempt += 1) {
        if (predicate()) {
          return true;
        }
        await delay();
      }
      return false;
    };
    const cvTab = document.querySelector('#navCvProgramming');
    const vehicleTab = document.querySelector('#navVehicleControl');
    const programmingTrack = document.querySelector('[data-programming-target="programming_track"]');
    const mainTrack = document.querySelector('[data-programming-target="main_track"]');
    cvTab?.click();
    await waitFor(() => document.querySelector('#cvProgrammingView')?.hidden === false);
    await waitFor(() => Boolean(document.querySelector('.cv-target-panel select') && document.querySelector('.cv-target-panel .cv-target-hint')));
    const currentTarget = document.querySelector('[data-programming-target][aria-pressed="true"]')?.dataset.programmingTarget || 'programming_track';
    const targetSelect = document.querySelector('.cv-target-panel select');
    const targetHint = document.querySelector('.cv-target-panel .cv-target-hint')?.textContent || '';
    const optionCount = targetSelect?.options.length || 0;
    vehicleTab?.click();
    await waitFor(() => document.querySelector('#vehicleControlView')?.hidden === false);
    return {
      cvViewVisible: true,
      targetButtonsVisible: Boolean(programmingTrack && mainTrack),
      currentTarget,
      targetSelectDisabled: targetSelect?.disabled,
      targetOptionCount: optionCount,
      targetHint,
      programmingTargetConsistent: currentTarget !== 'programming_track'
        || (targetSelect?.disabled === true && targetHint.includes('编程轨')),
      mainTrackTargetConsistent: currentTarget !== 'main_track'
        || (targetSelect?.disabled === false && optionCount > 0 && targetHint.includes('主轨')),
      vehicleViewRestored: document.querySelector('#vehicleControlView')?.hidden === false
    };
  })()`);
  assertNamedChecks("vehicle cab CV target smoke", [
    ["cvViewVisible", result.cvViewVisible === true],
    ["targetButtonsVisible", result.targetButtonsVisible === true],
    ["programmingTargetConsistent", result.programmingTargetConsistent === true],
    ["mainTrackTargetConsistent", result.mainTrackTargetConsistent === true],
    ["vehicleViewRestored", result.vehicleViewRestored === true]
  ], result);
}

async function assertDcModeGating() {
  const result = await evaluate(`(async () => {
    const nextFrame = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const delay = () => new Promise((resolve) => setTimeout(resolve, 50));
    const waitFor = async (predicate) => {
      for (let attempt = 0; attempt < 100; attempt += 1) {
        if (predicate()) {
          return true;
        }
        await delay();
      }
      return false;
    };
    const dcButton = document.querySelector('[data-track-mode="dc"]');
    const originalMode = document.querySelector('[data-track-mode][aria-pressed="true"]')?.dataset.trackMode || 'n';
    const restoreModeButton = document.querySelector('[data-track-mode="' + CSS.escape(originalMode) + '"]')
      || document.querySelector('[data-track-mode="n"]');
    const cvTab = document.querySelector('#navCvProgramming');
    const vehicleTab = document.querySelector('#navVehicleControl');
    dcButton?.click();
    await waitFor(() => dcButton?.getAttribute('aria-pressed') === 'true' && cvTab?.disabled === true);
    const dcMode = {
      dcButtonPressed: dcButton?.getAttribute('aria-pressed') === 'true',
      cvNavDisabled: cvTab?.disabled === true,
      importHidden: document.querySelector('.import-strip')?.hidden === true,
      vehicleViewVisible: document.querySelector('#vehicleControlView')?.hidden === false,
      dcControlVisible: Boolean(document.querySelector('#vehicleRegistry .dc-control-panel')),
      cabWorkspaceHidden: !document.querySelector('#vehicleRegistry .cab-workspace')
    };
    cvTab?.click();
    await nextFrame();
    dcMode.cvViewStayedHidden = document.querySelector('#cvProgrammingView')?.hidden === true;
    restoreModeButton?.click();
    await waitFor(() => restoreModeButton?.getAttribute('aria-pressed') === 'true' && cvTab?.disabled === false);
    const restored = {
      originalModeRestored: restoreModeButton?.getAttribute('aria-pressed') === 'true',
      cvNavEnabled: cvTab?.disabled === false,
      importVisible: document.querySelector('.import-strip')?.hidden === false
    };
    vehicleTab?.click();
    await waitFor(() => document.querySelector('#vehicleControlView')?.hidden === false);
    return {...dcMode, ...restored};
  })()`);
  assertNamedChecks("vehicle cab DC gating smoke", [
    ["dcButtonPressed", result.dcButtonPressed === true],
    ["cvNavDisabled", result.cvNavDisabled === true],
    ["importHidden", result.importHidden === true],
    ["vehicleViewVisible", result.vehicleViewVisible === true],
    ["dcControlVisible", result.dcControlVisible === true],
    ["cabWorkspaceHidden", result.cabWorkspaceHidden === true],
    ["cvViewStayedHidden", result.cvViewStayedHidden === true],
    ["originalModeRestored", result.originalModeRestored === true],
    ["cvNavEnabled", result.cvNavEnabled === true],
    ["importVisible", result.importVisible === true]
  ], result);
}

async function assertVehicleDragOrdering({data}) {
  assertNamedChecks("vehicle cab drag ordering smoke", [
    ["dragPreviewReordersRows", data.dragData.skipped || data.dragData.during.join("|") !== data.dragData.before.join("|")],
    ["dragDropSavesOrder", data.dragData.skipped || data.dragData.orderSaved === true]
  ], data.dragData);
}

async function run() {
  const preferredVehicleIds = await readPreferredVehicleIds();
  chrome = spawn(chromePath, [
    "--headless=new",
    "--remote-debugging-port=0",
    `--user-data-dir=${userDataDir}`,
    "--no-first-run",
    "--no-default-browser-check",
    "about:blank"
  ], {stdio: ["ignore", "ignore", "pipe"]});

  const browserWebSocketUrl = await waitForChromeWebSocket(chrome);
  const version = await fetchJson(browserWebSocketUrl.replace(/^ws:/, "http:").replace(/\/devtools\/browser\/.*/, "/json/version"));
  socket = await connectDevTools(version.webSocketDebuggerUrl || browserWebSocketUrl);
  const {targetId} = await cdp("Target.createTarget", {url: "about:blank"});
  const {sessionId} = await cdp("Target.attachToTarget", {targetId, flatten: true});
  pageSessionId = sessionId;
  const targetCdp = (method, params = {}) => cdp(method, params, pageSessionId);
  const elementRect = async (selector) => {
    const rect = await getBox(evaluate, selector, {scrollIntoView: true});
    if (!rect) {
      fail(`Missing element for selector: ${selector}`);
    }
    return rect;
  };
  const mouseClick = async (selector) => {
    await targetCdp("Page.bringToFront");
    const rect = await elementRect(selector);
    await targetCdp("Input.dispatchMouseEvent", {type: "mousePressed", x: rect.x, y: rect.y, button: "left", clickCount: 1});
    await targetCdp("Input.dispatchMouseEvent", {type: "mouseReleased", x: rect.x, y: rect.y, button: "left", clickCount: 1});
  };
  const mouseDragHorizontal = async (selector, fraction) => {
    await targetCdp("Page.bringToFront");
    const rect = await elementRect(selector);
    const startX = rect.left + rect.width * 0.2;
    const endX = rect.left + rect.width * fraction;
    const y = rect.y;
    await targetCdp("Input.dispatchMouseEvent", {type: "mousePressed", x: startX, y, button: "left", clickCount: 1});
    const steps = 8;
    for (let index = 1; index <= steps; index += 1) {
      const x = startX + ((endX - startX) * index) / steps;
      await targetCdp("Input.dispatchMouseEvent", {type: "mouseMoved", x, y, button: "left"});
    }
    await targetCdp("Input.dispatchMouseEvent", {type: "mouseReleased", x: endX, y, button: "left", clickCount: 1});
  };
  const mouseDragVertical = async (selector, fraction) => {
    await targetCdp("Page.bringToFront");
    const rect = await elementRect(selector);
    const x = rect.x;
    const startY = rect.bottom - rect.height * 0.2;
    const endY = rect.top + rect.height * (1 - fraction);
    await targetCdp("Input.dispatchMouseEvent", {type: "mousePressed", x, y: startY, button: "left", clickCount: 1});
    const steps = 8;
    for (let index = 1; index <= steps; index += 1) {
      const y = startY + ((endY - startY) * index) / steps;
      await targetCdp("Input.dispatchMouseEvent", {type: "mouseMoved", x, y, button: "left"});
    }
    await targetCdp("Input.dispatchMouseEvent", {type: "mouseReleased", x, y: endY, button: "left", clickCount: 1});
  };
  const nextFrame = () => waitForAnimationFrame(evaluate);
  const installFetchInterceptor = () => evaluate(`(() => {
    if (window.__digsightSmokeFetchInstalled) {
      return true;
    }
    window.__digsightSmokeFetchInstalled = true;
    window.__digsightSmokeRequests = [];
    const originalFetch = window.fetch.bind(window);
    window.fetch = async (input, options = {}) => {
      const url = typeof input === "string" ? input : input.url;
      if (url.includes("/api/loco/function") || url.includes("/api/loco/speed") || url.includes("/api/vehicles/order")) {
        window.__digsightSmokeRequests.push({url, method: options.method || "GET", body: options.body || ""});
        let data = {};
        if (url.includes("/api/vehicles/order")) {
          const stateResponse = await originalFetch("/api/state", {method: "GET"});
          const statePayload = await stateResponse.json();
          data = {vehicles: statePayload.data?.vehicles || []};
        }
        return new Response(JSON.stringify({ok: true, data}), {
          status: 200,
          headers: {"Content-Type": "application/json"}
        });
      }
      return originalFetch(input, options);
    };
    return true;
  })()`);

  await targetCdp("Runtime.enable");
  await targetCdp("Page.enable");
  await targetCdp("Emulation.setDeviceMetricsOverride", {
    width: 1600,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false
  });
  await targetCdp("Page.navigate", {url: targetUrl});
  await waitForExpression("document.readyState === 'complete'");
  await waitForExpression("Boolean(document.querySelector('.cab-workspace .cab-vehicle-row'))");

  const data = await evaluate(`(async () => {
    const nextFrame = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const imageOpaqueContentRect = async (image) => {
      if (!image || !image.complete || !image.naturalWidth || !image.naturalHeight) {
        return null;
      }
      const canvas = document.createElement('canvas');
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext('2d', {willReadFrequently: true});
      context.drawImage(image, 0, 0);
      const {data} = context.getImageData(0, 0, canvas.width, canvas.height);
      let minX = canvas.width;
      let minY = canvas.height;
      let maxX = -1;
      let maxY = -1;
      for (let y = 0; y < canvas.height; y += 1) {
        for (let x = 0; x < canvas.width; x += 1) {
          const index = (y * canvas.width + x) * 4;
          const alpha = data[index + 3];
          const nearWhite = data[index] >= 245 && data[index + 1] >= 245 && data[index + 2] >= 245;
          if (alpha <= 12 || nearWhite) {
            continue;
          }
          minX = Math.min(minX, x);
          minY = Math.min(minY, y);
          maxX = Math.max(maxX, x + 1);
          maxY = Math.max(maxY, y + 1);
        }
      }
      if (maxX < minX || maxY < minY) {
        return null;
      }
      const imageRect = image.getBoundingClientRect();
      const naturalRatio = image.naturalWidth / image.naturalHeight;
      const rectRatio = imageRect.width / imageRect.height;
      let renderedWidth = imageRect.width;
      let renderedHeight = imageRect.height;
      let offsetX = 0;
      let offsetY = 0;
      if (rectRatio > naturalRatio) {
        renderedWidth = imageRect.height * naturalRatio;
        offsetX = (imageRect.width - renderedWidth) / 2;
      } else {
        renderedHeight = imageRect.width / naturalRatio;
        offsetY = (imageRect.height - renderedHeight) / 2;
      }
      const scaleX = renderedWidth / image.naturalWidth;
      const scaleY = renderedHeight / image.naturalHeight;
      return {
        left: imageRect.left + offsetX + minX * scaleX,
        right: imageRect.left + offsetX + maxX * scaleX,
        top: imageRect.top + offsetY + minY * scaleY,
        bottom: imageRect.top + offsetY + maxY * scaleY
      };
    };
    const preferredVehicleIds = ${JSON.stringify(preferredVehicleIds)};
    const cabColumn = (cabId) => document.querySelector('.cab-column[data-cab-id="' + cabId + '"]');
    const cabImageMetrics = async (cabId) => {
      const cab = cabColumn(cabId);
      const media = cab?.querySelector('.cab-control-media');
      const imageBox = cab?.querySelector('.cab-control-image');
      const image = imageBox?.querySelector('img');
      const mediaRect = media?.getBoundingClientRect();
      const imageBoxRect = imageBox?.getBoundingClientRect();
      const imageRect = image?.getBoundingClientRect();
      const contentRect = await imageOpaqueContentRect(image);
      const imageStyle = image ? getComputedStyle(image) : null;
      return {
        imageElementInsideBox: Boolean(imageRect && imageBoxRect
          && imageRect.left >= imageBoxRect.left - 1
          && imageRect.right <= imageBoxRect.right + 1
          && imageRect.top >= imageBoxRect.top - 1
          && imageRect.bottom <= imageBoxRect.bottom + 1),
        imageObjectFitContain: imageStyle?.objectFit === 'contain',
        imageElementCentered: Boolean(mediaRect && imageRect
          && Math.abs(((imageRect.left + imageRect.right) / 2) - ((mediaRect.left + mediaRect.right) / 2)) <= 3
          && Math.abs(((imageRect.top + imageRect.bottom) / 2) - ((mediaRect.top + mediaRect.bottom) / 2)) <= 3),
        centered: Boolean(mediaRect && contentRect
          && Math.abs(((contentRect.left + contentRect.right) / 2) - ((mediaRect.left + mediaRect.right) / 2)) <= 8
          && Math.abs(((contentRect.top + contentRect.bottom) / 2) - ((mediaRect.top + mediaRect.bottom) / 2)) <= 8),
        fullyVisible: Boolean(mediaRect && contentRect
          && contentRect.left >= mediaRect.left - 1
          && contentRect.right <= mediaRect.right + 1
          && contentRect.top >= mediaRect.top - 1
          && contentRect.bottom <= mediaRect.bottom + 1),
        boxCentered: Boolean(mediaRect && imageBoxRect
          && Math.abs(((imageBoxRect.left + imageBoxRect.right) / 2) - ((mediaRect.left + mediaRect.right) / 2)) <= 2
          && Math.abs(((imageBoxRect.top + imageBoxRect.bottom) / 2) - ((mediaRect.top + mediaRect.bottom) / 2)) <= 2),
        media: mediaRect ? {
          left: mediaRect.left,
          right: mediaRect.right,
          top: mediaRect.top,
          bottom: mediaRect.bottom
        } : null,
        content: contentRect,
        box: imageBoxRect ? {
          left: imageBoxRect.left,
          right: imageBoxRect.right,
          top: imageBoxRect.top,
          bottom: imageBoxRect.bottom
        } : null,
        image: imageRect ? {
          left: imageRect.left,
          right: imageRect.right,
          top: imageRect.top,
          bottom: imageRect.bottom,
          width: imageRect.width,
          height: imageRect.height
        } : null
      };
    };
    let left = cabColumn('left');
    let right = cabColumn('right');
    const pickLeftRow = () => {
      for (const vehicleId of preferredVehicleIds) {
        const row = left.querySelector('.cab-vehicle-row[data-vehicle-id="' + CSS.escape(vehicleId) + '"]:not(.disabled-by-other-cab)');
        if (row && !row.classList.contains('selected')) {
          return row;
        }
      }
      return left.querySelector('.cab-vehicle-row:not(.selected):not(.disabled-by-other-cab)')
        || left.querySelector('.cab-vehicle-row:not(.disabled-by-other-cab)');
    };

    const lampRect = document.querySelector('.lamp').getBoundingClientRect();
    const firstRow = left.querySelector('.cab-vehicle-row');
    const firstImage = firstRow.querySelector('img, .vehicle-placeholder');
    const rowRect = firstRow.getBoundingClientRect();
    const imageRect = firstImage.getBoundingClientRect();
    const panel = left.querySelector('.cab-control-panel');
    const list = left.querySelector('.cab-vehicle-list');
    const initialLeftImage = await cabImageMetrics('left');
    const initialRightImage = await cabImageMetrics('right');

    const rowToSelect = pickLeftRow();
    const beforeSelection = left.querySelector('.cab-vehicle-row.selected')?.dataset.vehicleId || '';
    const rowToSelectId = rowToSelect?.dataset.vehicleId || '';
    const rowToSelectClass = rowToSelect?.className || '';
    rowToSelect.click();
    await nextFrame();
    left = cabColumn('left');
    right = cabColumn('right');
    const selectedVehicleId = left.querySelector('.cab-vehicle-row.selected')?.dataset.vehicleId || '';
    const rightSelectedBefore = right.querySelector('.cab-vehicle-row.selected')?.dataset.vehicleId || '';
    const rightBlockedRow = right.querySelector('.cab-vehicle-row[data-vehicle-id="' + CSS.escape(selectedVehicleId) + '"]');
    const rightBlockedButton = rightBlockedRow?.querySelector('.cab-vehicle-select');
    const otherCabSelectedVehicleDisabled = Boolean(rightBlockedRow?.classList.contains('disabled-by-other-cab') && rightBlockedButton?.disabled);
    rightBlockedButton?.click();
    rightBlockedRow?.click();
    await nextFrame();
    left = cabColumn('left');
    right = cabColumn('right');
    const rightSelectedAfter = right.querySelector('.cab-vehicle-row.selected')?.dataset.vehicleId || '';

    const speedThrottle = left.querySelector('.cab-speed-throttle');
    const speedControl = left.querySelector('.cab-speed-control');
    const sideActions = left.querySelector('.cab-control-side-actions');
    const leftHeader = left.querySelector('.cab-header');
    const rightHeader = right.querySelector('.cab-header');
    const leftHeaderTitle = leftHeader?.querySelector('h2')?.textContent.trim() || '';
    const rightHeaderTitle = rightHeader?.querySelector('h2')?.textContent.trim() || '';
    const leftHeaderText = leftHeader?.textContent || '';
    const leftFilterBar = leftHeader?.querySelector('.cab-filter-bar');
    const leftHeaderControls = leftHeader?.querySelector('.cab-header-controls');
    const filterInHeader = Boolean(leftFilterBar);
    const headerFilterRightOfTitle = Boolean(leftHeaderControls && leftHeader?.querySelector('h2')
      && leftHeaderControls.getBoundingClientRect().left > leftHeader.querySelector('h2').getBoundingClientRect().right);
    const controlInfo = left.querySelector('.cab-control-info');
    const controlIdentity = left.querySelector('.cab-control-identity');
    const controlMedia = left.querySelector('.cab-control-media');
    const controlFunctionGrid = left.querySelector('.cab-control-main-row > .cab-function-grid');
    const controlActions = left.querySelector('.cab-control-side-actions');
    const infoRect = controlInfo?.getBoundingClientRect();
    const identityRect = controlIdentity?.getBoundingClientRect();
    const mediaRect = controlMedia?.getBoundingClientRect();
    const functionGridRect = controlFunctionGrid?.getBoundingClientRect();
    const actionsRect = controlActions?.getBoundingClientRect();
    const directionRowRect = left.querySelector('.cab-direction-row')?.getBoundingClientRect();
    const identityName = controlIdentity?.querySelector('.cab-control-identity-primary');
    const addressRow = controlIdentity?.querySelector('.cab-control-address-row');
    const metaRow = controlIdentity?.querySelector('.cab-control-meta-row');
    const fullNameTag = controlIdentity?.querySelector('.cab-control-full-name-tag');
    const brandTag = controlIdentity?.querySelector('.cab-control-meta-tag[data-label="品牌"]');
    const articleNumberTag = controlIdentity?.querySelector('.cab-control-meta-tag[data-label="货号"]');
    const identityLines = Array.from(controlIdentity?.children || [])
      .map((node) => node.textContent.trim());
    const actionTexts = Array.from(controlActions?.querySelectorAll('button') || [])
      .map((node) => node.textContent.trim());
    const economicStopButton = controlActions?.querySelector('.cab-economic-stop');
    const economicStopRect = economicStopButton?.getBoundingClientRect();
    const economicStopStyle = economicStopButton ? getComputedStyle(economicStopButton) : null;
    const categorySelectRect = leftFilterBar?.querySelector('select')?.getBoundingClientRect();
    const headerControlsRect = leftHeaderControls?.getBoundingClientRect();
    const addressBadge = left.querySelector('.cab-control-address-badge')?.textContent.trim() || '';
    const economicStopIsRed = Boolean(economicStopStyle && (
      economicStopStyle.backgroundColor.includes('239, 68, 68')
      || economicStopStyle.backgroundColor.includes('220, 38, 38')
      || economicStopStyle.backgroundColor.includes('185, 28, 28')
    ));
    const emergencyStopHighContrastText = Boolean(economicStopStyle && economicStopStyle.color.includes('255, 255, 255'));
    const emergencyStopStrongBorder = Boolean(economicStopStyle && economicStopStyle.borderTopColor.includes('127, 29, 29'));
    const emergencyStopHeight = economicStopButton?.getBoundingClientRect().height || 0;
    const speedThrottleRect = speedThrottle?.getBoundingClientRect();
    const speedThrottleStyle = speedThrottle ? getComputedStyle(speedThrottle) : null;
    const speedControlRect = speedControl?.getBoundingClientRect();
    const controlImageRect = left.querySelector('.cab-control-image')?.getBoundingClientRect();
    const controlImageElement = left.querySelector('.cab-control-image img');
    const controlImageElementRect = controlImageElement?.getBoundingClientRect();
    const controlImageContentRect = await imageOpaqueContentRect(left.querySelector('.cab-control-image img'));
    const speedValueRect = left.querySelector('.cab-speed-value')?.getBoundingClientRect();
    const addressBadgeRect = left.querySelector('.cab-control-address-badge')?.getBoundingClientRect();
    const fullNameTagRect = fullNameTag?.getBoundingClientRect();
    const addressRowRect = addressRow?.getBoundingClientRect();
    const metaRowRect = metaRow?.getBoundingClientRect();
    const brandTagRect = brandTag?.getBoundingClientRect();
    const articleNumberTagRect = articleNumberTag?.getBoundingClientRect();
    const fullNameTagStyle = fullNameTag ? getComputedStyle(fullNameTag) : null;
    const brandTagStyle = brandTag ? getComputedStyle(brandTag) : null;
    const articleNumberTagStyle = articleNumberTag ? getComputedStyle(articleNumberTag) : null;
    const speedValueAboveThrottle = Boolean(speedValueRect && speedThrottleRect && speedControlRect
      && speedValueRect.bottom <= speedThrottleRect.top + 2
      && speedValueRect.left >= speedControlRect.left - 2
      && speedValueRect.right <= speedControlRect.right + 2);
    const speedValueInRightControl = Boolean(speedValueRect && speedControlRect
      && left.querySelector('.cab-speed-value')?.parentElement === speedControl
      && speedValueRect.top >= speedControlRect.top - 2);
    const fullNameAfterAddress = Boolean(addressBadgeRect && fullNameTagRect && addressRowRect
      && addressBadgeRect.right <= fullNameTagRect.left + 4
      && Math.abs(((addressBadgeRect.top + addressBadgeRect.bottom) / 2) - ((fullNameTagRect.top + fullNameTagRect.bottom) / 2)) <= 4
      && fullNameTagRect.right <= addressRowRect.right + 2);
    const brandArticleSameLine = Boolean(metaRowRect && brandTagRect && articleNumberTagRect
      && brandTagRect.right <= articleNumberTagRect.left + 8
      && Math.abs(((brandTagRect.top + brandTagRect.bottom) / 2) - ((articleNumberTagRect.top + articleNumberTagRect.bottom) / 2)) <= 4
      && brandTagRect.top >= metaRowRect.top - 2
      && articleNumberTagRect.bottom <= metaRowRect.bottom + 2);
    const identityTagsDoNotGrow = fullNameTagStyle?.flexGrow === '0'
      && brandTagStyle?.flexGrow === '0'
      && articleNumberTagStyle?.flexGrow === '0';
    const speedThrottleVertical = Boolean(speedThrottleRect && speedThrottleRect.height >= speedThrottleRect.width * 1.55);
    const speedThrottleTouchReady = speedThrottleStyle?.touchAction === 'none' && speedThrottleStyle?.cursor === 'ns-resize';
    const speedControlAboveDirection = Boolean(speedControlRect && directionRowRect
      && speedControlRect.bottom <= directionRowRect.top + 4);
    const imageLeftOfSpeed = Boolean(controlImageRect && speedControlRect
      && controlImageRect.right <= speedControlRect.left);
    const infoRegionOne = Boolean(infoRect && mediaRect
      && infoRect.right <= mediaRect.left + 2
      && Math.abs(infoRect.top - mediaRect.top) <= 8);
    const imageRegionTwo = Boolean(mediaRect && actionsRect
      && mediaRect.right <= actionsRect.left + 2
      && Math.abs(mediaRect.top - actionsRect.top) <= 8);
    const imageElementCenteredInRegion = Boolean(mediaRect && controlImageElementRect
      && Math.abs(((controlImageElementRect.left + controlImageElementRect.right) / 2) - ((mediaRect.left + mediaRect.right) / 2)) <= 3
      && Math.abs(((controlImageElementRect.top + controlImageElementRect.bottom) / 2) - ((mediaRect.top + mediaRect.bottom) / 2)) <= 3);
    const controlImageElementStyle = controlImageElement ? getComputedStyle(controlImageElement) : null;
    const imageElementInsideRegion = Boolean(mediaRect && controlImageElementRect
      && controlImageElementRect.left >= mediaRect.left - 1
      && controlImageElementRect.right <= mediaRect.right + 1
      && controlImageElementRect.top >= mediaRect.top - 1
      && controlImageElementRect.bottom <= mediaRect.bottom + 1);
    const imageObjectFitContain = controlImageElementStyle?.objectFit === 'contain';
    const imageContentCenteredInRegion = Boolean(mediaRect && controlImageContentRect
      && Math.abs(((controlImageContentRect.left + controlImageContentRect.right) / 2) - ((mediaRect.left + mediaRect.right) / 2)) <= 8
      && Math.abs(((controlImageContentRect.top + controlImageContentRect.bottom) / 2) - ((mediaRect.top + mediaRect.bottom) / 2)) <= 8);
    const imageContentFullyVisibleInRegion = Boolean(mediaRect && controlImageContentRect
      && controlImageContentRect.left >= mediaRect.left - 1
      && controlImageContentRect.right <= mediaRect.right + 1
      && controlImageContentRect.top >= mediaRect.top - 1
      && controlImageContentRect.bottom <= mediaRect.bottom + 1);
    const functionsRegionsFourFive = Boolean(infoRect && mediaRect && functionGridRect && actionsRect
      && functionGridRect.top >= Math.max(infoRect.bottom, mediaRect.bottom) - 2
      && functionGridRect.left <= infoRect.left + 2
      && functionGridRect.right >= mediaRect.right - 2
      && functionGridRect.right <= actionsRect.left + 2);
    const actionsRegionsThreeSix = Boolean(mediaRect && functionGridRect && actionsRect
      && actionsRect.top <= mediaRect.top + 2
      && actionsRect.bottom >= functionGridRect.bottom - 2
      && actionsRect.left >= mediaRect.right - 2);
    const imageDoesNotOverlapSpeed = Boolean(controlImageRect && speedControlRect
      && (
        controlImageRect.right <= speedControlRect.left
        || speedControlRect.right <= controlImageRect.left
        || controlImageRect.bottom <= speedControlRect.top
        || speedControlRect.bottom <= controlImageRect.top
      ));
    const filtersCompactRight = Boolean(categorySelectRect && headerControlsRect
      && categorySelectRect.width <= 150
      && categorySelectRect.right <= headerControlsRect.right + 2);
    const speedThrottleInsideControl = Boolean(speedThrottleRect && speedControlRect
      && speedThrottleRect.left >= speedControlRect.left - 2
      && speedThrottleRect.right <= speedControlRect.right + 2
      && speedThrottleRect.top >= speedControlRect.top - 2
      && speedThrottleRect.bottom <= speedControlRect.bottom + 2);
    const actionStackUsesFullHeight = Boolean(actionsRect && speedControlRect && economicStopRect
      && speedControlRect.top <= actionsRect.top + 2
      && economicStopRect.bottom >= actionsRect.bottom - 2);
    const functionButtonContentCentered = (button) => {
      const buttonRect = button.getBoundingClientRect();
      const visibleParts = ['.function-key', '.function-icon-slot', '.function-label']
        .map((selector) => button.querySelector(selector))
        .filter((part) => part && getComputedStyle(part).display !== 'none')
        .map((part) => part.getBoundingClientRect());
      if (!visibleParts.length) {
        return false;
      }
      const contentLeft = Math.min(...visibleParts.map((rect) => rect.left));
      const contentRight = Math.max(...visibleParts.map((rect) => rect.right));
      const contentTop = Math.min(...visibleParts.map((rect) => rect.top));
      const contentBottom = Math.max(...visibleParts.map((rect) => rect.bottom));
      const contentCenterX = (contentLeft + contentRight) / 2;
      const contentCenterY = (contentTop + contentBottom) / 2;
      const buttonCenterX = (buttonRect.left + buttonRect.right) / 2;
      const buttonCenterY = (buttonRect.top + buttonRect.bottom) / 2;
      return Math.abs(contentCenterX - buttonCenterX) <= 4
        && Math.abs(contentCenterY - buttonCenterY) <= 4;
    };
    const mainFunctionSlots = left.querySelectorAll('.cab-function-grid .function-slot-button, .cab-function-grid .function-slot-empty').length;
    const toggleButton = left.querySelector('.cab-function-grid .function-slot-button[data-trigger-mode="toggle"]');
    const collapsedButtons = Array.from(left.querySelectorAll('.cab-control-panel .cab-function-grid .function-slot-button'));
    const collapsedButtonCount = collapsedButtons.length;
    const collapsedFunctionContentCentered = collapsedButtons.every(functionButtonContentCentered);
    const toggle = left.querySelector('.cab-toggle-control') || left.querySelector('.cab-header button');
    toggle.click();
    await nextFrame();
    left = cabColumn('left');
    const expandedButtonCount = left.querySelectorAll('.cab-control-panel .function-slot-button').length;
    const expandedPanel = left.querySelector('.cab-control-panel');
    const expandedList = left.querySelector('.cab-vehicle-list');
    const expandedListVisible = Boolean(expandedList?.querySelector('.cab-vehicle-row'));
    const expandedListBelowPanel = Boolean(expandedPanel && expandedList
      && (expandedPanel.compareDocumentPosition(expandedList) & Node.DOCUMENT_POSITION_FOLLOWING));
    const cabFunctionGrid = left.querySelector('.cab-function-grid');
    const gridStyle = getComputedStyle(cabFunctionGrid);
    const gridColumns = gridStyle.gridTemplateColumns.split(' ').filter(Boolean).length;

    (left.querySelector('.cab-toggle-control') || left.querySelector('.cab-header button'))?.click();
    await nextFrame();
    left = cabColumn('left');
    const listBeforeScrollSelection = left.querySelector('.cab-vehicle-list');
    const listCanScroll = listBeforeScrollSelection.scrollHeight > listBeforeScrollSelection.clientHeight + 8;
    let selectionKeepsScrollPosition = true;
    let scrollBeforeListSelection = 0;
    let scrollAfterListSelection = 0;
    if (listCanScroll) {
      const targetScrollTop = Math.max(0, listBeforeScrollSelection.scrollHeight - listBeforeScrollSelection.clientHeight - 20);
      for (let attempt = 0; attempt < 4; attempt += 1) {
        listBeforeScrollSelection.scrollTop = targetScrollTop;
        await nextFrame();
        if (listBeforeScrollSelection.scrollTop > 0 || targetScrollTop === 0) {
          break;
        }
      }
      scrollBeforeListSelection = listBeforeScrollSelection.scrollTop;
      const listViewport = listBeforeScrollSelection.getBoundingClientRect();
      const visibleRows = Array.from(listBeforeScrollSelection.querySelectorAll('.cab-vehicle-row:not(.selected):not(.disabled-by-other-cab)')).filter((row) => {
        const rowRect = row.getBoundingClientRect();
        return rowRect.top >= listViewport.top
          && rowRect.bottom <= listViewport.bottom;
      });
      const rowInScrolledViewport = visibleRows[0]
        || Array.from(listBeforeScrollSelection.querySelectorAll('.cab-vehicle-row:not(.selected):not(.disabled-by-other-cab)')).at(-1);
      rowInScrolledViewport?.querySelector('.cab-vehicle-select')?.click();
      await nextFrame();
      left = cabColumn('left');
      scrollAfterListSelection = left.querySelector('.cab-vehicle-list')?.scrollTop || 0;
      selectionKeepsScrollPosition = scrollBeforeListSelection <= 0
        || Math.abs(scrollAfterListSelection - scrollBeforeListSelection) <= 2;
    }

    const functionNumberToggle = left.querySelector('.cab-function-number-toggle');
    const functionNameToggle = left.querySelector('.cab-function-label-toggle');
    const labelFilterBar = left.querySelector('.cab-filter-bar');
    const categorySelect = labelFilterBar?.querySelector('select');
    const labelFilterChildren = Array.from(labelFilterBar?.children || []);
    const rightFunctionNumberToggle = right.querySelector('.cab-function-number-toggle');
    const rightFunctionNameToggle = right.querySelector('.cab-function-label-toggle');
    const defaultFunctionNumberTogglePressed = functionNumberToggle?.getAttribute('aria-pressed') === 'true';
    const defaultFunctionNameTogglePressed = functionNameToggle?.getAttribute('aria-pressed') === 'true';
    const functionNumberToggleBeforeName = Boolean(functionNumberToggle && functionNameToggle
      && labelFilterChildren.indexOf(functionNumberToggle) >= 0
      && labelFilterChildren.indexOf(functionNumberToggle) < labelFilterChildren.indexOf(functionNameToggle));
    const functionNameToggleBeforeCategory = Boolean(functionNameToggle && categorySelect
      && labelFilterChildren.indexOf(functionNameToggle) >= 0
      && labelFilterChildren.indexOf(functionNameToggle) < labelFilterChildren.indexOf(categorySelect));
    const rightFunctionNumberToggleBefore = rightFunctionNumberToggle?.getAttribute('aria-pressed') || '';
    const rightFunctionNameToggleBefore = rightFunctionNameToggle?.getAttribute('aria-pressed') || '';
    functionNumberToggle?.click();
    await nextFrame();
    left = cabColumn('left');
    right = cabColumn('right');
    const noNumberGrid = left.querySelector('.cab-function-grid');
    const noNumberButtons = Array.from(noNumberGrid.querySelectorAll('.function-slot-button'));
    const noNumberTogglePressed = left.querySelector('.cab-function-number-toggle')?.getAttribute('aria-pressed') === 'false';
    const visibleFunctionNumbersWithoutNumbers = Array.from(noNumberGrid.querySelectorAll('.function-key'))
      .filter((key) => getComputedStyle(key).display !== 'none' && key.textContent.trim()).length;
    const noNumberButtonsKeepIconAndLabel = noNumberButtons.every((button) => {
      return button.querySelector('.function-icon-slot')
        && button.querySelector('.function-label')
        && button.classList.contains('without-number');
    });
    const noNumberContentCentered = noNumberButtons.every(functionButtonContentCentered);
    const rightFunctionNumberToggleIndependent = right.querySelector('.cab-function-number-toggle')?.getAttribute('aria-pressed') === rightFunctionNumberToggleBefore;
    const rightFunctionNumbersStillVisible = Array.from(right.querySelectorAll('.cab-function-grid .function-key'))
      .filter((key) => getComputedStyle(key).display !== 'none' && key.textContent.trim()).length > 0;
    left.querySelector('.cab-function-number-toggle')?.click();
    await nextFrame();
    left = cabColumn('left');
    right = cabColumn('right');
    const restoredFunctionNameToggle = left.querySelector('.cab-function-label-toggle');
    restoredFunctionNameToggle?.click();
    await nextFrame();
    left = cabColumn('left');
    right = cabColumn('right');
    const noLabelToggle = left.querySelector('.cab-function-label-toggle');
    const noLabelExpandButton = left.querySelector('.cab-toggle-control');
    const noLabelGrid = left.querySelector('.cab-function-grid');
    const noLabelGridStyle = getComputedStyle(noLabelGrid);
    const noLabelGridColumns = noLabelGridStyle.gridTemplateColumns.split(' ').filter(Boolean).length;
    const noLabelMainFunctionSlots = noLabelGrid.querySelectorAll('.function-slot-button, .function-slot-empty').length;
    const noLabelActionsRect = left.querySelector('.cab-control-side-actions')?.getBoundingClientRect();
    const noLabelSpeedThrottleRect = left.querySelector('.cab-speed-throttle')?.getBoundingClientRect();
    const noLabelSpeedControlRect = left.querySelector('.cab-speed-control')?.getBoundingClientRect();
    const noLabelStopRect = left.querySelector('.cab-economic-stop')?.getBoundingClientRect();
    const noLabelFirstButton = noLabelGrid.querySelector('.function-slot-button');
    const noLabelFirstButtonRect = noLabelFirstButton?.getBoundingClientRect();
    const noLabelFirstKey = noLabelFirstButton?.querySelector('.function-key');
    const noLabelFirstIcon = noLabelFirstButton?.querySelector('.function-icon');
    const noLabelFirstKeyStyle = noLabelFirstKey ? getComputedStyle(noLabelFirstKey) : null;
    const noLabelFirstIconRect = noLabelFirstIcon?.getBoundingClientRect();
    const visibleFunctionLabelsWithoutNames = Array.from(noLabelGrid.querySelectorAll('.function-label'))
      .filter((label) => getComputedStyle(label).display !== 'none' && label.textContent.trim()).length;
    const noLabelButtonsOnlyUseIconAndKey = Array.from(noLabelGrid.querySelectorAll('.function-slot-button')).every((button) => {
      return button.querySelector('.function-icon-slot') && button.querySelector('.function-key') && button.classList.contains('without-label');
    });
    const noLabelButtonsHorizontal = Array.from(noLabelGrid.querySelectorAll('.function-slot-button')).every((button) => {
      const keyRect = button.querySelector('.function-key')?.getBoundingClientRect();
      const iconRect = button.querySelector('.function-icon-slot')?.getBoundingClientRect();
      if (!keyRect || !iconRect) {
        return false;
      }
      const keyCenterY = (keyRect.top + keyRect.bottom) / 2;
      const iconCenterY = (iconRect.top + iconRect.bottom) / 2;
      return keyRect.right <= iconRect.left + 2 && Math.abs(keyCenterY - iconCenterY) <= 3;
    });
    const rightGridAfterLeftToggle = right.querySelector('.cab-function-grid');
    const rightGridColumnsAfterLeftToggle = getComputedStyle(rightGridAfterLeftToggle).gridTemplateColumns.split(' ').filter(Boolean).length;
    const rightFunctionNameToggleIndependent = right.querySelector('.cab-function-label-toggle')?.getAttribute('aria-pressed') === rightFunctionNameToggleBefore;

    return {
      beforeSelection,
      rowToSelectId,
      rowToSelectClass,
      selectedVehicleId,
      leftHeaderTitle,
      rightHeaderTitle,
      leftHeaderText,
      filterInHeader,
      headerFilterRightOfTitle,
      initialLeftImage,
      initialRightImage,
      identityLines,
      actionTexts,
      economicStopIsRed,
      emergencyStopHighContrastText,
      emergencyStopStrongBorder,
      speedValueAboveThrottle,
      speedValueInRightControl,
      imageDoesNotOverlapSpeed,
      filtersCompactRight,
      identityHasAddressBadge: Boolean(addressBadge && !addressBadge.includes('编号')),
      identityHasPrimaryName: Boolean(identityName?.textContent.trim()),
      identityHasNoRailway: !left.querySelector('.cab-control-railway'),
      identityHasFullNameTag: Boolean(fullNameTag?.textContent.trim()),
      identityHasBrandTag: Boolean(brandTag?.textContent.trim()),
      identityHasArticleNumberTag: Boolean(articleNumberTag?.textContent.trim()),
      fullNameAfterAddress,
      brandArticleSameLine,
      identityTagsDoNotGrow,
      infoRegionOne,
      imageRegionTwo,
      imageElementCenteredInRegion,
      imageElementInsideRegion,
      imageObjectFitContain,
      imageContentCenteredInRegion,
      imageContentFullyVisibleInRegion,
      functionsRegionsFourFive,
      actionsRegionsThreeSix,
      imageLeftOfSpeed,
      speedThrottleVertical,
      speedThrottleTouchReady,
      speedControlAboveDirection,
      emergencyStopHeight,
      lamp: {w: Math.round(lampRect.width), h: Math.round(lampRect.height)},
      panelBeforeList: Boolean(panel && list && (panel.compareDocumentPosition(list) & Node.DOCUMENT_POSITION_FOLLOWING)),
      imageInsideRow: imageRect.left >= rowRect.left && imageRect.right <= rowRect.right && imageRect.top >= rowRect.top && imageRect.bottom <= rowRect.bottom,
      selectionChanged: Boolean(selectedVehicleId && selectedVehicleId !== beforeSelection),
      otherCabSelectedVehicleDisabled,
      blockedSelectionDidNotChange: rightSelectedAfter === rightSelectedBefore,
      listCanScroll,
      scrollBeforeListSelection,
      scrollAfterListSelection,
      selectionKeepsScrollPosition,
      expandedButtonCount,
      expandedListVisible,
      expandedListBelowPanel,
      collapsedButtonCount,
      collapsedFunctionContentCentered,
      speedThrottleInsideControl,
      speedThrottleHeight: speedThrottleRect?.height || 0,
      actionStackUsesFullHeight,
      speedThrottleAriaMax: speedThrottle?.getAttribute('aria-valuemax') || "",
      mainFunctionSlots,
      toggleFunctionHasTriggerMode: Boolean(toggleButton),
      gridColumns,
      gridDisplay: gridStyle.display,
      gridTemplateColumns: gridStyle.gridTemplateColumns,
      defaultFunctionNumberTogglePressed,
      defaultFunctionNameTogglePressed,
      functionNumberToggleBeforeName,
      functionNameToggleBeforeCategory,
      noNumberTogglePressed,
      visibleFunctionNumbersWithoutNumbers,
      noNumberButtonsKeepIconAndLabel,
      noNumberContentCentered,
      rightFunctionNumberToggleIndependent,
      rightFunctionNumbersStillVisible,
      noLabelTogglePressed: noLabelToggle?.getAttribute('aria-pressed') === 'false',
      noLabelExpandDisabled: noLabelExpandButton?.disabled === true,
      noLabelGridColumns,
      noLabelMainFunctionSlots,
      noLabelSpeedThrottleHeight: noLabelSpeedThrottleRect?.height || 0,
      noLabelActionStackUsesFullHeight: Boolean(noLabelActionsRect && noLabelSpeedControlRect && noLabelStopRect
        && noLabelSpeedControlRect.top <= noLabelActionsRect.top + 2
        && noLabelStopRect.bottom >= noLabelActionsRect.bottom - 2),
      visibleFunctionLabelsWithoutNames,
      noLabelButtonsOnlyUseIconAndKey,
      noLabelButtonsHorizontal,
      noLabelKeyFontSize: Number.parseFloat(noLabelFirstKeyStyle?.fontSize || "0"),
      noLabelIconSize: Math.min(noLabelFirstIconRect?.width || 0, noLabelFirstIconRect?.height || 0),
      noLabelButtonHeight: noLabelFirstButtonRect?.height || 0,
      rightFunctionNameToggleIndependent,
      rightGridColumnsAfterLeftToggle
    };
  })()`);

  const assertions = [
    ["lampIsRound", data.lamp.w === data.lamp.h && data.lamp.w >= 16],
    ["leftTitleRenamed", data.leftHeaderTitle === "左控制台"],
    ["rightTitleRenamed", data.rightHeaderTitle === "右控制台"],
    ["headerHasNoSelectedSummary", !data.leftHeaderText.includes(" / ") && !data.leftHeaderText.includes("未选择")],
    ["filtersMovedIntoHeader", data.filterInHeader === true],
    ["headerFilterRightOfTitle", data.headerFilterRightOfTitle === true],
    ["initialLeftImageElementCentered", data.initialLeftImage.imageElementCentered === true],
    ["initialLeftImageElementInsideBox", data.initialLeftImage.imageElementInsideBox === true],
    ["initialLeftImageObjectFitContain", data.initialLeftImage.imageObjectFitContain === true],
    ["initialLeftImageContentCentered", data.initialLeftImage.centered === true],
    ["initialLeftImageFullyVisible", data.initialLeftImage.fullyVisible === true],
    ["initialLeftImageBoxCentered", data.initialLeftImage.boxCentered === true],
    ["initialRightImageElementCentered", data.initialRightImage.imageElementCentered === true],
    ["initialRightImageElementInsideBox", data.initialRightImage.imageElementInsideBox === true],
    ["initialRightImageObjectFitContain", data.initialRightImage.imageObjectFitContain === true],
    ["initialRightImageContentCentered", data.initialRightImage.centered === true],
    ["initialRightImageFullyVisible", data.initialRightImage.fullyVisible === true],
    ["initialRightImageBoxCentered", data.initialRightImage.boxCentered === true],
    ["controlIdentityHasThreeRows", data.identityLines.length === 3 && data.identityLines.every((line) => line.length > 0)],
    ["identityHasPrimaryName", data.identityHasPrimaryName === true],
    ["identityHasAddressBadge", data.identityHasAddressBadge === true],
    ["identityHasFullNameTag", data.identityHasFullNameTag === true],
    ["identityHasBrandTag", data.identityHasBrandTag === true],
    ["identityHasArticleNumberTag", data.identityHasArticleNumberTag === true],
    ["identityFullNameAfterAddress", data.fullNameAfterAddress === true],
    ["identityBrandArticleSameLine", data.brandArticleSameLine === true],
    ["identityTagsDoNotGrow", data.identityTagsDoNotGrow === true],
    ["identityOmitsRailway", data.identityHasNoRailway === true],
    ["controlRegionOneInfo", data.infoRegionOne === true],
    ["controlRegionTwoImage", data.imageRegionTwo === true],
    ["controlImageElementCenteredInRegion", data.imageElementCenteredInRegion === true],
    ["controlImageElementInsideRegion", data.imageElementInsideRegion === true],
    ["controlImageObjectFitContain", data.imageObjectFitContain === true],
    ["controlImageContentCenteredInRegion", data.imageContentCenteredInRegion === true],
    ["controlImageContentFullyVisibleInRegion", data.imageContentFullyVisibleInRegion === true],
    ["controlRegionsFourFiveFunctions", data.functionsRegionsFourFive === true],
    ["controlRegionsThreeSixActions", data.actionsRegionsThreeSix === true],
    ["directionButtonsUseArrowMarks", data.actionTexts[0] === "←" && data.actionTexts[1] === "→"],
    ["emergencyStopLabel", data.actionTexts[2] === "紧急停车"],
    ["economicStopRed", data.economicStopIsRed === true],
    ["emergencyStopHighContrastText", data.emergencyStopHighContrastText === true],
    ["emergencyStopStrongBorder", data.emergencyStopStrongBorder === true],
    ["speedValueAboveThrottle", data.speedValueAboveThrottle === true],
    ["speedValueInRightControl", data.speedValueInRightControl === true],
    ["speedThrottleVertical", data.speedThrottleVertical === true],
    ["speedThrottleTouchReady", data.speedThrottleTouchReady === true],
    ["speedControlAboveDirection", data.speedControlAboveDirection === true],
    ["imageLeftOfSpeed", data.imageLeftOfSpeed === true],
    ["imageDoesNotOverlapSpeed", data.imageDoesNotOverlapSpeed === true],
    ["emergencyStopNotTall", data.emergencyStopHeight > 0 && data.emergencyStopHeight <= 48],
    ["filtersCompactRight", data.filtersCompactRight === true],
    ["panelBeforeList", data.panelBeforeList === true],
    ["imageInsideRow", data.imageInsideRow === true],
    ["selectionChanged", data.selectionChanged === true],
    ["otherCabSelectedVehicleDisabled", data.otherCabSelectedVehicleDisabled === true],
    ["blockedSelectionDidNotChange", data.blockedSelectionDidNotChange === true],
    ["selectionKeepsScrollPosition", data.selectionKeepsScrollPosition === true],
    ["expandedShowsMoreButtons", data.expandedButtonCount > data.collapsedButtonCount],
    ["expandedKeepsVehicleListVisible", data.expandedListVisible === true],
    ["expandedVehicleListBelowPanel", data.expandedListBelowPanel === true],
    ["collapsedHasTenButtons", data.collapsedButtonCount === 10],
    ["collapsedFunctionContentCentered", data.collapsedFunctionContentCentered === true],
    ["speedThrottleInsideControl", data.speedThrottleInsideControl === true],
    ["actionStackUsesFullHeight", data.actionStackUsesFullHeight === true],
    ["speedThrottleAriaMax126", data.speedThrottleAriaMax === "126"],
    ["mainFunctionSlotsFixed", data.mainFunctionSlots === 10],
    ["toggleFunctionHasTriggerMode", data.toggleFunctionHasTriggerMode === true],
    ["gridFiveColumns", data.gridColumns === 5],
    ["functionNumberToggleDefaultsPressed", data.defaultFunctionNumberTogglePressed === true],
    ["functionNameToggleDefaultsPressed", data.defaultFunctionNameTogglePressed === true],
    ["functionNumberToggleBeforeName", data.functionNumberToggleBeforeName === true],
    ["functionNameToggleBeforeCategory", data.functionNameToggleBeforeCategory === true],
    ["functionNumberToggleOffPressedState", data.noNumberTogglePressed === true],
    ["functionNumberToggleHidesFunctionKey", data.visibleFunctionNumbersWithoutNumbers === 0],
    ["functionNumberToggleKeepsIconAndLabel", data.noNumberButtonsKeepIconAndLabel === true],
    ["functionNumberToggleContentCentered", data.noNumberContentCentered === true],
    ["functionNumberToggleIsPerCab", data.rightFunctionNumberToggleIndependent === true && data.rightFunctionNumbersStillVisible === true],
    ["functionNameToggleOffPressedState", data.noLabelTogglePressed === true],
    ["functionNameToggleDisablesExpand", data.noLabelExpandDisabled === true],
    ["functionNameToggleShowsThirtyTwoSlots", data.noLabelMainFunctionSlots === 32],
    ["functionNameToggleUsesEightColumns", data.noLabelGridColumns === 8],
    ["functionNameToggleGrowsThrottleWithFullPanel", data.noLabelSpeedThrottleHeight >= data.speedThrottleHeight + 12],
    ["functionNameToggleActionStackUsesFullHeight", data.noLabelActionStackUsesFullHeight === true],
    ["functionNameToggleHidesTextLabels", data.visibleFunctionLabelsWithoutNames === 0],
    ["functionNameToggleKeepsIconAndKey", data.noLabelButtonsOnlyUseIconAndKey === true],
    ["functionNameToggleUsesHorizontalKeyIconLayout", data.noLabelButtonsHorizontal === true],
    ["functionNameToggleUsesLargerKeyText", data.noLabelKeyFontSize >= 13],
    ["functionNameToggleUsesLargerIcons", data.noLabelIconSize >= 20],
    ["functionNameToggleDoesNotGrowButtonFrame", data.noLabelButtonHeight <= 42.5],
    ["functionNameToggleIsPerCab", data.rightFunctionNameToggleIndependent === true && data.rightGridColumnsAfterLeftToggle === 5],
  ];

  assertNamedChecks("vehicle cab layout smoke", assertions, data);
  await assertCvTargetSwitching();
  await assertDcModeGating();

  await targetCdp("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 900,
    deviceScaleFactor: 2,
    mobile: true
  });
  await targetCdp("Page.navigate", {url: targetUrl});
  await waitForExpression("document.readyState === 'complete'");
  await waitForExpression("Boolean(document.querySelector('.cab-workspace .cab-function-grid .function-slot-button'))");

  const mobileFunctionLayoutData = await evaluate(`(async () => {
    const nextFrame = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    let left = document.querySelector('.cab-column[data-cab-id="left"]');
    const gridColumnCount = (grid) => {
      return getComputedStyle(grid).gridTemplateColumns.split(' ').filter(Boolean).length;
    };
    const childContentFits = (button) => {
      const buttonRect = button.getBoundingClientRect();
      return Array.from(button.children).every((child) => {
        const style = getComputedStyle(child);
        if (style.display === 'none') {
          return true;
        }
        const rect = child.getBoundingClientRect();
        return rect.left >= buttonRect.left - 1
          && rect.right <= buttonRect.right + 1
          && rect.top >= buttonRect.top - 1
          && rect.bottom <= buttonRect.bottom + 1;
      });
    };
    const functionButtonContentCentered = (button) => {
      const buttonRect = button.getBoundingClientRect();
      const visibleParts = ['.function-key', '.function-icon-slot', '.function-label']
        .map((selector) => button.querySelector(selector))
        .filter((part) => part && getComputedStyle(part).display !== 'none')
        .map((part) => part.getBoundingClientRect());
      if (!visibleParts.length) {
        return false;
      }
      const contentLeft = Math.min(...visibleParts.map((rect) => rect.left));
      const contentRight = Math.max(...visibleParts.map((rect) => rect.right));
      const contentTop = Math.min(...visibleParts.map((rect) => rect.top));
      const contentBottom = Math.max(...visibleParts.map((rect) => rect.bottom));
      const contentCenterX = (contentLeft + contentRight) / 2;
      const contentCenterY = (contentTop + contentBottom) / 2;
      const buttonCenterX = (buttonRect.left + buttonRect.right) / 2;
      const buttonCenterY = (buttonRect.top + buttonRect.bottom) / 2;
      return Math.abs(contentCenterX - buttonCenterX) <= 4
        && Math.abs(contentCenterY - buttonCenterY) <= 4;
    };
    const firstOverflow = (buttons) => {
      for (const button of buttons) {
        const buttonRect = button.getBoundingClientRect();
        for (const child of Array.from(button.children)) {
          const style = getComputedStyle(child);
          if (style.display === 'none') {
            continue;
          }
          const rect = child.getBoundingClientRect();
          const fits = rect.left >= buttonRect.left - 1
            && rect.right <= buttonRect.right + 1
            && rect.top >= buttonRect.top - 1
            && rect.bottom <= buttonRect.bottom + 1;
          if (!fits) {
            return {
              button: button.textContent.trim(),
              childClass: child.className,
              buttonRect: {
                left: Math.round(buttonRect.left),
                right: Math.round(buttonRect.right),
                top: Math.round(buttonRect.top),
                bottom: Math.round(buttonRect.bottom)
              },
              childRect: {
                left: Math.round(rect.left),
                right: Math.round(rect.right),
                top: Math.round(rect.top),
                bottom: Math.round(rect.bottom)
              }
            };
          }
        }
      }
      return null;
    };
    const labelsFitFixedButtonBox = (scope) => {
      return Array.from(scope.querySelectorAll('.function-label')).every((label) => {
        if (!label.textContent.trim() || getComputedStyle(label).display === 'none') {
          return true;
        }
        const buttonRect = label.closest('.function-slot-button')?.getBoundingClientRect();
        const labelRect = label.getBoundingClientRect();
        return Boolean(buttonRect)
          && labelRect.left >= buttonRect.left - 1
          && labelRect.right <= buttonRect.right + 1
          && labelRect.top >= buttonRect.top - 1
          && labelRect.bottom <= buttonRect.bottom + 1;
      });
    };
    const labelToggle = left.querySelector('.cab-function-label-toggle');
    if (labelToggle?.getAttribute('aria-pressed') === 'false') {
      labelToggle.click();
      await nextFrame();
      left = document.querySelector('.cab-column[data-cab-id="left"]');
    }
    const defaultGrid = left.querySelector('.cab-function-grid');
    const defaultButtons = Array.from(defaultGrid.querySelectorAll('.function-slot-button'));
    const defaultColumns = gridColumnCount(defaultGrid);
    const defaultButtonsFit = defaultButtons.every(childContentFits);
    const defaultOverflow = firstOverflow(defaultButtons);
    const defaultLabelsFitButtonBox = labelsFitFixedButtonBox(defaultGrid);
    const defaultButtonHeightsFixed = defaultButtons.every((button) => button.getBoundingClientRect().height <= 50);
    const defaultContentCentered = defaultButtons.every(functionButtonContentCentered);

    const compactToggle = left.querySelector('.cab-function-label-toggle');
    if (compactToggle?.getAttribute('aria-pressed') === 'true') {
      compactToggle.click();
    }
    await nextFrame();
    left = document.querySelector('.cab-column[data-cab-id="left"]');
    const compactGrid = left.querySelector('.cab-function-grid');
    const compactButtons = Array.from(compactGrid.querySelectorAll('.function-slot-button'));
    const compactMode = Boolean(compactToggle) && compactGrid.classList.contains('hide-function-labels');
    const compactColumns = gridColumnCount(compactGrid);
    const compactButtonsFit = compactButtons.every(childContentFits);
    const compactOverflow = firstOverflow(compactButtons);
    const compactButtonsHorizontal = compactButtons.every((button) => {
      const keyRect = button.querySelector('.function-key')?.getBoundingClientRect();
      const iconRect = button.querySelector('.function-icon-slot')?.getBoundingClientRect();
      if (!keyRect || !iconRect) {
        return false;
      }
      const keyCenterY = (keyRect.top + keyRect.bottom) / 2;
      const iconCenterY = (iconRect.top + iconRect.bottom) / 2;
      return keyRect.right <= iconRect.left + 2 && Math.abs(keyCenterY - iconCenterY) <= 3;
    });

    return {
      viewportWidth: window.innerWidth,
      defaultColumns,
      defaultButtonsFit,
      defaultOverflow,
      defaultLabelsFitButtonBox,
      defaultButtonHeightsFixed,
      defaultContentCentered,
      compactMode,
      compactColumns,
      compactButtonsFit,
      compactOverflow,
      compactButtonsHorizontal
    };
  })()`);

  const mobileFunctionLayoutAssertions = [
    ["mobileDefaultColumnsAdaptToWidth", mobileFunctionLayoutData.defaultColumns > 1 && mobileFunctionLayoutData.defaultColumns <= 3],
    ["mobileDefaultButtonContentFits", mobileFunctionLayoutData.defaultButtonsFit === true],
    ["mobileDefaultLabelsFitButtonBox", mobileFunctionLayoutData.defaultLabelsFitButtonBox === true],
    ["mobileDefaultButtonHeightsFixed", mobileFunctionLayoutData.defaultButtonHeightsFixed === true],
    ["mobileDefaultContentCentered", mobileFunctionLayoutData.defaultContentCentered === true],
    ["mobileCompactModeEnabled", mobileFunctionLayoutData.compactMode === true],
    ["mobileCompactColumnsAdaptToWidth", mobileFunctionLayoutData.compactColumns > 1 && mobileFunctionLayoutData.compactColumns <= 4],
    ["mobileCompactButtonContentFits", mobileFunctionLayoutData.compactButtonsFit === true],
    ["mobileCompactButtonsStayHorizontal", mobileFunctionLayoutData.compactButtonsHorizontal === true],
  ];
  assertNamedChecks("vehicle cab mobile function layout smoke", mobileFunctionLayoutAssertions, mobileFunctionLayoutData);

  await targetCdp("Emulation.setDeviceMetricsOverride", {
    width: 1600,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false
  });
  await targetCdp("Page.navigate", {url: targetUrl});
  await waitForExpression("document.readyState === 'complete'");
  await waitForExpression("Boolean(document.querySelector('.cab-workspace .cab-vehicle-row'))");
  await installFetchInterceptor();

  const beforeMouseSelection = await evaluate(`document.querySelector('.cab-column[data-cab-id="left"] .cab-vehicle-row.selected')?.dataset.vehicleId || ''`);
  await mouseClick('.cab-column[data-cab-id="left"] .cab-vehicle-row:not(.selected):not(.disabled-by-other-cab) .cab-vehicle-select');
  await nextFrame();
  const afterMouseSelection = await evaluate(`document.querySelector('.cab-column[data-cab-id="left"] .cab-vehicle-row.selected')?.dataset.vehicleId || ''`);

  await mouseClick('.cab-column[data-cab-id="left"] .cab-toggle-control');
  await nextFrame();
  const expandedByMouse = await evaluate(`document.querySelector('.cab-column[data-cab-id="left"] .cab-toggle-control')?.textContent.includes('返回列表') === true`);
  await mouseClick('.cab-column[data-cab-id="left"] .cab-toggle-control');
  await nextFrame();

  const beforeSpeed = await evaluate(`parseInt(document.querySelector('.cab-column[data-cab-id="left"] .cab-speed-value')?.textContent || "0", 10)`);
  await mouseDragVertical('.cab-column[data-cab-id="left"] .cab-speed-throttle', 0.75);
  await nextFrame();
  const afterSpeed = await evaluate(`parseInt(document.querySelector('.cab-column[data-cab-id="left"] .cab-speed-value')?.textContent || "0", 10)`);

  await mouseClick('.cab-column[data-cab-id="left"] .cab-function-grid .function-slot-button[data-trigger-mode="toggle"]');
  await nextFrame();
  const functionClicked = await evaluate(`window.__digsightSmokeRequests.some((request) => request.url.includes('/api/loco/function'))`);
  const toggleFunctionStayedActive = await evaluate(`Boolean(document.querySelector('.cab-column[data-cab-id="left"] .cab-function-grid .function-slot-button[data-trigger-mode="toggle"]')?.classList.contains("active"))`);
  await mouseClick('.cab-column[data-cab-id="left"] .cab-function-grid .function-slot-button[data-trigger-mode="toggle"]');
  await nextFrame();
  const toggleFunctionClearedAfterSecondClick = await evaluate(`!document.querySelector('.cab-column[data-cab-id="left"] .cab-function-grid .function-slot-button[data-trigger-mode="toggle"]')?.classList.contains("active")`);

  const dragData = await evaluate(`(async () => {
    const nextFrame = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const left = document.querySelector('.cab-column[data-cab-id="left"]');
    const list = left.querySelector('.cab-vehicle-list');
    const rows = Array.from(list.querySelectorAll('.cab-vehicle-row:not(.disabled-by-other-cab)'));
    if (rows.length < 2) {
      return {skipped: true};
    }
    window.__digsightSmokeRequests = [];
    const before = Array.from(list.querySelectorAll('.cab-vehicle-row')).map((row) => row.dataset.vehicleId);
    const dragged = rows[0];
    const target = rows[1];
    const transfer = new DataTransfer();
    dragged.dispatchEvent(new DragEvent('dragstart', {bubbles: true, dataTransfer: transfer}));
    const rect = target.getBoundingClientRect();
    target.dispatchEvent(new DragEvent('dragover', {
      bubbles: true,
      cancelable: true,
      clientY: rect.bottom - 1,
      dataTransfer: transfer
    }));
    const during = Array.from(list.querySelectorAll('.cab-vehicle-row')).map((row) => row.dataset.vehicleId);
    target.dispatchEvent(new DragEvent('drop', {
      bubbles: true,
      cancelable: true,
      clientY: rect.bottom - 1,
      dataTransfer: transfer
    }));
    await nextFrame();
    return {
      skipped: false,
      before,
      during,
      orderSaved: window.__digsightSmokeRequests.some((request) => request.url.includes('/api/vehicles/order'))
    };
  })()`);

  const editTarget = await evaluate(`(async () => {
    const payload = await fetch('/api/state').then((response) => response.json());
    const state = payload.data || {};
    const mode = String(state.controller?.track_mode || '').toLowerCase();
    const vehicle = (state.vehicles || []).find((item) => Number(item.type ?? 0) !== 3
      && String(item.track_mode || '').toLowerCase() === mode);
    return vehicle ? {id: String(vehicle.id), name: vehicle.name || ''} : null;
  })()`);
  let editOpenedName = "";
  let normalEditorOpened = false;
  let editorLayoutData = {skipped: true};
  let consistEditorLayoutData = {skipped: true};
  let consistEditorOpened = false;
  let energyIconData = {skipped: true};
  if (editTarget?.id) {
    await mouseClick(`.cab-column[data-cab-id="left"] .cab-vehicle-row[data-vehicle-id="${editTarget.id}"] .cab-vehicle-edit`);
    await nextFrame();
    await waitForExpression("document.querySelector('#vehicleEditView:not([hidden]) form input[type=\"text\"]')");
    normalEditorOpened = true;
    editOpenedName = await evaluate(`document.querySelector('#vehicleEditView form input[type="text"]')?.value || ''`);
    editorLayoutData = await evaluate(`(() => {
      const editorLayout = document.querySelector('.vehicle-editor-layout');
      const leftColumn = document.querySelector('.vehicle-editor-left-column');
      const functionColumn = document.querySelector('.vehicle-editor-function-column');
      const imageUpload = leftColumn?.querySelector('.vehicle-image-upload');
      const basicInfo = leftColumn?.querySelector('.vehicle-editor-basic-info');
      const functionEditor = functionColumn?.querySelector('.function-editor-grid');
      const rowClassNames = Array.from(basicInfo?.children || []).map((child) => child.className || "");
      const nameRow = basicInfo?.querySelector('.vehicle-editor-name-row');
      const kindRow = basicInfo?.querySelector('.vehicle-editor-kind-row');
      const runningRow = basicInfo?.querySelector('.vehicle-editor-running-row');
      const modelRow = basicInfo?.querySelector('.vehicle-editor-model-row');
      const layoutRect = editorLayout?.getBoundingClientRect();
      const leftRect = leftColumn?.getBoundingClientRect();
      const functionRect = functionColumn?.getBoundingClientRect();
      const nameRowRect = nameRow?.getBoundingClientRect();
      const nameFieldRect = nameRow?.querySelector('.vehicle-field-name')?.getBoundingClientRect();
      const fullNameFieldRect = nameRow?.querySelector('.vehicle-field-full-name')?.getBoundingClientRect();
      const editorColumnsRatio = Boolean(layoutRect && leftRect && functionRect)
        && leftRect.width / layoutRect.width >= 0.27
        && leftRect.width / layoutRect.width <= 0.39
        && functionRect.width / layoutRect.width >= 0.56;
      const imageAboveBasicInfo = Boolean(imageUpload && basicInfo)
        && imageUpload.getBoundingClientRect().bottom <= basicInfo.getBoundingClientRect().top + 8;
      const functionEditorRightOfBasicInfo = Boolean(functionRect && leftRect)
        && functionRect.left >= leftRect.right - 2;
      const nameRowUsesOneThirdTwoThirds = Boolean(nameRowRect && nameFieldRect && fullNameFieldRect)
        && nameFieldRect.width / nameRowRect.width >= 0.28
        && nameFieldRect.width / nameRowRect.width <= 0.38
        && fullNameFieldRect.width / nameRowRect.width >= 0.58;
      const editorRowsOrdered = rowClassNames.slice(0, 4).join('|')
        === 'vehicle-editor-name-row|vehicle-editor-kind-row|vehicle-editor-running-row|vehicle-editor-model-row';
      const rowContainsOrderedFields = (row, selectors) => {
        const fields = selectors.map((selector) => row?.querySelector(selector));
        return fields.every(Boolean)
          && fields.every((field, index) => index === 0 || field.getBoundingClientRect().left >= fields[index - 1].getBoundingClientRect().right - 2);
      };
      return {
        skipped: false,
        editorColumnsRatio,
        imageAboveBasicInfo,
        functionEditorRightOfBasicInfo,
        functionEditorInRightColumn: Boolean(functionEditor),
        editorRowsOrdered,
        nameRowUsesOneThirdTwoThirds,
        kindRowHasTypeAndDynamicKind: Boolean(kindRow?.querySelector('.vehicle-field-type') && kindRow?.querySelector('.vehicle-kind-dynamic-fields')),
        runningRowFieldsOrdered: rowContainsOrderedFields(runningRow, ['.vehicle-field-address', '.vehicle-field-scale', '.vehicle-field-max-speed', '.vehicle-field-railway']),
        modelRowFieldsOrdered: rowContainsOrderedFields(modelRow, ['.vehicle-field-brand', '.vehicle-field-article-number', '.vehicle-field-decoder-type'])
      };
    })()`);
    energyIconData = await evaluate(`(() => {
      const energyChoices = Array.from(document.querySelectorAll('.vehicle-energy-field .vehicle-kind-choice'));
      const energyGlyphs = energyChoices.map((choice) => choice.querySelector('.vehicle-energy-glyph')?.className || "");
      const energyGlyphsComplete = ["vehicle-energy-diesel", "vehicle-energy-electric", "vehicle-energy-steam", "vehicle-energy-hybrid"]
        .every((className) => energyGlyphs.some((value) => value.includes(className)));
      const electricHasBodyWheelsPantographAndLightning = Boolean(document.querySelector('.vehicle-energy-electric .vehicle-energy-body'))
        && document.querySelectorAll('.vehicle-energy-electric .vehicle-energy-wheel').length >= 3
        && Boolean(document.querySelector('.vehicle-energy-electric .vehicle-energy-pantograph'))
        && Boolean(document.querySelector('.vehicle-energy-electric .vehicle-energy-pantograph-diamond'))
        && Boolean(document.querySelector('.vehicle-energy-electric .vehicle-energy-body > .vehicle-energy-bolt'))
        && !document.querySelector('.vehicle-energy-electric .vehicle-energy-electric-sign');
      const steamHasSteamLocomotiveShape = Boolean(document.querySelector('.vehicle-energy-steam .vehicle-energy-boiler'))
        && Boolean(document.querySelector('.vehicle-energy-steam .vehicle-energy-cab'))
        && Boolean(document.querySelector('.vehicle-energy-steam .vehicle-energy-smokestack'))
        && Boolean(document.querySelector('.vehicle-energy-steam .vehicle-energy-smoke'))
        && document.querySelectorAll('.vehicle-energy-steam .vehicle-energy-wheel').length >= 4;
      const dieselHasBodyWheelsAndEngineOnly = Boolean(document.querySelector('.vehicle-energy-diesel .vehicle-energy-body'))
        && document.querySelectorAll('.vehicle-energy-diesel .vehicle-energy-wheel').length >= 3
        && Boolean(document.querySelector('.vehicle-energy-diesel .vehicle-energy-engine'))
        && !document.querySelector('.vehicle-energy-diesel .vehicle-energy-pantograph')
        && !document.querySelector('.vehicle-energy-diesel .vehicle-energy-electric-sign');
      const hybridHasEngineAndPantograph = Boolean(document.querySelector('.vehicle-energy-hybrid .vehicle-energy-engine'))
        && document.querySelectorAll('.vehicle-energy-hybrid .vehicle-energy-wheel').length >= 3
        && Boolean(document.querySelector('.vehicle-energy-hybrid .vehicle-energy-pantograph'))
        && Boolean(document.querySelector('.vehicle-energy-hybrid .vehicle-energy-pantograph-diamond'))
        && !document.querySelector('.vehicle-energy-hybrid .vehicle-energy-electric-sign');
      const styleColor = (selector) => {
        const element = document.querySelector(selector);
        return element ? getComputedStyle(element).color : "";
      };
      const energyIconColorsMatch = styleColor('.vehicle-energy-diesel') === 'rgb(220, 38, 38)'
        && styleColor('.vehicle-energy-electric') === 'rgb(234, 179, 8)'
        && styleColor('.vehicle-energy-steam') === 'rgb(17, 24, 39)'
        && styleColor('.vehicle-energy-hybrid') === 'rgb(22, 163, 74)';
      const electricBody = document.querySelector('.vehicle-energy-electric .vehicle-energy-body');
      const electricBodyBackgroundTransparent = electricBody
        ? getComputedStyle(electricBody).backgroundColor === 'rgba(0, 0, 0, 0)'
        : false;
      return {
        skipped: false,
        energyGlyphsComplete,
        electricHasBodyWheelsPantographAndLightning,
        steamHasSteamLocomotiveShape,
        dieselHasBodyWheelsAndEngineOnly,
        hybridHasEngineAndPantograph,
        energyIconColorsMatch,
        electricBodyBackgroundTransparent
      };
    })()`);
  }
  const consistEditTarget = await evaluate(`(async () => {
    const payload = await fetch('/api/state').then((response) => response.json());
    const state = payload.data || {};
    const mode = String(state.controller?.track_mode || '').toLowerCase();
    const vehicle = (state.vehicles || []).find((item) => Number(item.type ?? 0) === 3
      && String(item.track_mode || '').toLowerCase() === mode);
    return vehicle ? {id: String(vehicle.id), name: vehicle.name || ''} : null;
  })()`);
  if (consistEditTarget?.id) {
    await evaluate(`document.querySelector('#vehicleEditView:not([hidden]) .subview-toolbar button')?.click()`);
    await nextFrame();
    await waitForExpression("document.querySelector('#vehicleRegistry:not([hidden]) .cab-workspace')");
    await mouseClick(`.cab-column[data-cab-id="left"] .cab-vehicle-row[data-vehicle-id="${consistEditTarget.id}"] .cab-vehicle-edit`);
    await waitForExpression("document.querySelector('#vehicleEditView:not([hidden]) .vehicle-consist-editor-layout')");
    consistEditorOpened = true;
    consistEditorLayoutData = await evaluate(`(() => {
      const editorLayout = document.querySelector('.vehicle-consist-editor-layout');
      const leftColumn = document.querySelector('.vehicle-consist-editor-left-column');
      const functionColumn = document.querySelector('.vehicle-consist-editor-function-column');
      const imageUpload = leftColumn?.querySelector('.vehicle-image-upload');
      const basicInfo = leftColumn?.querySelector('.vehicle-consist-basic-info');
      const consistNameRow = basicInfo?.querySelector('.vehicle-consist-name-row');
      const consistKindRow = basicInfo?.querySelector('.vehicle-consist-kind-row');
      const functionPanel = functionColumn?.querySelector('.vehicle-consist-function-panel');
      const layoutRect = editorLayout?.getBoundingClientRect();
      const leftRect = leftColumn?.getBoundingClientRect();
      const functionRect = functionColumn?.getBoundingClientRect();
      const nameFieldRect = consistNameRow?.querySelector('.vehicle-field-name')?.getBoundingClientRect();
      const scaleFieldRect = consistNameRow?.querySelector('.vehicle-field-scale')?.getBoundingClientRect();
      const syncRect = consistNameRow?.querySelector('.sync-toggle-inline')?.getBoundingClientRect();
      const kindField = consistKindRow?.querySelector('.vehicle-consist-kind-field');
      const functionColumnChildren = Array.from(functionColumn?.children || []).map((child) => child.className || child.tagName);
      return {
        skipped: false,
        consistColumnsRatio: Boolean(layoutRect && leftRect && functionRect)
          && leftRect.width / layoutRect.width >= 0.27
          && leftRect.width / layoutRect.width <= 0.39
          && functionRect.width / layoutRect.width >= 0.56,
        consistImageAboveBasicInfo: Boolean(imageUpload && basicInfo)
          && imageUpload.getBoundingClientRect().bottom <= basicInfo.getBoundingClientRect().top + 8,
        consistFunctionColumnRight: Boolean(functionRect && leftRect)
          && functionRect.left >= leftRect.right - 2,
        consistFunctionColumnOnlyPanel: functionColumnChildren.length === 1
          && functionColumnChildren[0] === 'vehicle-consist-function-panel',
        consistBasicInfoInLeftColumn: Boolean(basicInfo?.querySelector('.vehicle-consist-name-row')
          && basicInfo?.querySelector('.vehicle-consist-kind-row')
          && basicInfo?.querySelector('.vehicle-category-editor')
          && basicInfo?.querySelector('.vehicle-consist-member-list')),
        consistSyncToggleInLeftColumn: Boolean(leftColumn?.querySelector('.sync-toggle-inline'))
          && !functionColumn?.querySelector('.sync-toggle-inline'),
        consistFunctionPanelInRightColumn: Boolean(functionPanel),
        consistFirstRowPlacesSyncAfterScale: Boolean(nameFieldRect && scaleFieldRect && syncRect)
          && nameFieldRect.right <= scaleFieldRect.left + 2
          && scaleFieldRect.right <= syncRect.left + 2,
        consistScaleFieldCompact: Boolean(scaleFieldRect && nameFieldRect)
          && scaleFieldRect.width <= 90
          && nameFieldRect.width >= scaleFieldRect.width * 2.2,
        consistKindStandaloneRow: Boolean(kindField)
          && consistKindRow?.children.length === 1
          && !consistKindRow.querySelector('.sync-toggle-inline'),
        consistKindRowBelowNameRow: Boolean(consistNameRow && consistKindRow)
          && consistNameRow.getBoundingClientRect().bottom <= consistKindRow.getBoundingClientRect().top + 8
      };
    })()`);
  }

  const interactionData = {
    ...data,
    beforeMouseSelection,
    afterMouseSelection,
    expandedByMouse,
    beforeSpeed,
    afterSpeed,
    functionClicked,
    toggleFunctionStayedActive,
    toggleFunctionClearedAfterSecondClick,
    dragData,
    editTarget,
    editOpenedName,
    normalEditorOpened,
    editorLayoutData,
    consistEditTarget,
    consistEditorOpened,
    consistEditorLayoutData,
    energyIconData
  };

  const mouseAssertions = [
    ["mouseSelectionChanged", afterMouseSelection && afterMouseSelection !== beforeMouseSelection],
    ["mouseExpandWorks", expandedByMouse === true],
    ["mouseSpeedDragWorks", afterSpeed !== beforeSpeed],
    ["mouseFunctionClickWorks", functionClicked === true],
    ["toggleFunctionStayedActive", toggleFunctionStayedActive === true],
    ["toggleFunctionClearedAfterSecondClick", toggleFunctionClearedAfterSecondClick === true],
    ["dragPreviewReordersRows", dragData.skipped || dragData.during.join("|") !== dragData.before.join("|")],
    ["dragDropSavesOrder", dragData.skipped || dragData.orderSaved === true],
    ["normalVehicleEditTargetFound", Boolean(editTarget?.id)],
    ["normalVehicleEditorOpened", normalEditorOpened === true],
    ["mouseEditOpensClickedVehicle", !editTarget || editOpenedName === editTarget.name],
    ["vehicleEditorUsesTwoColumns", editorLayoutData.skipped || editorLayoutData.editorColumnsRatio === true],
    ["vehicleEditorImageAboveBasicInfo", editorLayoutData.skipped || editorLayoutData.imageAboveBasicInfo === true],
    ["vehicleEditorFunctionColumnRight", editorLayoutData.skipped || editorLayoutData.functionEditorRightOfBasicInfo === true],
    ["vehicleEditorFunctionGridInRightColumn", editorLayoutData.skipped || editorLayoutData.functionEditorInRightColumn === true],
    ["vehicleEditorRowsOrdered", editorLayoutData.skipped || editorLayoutData.editorRowsOrdered === true],
    ["vehicleEditorNameRowRatio", editorLayoutData.skipped || editorLayoutData.nameRowUsesOneThirdTwoThirds === true],
    ["vehicleEditorKindRowHasTypeAndDynamicKind", editorLayoutData.skipped || editorLayoutData.kindRowHasTypeAndDynamicKind === true],
    ["vehicleEditorRunningRowFieldsOrdered", editorLayoutData.skipped || editorLayoutData.runningRowFieldsOrdered === true],
    ["vehicleEditorModelRowFieldsOrdered", editorLayoutData.skipped || editorLayoutData.modelRowFieldsOrdered === true],
    ["consistVehicleEditTargetFound", Boolean(consistEditTarget?.id)],
    ["consistVehicleEditorOpened", consistEditorOpened === true],
    ["consistEditorUsesTwoColumns", consistEditorLayoutData.skipped || consistEditorLayoutData.consistColumnsRatio === true],
    ["consistEditorImageAboveBasicInfo", consistEditorLayoutData.skipped || consistEditorLayoutData.consistImageAboveBasicInfo === true],
    ["consistEditorFunctionColumnRight", consistEditorLayoutData.skipped || consistEditorLayoutData.consistFunctionColumnRight === true],
    ["consistEditorFunctionColumnOnlyPanel", consistEditorLayoutData.skipped || consistEditorLayoutData.consistFunctionColumnOnlyPanel === true],
    ["consistEditorBasicInfoInLeftColumn", consistEditorLayoutData.skipped || consistEditorLayoutData.consistBasicInfoInLeftColumn === true],
    ["consistEditorSyncToggleInLeftColumn", consistEditorLayoutData.skipped || consistEditorLayoutData.consistSyncToggleInLeftColumn === true],
    ["consistEditorFunctionPanelInRightColumn", consistEditorLayoutData.skipped || consistEditorLayoutData.consistFunctionPanelInRightColumn === true],
    ["consistEditorSyncAfterScale", consistEditorLayoutData.skipped || consistEditorLayoutData.consistFirstRowPlacesSyncAfterScale === true],
    ["consistEditorScaleFieldCompact", consistEditorLayoutData.skipped || consistEditorLayoutData.consistScaleFieldCompact === true],
    ["consistEditorKindStandaloneRow", consistEditorLayoutData.skipped || consistEditorLayoutData.consistKindStandaloneRow === true],
    ["consistEditorKindRowBelowNameRow", consistEditorLayoutData.skipped || consistEditorLayoutData.consistKindRowBelowNameRow === true],
    ["energyGlyphsComplete", energyIconData.skipped || energyIconData.energyGlyphsComplete === true],
    ["electricHasBodyWheelsPantographAndLightning", energyIconData.skipped || energyIconData.electricHasBodyWheelsPantographAndLightning === true],
    ["steamHasSteamLocomotiveShape", energyIconData.skipped || energyIconData.steamHasSteamLocomotiveShape === true],
    ["dieselHasBodyWheelsAndEngineOnly", energyIconData.skipped || energyIconData.dieselHasBodyWheelsAndEngineOnly === true],
    ["hybridHasEngineAndPantograph", energyIconData.skipped || energyIconData.hybridHasEngineAndPantograph === true],
    ["energyIconColorsMatch", energyIconData.skipped || energyIconData.energyIconColorsMatch === true],
    ["electricBodyBackgroundTransparent", energyIconData.skipped || energyIconData.electricBodyBackgroundTransparent === true],
  ];

  await assertCabSelection({data: interactionData});
  await assertFunctionButtonState({data: interactionData, mobileFunctionLayoutData});
  await assertVehicleDragOrdering({data: interactionData});
  assertNamedChecks("vehicle cab mouse smoke", mouseAssertions, interactionData);

  await targetCdp("Emulation.setDeviceMetricsOverride", {
    width: 390,
    height: 844,
    deviceScaleFactor: 2,
    mobile: true
  });
  await targetCdp("Page.navigate", {url: targetUrl});
  await waitForExpression("document.readyState === 'complete'");
  await waitForExpression("Boolean(document.querySelector('.cab-workspace .cab-vehicle-row'))");
  const mobileData = await evaluate(`(async () => {
    const imageOpaqueContentRect = async (image) => {
      if (!image || !image.complete || !image.naturalWidth || !image.naturalHeight) {
        return null;
      }
      const canvas = document.createElement('canvas');
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const context = canvas.getContext('2d', {willReadFrequently: true});
      context.drawImage(image, 0, 0);
      const {data} = context.getImageData(0, 0, canvas.width, canvas.height);
      let minX = canvas.width;
      let minY = canvas.height;
      let maxX = -1;
      let maxY = -1;
      for (let y = 0; y < canvas.height; y += 1) {
        for (let x = 0; x < canvas.width; x += 1) {
          const index = (y * canvas.width + x) * 4;
          const alpha = data[index + 3];
          const nearWhite = data[index] >= 245 && data[index + 1] >= 245 && data[index + 2] >= 245;
          if (alpha <= 12 || nearWhite) {
            continue;
          }
          minX = Math.min(minX, x);
          minY = Math.min(minY, y);
          maxX = Math.max(maxX, x + 1);
          maxY = Math.max(maxY, y + 1);
        }
      }
      if (maxX < minX || maxY < minY) {
        return null;
      }
      const imageRect = image.getBoundingClientRect();
      const naturalRatio = image.naturalWidth / image.naturalHeight;
      const rectRatio = imageRect.width / imageRect.height;
      let renderedWidth = imageRect.width;
      let renderedHeight = imageRect.height;
      let offsetX = 0;
      let offsetY = 0;
      if (rectRatio > naturalRatio) {
        renderedWidth = imageRect.height * naturalRatio;
        offsetX = (imageRect.width - renderedWidth) / 2;
      } else {
        renderedHeight = imageRect.width / naturalRatio;
        offsetY = (imageRect.height - renderedHeight) / 2;
      }
      const scaleX = renderedWidth / image.naturalWidth;
      const scaleY = renderedHeight / image.naturalHeight;
      return {
        left: imageRect.left + offsetX + minX * scaleX,
        right: imageRect.left + offsetX + maxX * scaleX,
        top: imageRect.top + offsetY + minY * scaleY,
        bottom: imageRect.top + offsetY + maxY * scaleY
      };
    };
    const left = document.querySelector('.cab-column[data-cab-id="left"]');
    const header = left?.querySelector('.cab-header');
    const title = header?.querySelector('h2');
    const headerControls = header?.querySelector('.cab-header-controls');
    const filterBar = header?.querySelector('.cab-filter-bar');
    const titleRect = title?.getBoundingClientRect();
    const controlsRect = headerControls?.getBoundingClientRect();
    const filterRect = filterBar?.getBoundingClientRect();
    const childHeights = Array.from(filterBar?.children || []).map((child) => child.getBoundingClientRect().height);
    const functionLabels = Array.from(left?.querySelectorAll('.cab-function-grid .function-label') || [])
      .filter((label) => label.textContent.trim());
    const firstFunctionLabelStyle = functionLabels[0] ? getComputedStyle(functionLabels[0]) : null;
    const stopButton = left?.querySelector('.cab-economic-stop');
    const stopRect = stopButton?.getBoundingClientRect();
    const stopStyle = stopButton ? getComputedStyle(stopButton) : null;
    const infoRect = left?.querySelector('.cab-control-info')?.getBoundingClientRect();
    const mediaRect = left?.querySelector('.cab-control-media')?.getBoundingClientRect();
    const functionGridRect = left?.querySelector('.cab-control-main-row > .cab-function-grid')?.getBoundingClientRect();
    const functionButtons = Array.from(left?.querySelectorAll('.cab-function-grid .function-slot-button') || []);
    const actionsRect = left?.querySelector('.cab-control-side-actions')?.getBoundingClientRect();
    const imageRect = left?.querySelector('.cab-control-image')?.getBoundingClientRect();
    const imageElement = left?.querySelector('.cab-control-image img');
    const imageElementRect = imageElement?.getBoundingClientRect();
    const imageContentRect = await imageOpaqueContentRect(imageElement);
    const imageElementStyle = imageElement ? getComputedStyle(imageElement) : null;
    const speedRect = left?.querySelector('.cab-speed-control')?.getBoundingClientRect();
    const speedThrottleRect = left?.querySelector('.cab-speed-throttle')?.getBoundingClientRect();
    const speedThrottleStyle = left?.querySelector('.cab-speed-throttle')
      ? getComputedStyle(left.querySelector('.cab-speed-throttle'))
      : null;
    const directionRect = left?.querySelector('.cab-direction-row')?.getBoundingClientRect();
    const headerStyle = header ? getComputedStyle(header) : null;
    const filterStyle = filterBar ? getComputedStyle(filterBar) : null;
    return {
      headerRow: Boolean(headerStyle && headerStyle.flexDirection === 'row' && headerStyle.flexWrap === 'nowrap'),
      headerControlsInline: Boolean(titleRect && controlsRect
        && Math.abs(((titleRect.top + titleRect.bottom) / 2) - ((controlsRect.top + controlsRect.bottom) / 2)) <= 10),
      filterSingleLine: Boolean(filterRect && childHeights.length
        && filterRect.height <= Math.max(...childHeights) + 6),
      filterUsesCompactColumns: Boolean(filterStyle && filterStyle.gridTemplateColumns.split(' ').filter(Boolean).length === 5),
      functionLabelsFitButtons: functionLabels.every((label) => {
        if (getComputedStyle(label).display === 'none') {
          return true;
        }
        const buttonRect = label.closest('.function-slot-button')?.getBoundingClientRect();
        const labelRect = label.getBoundingClientRect();
        return Boolean(buttonRect)
          && labelRect.left >= buttonRect.left - 1
          && labelRect.right <= buttonRect.right + 1
          && labelRect.top >= buttonRect.top - 1
          && labelRect.bottom <= buttonRect.bottom + 1;
      }),
      functionButtonsKeepFixedHeight: functionButtons.every((button) => button.getBoundingClientRect().height <= 50),
      functionLabelFontSmall: !functionLabels.length || Boolean(firstFunctionLabelStyle && parseFloat(firstFunctionLabelStyle.fontSize) <= 13.5),
      stopSingleLine: Boolean(stopRect && stopStyle && stopStyle.whiteSpace === 'nowrap' && stopRect.height <= 96),
      stopHeight: stopRect?.height || 0,
      stopWhiteSpace: stopStyle?.whiteSpace || '',
      speedThrottleVertical: Boolean(speedThrottleRect && speedThrottleRect.height >= speedThrottleRect.width * 1.45),
      speedThrottleTouchReady: speedThrottleStyle?.touchAction === 'none' && speedThrottleStyle?.cursor === 'ns-resize',
      speedControlAboveDirection: Boolean(speedRect && directionRect && speedRect.bottom <= directionRect.top + 4),
      imageLeftOfSpeed: Boolean(imageRect && speedRect && imageRect.right <= speedRect.left + 2),
      imageElementCenteredInRegion: Boolean(mediaRect && imageElementRect
        && Math.abs(((imageElementRect.left + imageElementRect.right) / 2) - ((mediaRect.left + mediaRect.right) / 2)) <= 3
        && Math.abs(((imageElementRect.top + imageElementRect.bottom) / 2) - ((mediaRect.top + mediaRect.bottom) / 2)) <= 3),
      imageElementInsideRegion: Boolean(mediaRect && imageElementRect
        && imageElementRect.left >= mediaRect.left - 1
        && imageElementRect.right <= mediaRect.right + 1
        && imageElementRect.top >= mediaRect.top - 1
        && imageElementRect.bottom <= mediaRect.bottom + 1),
      imageObjectFitContain: imageElementStyle?.objectFit === 'contain',
      imageContentCenteredInRegion: Boolean(mediaRect && imageContentRect
        && Math.abs(((imageContentRect.left + imageContentRect.right) / 2) - ((mediaRect.left + mediaRect.right) / 2)) <= 8
        && Math.abs(((imageContentRect.top + imageContentRect.bottom) / 2) - ((mediaRect.top + mediaRect.bottom) / 2)) <= 8),
      imageContentFullyVisibleInRegion: Boolean(mediaRect && imageContentRect
        && imageContentRect.left >= mediaRect.left - 1
        && imageContentRect.right <= mediaRect.right + 1
        && imageContentRect.top >= mediaRect.top - 1
        && imageContentRect.bottom <= mediaRect.bottom + 1),
      functionGridBelowInfoAndImage: Boolean(infoRect && mediaRect && functionGridRect
        && functionGridRect.top >= Math.max(infoRect.bottom, mediaRect.bottom) - 2
        && functionGridRect.left <= infoRect.left + 2
        && functionGridRect.right >= mediaRect.right - 2),
      actionsSpanRows: Boolean(mediaRect && functionGridRect && actionsRect
        && actionsRect.top <= mediaRect.top + 2
        && actionsRect.bottom >= functionGridRect.bottom - 2),
      imageDoesNotOverlapSpeed: Boolean(imageRect && speedRect
        && (
          imageRect.right <= speedRect.left
          || speedRect.right <= imageRect.left
          || imageRect.bottom <= speedRect.top
          || speedRect.bottom <= imageRect.top
        ))
    };
  })()`);

  const mobileAssertions = [
    ["mobileHeaderRow", mobileData.headerRow === true],
    ["mobileHeaderControlsInline", mobileData.headerControlsInline === true],
    ["mobileFilterSingleLine", mobileData.filterSingleLine === true],
    ["mobileFilterUsesCompactColumns", mobileData.filterUsesCompactColumns === true],
    ["mobileFunctionLabelsFitButtons", mobileData.functionLabelsFitButtons === true],
    ["mobileFunctionButtonsKeepFixedHeight", mobileData.functionButtonsKeepFixedHeight === true],
    ["mobileFunctionLabelFontSmall", mobileData.functionLabelFontSmall === true],
    ["mobileStopSingleLine", mobileData.stopSingleLine === true],
    ["mobileSpeedThrottleVertical", mobileData.speedThrottleVertical === true],
    ["mobileSpeedThrottleTouchReady", mobileData.speedThrottleTouchReady === true],
    ["mobileSpeedControlAboveDirection", mobileData.speedControlAboveDirection === true],
    ["mobileImageLeftOfSpeed", mobileData.imageLeftOfSpeed === true],
    ["mobileImageElementCenteredInRegion", mobileData.imageElementCenteredInRegion === true],
    ["mobileImageElementInsideRegion", mobileData.imageElementInsideRegion === true],
    ["mobileImageObjectFitContain", mobileData.imageObjectFitContain === true],
    ["mobileImageContentCenteredInRegion", mobileData.imageContentCenteredInRegion === true],
    ["mobileImageContentFullyVisibleInRegion", mobileData.imageContentFullyVisibleInRegion === true],
    ["mobileFunctionGridBelowInfoAndImage", mobileData.functionGridBelowInfoAndImage === true],
    ["mobileActionsSpanRows", mobileData.actionsSpanRows === true],
    ["mobileImageDoesNotOverlapSpeed", mobileData.imageDoesNotOverlapSpeed === true],
  ];

  assertNamedChecks("vehicle cab mobile smoke", mobileAssertions, mobileData);

  if (editTarget?.id) {
    await evaluate(`document.querySelector('.cab-column[data-cab-id="left"] .cab-vehicle-row[data-vehicle-id="${editTarget.id}"] .cab-vehicle-edit')?.click()`);
    await waitForExpression("document.querySelector('#vehicleEditView:not([hidden]) .vehicle-editor-layout')");
    const mobileEditorData = await evaluate(`(() => {
      const leftColumn = document.querySelector('.vehicle-editor-left-column');
      const functionColumn = document.querySelector('.vehicle-editor-function-column');
      const mobileLeftRect = leftColumn?.getBoundingClientRect();
      const mobileFunctionRect = functionColumn?.getBoundingClientRect();
      return {
        mobileEditorOneColumn: Boolean(mobileLeftRect && mobileFunctionRect)
          && mobileFunctionRect.top >= mobileLeftRect.bottom - 2
      };
    })()`);
    assertNamedChecks("vehicle editor mobile layout smoke", [
      ["mobileEditorOneColumn", mobileEditorData.mobileEditorOneColumn === true]
    ], mobileEditorData);
  }

  console.log("vehicle cab smoke: OK");
}

function cleanup() {
  if (socket) {
    socket.close();
  }
  if (chrome) {
    chrome.kill("SIGTERM");
  }
  try {
    rmSync(userDataDir, {recursive: true, force: true});
  } catch (_error) {
    // Chrome may still be releasing profile files; leave the temp folder behind rather than hiding test failures.
  }
}

run().then(() => {
  cleanup();
}).catch((error) => {
  cleanup();
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
