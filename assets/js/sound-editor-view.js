import {
  addSoundConnector,
  addSoundNode,
  applySlotLibraryEntry,
  canPasteSoundSelection,
  clearSoundSlot,
  copySoundSelection,
  defaultSlotLibraryCategories,
  deleteSoundSelection,
  deleteUnusedSoundFiles,
  ensureDefaultSoundEditorSelection,
  closeSoundFileEditor,
  deleteUnusedSoundFile,
  filterSoundLibrary,
  filterSlotLibrary,
  formatBitCount,
  formatMegabitCount,
  markSoundEditorChanged,
  openSoundFileEditor,
  panSoundCanvas,
  pasteSoundSelection,
  projectSoundFiles,
  replaceSoundFile,
  resetSoundCanvasViewport,
  saveActiveSlotToLibrary,
  saveSoundFileToLibrary,
  selectSoundForSlot,
  selectSoundItemsInRect,
  setCanvasSelectionMode,
  setSoundPanelWidth,
  setNodeSoundFile,
  setSoundCanvasZoom,
  soundPreviewUrl,
  soundUsageForProject,
  soundCapacityUsageForState,
  soundCanvasBoundsForSlot,
  moveSoundNode,
  resizeSoundNode,
  setSoundSelection,
  sortSoundFiles,
  toggleSoundFileSort,
  updateSoundConnectorEndpoint,
  updateSoundConnectorField,
  updateSoundNodeField,
  updateSelectedSlotField
} from "./sound-editor-controller.js";

let activeSoundPreview = null;
let activeSoundPreviewFileId = 0;

export function renderSoundEditor(root, state, handlers = {}) {
  if (!root) {
    return;
  }
  ensureDefaultSoundEditorSelection(state);
  root.style.setProperty("--sound-slot-panel-width", `${Number(state.slotListWidthPx || 240)}px`);
  root.style.setProperty("--sound-property-panel-width", `${Number(state.propertyPanelWidthPx || 300)}px`);
  renderChipProfiles(root, state);
  renderProjectSummary(root, state);
  renderSlots(root, state, handlers);
  renderCanvas(root, state, handlers);
  renderProperties(root, state, handlers);
  renderSoundFileInventory(root, state, handlers);
  renderLibrary(root, state, handlers);
  renderSoundFileEditorDialog(root, state, handlers);
  renderWarnings(root, state);
}

function renderChipProfiles(root, state) {
  const chipSelect = root.querySelector("#soundChipSelect");
  if (!chipSelect) {
    return;
  }
  chipSelect.innerHTML = (state.chipProfiles || []).map((profile) => {
    return `<option value="${esc(profile.chip_id)}"${profile.chip_id === state.chipId ? " selected" : ""}>${esc(profile.label)}</option>`;
  }).join("");
}

function renderProjectSummary(root, state) {
  const summary = root.querySelector("#soundProjectSummary");
  const packageName = root.querySelector("#soundPackageName");
  if (packageName && packageName.value !== state.packageName) {
    packageName.value = state.packageName || "";
    packageName.oninput = () => {
      const nextPackageName = packageName.value || "新音效工程";
      if (state.packageName !== nextPackageName) {
        state.packageName = nextPackageName;
        markSoundEditorChanged(state);
      }
    };
  }
  if (!summary) {
    return;
  }
  const counts = state.projectSummary?.counts || {};
  const capacity = soundCapacityUsageForState(state);
  const capacitySummary = capacity.known
    ? [
      `<span>音效空间 已用 ${formatMegabitCount(capacity.usedBits)} / 总计 ${formatMegabitCount(capacity.totalBits)}</span>`,
      `<span>剩余 ${formatMegabitCount(capacity.remainingBits)}</span>`
    ]
    : [`<span>音效空间未确认，已用 ${formatMegabitCount(capacity.usedBits)}</span>`];
  summary.innerHTML = state.projectSummary ? [
    `<span>模块 ${esc(state.projectSummary.base_info?.decoder_module || "--")}</span>`,
    `<span>${counts.slots || 0} 个 Slot</span>`,
    `<span>${counts.nodes || 0} 个节点</span>`,
    `<span>${counts.connectors || 0} 条连接</span>`,
    `<span>${counts.sound_files || 0} 个音频</span>`,
    ...capacitySummary
  ].join("") : "<span>未导入音效工程，可直接从音效库创建新工程</span>";
}

function renderSlots(root, state, handlers) {
  const list = root.querySelector("#soundSlotList");
  if (!list) {
    return;
  }
  const slots = state.projectViewModel.slots.length
    ? state.projectViewModel.slots
    : fallbackSlots(state.selectedSlots);
  list.innerHTML = slots.map((slot) => {
    const selected = Number(slot.slot_id) === Number(state.activeSlotId);
    const functionNumber = slotFunctionNumberForRow(state, slot);
    return `<div class="sound-slot-row${selected ? " active" : ""}" data-slot-row="${slot.slot_id}">
      <button type="button" class="sound-slot-select" data-slot-id="${slot.slot_id}" aria-pressed="${selected ? "true" : "false"}">
        <span class="sound-slot-number">${slot.slot_id}</span>
        <span class="sound-slot-name">${esc(slot.slot_name || `Slot ${slot.slot_id}`)}</span>
      </button>
      <label class="sound-slot-function-field" title="留空表示未映射；0 表示 F0，1-68 对应 DCC 功能键 F1-F68">
        <span>F</span>
        <input class="sound-slot-function-input" type="number" min="0" max="68" placeholder="-" value="${functionNumber ?? ""}" data-slot-function-input="${slot.slot_id}" aria-label="Slot ${slot.slot_id} 映射功能键">
      </label>
    </div>`;
  }).join("");
  const slotAside = root.querySelector(".sound-slot-list");
  if (slotAside && !slotAside.querySelector("[data-sound-panel-resizer='slots']")) {
    slotAside.insertAdjacentHTML("beforeend", `<div class="sound-panel-resizer sound-panel-resizer-slots" data-sound-panel-resizer="slots" title="拖动调整 Slot 列表宽度"></div>`);
  }
  list.querySelectorAll("[data-slot-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeSlotId = Number(button.dataset.slotId || 0);
      state.selectedNodeKey = "";
      state.selectedConnectorId = 0;
      handlers.renderAll?.();
    });
  });
  list.querySelectorAll("[data-slot-function-input]").forEach((input) => {
    input.addEventListener("change", () => {
      const slotId = Number(input.dataset.slotFunctionInput || 0);
      state.activeSlotId = slotId;
      updateSelectedSlotField(state, slotId, "functionNumber", input.value);
      handlers.renderAll?.();
    });
  });
  wirePanelResizers(root, state, handlers);
}

