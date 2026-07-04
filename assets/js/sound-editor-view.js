import {
  addSoundConnector,
  addSoundNode,
  ensureDefaultSoundEditorSelection,
  closeSoundFileEditor,
  deleteUnusedSoundFile,
  filterSoundLibrary,
  markSoundEditorChanged,
  openSoundFileEditor,
  panSoundCanvas,
  projectSoundFiles,
  replaceSoundFile,
  resetSoundCanvasViewport,
  selectSoundForSlot,
  setNodeSoundFile,
  setSoundCanvasZoom,
  soundUsageForProject,
  soundCanvasBoundsForSlot,
  moveSoundNode,
  resizeSoundNode,
  updateSoundConnectorEndpoint,
  updateSoundConnectorField,
  updateSoundNodeField,
  updateSelectedSlotField
} from "./sound-editor-controller.js";

export function renderSoundEditor(root, state, handlers = {}) {
  if (!root) {
    return;
  }
  ensureDefaultSoundEditorSelection(state);
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
  summary.innerHTML = state.projectSummary ? [
    `<span>模块 ${esc(state.projectSummary.base_info?.decoder_module || "--")}</span>`,
    `<span>${counts.slots || 0} 个 Slot</span>`,
    `<span>${counts.nodes || 0} 个节点</span>`,
    `<span>${counts.connectors || 0} 条连接</span>`,
    `<span>${counts.sound_files || 0} 个音频</span>`
  ].join("") : "<span>未导入 DXSD，可直接从音效库创建新工程</span>";
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
    return `<button type="button" class="sound-slot-row${selected ? " active" : ""}" data-slot-id="${slot.slot_id}">
      <span class="sound-slot-number">${slot.slot_id}</span>
      <span class="sound-slot-name">${esc(slot.slot_name || `Slot ${slot.slot_id}`)}</span>
      <span class="sound-slot-meta">${esc(slot.functionKey || "")}</span>
    </button>`;
  }).join("");
  list.querySelectorAll("[data-slot-id]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeSlotId = Number(button.dataset.slotId || 0);
      state.selectedNodeKey = "";
      state.selectedConnectorId = 0;
      handlers.renderAll?.();
    });
  });
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
  canvas.innerHTML = `<div class="sound-canvas-toolbar" aria-label="节点图缩放">
    <button id="soundCanvasZoomOut" type="button" title="缩小">-</button>
    <span>${Math.round(zoom * 100)}%</span>
    <button id="soundCanvasZoomIn" type="button" title="放大">+</button>
    <button id="soundCanvasZoomReset" type="button">100%</button>
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
    </div>
  </div>`;
  wireCanvasViewport(canvas, state, handlers);
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
      handlers.renderAll?.();
    });
  });
  canvas.querySelectorAll("[data-connector-id]").forEach((element) => {
    element.addEventListener("click", () => {
      state.selectedConnectorId = Number(element.dataset.connectorId || 0);
      state.selectedNodeKey = "";
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
    dragState = {
      pointerId: event.pointerId,
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
    scroll.scrollLeft = dragState.startLeft - (event.clientX - dragState.startX);
    scroll.scrollTop = dragState.startTop - (event.clientY - dragState.startY);
    state.canvasViewport.offsetX = scroll.scrollLeft;
    state.canvasViewport.offsetY = scroll.scrollTop;
  });
  const stopDragging = (event) => {
    if (!dragState || dragState.pointerId !== event.pointerId) {
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
    `<h2>属性</h2>`,
    slot ? slotEditor(slot) : `<p class="empty-state">选择 Slot 后编辑功能键和音效。</p>`,
    node ? nodeDetails(node, state) : "",
    connector ? connectorDetails(connector, state) : ""
  ].join("");
  panel.querySelectorAll("[data-slot-field]").forEach((input) => {
    input.addEventListener("change", () => {
      updateSelectedSlotField(state, state.activeSlotId, input.dataset.slotField, input.value);
      handlers.renderAll?.();
    });
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
}

function renderSoundFileInventory(root, state, handlers) {
  const panel = root.querySelector("#soundFileInventoryPanel");
  if (!panel) {
    return;
  }
  const files = soundUsageForProject(state);
  panel.innerHTML = `<div class="sound-file-inventory-header">
    <h2>当前音效包文件</h2>
    <span>${files.length} 个文件</span>
  </div>
  ${files.length ? `<div class="sound-file-table" role="table" aria-label="当前音效包音频文件">
    <div class="sound-file-row sound-file-row-head" role="row">
      <span role="columnheader">ID</span>
      <span role="columnheader">文件</span>
      <span role="columnheader">时长</span>
      <span role="columnheader">大小</span>
      <span role="columnheader">来源</span>
      <span role="columnheader">使用位置</span>
      <span role="columnheader">操作</span>
    </div>
    ${files.map((file) => {
      const used = file.used_by.length > 0;
      return `<div class="sound-file-row" role="row">
      <span role="cell">#${Number(file.file_id || 0)}</span>
      <span role="cell">${esc(file.file_name || "")}</span>
      <span role="cell">${formatDuration(file.duration_seconds)}</span>
      <span role="cell">${formatBytes(file.pcm_bytes)}</span>
      <span role="cell">${sourceLabel(file)}</span>
      <span role="cell">${file.used_by.length ? esc(file.used_by.join("，")) : "未使用"}</span>
      <span role="cell" class="sound-file-actions">
        <button type="button" data-sound-file-edit="${Number(file.file_id || 0)}">编辑</button>
        <button type="button" class="danger" data-sound-file-delete="${Number(file.file_id || 0)}"${used ? " disabled title=\"已被 Slot 或节点引用，不能删除\"" : ""}>删除</button>
      </span>
    </div>`;
    }).join("")}
  </div>` : `<p class="empty-state">导入 DXSD 或上传音频后显示文件用量。</p>`}`;
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
  const librarySounds = state.libraryCatalog.sounds || [];
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
  <div class="sound-file-editor-library" aria-label="选择系统音效">
    ${librarySounds.map((sound) => `<button type="button" class="sound-library-item" data-replacement-sound-id="${esc(sound.sound_id)}">
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
  const categorySelect = root.querySelector("#soundLibraryCategory");
  const searchInput = root.querySelector("#soundLibrarySearch");
  if (!panel) {
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
    sounds: [...(state.libraryCatalog.sounds || []), ...state.customSounds]
  }, state.libraryFilter);
  panel.innerHTML = sounds.map((sound) => {
    return `<button type="button" class="sound-library-item" data-sound-id="${esc(sound.sound_id)}">
      <strong>${esc(sound.label)}</strong>
      <span>${esc(sound.description || "")}</span>
      <small>${sound.audio_available ? "含音频" : "仅元数据"}</small>
    </button>`;
  }).join("") || `<p class="empty-state">没有匹配的音效。</p>`;
  panel.querySelectorAll("[data-sound-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const sound = sounds.find((entry) => entry.sound_id === button.dataset.soundId);
      if (!sound) {
        return;
      }
      selectSoundForSlot(state, state.activeSlotId || 1, sound);
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
  const selected = Number(connector.connector_id) === Number(state.selectedConnectorId);
  return `<g class="sound-connector-group${selected ? " selected" : ""}">
    <path class="sound-connector${selected ? " selected" : ""}" data-connector-id="${connector.connector_id}" d="M${x1} ${y1} C${x1 + 60} ${y1}, ${x2 - 60} ${y2}, ${x2} ${y2}" marker-end="url(#soundArrow)"></path>
    <circle class="sound-connector-handle source" data-connector-id="${connector.connector_id}" data-connector-end="source" cx="${x1}" cy="${y1}" r="6"></circle>
    <circle class="sound-connector-handle target" data-connector-id="${connector.connector_id}" data-connector-end="target" cx="${x2}" cy="${y2}" r="6"></circle>
  </g>`;
}

function nodeSvg(node, state) {
  const selected = node.node_key === state.selectedNodeKey;
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

function slotEditor(slot) {
  return `<div class="sound-property-block">
    <label>Slot 名称<input data-slot-field="slotName" value="${esc(slot.slotName || slot.slot_name || "")}"></label>
    <label>功能键<input type="number" min="0" max="68" data-slot-field="functionNumber" value="${Number(slot.functionNumber || 0)}"></label>
    <p>音效文件：${esc(slot.sound?.fileName || "未选择")}</p>
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
    <label>类型<input type="number" min="0" max="999" data-node-field="nodeType" value="${Number(node.node_type || 0)}"></label>
    <label>重复次数<input type="number" min="0" max="9999" data-node-field="repeatAmount" value="${Number(node.repeat_amount || 0)}"></label>
    <label>音量<input type="number" min="0" max="255" data-node-field="soundVolume" value="${Number(node.sound_volume || 0)}"></label>
    <div class="sound-property-grid">
      <label>宽<input type="number" min="80" max="500" data-node-field="width" value="${Number(node.width ?? 96)}"></label>
      <label>高<input type="number" min="56" max="300" data-node-field="height" value="${Number(node.height ?? 64)}"></label>
    </div>
    <p>音频：${esc(file?.file_name || "无")}</p>
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
    functionNumber: Number(String(slot.functionKey || "").replace(/^F/i, "")) || slot.slot_id,
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
  return (selectedSlots.length ? selectedSlots : [{slotId: 1, slotName: "Slot 1", functionNumber: 1}]).map((slot) => ({
    slot_id: slot.slotId,
    slot_name: slot.slotName,
    functionKey: slot.functionNumber ? `F${slot.functionNumber}` : "",
  }));
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
  return "DXSD";
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
