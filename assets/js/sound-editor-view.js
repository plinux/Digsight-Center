import {
  ensureDefaultSoundEditorSelection,
  filterSoundLibrary,
  projectSoundFiles,
  selectSoundForSlot,
  setNodeSoundFile,
  soundUsageForProject,
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
  renderSoundFileInventory(root, state);
  renderLibrary(root, state, handlers);
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
      state.packageName = packageName.value || "新音效工程";
    };
  }
  if (!summary) {
    return;
  }
  const counts = state.projectSummary?.counts || {};
  summary.innerHTML = state.projectSummary ? [
    `<span>模块 ${esc(state.projectSummary.base_info?.decoder_module || "--")}</span>`,
    `<span>${counts.slots || 0} slots</span>`,
    `<span>${counts.nodes || 0} nodes</span>`,
    `<span>${counts.connectors || 0} links</span>`,
    `<span>${counts.sound_files || 0} sounds</span>`
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
      <span class="sound-slot-name">${esc(slot.slot_name || `Sound slot ${slot.slot_id}`)}</span>
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
  const width = 760;
  const height = 420;
  const connectorMarkup = connectors.map((connector) => connectorSvg(connector, nodes, state)).join("");
  const nodeMarkup = nodes.map((node) => nodeSvg(node, state)).join("");
  canvas.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="音效节点图">
    <defs>
      <marker id="soundArrow" markerWidth="10" markerHeight="8" refX="8" refY="4" orient="auto">
        <path d="M0,0 L10,4 L0,8 Z" fill="#176b87"></path>
      </marker>
    </defs>
    <g class="sound-grid">${gridLines(width, height)}</g>
    <g>${connectorMarkup}</g>
    <g>${nodeMarkup}</g>
  </svg>`;
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
    slot ? slotEditor(slot) : `<p class="empty-state">选择 slot 后编辑功能键和音效。</p>`,
    node ? nodeDetails(node, state) : "",
    connector ? connectorDetails(connector) : ""
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
}

function renderSoundFileInventory(root, state) {
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
    </div>
    ${files.map((file) => `<div class="sound-file-row" role="row">
      <span role="cell">#${Number(file.file_id || 0)}</span>
      <span role="cell">${esc(file.file_name || "")}</span>
      <span role="cell">${formatDuration(file.duration_seconds)}</span>
      <span role="cell">${formatBytes(file.pcm_bytes)}</span>
      <span role="cell">${sourceLabel(file)}</span>
      <span role="cell">${file.used_by.length ? esc(file.used_by.join("，")) : "未使用"}</span>
    </div>`).join("")}
  </div>` : `<p class="empty-state">导入 DXSD 或上传音频后显示文件用量。</p>`}`;
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
  return `<path class="sound-connector${selected ? " selected" : ""}" data-connector-id="${connector.connector_id}" d="M${x1} ${y1} C${x1 + 60} ${y1}, ${x2 - 60} ${y2}, ${x2} ${y2}" marker-end="url(#soundArrow)"></path>`;
}

function nodeSvg(node, state) {
  const selected = node.node_key === state.selectedNodeKey;
  const x = nodeX(node);
  const y = nodeY(node);
  const w = nodeWidth(node);
  const h = nodeHeight(node);
  return `<g class="sound-node${selected ? " selected" : ""}" data-node-key="${esc(node.node_key)}">
    <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="6"></rect>
    <text x="${x + w / 2}" y="${y + 25}" text-anchor="middle">${esc(node.node_name || `Node ${node.node_id}`)}</text>
    <text x="${x + w / 2}" y="${y + 47}" text-anchor="middle">File ${Number(node.file_id || 0)}</text>
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
    <h3>Node ${Number(node.node_id)}</h3>
    <p>类型 ${Number(node.node_type || 0)}，音量 ${Number(node.sound_volume || 0)}</p>
    <p>音频：${esc(file?.file_name || "无")}</p>
    <label>音效文件<select id="soundNodeFileSelect">${options}</select></label>
  </div>`;
}

function connectorDetails(connector) {
  return `<div class="sound-property-block">
    <h3>Connection ${Number(connector.connector_id)}</h3>
    <p>${esc(connector.source_node_key)} → ${esc(connector.target_node_key)}</p>
    <p>Judgment ${Number(connector.judgment_count || 0)} / Action ${Number(connector.action_count || 0)}</p>
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
  return (selectedSlots.length ? selectedSlots : [{slotId: 1, slotName: "Sound slot 1", functionNumber: 1}]).map((slot) => ({
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