function renderCanvas(root, state, handlers) {
  const canvas = root.querySelector("#soundNodeCanvas");
  if (!canvas) {
    return;
  }
  const slotId = Number(state.activeSlotId || 0);
  const nodes = state.projectViewModel.nodesBySlot.get(slotId) || fallbackNodesForSlot(slotId);
  const connectors = state.projectViewModel.connectorsBySlot.get(slotId) || fallbackConnectorsForSlot(slotId);
  const bounds = soundCanvasBoundsForSlot(state, slotId);
  const width = bounds.width;
  const height = bounds.height;
  const viewport = state.canvasViewport || {zoom: 1, offsetX: 0, offsetY: 0};
  const zoom = Number(viewport.zoom || 1);
  const scaledWidth = Math.ceil(width * zoom);
  const scaledHeight = Math.ceil(height * zoom);
  const connectorMarkup = connectors.map((connector) => connectorSvg(connector, nodes, state)).join("");
  const nodeMarkup = nodes.map((node) => nodeSvg(node, state)).join("");
  const selectionModePressed = state.canvasSelectionMode ? "true" : "false";
  const contextMenu = state.canvasContextMenu?.open ? `<div class="sound-canvas-menu" style="left:${Number(state.canvasContextMenu.x || 0)}px;top:${Number(state.canvasContextMenu.y || 0)}px" role="menu">
    <button type="button" data-sound-canvas-command="copy" role="menuitem">复制</button>
    <button type="button" data-sound-canvas-command="paste" role="menuitem"${canPasteSoundSelection(state) ? "" : " disabled"}>粘贴</button>
    <button type="button" data-sound-canvas-command="delete" class="danger" role="menuitem">删除</button>
  </div>` : "";
  canvas.innerHTML = `<div class="sound-canvas-toolbar" aria-label="节点图缩放">
    <button id="soundCanvasZoomOut" type="button" title="缩小">-</button>
    <span>${Math.round(zoom * 100)}%</span>
    <button id="soundCanvasZoomIn" type="button" title="放大">+</button>
    <button id="soundCanvasZoomReset" type="button">100%</button>
    <button id="soundCanvasSelectModeButton" type="button" aria-pressed="${selectionModePressed}" title="启用后用鼠标拖框选择节点和连接">框选</button>
    <button id="soundAddNodeButton" type="button">添加节点</button>
    <button id="soundAddConnectorButton" type="button">添加连接</button>
  </div>
  <div class="sound-node-canvas-scroll" tabindex="0" aria-label="可拖拽和滚动的节点图">
    <div class="sound-node-canvas-content" style="width:${scaledWidth}px;height:${scaledHeight}px">
      <svg width="${scaledWidth}" height="${scaledHeight}" viewBox="0 0 ${width} ${height}" role="img" aria-label="音效节点图">
        <defs>
          <marker id="soundArrow" markerWidth="10" markerHeight="8" refX="8" refY="4" orient="auto">
            <path d="M0,0 L10,4 L0,8 Z" fill="#176b87"></path>
          </marker>
        </defs>
        <g class="sound-grid">${gridLines(width, height)}</g>
        <g>${connectorMarkup}</g>
        <g>${nodeMarkup}</g>
      </svg>
      <div class="sound-selection-rect" hidden></div>
    </div>
  </div>
  ${contextMenu}`;
  wireCanvasViewport(canvas, state, handlers);
  canvas.querySelector("#soundCanvasSelectModeButton")?.addEventListener("click", () => {
    setCanvasSelectionMode(state, !state.canvasSelectionMode);
    handlers.renderAll?.();
  });
  canvas.querySelectorAll("[data-sound-canvas-command]").forEach((button) => {
    button.addEventListener("click", () => {
      const command = button.dataset.soundCanvasCommand || "";
      if (command === "copy") {
        const count = copySoundSelection(state);
        handlers.setStatus?.(count ? `已复制 ${count} 个对象` : "没有可复制的节点或连接");
      } else if (command === "paste") {
        const result = pasteSoundSelection(state, slotId || 1, {x: 40, y: 40});
        handlers.setStatus?.(`已粘贴 ${result.nodes} 个节点、${result.connectors} 条连接`);
      } else if (command === "delete") {
        const result = deleteSoundSelection(state);
        handlers.setStatus?.(`已删除 ${result.nodes} 个节点、${result.connectors} 条连接`);
      }
      state.canvasContextMenu = {open: false, x: 0, y: 0};
      handlers.renderAll?.();
    });
  });
  canvas.querySelector("#soundAddNodeButton")?.addEventListener("click", () => {
    addSoundNode(state, slotId || 1);
    handlers.setStatus?.("已添加节点");
    handlers.renderAll?.();
  });
  canvas.querySelector("#soundAddConnectorButton")?.addEventListener("click", () => {
    const connector = addSoundConnector(state, slotId || 1, state.selectedNodeKey, "");
    handlers.setStatus?.(connector ? "已添加连接" : "当前 Slot 至少需要两个节点才能添加连接");
    handlers.renderAll?.();
  });
  wireNodeDragging(canvas, state, handlers, zoom);
  wireNodeResizeDragging(canvas, state, handlers, zoom);
  wireConnectorEndpointDragging(canvas, state, handlers);
  canvas.querySelectorAll("[data-node-key]").forEach((element) => {
    element.addEventListener("click", () => {
      state.selectedNodeKey = element.dataset.nodeKey || "";
      state.selectedConnectorId = 0;
      setSoundSelection(state, [state.selectedNodeKey], []);
      handlers.renderAll?.();
    });
  });
  canvas.querySelectorAll("[data-connector-id]").forEach((element) => {
    element.addEventListener("click", () => {
      state.selectedConnectorId = Number(element.dataset.connectorId || 0);
      state.selectedNodeKey = "";
      setSoundSelection(state, [], [state.selectedConnectorId]);
      handlers.renderAll?.();
    });
  });
}

function wireCanvasViewport(canvas, state, handlers) {
  const scroll = canvas.querySelector(".sound-node-canvas-scroll");
  if (!scroll) {
    return;
  }
  scroll.scrollLeft = Math.max(0, Number(state.canvasViewport?.offsetX || 0));
  scroll.scrollTop = Math.max(0, Number(state.canvasViewport?.offsetY || 0));
  canvas.querySelector("#soundCanvasZoomOut")?.addEventListener("click", () => {
    setSoundCanvasZoom(state, Number(state.canvasViewport?.zoom || 1) - 0.1);
    handlers.renderAll?.();
  });
  canvas.querySelector("#soundCanvasZoomIn")?.addEventListener("click", () => {
    setSoundCanvasZoom(state, Number(state.canvasViewport?.zoom || 1) + 0.1);
    handlers.renderAll?.();
  });
  canvas.querySelector("#soundCanvasZoomReset")?.addEventListener("click", () => {
    resetSoundCanvasViewport(state);
    handlers.renderAll?.();
  });
  scroll.addEventListener("wheel", (event) => {
    event.preventDefault();
    const step = event.deltaY < 0 ? 0.1 : -0.1;
    setSoundCanvasZoom(state, Number(state.canvasViewport?.zoom || 1) + step);
    state.canvasViewport.offsetX = scroll.scrollLeft;
    state.canvasViewport.offsetY = scroll.scrollTop;
    handlers.renderAll?.();
  }, {passive: false});
  let dragState = null;
  scroll.addEventListener("pointerdown", (event) => {
    if (event.target.closest?.("[data-node-key], [data-connector-id]")) {
      return;
    }
    state.canvasContextMenu = {open: false, x: 0, y: 0};
    if (state.canvasSelectionMode) {
      const start = canvasPointFromEvent(scroll, event, state.canvasViewport?.zoom || 1);
      const selectionRect = scroll.querySelector(".sound-selection-rect");
      dragState = {
        pointerId: event.pointerId,
        mode: "select",
        startX: start.x,
        startY: start.y,
        selectionRect
      };
      updateSelectionRect(selectionRect, start.x, start.y, start.x, start.y, state.canvasViewport?.zoom || 1);
      scroll.setPointerCapture?.(event.pointerId);
      event.preventDefault();
      return;
    }
    dragState = {
      pointerId: event.pointerId,
      mode: "pan",
      startX: event.clientX,
      startY: event.clientY,
      startLeft: scroll.scrollLeft,
      startTop: scroll.scrollTop
    };
    scroll.classList.add("dragging");
    scroll.setPointerCapture?.(event.pointerId);
  });
  scroll.addEventListener("pointermove", (event) => {
    if (!dragState || dragState.pointerId !== event.pointerId) {
      return;
    }
    if (dragState.mode === "select") {
      const current = canvasPointFromEvent(scroll, event, state.canvasViewport?.zoom || 1);
      updateSelectionRect(dragState.selectionRect, dragState.startX, dragState.startY, current.x, current.y, state.canvasViewport?.zoom || 1);
      event.preventDefault();
      return;
    }
    scroll.scrollLeft = dragState.startLeft - (event.clientX - dragState.startX);
    scroll.scrollTop = dragState.startTop - (event.clientY - dragState.startY);
    state.canvasViewport.offsetX = scroll.scrollLeft;
    state.canvasViewport.offsetY = scroll.scrollTop;
  });
  const stopDragging = (event) => {
    if (!dragState || dragState.pointerId !== event.pointerId) {
      return;
    }
    if (dragState.mode === "select") {
      const current = canvasPointFromEvent(scroll, event, state.canvasViewport?.zoom || 1);
      selectSoundItemsInRect(state, state.activeSlotId, {
        x1: dragState.startX,
        y1: dragState.startY,
        x2: current.x,
        y2: current.y
      });
      dragState.selectionRect.hidden = true;
      scroll.releasePointerCapture?.(event.pointerId);
      dragState = null;
      handlers.renderAll?.();
      event.preventDefault();
      return;
    }
    scroll.classList.remove("dragging");
    scroll.releasePointerCapture?.(event.pointerId);
    dragState = null;
  };
  scroll.addEventListener("pointerup", stopDragging);
  scroll.addEventListener("pointercancel", stopDragging);
  scroll.addEventListener("scroll", () => {
    state.canvasViewport.offsetX = scroll.scrollLeft;
    state.canvasViewport.offsetY = scroll.scrollTop;
  });
  scroll.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    const rect = canvas.getBoundingClientRect();
    state.canvasContextMenu = {
      open: true,
      x: Math.max(8, event.clientX - rect.left),
      y: Math.max(44, event.clientY - rect.top)
    };
    handlers.renderAll?.();
  });
}

function canvasPointFromEvent(scroll, event, zoom) {
  const rect = scroll.querySelector(".sound-node-canvas-content")?.getBoundingClientRect() || scroll.getBoundingClientRect();
  const scale = Number(zoom || 1);
  return {
    x: (event.clientX - rect.left) / scale,
    y: (event.clientY - rect.top) / scale
  };
}

function updateSelectionRect(element, x1, y1, x2, y2, zoom) {
  if (!element) {
    return;
  }
  const scale = Number(zoom || 1);
  const left = Math.min(x1, x2) * scale;
  const top = Math.min(y1, y2) * scale;
  const width = Math.abs(x2 - x1) * scale;
  const height = Math.abs(y2 - y1) * scale;
  element.hidden = false;
  element.style.left = `${left}px`;
  element.style.top = `${top}px`;
  element.style.width = `${width}px`;
  element.style.height = `${height}px`;
}

function wirePanelResizers(root, state, handlers) {
  root.querySelectorAll("[data-sound-panel-resizer]").forEach((resizer) => {
    resizer.onpointerdown = (event) => {
      const panel = resizer.dataset.soundPanelResizer || "";
      const startX = event.clientX;
      const initialWidth = panel === "slots" ? Number(state.slotListWidthPx || 240) : Number(state.propertyPanelWidthPx || 300);
      resizer.setPointerCapture?.(event.pointerId);
      resizer.classList.add("dragging");
      const move = (moveEvent) => {
        const delta = moveEvent.clientX - startX;
        setSoundPanelWidth(state, panel, panel === "slots" ? initialWidth + delta : initialWidth - delta);
        root.style.setProperty("--sound-slot-panel-width", `${Number(state.slotListWidthPx || 240)}px`);
        root.style.setProperty("--sound-property-panel-width", `${Number(state.propertyPanelWidthPx || 300)}px`);
      };
      const stop = (upEvent) => {
        resizer.classList.remove("dragging");
        resizer.releasePointerCapture?.(upEvent.pointerId);
        document.removeEventListener("pointermove", move);
        document.removeEventListener("pointerup", stop);
        handlers.renderAll?.();
      };
      document.addEventListener("pointermove", move);
      document.addEventListener("pointerup", stop);
      event.preventDefault();
    };
  });
}

function wireNodeDragging(canvas, state, handlers, zoom) {
  let dragState = null;
  canvas.querySelectorAll("[data-node-key]").forEach((element) => {
    element.addEventListener("pointerdown", (event) => {
      const nodeKey = element.dataset.nodeKey || "";
      const node = (state.projectSummary?.nodes || []).find((entry) => entry.node_key === nodeKey);
      if (!node) {
        return;
      }
      dragState = {
        pointerId: event.pointerId,
        nodeKey,
        startX: event.clientX,
        startY: event.clientY,
        originalX: Number(node.x ?? 0),
        originalY: Number(node.y ?? 0),
        moved: false,
        element
      };
      element.classList.add("dragging");
      element.setPointerCapture?.(event.pointerId);
      event.preventDefault();
      event.stopPropagation();
    });
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!dragState || dragState.pointerId !== event.pointerId) {
      return;
    }
    const deltaX = (event.clientX - dragState.startX) / Number(zoom || 1);
    const deltaY = (event.clientY - dragState.startY) / Number(zoom || 1);
    if (Math.abs(deltaX) > 2 || Math.abs(deltaY) > 2) {
      dragState.moved = true;
    }
    dragState.element.setAttribute("transform", `translate(${deltaX} ${deltaY})`);
    event.preventDefault();
  });
  const stopDragging = (event) => {
    if (!dragState || dragState.pointerId !== event.pointerId) {
      return;
    }
    dragState.element.classList.remove("dragging");
    dragState.element.releasePointerCapture?.(event.pointerId);
    if (dragState.moved) {
      const deltaX = (event.clientX - dragState.startX) / Number(zoom || 1);
      const deltaY = (event.clientY - dragState.startY) / Number(zoom || 1);
      moveSoundNode(state, dragState.nodeKey, dragState.originalX + deltaX, dragState.originalY + deltaY);
      handlers.renderAll?.();
    }
    dragState = null;
    event.preventDefault();
  };
  canvas.addEventListener("pointerup", stopDragging);
  canvas.addEventListener("pointercancel", stopDragging);
}

function wireNodeResizeDragging(canvas, state, handlers, zoom) {
  let dragState = null;
  canvas.querySelectorAll("[data-node-resize-key]").forEach((element) => {
    element.addEventListener("pointerdown", (event) => {
      const nodeKey = element.dataset.nodeResizeKey || "";
      const node = (state.projectSummary?.nodes || []).find((entry) => entry.node_key === nodeKey);
      if (!node) {
        return;
      }
      dragState = {
        pointerId: event.pointerId,
        nodeKey,
        startX: event.clientX,
        startY: event.clientY,
        originalWidth: Number(node.width ?? 96),
        originalHeight: Number(node.height ?? 64),
        moved: false,
        element
      };
      element.classList.add("dragging");
      element.setPointerCapture?.(event.pointerId);
      event.preventDefault();
      event.stopPropagation();
    });
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!dragState || dragState.pointerId !== event.pointerId) {
      return;
    }
    const deltaX = (event.clientX - dragState.startX) / Number(zoom || 1);
    const deltaY = (event.clientY - dragState.startY) / Number(zoom || 1);
    if (Math.abs(deltaX) > 2 || Math.abs(deltaY) > 2) {
      dragState.moved = true;
    }
    event.preventDefault();
  });
  const stopDragging = (event) => {
    if (!dragState || dragState.pointerId !== event.pointerId) {
      return;
    }
    dragState.element.classList.remove("dragging");
    dragState.element.releasePointerCapture?.(event.pointerId);
    if (dragState.moved) {
      const deltaX = (event.clientX - dragState.startX) / Number(zoom || 1);
      const deltaY = (event.clientY - dragState.startY) / Number(zoom || 1);
      resizeSoundNode(state, dragState.nodeKey, dragState.originalWidth + deltaX, dragState.originalHeight + deltaY);
      handlers.renderAll?.();
    }
    dragState = null;
    event.preventDefault();
  };
  canvas.addEventListener("pointerup", stopDragging);
  canvas.addEventListener("pointercancel", stopDragging);
}

function wireConnectorEndpointDragging(canvas, state, handlers) {
  let dragState = null;
  canvas.querySelectorAll("[data-connector-end]").forEach((element) => {
    element.addEventListener("pointerdown", (event) => {
      dragState = {
        pointerId: event.pointerId,
        connectorId: Number(element.dataset.connectorId || 0),
        endpoint: element.dataset.connectorEnd || ""
      };
      element.setPointerCapture?.(event.pointerId);
      event.preventDefault();
      event.stopPropagation();
    });
  });
  const stopDragging = (event) => {
    if (!dragState || dragState.pointerId !== event.pointerId) {
      return;
    }
    const targetNode = nodeElementAtPoint(event.clientX, event.clientY);
    if (targetNode?.dataset?.nodeKey) {
      updateSoundConnectorEndpoint(state, dragState.connectorId, dragState.endpoint, targetNode.dataset.nodeKey);
      handlers.setStatus?.("已调整连接");
      handlers.renderAll?.();
    }
    dragState = null;
    event.preventDefault();
  };
  canvas.addEventListener("pointerup", stopDragging);
  canvas.addEventListener("pointercancel", () => {
    dragState = null;
  });
}

function nodeElementAtPoint(clientX, clientY) {
  const elements = typeof document.elementsFromPoint === "function"
    ? document.elementsFromPoint(clientX, clientY)
    : [document.elementFromPoint(clientX, clientY)].filter(Boolean);
  for (const element of elements) {
    const node = element.closest?.("[data-node-key]");
    if (node) {
      return node;
    }
  }
  return null;
}

function renderProperties(root, state, handlers) {
  const panel = root.querySelector("#soundPropertyPanel");
  if (!panel) {
    return;
  }
  const slot = state.selectedSlots.find((entry) => Number(entry.slotId) === Number(state.activeSlotId))
    || selectedSlotFromSummary(state);
  const node = selectedNode(state);
  const connector = selectedConnector(state);
  panel.innerHTML = [
    `<div class="sound-panel-resizer sound-panel-resizer-properties" data-sound-panel-resizer="properties" title="拖动调整属性栏宽度"></div>`,
    `<h2>属性</h2>`,
    slot ? slotEditor(slot, state) : `<p class="empty-state">选择 Slot 后编辑功能键和音效。</p>`,
    node ? nodeDetails(node, state) : "",
    connector ? connectorDetails(connector, state) : ""
  ].join("");
  bindSoundPreviewControls(panel, state, handlers);
  panel.querySelectorAll("[data-slot-field]").forEach((input) => {
    input.addEventListener("change", () => {
      updateSelectedSlotField(state, state.activeSlotId, input.dataset.slotField, input.value);
      handlers.renderAll?.();
    });
  });
  panel.querySelector("[data-clear-slot]")?.addEventListener("click", () => {
    if (typeof window.confirm === "function" && !window.confirm("清空当前 Slot 会删除其中所有节点、连接和功能键映射。确定继续？")) {
      return;
    }
    clearSoundSlot(state, state.activeSlotId);
    handlers.setStatus?.("已清空当前 Slot");
    handlers.renderAll?.();
  });
  panel.querySelector("[data-save-slot-library]")?.addEventListener("click", async () => {
    const category = panel.querySelector("[data-slot-library-category]")?.value || "power_unit";
    const entry = saveActiveSlotToLibrary(state, category);
    if (!entry) {
      handlers.setStatus?.("当前 Slot 无法保存");
      handlers.renderAll?.();
      return;
    }
    try {
      const saved = await handlers.saveSoundLibrarySlot?.(entry, category);
      if (saved) {
        replaceLibraryEntryByKey(state.slotLibrary?.slots || [], "slot_library_id", entry.slot_library_id, saved);
      }
      handlers.setStatus?.("已入库");
    } catch (error) {
      state.slotLibrary.slots = (state.slotLibrary?.slots || [])
        .filter((slot) => slot.slot_library_id !== entry.slot_library_id);
      handlers.setStatus?.(`保存 Slot 库失败：${error.message || error}`);
    }
    handlers.renderAll?.();
  });
  const fileSelect = panel.querySelector("#soundNodeFileSelect");
  fileSelect?.addEventListener("change", () => {
    setNodeSoundFile(state, state.selectedNodeKey, fileSelect.value);
    handlers.renderAll?.();
  });
  panel.querySelectorAll("[data-node-field]").forEach((input) => {
    input.addEventListener("change", () => {
      updateSoundNodeField(state, state.selectedNodeKey, input.dataset.nodeField, input.value);
      handlers.renderAll?.();
    });
  });
  panel.querySelectorAll("[data-connector-field]").forEach((input) => {
    input.addEventListener("change", () => {
      updateSoundConnectorField(state, state.selectedConnectorId, input.dataset.connectorField, input.value);
      handlers.renderAll?.();
    });
  });
  wirePanelResizers(root, state, handlers);
}

function renderSoundFileInventory(root, state, handlers) {
  const panel = root.querySelector("#soundFileInventoryPanel");
  if (!panel) {
    return;
  }
  const files = sortSoundFiles(soundUsageForProject(state), state.soundFileSort);
  const unusedCount = files.filter((file) => !file.used_by.length).length;
  const categoryOptions = soundLibraryCategoryOptions(state);
  const header = (field, label) => {
    const active = state.soundFileSort?.field === field;
    const suffix = active ? (state.soundFileSort.direction === "desc" ? " ↓" : " ↑") : "";
    return `<button type="button" class="sound-file-sort-button" data-sound-file-sort="${field}">${esc(label)}${suffix}</button>`;
  };
  panel.innerHTML = `<div class="sound-file-inventory-header">
    <h2>当前音效包文件</h2>
    <div class="sound-file-inventory-actions">
      <span>${files.length} 个文件</span>
      <button type="button" class="danger" data-delete-unused-sounds${unusedCount ? "" : " disabled"}>一键删除未使用音效</button>
    </div>
  </div>
  ${files.length ? `<div class="sound-file-table" role="table" aria-label="当前音效包音频文件">
    <div class="sound-file-row sound-file-row-head" role="row">
      <span role="columnheader">${header("file_id", "ID")}</span>
      <span role="columnheader">${header("file_name", "文件")}</span>
      <span role="columnheader">${header("duration_seconds", "时长")}</span>
      <span role="columnheader">${header("size_bits", "大小")}</span>
      <span role="columnheader">${header("source", "来源")}</span>
      <span role="columnheader">${header("used_by", "使用位置")}</span>
      <span role="columnheader">操作</span>
    </div>
    ${files.map((file) => {
      const used = file.used_by.length > 0;
      return `<div class="sound-file-row" role="row">
      <span role="cell">#${Number(file.file_id || 0)}</span>
      <span role="cell">${esc(file.file_name || "")}</span>
      <span role="cell">${formatDuration(file.duration_seconds)}</span>
      <span role="cell">${formatBitCount(Number(file.pcm_bytes || 0) * 8)}b</span>
      <span role="cell">${sourceLabel(file)}</span>
      <span role="cell">${file.used_by.length ? esc(file.used_by.join("，")) : "未使用"}</span>
      <span role="cell" class="sound-file-actions">
        ${soundPreviewButton(file)}
        <button type="button" data-sound-file-edit="${Number(file.file_id || 0)}">编辑</button>
        <select data-sound-file-save-category="${Number(file.file_id || 0)}" aria-label="保存音效分类">${categoryOptions}</select>
        <button type="button" data-sound-file-save="${Number(file.file_id || 0)}">入库</button>
        <button type="button" class="danger" data-sound-file-delete="${Number(file.file_id || 0)}"${used ? " disabled title=\"已被 Slot 或节点引用，不能删除\"" : ""}>删除</button>
      </span>
    </div>`;
    }).join("")}
  </div>` : `<p class="empty-state">导入音效工程或上传音频后显示文件用量。</p>`}`;
  bindSoundPreviewControls(panel, state, handlers);
  panel.querySelector("[data-delete-unused-sounds]")?.addEventListener("click", () => {
    const deletedCount = deleteUnusedSoundFiles(state);
    handlers.setStatus?.(deletedCount ? `已删除 ${deletedCount} 个未使用音效` : "没有未使用音效可删除");
    handlers.renderAll?.();
  });
  panel.querySelectorAll("[data-sound-file-sort]").forEach((button) => {
    button.addEventListener("click", () => {
      toggleSoundFileSort(state, button.dataset.soundFileSort || "file_id");
      handlers.renderAll?.();
    });
  });
  panel.querySelectorAll("[data-sound-file-edit]").forEach((button) => {
    button.addEventListener("click", () => {
      openSoundFileEditor(state, button.dataset.soundFileEdit);
      handlers.renderAll?.();
    });
  });
  panel.querySelectorAll("[data-sound-file-delete]").forEach((button) => {
    button.addEventListener("click", () => {
      if (deleteUnusedSoundFile(state, button.dataset.soundFileDelete)) {
        handlers.setStatus?.("已删除未引用音效文件");
      }
      handlers.renderAll?.();
    });
  });
  panel.querySelectorAll("[data-sound-file-save]").forEach((button) => {
    button.addEventListener("click", async () => {
      const fileId = Number(button.dataset.soundFileSave || 0);
      const category = panel.querySelector(`[data-sound-file-save-category="${fileId}"]`)?.value || "custom";
      const saved = saveSoundFileToLibrary(state, fileId, category);
      if (!saved) {
        handlers.setStatus?.("音效文件不存在，无法保存");
        handlers.renderAll?.();
        return;
      }
      try {
        const persisted = await handlers.saveSoundLibrarySound?.(saved, category);
        if (persisted) {
          replaceLibraryEntryByKey(state.savedSoundLibrary || [], "sound_id", saved.sound_id, persisted);
        }
        handlers.setStatus?.("已入库");
      } catch (error) {
        state.savedSoundLibrary = (state.savedSoundLibrary || [])
          .filter((sound) => sound.sound_id !== saved.sound_id);
        handlers.setStatus?.(`保存音效库失败：${error.message || error}`);
      }
      handlers.renderAll?.();
    });
  });
}

function replaceLibraryEntryByKey(entries, key, keyValue, replacement) {
  const index = entries.findIndex((entry) => entry?.[key] === keyValue);
  if (index >= 0) {
    entries[index] = replacement;
  }
}

function renderSoundFileEditorDialog(root, state, handlers) {
  const dialog = root.querySelector("#soundFileEditorDialog");
  const content = root.querySelector("#soundFileEditorDialogContent");
  if (!dialog || !content) {
    return;
  }
  const fileId = Number(state.editingSoundFileId || 0);
  const file = projectSoundFiles(state).find((entry) => Number(entry.file_id) === fileId);
  if (!fileId || !file) {
    if (dialog.open) {
      dialog.close();
    }
    content.replaceChildren();
    return;
  }
  const librarySounds = filterSoundLibrary({
    sounds: [...(state.libraryCatalog.sounds || []), ...(state.savedSoundLibrary || []), ...(state.customSounds || [])]
  }, state.soundFileEditorFilter || {});
  const editorCategories = `<option value="">全部分类</option>${soundLibraryCategoryOptions(state, state.soundFileEditorFilter?.category || "")}`;
  content.innerHTML = `<div class="sound-file-editor-header">
    <div>
      <h2>编辑音效文件 #${fileId}</h2>
      <p>${esc(file.file_name || "")}</p>
    </div>
    <button id="soundFileEditorClose" type="button" aria-label="关闭">×</button>
  </div>
  <div class="sound-file-editor-actions">
    <button id="soundFileReplaceUploadButton" type="button">上传 WAV 替换</button>
  </div>
  <div class="sound-file-editor-filters">
    <select id="soundFileEditorCategory" aria-label="音效文件编辑分类">${editorCategories}</select>
    <input id="soundFileEditorSearch" value="${esc(state.soundFileEditorFilter?.query || "")}" placeholder="过滤音效">
  </div>
  <div class="sound-file-editor-library" aria-label="选择系统音效">
    ${librarySounds.map((sound) => `<button type="button" class="sound-library-item compact" data-replacement-sound-id="${esc(sound.sound_id)}">
      <strong>${esc(sound.label)}</strong>
      <span>${esc(sound.description || "")}</span>
      <small>${sound.audio_available ? "含音频" : "仅元数据"}</small>
    </button>`).join("") || `<p class="empty-state">系统音效库为空。</p>`}
  </div>`;
  if (!dialog.open) {
    dialog.showModal();
  }
  content.querySelector("#soundFileEditorClose")?.addEventListener("click", () => {
    closeSoundFileEditor(state);
    handlers.renderAll?.();
  });
  content.querySelector("#soundFileReplaceUploadButton")?.addEventListener("click", () => {
    handlers.triggerReplacementUpload?.();
  });
  content.querySelector("#soundFileEditorCategory")?.addEventListener("change", (event) => {
    state.soundFileEditorFilter.category = event.target.value || "";
    handlers.renderAll?.();
  });
  content.querySelector("#soundFileEditorSearch")?.addEventListener("input", (event) => {
    state.soundFileEditorFilter.query = event.target.value || "";
    handlers.renderAll?.();
  });
  content.querySelectorAll("[data-replacement-sound-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const sound = librarySounds.find((entry) => entry.sound_id === button.dataset.replacementSoundId);
      if (!sound) {
        return;
      }
      replaceSoundFile(state, fileId, sound);
      handlers.setStatus?.("已替换音效文件");
      closeSoundFileEditor(state);
      handlers.renderAll?.();
    });
  });
}

function renderLibrary(root, state, handlers) {
  const panel = root.querySelector("#soundLibraryPanel");
  const soundItems = root.querySelector("#soundLibraryItems");
  const slotHeader = root.querySelector("#soundSlotLibraryHeader");
  const slotItems = root.querySelector("#soundSlotLibraryItems");
  const categorySelect = root.querySelector("#soundLibraryCategory");
  const searchInput = root.querySelector("#soundLibrarySearch");
  if (!panel || !soundItems || !slotHeader || !slotItems) {
    return;
  }
  if (categorySelect) {
    categorySelect.innerHTML = `<option value="">全部分类</option>${(state.libraryCatalog.categories || []).map((category) => {
      return `<option value="${esc(category.category)}"${state.libraryFilter.category === category.category ? " selected" : ""}>${esc(category.label)}</option>`;
    }).join("")}<option value="custom"${state.libraryFilter.category === "custom" ? " selected" : ""}>自定义上传</option>`;
    categorySelect.onchange = () => {
      state.libraryFilter.category = categorySelect.value;
      handlers.renderAll?.();
    };
  }
  if (searchInput) {
    searchInput.value = state.libraryFilter.query || "";
    searchInput.oninput = () => {
      state.libraryFilter.query = searchInput.value;
      handlers.renderAll?.();
    };
  }
  const sounds = filterSoundLibrary({
    sounds: [...(state.libraryCatalog.sounds || []), ...(state.savedSoundLibrary || []), ...state.customSounds]
  }, state.libraryFilter);
  const slotCategories = state.slotLibrary?.categories || defaultSlotLibraryCategories();
  const slotTemplates = filterSlotLibrary(state);
  soundItems.innerHTML = sounds.map((sound) => {
    return `<button type="button" class="sound-library-item" data-sound-id="${esc(sound.sound_id)}">
      <strong>${esc(sound.label)}</strong>
      <span>${esc(sound.description || "")}</span>
      <small>${sound.audio_available ? "含音频" : "仅元数据"}</small>
    </button>`;
  }).join("") || `<p class="empty-state">没有匹配的音效。</p>`;
  slotHeader.innerHTML = `<h2>Slot 库</h2>
    <select data-slot-library-filter-category aria-label="Slot 库分类">
      <option value="">全部类型</option>
      ${slotCategories.map((category) => `<option value="${esc(category.category)}"${state.slotLibraryFilter.category === category.category ? " selected" : ""}>${esc(category.label)}</option>`).join("")}
    </select>
    <input data-slot-library-filter-query value="${esc(state.slotLibraryFilter.query || "")}" placeholder="搜索 Slot">`;
  slotItems.innerHTML = slotTemplates.map((slot) => `<button type="button" class="sound-library-item" data-slot-library-id="${esc(slot.slot_library_id)}">
        <strong>${esc(slot.label)}</strong>
        <span>${esc(slotCategoryLabel(slotCategories, slot.category))}</span>
        <small>${Number(slot.nodes?.length || 0)} 个节点，${Number(slot.connectors?.length || 0)} 条连接</small>
      </button>`).join("") || `<p class="empty-state">Slot 库为空，可在右侧属性栏保存当前 Slot。</p>`;
  soundItems.querySelectorAll("[data-sound-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const sound = sounds.find((entry) => entry.sound_id === button.dataset.soundId);
      if (!sound) {
        return;
      }
      selectSoundForSlot(state, state.activeSlotId || 1, sound);
      handlers.renderAll?.();
    });
  });
  slotHeader.querySelector("[data-slot-library-filter-category]")?.addEventListener("change", (event) => {
    state.slotLibraryFilter.category = event.target.value || "";
    handlers.renderAll?.();
  });
  slotHeader.querySelector("[data-slot-library-filter-query]")?.addEventListener("input", (event) => {
    state.slotLibraryFilter.query = event.target.value || "";
    handlers.renderAll?.();
  });
  slotItems.querySelectorAll("[data-slot-library-id]").forEach((button) => {
    button.addEventListener("click", () => {
      if (applySlotLibraryEntry(state, button.dataset.slotLibraryId, state.activeSlotId || 1)) {
        handlers.setStatus?.("已应用 Slot 库模板");
      }
      handlers.renderAll?.();
    });
  });
}

function renderWarnings(root, state) {
  const warningPanel = root.querySelector("#soundPackageWarnings");
  if (!warningPanel) {
    return;
  }
  warningPanel.innerHTML = (state.packageWarnings || []).map((warning) => {
    return `<li>${esc(warning.message || warning.type || String(warning))}</li>`;
  }).join("");
}

function connectorSvg(connector, nodes, state) {
  const source = nodes.find((node) => node.node_key === connector.source_node_key);
  const target = nodes.find((node) => node.node_key === connector.target_node_key);
  if (!source || !target) {
    return "";
  }
  const x1 = nodeX(source) + nodeWidth(source);
  const y1 = nodeY(source) + nodeHeight(source) / 2;
  const x2 = nodeX(target);
  const y2 = nodeY(target) + nodeHeight(target) / 2;
  const selected = Number(connector.connector_id) === Number(state.selectedConnectorId)
    || (state.selectedConnectorIds || []).map(Number).includes(Number(connector.connector_id));
  return `<g class="sound-connector-group${selected ? " selected" : ""}">
    <path class="sound-connector${selected ? " selected" : ""}" data-connector-id="${connector.connector_id}" d="M${x1} ${y1} C${x1 + 60} ${y1}, ${x2 - 60} ${y2}, ${x2} ${y2}" marker-end="url(#soundArrow)"></path>
    <circle class="sound-connector-handle source" data-connector-id="${connector.connector_id}" data-connector-end="source" cx="${x1}" cy="${y1}" r="6"></circle>
    <circle class="sound-connector-handle target" data-connector-id="${connector.connector_id}" data-connector-end="target" cx="${x2}" cy="${y2}" r="6"></circle>
  </g>`;
}

function nodeSvg(node, state) {
  const selected = node.node_key === state.selectedNodeKey || (state.selectedNodeKeys || []).includes(node.node_key);
  const x = nodeX(node);
  const y = nodeY(node);
  const w = nodeWidth(node);
  const h = nodeHeight(node);
  return `<g class="sound-node${selected ? " selected" : ""}" data-node-key="${esc(node.node_key)}">
    <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="6"></rect>
    <text x="${x + w / 2}" y="${y + 25}" text-anchor="middle">${esc(node.node_name || `节点 ${node.node_id}`)}</text>
    <text x="${x + w / 2}" y="${y + 47}" text-anchor="middle">文件 ${Number(node.file_id || 0)}</text>
    <rect class="sound-node-resize-handle" data-node-resize-key="${esc(node.node_key)}" x="${x + w - 13}" y="${y + h - 13}" width="11" height="11" rx="2"></rect>
  </g>`;
}

function gridLines(width, height) {
  const lines = [];
  for (let x = 0; x <= width; x += 40) {
    lines.push(`<line x1="${x}" y1="0" x2="${x}" y2="${height}"></line>`);
  }
  for (let y = 0; y <= height; y += 40) {
    lines.push(`<line x1="0" y1="${y}" x2="${width}" y2="${y}"></line>`);
  }
  return lines.join("");
}

function slotEditor(slot, state) {
  const functionNumber = slotFunctionNumberInputValue(slot.functionNumber ?? slot.function_number);
  const slotSoundFileId = Number(slot.sound?.fileId ?? slot.sound?.file_id ?? 0);
  const file = projectSoundFiles(state).find((entry) => Number(entry.file_id) === slotSoundFileId);
  const soundFileName = file?.file_name || slot.sound?.fileName || slot.sound?.file_name || "未选择";
  const slotCategories = (state.slotLibrary?.categories || defaultSlotLibraryCategories()).map((category) => {
    return `<option value="${esc(category.category)}">${esc(category.label)}</option>`;
  }).join("");
  return `<div class="sound-property-block">
    <label>Slot 名称<input data-slot-field="slotName" value="${esc(slot.slotName || slot.slot_name || "")}"></label>
    <label>功能键<input type="number" min="0" max="68" placeholder="-" data-slot-field="functionNumber" value="${functionNumber}"></label>
    <p class="sound-property-file-line"><span>音效文件：${esc(soundFileName)}</span>${file ? soundPreviewButton(file, "compact") : ""}</p>
    <div class="sound-property-actions">
      <button type="button" class="danger" data-clear-slot>清空 Slot</button>
    </div>
    <div class="sound-slot-library-save">
      <label>Slot 类型<select data-slot-library-category>${slotCategories}</select></label>
      <button type="button" data-save-slot-library>入库</button>
    </div>
  </div>`;
}

function nodeDetails(node, state) {
  const files = projectSoundFiles(state);
  const currentFileId = Number(node.file_id || 0);
  const file = files.find((entry) => Number(entry.file_id) === currentFileId);
  const options = [
    `<option value="0"${currentFileId ? "" : " selected"}>无音效文件</option>`,
    ...files.map((entry) => {
      const selected = Number(entry.file_id) === currentFileId ? " selected" : "";
      return `<option value="${Number(entry.file_id)}"${selected}>#${Number(entry.file_id)} ${esc(entry.file_name || "")}</option>`;
    })
  ].join("");
  return `<div class="sound-property-block">
    <h3>节点 ${Number(node.node_id)}</h3>
    <label>名称<input data-node-field="nodeName" value="${esc(node.node_name || "")}"></label>
    <div class="sound-property-grid sound-property-grid-three">
      <label>类型<input type="number" min="0" max="999" data-node-field="nodeType" value="${Number(node.node_type || 0)}"></label>
      <label>重复次数<input type="number" min="0" max="9999" data-node-field="repeatAmount" value="${Number(node.repeat_amount || 0)}"></label>
      <label>音量<input type="number" min="0" max="255" data-node-field="soundVolume" value="${Number(node.sound_volume || 0)}"></label>
    </div>
    <div class="sound-property-grid">
      <label>宽<input type="number" min="80" max="500" data-node-field="width" value="${Number(node.width ?? 96)}"></label>
      <label>高<input type="number" min="56" max="300" data-node-field="height" value="${Number(node.height ?? 64)}"></label>
    </div>
    <p class="sound-property-file-line"><span>音频：${esc(file?.file_name || "无")}</span>${file ? soundPreviewButton(file, "compact") : ""}</p>
    <label>音效文件<select id="soundNodeFileSelect">${options}</select></label>
  </div>`;
}

function connectorDetails(connector, state) {
  const nodes = (state.projectSummary?.nodes || []).filter((node) => Number(node.slot_id) === Number(connector.slot_id));
  const nodeOptions = (selectedKey) => nodes.map((node) => {
    const selected = node.node_key === selectedKey ? " selected" : "";
    return `<option value="${esc(node.node_key)}"${selected}>${Number(node.node_id)} ${esc(node.node_name || "")}</option>`;
  }).join("");
  return `<div class="sound-property-block">
    <h3>连接 ${Number(connector.connector_id)}</h3>
    <label>源节点<select id="soundConnectorSourceSelect" data-connector-field="sourceNodeKey">${nodeOptions(connector.source_node_key)}</select></label>
    <label>目标节点<select id="soundConnectorTargetSelect" data-connector-field="targetNodeKey">${nodeOptions(connector.target_node_key)}</select></label>
    <label>连接类型<input type="number" min="0" max="999" data-connector-field="connectorType" value="${Number(connector.connector_type || 0)}"></label>
    <label>源端口<input type="number" min="0" max="999" data-connector-field="sourcePortIndex" value="${Number(connector.source_port_index || 0)}"></label>
    <p>判断 ${Number(connector.judgment_count || 0)} / 动作 ${Number(connector.action_count || 0)}</p>
  </div>`;
}

function selectedSlotFromSummary(state) {
  const slot = state.projectViewModel.slots.find((entry) => Number(entry.slot_id) === Number(state.activeSlotId));
  if (!slot) {
    return null;
  }
  return {
    slotId: slot.slot_id,
    slotName: slot.slot_name,
    functionNumber: slotFunctionNumberForRow(state, slot),
    sound: {}
  };
}

function selectedNode(state) {
  if (!state.selectedNodeKey) {
    return null;
  }
  return (state.projectSummary?.nodes || []).find((node) => node.node_key === state.selectedNodeKey) || null;
}

function selectedConnector(state) {
  if (!state.selectedConnectorId) {
    return null;
  }
  return (state.projectSummary?.connectors || []).find((connector) => Number(connector.connector_id) === Number(state.selectedConnectorId)) || null;
}

function fallbackSlots(selectedSlots) {
  return (selectedSlots.length ? selectedSlots : [{slotId: 1, slotName: "Slot 1", functionNumber: null}]).map((slot) => ({
    slot_id: slot.slotId,
    slot_name: slot.slotName,
    functionKey: slot.functionNumber === null || slot.functionNumber === undefined ? "" : `F${slot.functionNumber}`,
  }));
}

function slotFunctionNumberForRow(state, slot) {
  const slotId = Number(slot.slot_id || 0);
  const selected = (state.selectedSlots || []).find((entry) => Number(entry.slotId) === slotId);
  const mappedText = String(slot.functionKey || "").replace(/^F/i, "");
  const mappedNumber = mappedText === "" ? null : Number(mappedText);
  if (Number.isFinite(mappedNumber) && mappedNumber >= 0) {
    return Math.min(68, Math.round(mappedNumber));
  }
  const selectedNumber = selected?.functionNumber;
  return selectedNumber === null || selectedNumber === undefined || selectedNumber === "" ? null : Math.min(68, Math.max(0, Math.round(Number(selectedNumber))));
}

function slotFunctionNumberInputValue(value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }
  const number = Number(value);
  return Number.isFinite(number) ? String(Math.min(68, Math.max(0, Math.round(number)))) : "";
}

function fallbackNodesForSlot(slotId) {
  return [
    {node_key: `${slotId}:0`, slot_id: slotId, node_id: 0, node_name: "入口", file_id: 0, x: 60, y: 160, width: 96, height: 64},
    {node_key: `${slotId}:1`, slot_id: slotId, node_id: 1, node_name: "播放音效", file_id: 1, x: 260, y: 160, width: 112, height: 64},
  ];
}

function fallbackConnectorsForSlot(slotId) {
  return [{connector_id: 1, slot_id: slotId, source_node_key: `${slotId}:0`, target_node_key: `${slotId}:1`}];
}

function nodeX(node) {
  return Math.max(20, Number(node.x ?? node.Node_X ?? 0));
}

function nodeY(node) {
  return Math.max(20, Number(node.y ?? node.Node_Y ?? 0));
}

function nodeWidth(node) {
  return Math.max(80, Number(node.width ?? node.Node_W ?? 96));
}

function nodeHeight(node) {
  return Math.max(56, Number(node.height ?? node.Node_H ?? 64));
}

function formatDuration(value) {
  const seconds = Number(value || 0);
  return seconds > 0 ? `${seconds.toFixed(2)}s` : "--";
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (!bytes) {
    return "--";
  }
  if (bytes >= 1024 * 1024) {
    return `${Math.round(bytes / 1024 / 1024)} MB`;
  }
  if (bytes >= 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${bytes} B`;
}

function sourceLabel(file) {
  if (file.source === "custom") {
    return "上传";
  }
  if (file.source === "missing") {
    return "缺失";
  }
  return "工程";
}

function soundLibraryCategoryOptions(state, selectedCategory = "") {
  const categories = [
    ...(state.libraryCatalog?.categories || []),
    {category: "custom", label: "自定义上传"},
  ];
  return categories.map((category) => {
    return `<option value="${esc(category.category)}"${selectedCategory === category.category ? " selected" : ""}>${esc(category.label)}</option>`;
  }).join("");
}

function slotCategoryLabel(categories, value) {
  return (categories || []).find((category) => category.category === value)?.label || value || "未分类";
}

function bindSoundPreviewControls(root, state, handlers) {
  root.querySelectorAll("[data-sound-file-play]").forEach((button) => {
    button.addEventListener("click", () => {
      const fileId = Number(button.dataset.soundFilePlay || 0);
      const file = projectSoundFiles(state).find((entry) => Number(entry.file_id) === fileId);
      playSoundPreview(file, handlers);
    });
  });
  syncSoundPreviewButtons(root);
}

function playSoundPreview(file, handlers) {
  const url = soundPreviewUrl(file);
  if (!url) {
    handlers.setStatus?.("该音效没有可试听音频数据");
    return;
  }
  const fileId = Number(file?.file_id || 0);
  if (activeSoundPreview && activeSoundPreviewFileId === fileId) {
    if (activeSoundPreview.paused || activeSoundPreview.ended) {
      resumeActiveSoundPreview(file, handlers);
      return;
    }
    pauseActiveSoundPreview(file, handlers);
    return;
  }
  activeSoundPreview?.pause?.();
  activeSoundPreviewFileId = fileId;
  activeSoundPreview = new Audio(url);
  activeSoundPreview.addEventListener?.("ended", () => {
    if (activeSoundPreviewFileId === fileId) {
      activeSoundPreview = null;
      activeSoundPreviewFileId = 0;
      syncSoundPreviewButtons();
    }
  });
  resumeActiveSoundPreview(file, handlers);
}

function pauseActiveSoundPreview(file, handlers) {
  activeSoundPreview?.pause?.();
  syncSoundPreviewButtons();
  handlers.setStatus?.(`已暂停试听 ${file.file_name || `音效 ${file.file_id}`}`);
}

function resumeActiveSoundPreview(file, handlers) {
  if (activeSoundPreview?.ended) {
    activeSoundPreview.currentTime = 0;
  }
  activeSoundPreview.play()
    .then(() => handlers.setStatus?.(`正在试听 ${file.file_name || `音效 ${file.file_id}`}`))
    .then(() => syncSoundPreviewButtons())
    .catch((error) => {
      activeSoundPreview = null;
      activeSoundPreviewFileId = 0;
      syncSoundPreviewButtons();
      handlers.setStatus?.(`试听失败：${error.message || String(error)}`);
    });
}

function soundPreviewButton(file, variant = "") {
  const fileId = Number(file?.file_id || 0);
  const canPlay = Boolean(soundPreviewUrl(file));
  const className = `sound-preview-button${variant ? ` ${variant}` : ""}`;
  const soundName = file?.file_name || `音效 ${fileId}`;
  const label = `试听 ${soundName}`;
  return `<button type="button" class="${className}" data-sound-file-play="${fileId}" data-sound-file-name="${esc(soundName)}" aria-label="${esc(label)}" aria-pressed="false" title="${canPlay ? esc(label) : "该音效没有可试听音频数据"}"${canPlay ? "" : " disabled"}>▶</button>`;
}

function syncSoundPreviewButtons(scope = document) {
  if (!scope?.querySelectorAll) {
    return;
  }
  scope.querySelectorAll("[data-sound-file-play]").forEach((button) => {
    const fileId = Number(button.dataset.soundFilePlay || 0);
    const soundName = button.dataset.soundFileName || `音效 ${fileId}`;
    const sameFile = Boolean(activeSoundPreview && activeSoundPreviewFileId === fileId);
    const isPlaying = sameFile && !activeSoundPreview.paused && !activeSoundPreview.ended;
    const action = isPlaying ? "暂停" : sameFile ? "继续试听" : "试听";
    button.textContent = isPlaying ? "⏸" : "▶";
    button.classList.toggle("playing", isPlaying);
    button.setAttribute("aria-pressed", isPlaying ? "true" : "false");
    button.setAttribute("aria-label", `${action} ${soundName}`);
    button.title = `${action} ${soundName}`;
  });
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[char]);
}
