export function createSoundEditorState() {
  return {
    chipProfiles: [],
    libraryCatalog: {categories: [], sounds: []},
    projectSummary: null,
    projectViewModel: createSoundProjectViewModel(null),
    activeSlotId: 0,
    selectedNodeKey: "",
    selectedConnectorId: 0,
    selectedNodeKeys: [],
    selectedConnectorIds: [],
    expandedPropertyItemKeys: [],
    expandedPropertySectionKeys: [],
    selectedSlots: [],
    customSounds: [],
    canvasViewport: {zoom: 1, offsetX: 0, offsetY: 0},
    canvasSelectionMode: false,
    canvasContextMenu: {open: false, x: 0, y: 0},
    editingSoundFileId: null,
    pendingSoundExport: false,
    isExportingSoundPackage: false,
    changedDuringSoundExport: false,
    packageName: "新音效工程",
    chipId: "",
    libraryFilter: {category: "", query: ""},
    soundFileEditorFilter: {category: "", query: ""},
    soundFileSort: {field: "file_id", direction: "asc"},
    savedSoundLibrary: [],
    slotLibrary: {categories: defaultSlotLibraryCategories(), slots: []},
    slotLibraryFilter: {category: "", query: ""},
    slotListWidthPx: 240,
    propertyPanelWidthPx: 300,
    soundClipboard: null,
    packageWarnings: [],
    statusMessage: ""
  };
}

export function markSoundEditorChanged(state) {
  state.pendingSoundExport = true;
  if (state.isExportingSoundPackage) {
    state.changedDuringSoundExport = true;
  }
}

export function markSoundEditorExportStarted(state) {
  state.isExportingSoundPackage = true;
  state.changedDuringSoundExport = false;
}

export function markSoundEditorExported(state) {
  state.pendingSoundExport = Boolean(state.changedDuringSoundExport);
  state.isExportingSoundPackage = false;
  state.changedDuringSoundExport = false;
}

export function markSoundEditorExportFailed(state) {
  state.isExportingSoundPackage = false;
  state.changedDuringSoundExport = false;
}

export function hasPendingSoundExport(state) {
  return Boolean(state?.pendingSoundExport || state?.isExportingSoundPackage);
}

export function isSoundPropertyItemExpanded(state, itemKey) {
  const key = String(itemKey || "");
  return key ? soundPropertyItemKeys(state).includes(key) : false;
}

export function toggleSoundPropertyItemExpansion(state, itemKey) {
  const key = String(itemKey || "");
  if (!key) {
    return false;
  }
  const keys = soundPropertyItemKeys(state);
  const index = keys.indexOf(key);
  if (index >= 0) {
    keys.splice(index, 1);
    return false;
  }
  keys.push(key);
  return true;
}

export function isSoundPropertySectionExpanded(state, sectionKey) {
  const key = String(sectionKey || "");
  return key ? soundPropertySectionKeys(state).includes(key) : false;
}

export function toggleSoundPropertySectionExpansion(state, sectionKey) {
  const key = String(sectionKey || "");
  if (!key) {
    return false;
  }
  const keys = soundPropertySectionKeys(state);
  const index = keys.indexOf(key);
  if (index >= 0) {
    keys.splice(index, 1);
    return false;
  }
  keys.push(key);
  return true;
}

export function setSoundCanvasZoom(state, nextZoom) {
  state.canvasViewport ||= {zoom: 1, offsetX: 0, offsetY: 0};
  state.canvasViewport.zoom = clamp(Number(nextZoom || 1), 0.5, 2.5);
}

export function panSoundCanvas(state, deltaX, deltaY) {
  state.canvasViewport ||= {zoom: 1, offsetX: 0, offsetY: 0};
  state.canvasViewport.offsetX = Math.max(0, state.canvasViewport.offsetX + Number(deltaX || 0));
  state.canvasViewport.offsetY = Math.max(0, state.canvasViewport.offsetY + Number(deltaY || 0));
}

export function resetSoundCanvasViewport(state) {
  state.canvasViewport = {zoom: 1, offsetX: 0, offsetY: 0};
}

export function soundCanvasBoundsForSlot(state, slotId) {
  const nodes = state.projectViewModel?.nodesBySlot?.get(Number(slotId || 0)) || [];
  const fallbackWidth = 760;
  const fallbackHeight = 420;
  let width = fallbackWidth;
  let height = fallbackHeight;
  for (const node of nodes) {
    width = Math.max(width, Number(node.x ?? node.Node_X ?? 0) + Number(node.width ?? node.Node_W ?? 96) + 80);
    height = Math.max(height, Number(node.y ?? node.Node_Y ?? 0) + Number(node.height ?? node.Node_H ?? 64) + 80);
  }
  return {width: Math.ceil(width), height: Math.ceil(height)};
}

export function createSoundProjectViewModel(summary) {
  const slots = (summary?.slots || []).map((slot) => ({
    ...slot,
    functionKey: functionKeyForSlot(summary, slot.slot_id),
    nodeCount: (summary?.nodes || []).filter((node) => Number(node.slot_id) === Number(slot.slot_id)).length,
    connectorCount: (summary?.connectors || []).filter((connector) => Number(connector.slot_id) === Number(slot.slot_id)).length
  }));
  const nodesBySlot = new Map();
  for (const node of summary?.nodes || []) {
    const slotId = Number(node.slot_id || 0);
    if (!nodesBySlot.has(slotId)) {
      nodesBySlot.set(slotId, []);
    }
    nodesBySlot.get(slotId).push(node);
  }
  const connectorsBySlot = new Map();
  for (const connector of summary?.connectors || []) {
    const slotId = Number(connector.slot_id || 0);
    if (!connectorsBySlot.has(slotId)) {
      connectorsBySlot.set(slotId, []);
    }
    connectorsBySlot.get(slotId).push(connector);
  }
  const soundFilesById = new Map();
  for (const file of summary?.sound_files || []) {
    soundFilesById.set(Number(file.file_id), file);
  }
  return {slots, nodesBySlot, connectorsBySlot, soundFilesById};
}

export function functionKeyForSlot(summary, slotId) {
  const mapping = (summary?.function_mappings || []).find((entry) => Number(entry.slot_id) === Number(slotId));
  return mapping?.function_key || "";
}

export function filterSoundLibrary(catalog, filter = {}) {
  const category = String(filter.category || "").trim();
  const query = String(filter.query || "").trim().toLowerCase();
  return (catalog?.sounds || []).filter((entry) => {
    if (category && entry.category !== category) {
      return false;
    }
    if (!query) {
      return true;
    }
    const haystack = [
      entry.label,
      entry.description,
      entry.category,
      ...(entry.tags || [])
    ].join(" ").toLowerCase();
    return haystack.includes(query);
  });
}

export function buildSoundPackagePayload({chipId, packageName, selectedSlots, state}) {
  const slots = state ? packageSlotsForState(state, selectedSlots) : (selectedSlots || []);
  return {
    chip_id: chipId,
    package_name: packageName,
    slots: slots.map((slot) => ({
      slot_id: Number(slot.slotId || slot.slot_id || 0),
      slot_name: slot.slotName || slot.slot_name || "",
      function_key: serializedFunctionKey(slot.functionNumber ?? slot.function_key),
      sound: {
        library_id: slot.sound?.libraryId || slot.sound?.library_id || "",
        file_name: slot.sound?.fileName || slot.sound?.file_name || "",
        content_base64: soundPackageContentBase64(slot.sound)
      },
      nodes: slot.nodes || [],
      connectors: slot.connectors || [],
      judgments: slot.judgments || [],
      actions: slot.actions || [],
      sound_files: slot.soundFiles || slot.sound_files || [],
      legacy_user_type: slot.legacyUserType ?? slot.legacy_user_type ?? null,
      legacy_user_volume: slot.legacyUserVolume ?? slot.legacy_user_volume ?? null,
      legacy_user_files: legacyUserFilesForSlot(slot)
    }))
  };
}

export function projectSoundFiles(state) {
  const byId = new Map();
  for (const file of state.projectSummary?.sound_files || []) {
    const fileId = soundFileId(file.file_id ?? file.fileId);
    if (fileId === null) {
      continue;
    }
    byId.set(fileId, normalizeProjectSoundFile(file, "dxsd"));
  }
  for (const sound of state.customSounds || []) {
    const fileId = soundFileId(sound.fileId ?? sound.file_id);
    if (fileId === null) {
      continue;
    }
    byId.set(fileId, normalizeProjectSoundFile({
      file_id: fileId,
      file_name: sound.fileName || sound.file_name || sound.label || `sound-${fileId}.wav`,
      duration_seconds: sound.durationSeconds ?? sound.duration_seconds ?? 0,
      pcm_bytes: sound.pcmBytes ?? sound.pcm_bytes ?? 0,
      content_base64: sound.contentBase64 || sound.content_base64 || "",
      content_encoding: sound.contentEncoding || sound.content_encoding || "wav",
      preview_format: sound.previewFormat || sound.preview_format || sound.wavMetadata || null,
      has_audio_data: Boolean(sound.audio_available || sound.contentBase64 || sound.content_base64),
      sound_id: sound.sound_id || sound.libraryId || "",
      source_label: sound.asset_source || "user_upload"
    }, "custom"));
  }
  return Array.from(byId.values()).sort((left, right) => Number(left.file_id) - Number(right.file_id));
}

export function soundPreviewUrl(file) {
  const contentBase64 = String(file?.content_base64 || file?.contentBase64 || "").trim();
  if (!contentBase64) {
    return "";
  }
  const contentBytes = base64ToBytes(contentBase64);
  const contentEncoding = String(file?.content_encoding || file?.contentEncoding || "").toLowerCase();
  if (contentEncoding === "wav" || asciiFromBytes(contentBytes, 0, 4) === "RIFF") {
    return `data:audio/wav;base64,${contentBase64}`;
  }
  return `data:audio/wav;base64,${pcmWavBase64(contentBytes, file?.preview_format || file?.previewFormat)}`;
}

export function openSoundFileEditor(state, fileId) {
  state.editingSoundFileId = soundFileId(fileId);
}

export function closeSoundFileEditor(state) {
  state.editingSoundFileId = null;
}

export function deleteUnusedSoundFile(state, fileId) {
  const numericFileId = soundFileId(fileId);
  if (numericFileId === null) {
    return false;
  }
  const usage = soundUsageForProject(state).find((file) => Number(file.file_id) === numericFileId);
  if (usage?.used_by?.length) {
    return false;
  }
  if (state.projectSummary?.sound_files) {
    state.projectSummary.sound_files = state.projectSummary.sound_files.filter((file) => Number(file.file_id) !== numericFileId);
  }
  state.customSounds = (state.customSounds || []).filter((sound) => Number(sound.fileId ?? sound.file_id ?? 0) !== numericFileId);
  for (const slot of state.selectedSlots || []) {
    if (Number(slot.sound?.fileId ?? slot.sound?.file_id ?? 0) === numericFileId) {
      slot.sound = {};
    }
  }
  closeSoundFileEditor(state);
  state.projectViewModel = createSoundProjectViewModel(state.projectSummary);
  markSoundEditorChanged(state);
  return true;
}

export function replaceSoundFile(state, fileId, sound) {
  const numericFileId = soundFileId(fileId);
  if (numericFileId === null || !sound) {
    return null;
  }
  const replacement = {
    ...sound,
    fileId: numericFileId,
    fileName: sound.fileName || sound.file_name || sound.label || `sound-${numericFileId}.wav`,
    contentBase64: sound.contentBase64 || sound.content_base64 || "",
    contentEncoding: sound.contentEncoding || sound.content_encoding || "",
    previewFormat: sound.previewFormat || sound.preview_format || null
  };
  const customSounds = state.customSounds || [];
  const existingIndex = customSounds.findIndex((entry) => Number(entry.fileId ?? entry.file_id ?? 0) === numericFileId);
  if (existingIndex >= 0) {
    customSounds[existingIndex] = {...customSounds[existingIndex], ...replacement};
  } else {
    customSounds.push(replacement);
  }
  state.customSounds = customSounds;
  for (const slot of state.selectedSlots || []) {
    if (Number(slot.sound?.fileId ?? slot.sound?.file_id ?? 0) === numericFileId) {
      slot.sound = normalizeSelectedSound({
        ...replacement,
        file_id: numericFileId,
        file_name: replacement.fileName,
        content_base64: replacement.contentBase64,
        content_encoding: replacement.contentEncoding,
        preview_format: replacement.previewFormat
      });
    }
  }
  state.projectViewModel = createSoundProjectViewModel(state.projectSummary);
  markSoundEditorChanged(state);
  return soundFileById(state, numericFileId);
}

export function soundUsageForProject(state) {
  const byId = new Map(projectSoundFiles(state).map((file) => [
    Number(file.file_id),
    {...file, used_by: []}
  ]));
  for (const node of state.projectSummary?.nodes || []) {
    const fileId = assignedSoundFileId(node.file_id);
    if (fileId === null) {
      continue;
    }
    if (!byId.has(fileId)) {
      byId.set(fileId, normalizeProjectSoundFile({
        file_id: fileId,
        file_name: `File ${fileId}`,
        has_audio_data: false
      }, "missing"));
      byId.get(fileId).used_by = [];
    }
    byId.get(fileId).used_by.push(`Slot ${Number(node.slot_id || 0)} / 节点 ${Number(node.node_id || 0)}`);
  }
  if (!(state.projectSummary?.nodes || []).length) {
    const selectedBySlotId = new Map((state.selectedSlots || []).map((slot) => [
      Number(slot.slotId ?? slot.slot_id ?? 0),
      slot
    ]));
    const slots = state.projectSummary?.slots?.length ? state.projectSummary.slots : (state.selectedSlots || []);
    for (const slot of slots) {
      const slotId = Number(slot.slot_id ?? slot.slotId ?? 0);
      const selected = selectedBySlotId.get(slotId) || slot;
      const fileIds = new Set(legacySoundFileIdsForSlot(slot));
      const selectedFileId = selectedSoundFileId(selected.sound);
      if (selectedFileId !== null) {
        fileIds.add(selectedFileId);
      }
      for (const fileId of fileIds) {
        ensureSoundUsageEntry(byId, fileId, selected.sound || soundFileById(state, fileId) || {});
        byId.get(fileId).used_by.push(`Slot ${slotId}`);
      }
    }
  }
  return Array.from(byId.values()).sort((left, right) => Number(left.file_id) - Number(right.file_id));
}

export function sortSoundFiles(files, sort = {}) {
  const field = sort.field || "file_id";
  const direction = sort.direction === "desc" ? -1 : 1;
  const collator = new Intl.Collator("zh-Hans-CN", {numeric: true, sensitivity: "base"});
  const valueFor = (file) => {
    if (field === "file_name") {
      return String(file.file_name || "");
    }
    if (field === "duration_seconds") {
      return Number(file.duration_seconds || 0);
    }
    if (field === "size_bits") {
      return Number(file.pcm_bytes || 0) * 8;
    }
    if (field === "source") {
      return String(file.source || file.source_label || "");
    }
    if (field === "used_by") {
      return (file.used_by || []).join(" ");
    }
    return Number(file.file_id || 0);
  };
  return [...(files || [])].sort((left, right) => {
    const leftValue = valueFor(left);
    const rightValue = valueFor(right);
    if (typeof leftValue === "number" && typeof rightValue === "number") {
      return (leftValue - rightValue) * direction || (Number(left.file_id || 0) - Number(right.file_id || 0));
    }
    return collator.compare(String(leftValue), String(rightValue)) * direction
      || (Number(left.file_id || 0) - Number(right.file_id || 0));
  });
}

export function toggleSoundFileSort(state, field) {
  const current = state.soundFileSort || {field: "file_id", direction: "asc"};
  state.soundFileSort = {
    field,
    direction: current.field === field && current.direction === "asc" ? "desc" : "asc"
  };
}

export function formatBitCount(bits, decimals = 0) {
  const number = Number(bits || 0);
  if (!Number.isFinite(number)) {
    return decimals > 0 ? Number(0).toFixed(decimals) : "0";
  }
  return number.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

export function formatMegabitCount(bits) {
  return `${formatBitCount(Number(bits || 0) / 1024 / 1024, 2)}Mb`;
}

export function deleteUnusedSoundFiles(state) {
  const unusedFileIds = soundUsageForProject(state)
    .filter((file) => !(file.used_by || []).length)
    .map((file) => soundFileId(file.file_id))
    .filter((fileId) => fileId !== null);
  let deletedCount = 0;
  for (const fileId of unusedFileIds) {
    if (deleteUnusedSoundFile(state, fileId)) {
      deletedCount += 1;
    }
  }
  return deletedCount;
}

export function clearSoundSlot(state, slotId) {
  const numericSlotId = Number(slotId || state.activeSlotId || 0);
  if (!numericSlotId) {
    return false;
  }
  ensureSoundProjectSummaryBase(state);
  const connectorIdsToDelete = slotConnectorIds(state, numericSlotId);
  const beforeNodeCount = (state.projectSummary.nodes || []).length;
  const beforeConnectorCount = (state.projectSummary.connectors || []).length;
  state.projectSummary.nodes = (state.projectSummary.nodes || [])
    .filter((node) => Number(node.slot_id) !== numericSlotId);
  state.projectSummary.connectors = (state.projectSummary.connectors || [])
    .filter((connector) => Number(connector.slot_id) !== numericSlotId);
  state.projectSummary.judgments = (state.projectSummary.judgments || [])
    .filter((judgment) => !connectorIdsToDelete.has(Number(judgment.connector_id || 0)));
  state.projectSummary.actions = (state.projectSummary.actions || [])
    .filter((action) => !connectorIdsToDelete.has(Number(action.connector_id || 0)));
  state.projectSummary.function_mappings = (state.projectSummary.function_mappings || [])
    .filter((mapping) => Number(mapping.slot_id) !== numericSlotId);
  const summarySlot = summarySlotById(state, numericSlotId);
  if (summarySlot) {
    summarySlot.is_use = false;
    summarySlot.slot_start_node = 0;
    summarySlot.legacy_user_type = 0;
    summarySlot.legacy_user_volume = 0;
    summarySlot.legacy_user_files = [null, null, null];
    summarySlot.legacy_file_ids = [];
  }
  const selectedSlot = (state.selectedSlots || []).find((slot) => Number(slot.slotId) === numericSlotId);
  if (selectedSlot) {
    selectedSlot.sound = {};
    selectedSlot.functionNumber = null;
    selectedSlot.legacyUserType = 0;
    selectedSlot.legacyUserVolume = 0;
    selectedSlot.legacyUserFiles = [null, null, null];
  }
  state.selectedNodeKey = "";
  state.selectedConnectorId = 0;
  state.selectedNodeKeys = [];
  state.selectedConnectorIds = [];
  state.expandedPropertyItemKeys = soundPropertyItemKeys(state)
    .filter((itemKey) => !itemKey.startsWith(`node:${numericSlotId}:`)
      && !itemKey.startsWith(`connector:${numericSlotId}:`));
  state.expandedPropertySectionKeys = soundPropertySectionKeys(state)
    .filter((sectionKey) => !sectionKey.startsWith(`section:${numericSlotId}:`));
  refreshSoundProjectViewModel(state);
  const changed = beforeNodeCount !== state.projectSummary.nodes.length
    || beforeConnectorCount !== state.projectSummary.connectors.length
    || Boolean(selectedSlot?.sound);
  markSoundEditorChanged(state);
  return Boolean(changed || summarySlot || selectedSlot);
}

export function setSoundPanelWidth(state, panelName, widthPx) {
  const width = boundedNumber(widthPx, 180, 520);
  if (panelName === "slots") {
    state.slotListWidthPx = width;
  } else if (panelName === "properties") {
    state.propertyPanelWidthPx = width;
  }
}

export function setCanvasSelectionMode(state, enabled) {
  state.canvasSelectionMode = Boolean(enabled);
  state.canvasContextMenu = {open: false, x: 0, y: 0};
}

export function selectSoundItemsInRect(state, slotId, rect) {
  const numericSlotId = Number(slotId || state.activeSlotId || 0);
  const normalized = normalizeRect(rect);
  const nodes = (state.projectSummary?.nodes || []).filter((node) => Number(node.slot_id) === numericSlotId);
  const selectedNodeKeys = nodes
    .filter((node) => rectIntersectsNode(normalized, node))
    .map((node) => node.node_key);
  const selectedNodeIds = new Set(nodes
    .filter((node) => selectedNodeKeys.includes(node.node_key))
    .map((node) => Number(node.node_id || 0)));
  const selectedConnectorIds = (state.projectSummary?.connectors || [])
    .filter((connector) => Number(connector.slot_id) === numericSlotId)
    .filter((connector) => selectedNodeIds.has(Number(connector.source_node_id || 0))
      && selectedNodeIds.has(Number(connector.target_node_id || 0)))
    .map((connector) => Number(connector.connector_id || 0));
  state.selectedNodeKeys = selectedNodeKeys;
  state.selectedConnectorIds = selectedConnectorIds;
  state.selectedNodeKey = selectedNodeKeys.length === 1 ? selectedNodeKeys[0] : "";
  state.selectedConnectorId = !selectedNodeKeys.length && selectedConnectorIds.length === 1 ? selectedConnectorIds[0] : 0;
  return {nodeKeys: selectedNodeKeys, connectorIds: selectedConnectorIds};
}

export function setSoundSelection(state, nodeKeys = [], connectorIds = []) {
  state.selectedNodeKeys = Array.from(new Set((nodeKeys || []).filter(Boolean)));
  state.selectedConnectorIds = Array.from(new Set((connectorIds || []).map(Number).filter(Boolean)));
  state.selectedNodeKey = state.selectedNodeKeys.length === 1 ? state.selectedNodeKeys[0] : "";
  state.selectedConnectorId = !state.selectedNodeKeys.length && state.selectedConnectorIds.length === 1
    ? state.selectedConnectorIds[0]
    : 0;
}

export function copySoundSelection(state) {
  const selectedNodeKeys = effectiveSelectedNodeKeys(state);
  const selectedConnectorIds = effectiveSelectedConnectorIds(state);
  const selectedNodes = (state.projectSummary?.nodes || [])
    .filter((node) => selectedNodeKeys.has(node.node_key))
    .map((node) => ({...node}));
  const nodeIdSet = new Set(selectedNodes.map((node) => Number(node.node_id || 0)));
  const selectedConnectors = (state.projectSummary?.connectors || [])
    .filter((connector) => selectedConnectorIds.has(Number(connector.connector_id || 0))
      || (nodeIdSet.has(Number(connector.source_node_id || 0)) && nodeIdSet.has(Number(connector.target_node_id || 0))))
    .map((connector) => ({...connector}));
  const selectedConnectorIdSet = new Set(selectedConnectors.map((connector) => Number(connector.connector_id || 0)));
  const selectedJudgments = (state.projectSummary?.judgments || [])
    .filter((judgment) => selectedConnectorIdSet.has(Number(judgment.connector_id || 0)))
    .map((judgment) => ({...judgment}));
  const selectedActions = (state.projectSummary?.actions || [])
    .filter((action) => selectedConnectorIdSet.has(Number(action.connector_id || 0)))
    .map((action) => ({...action}));
  if (!selectedNodes.length && !selectedConnectors.length) {
    state.soundClipboard = null;
    return 0;
  }
  state.soundClipboard = {
    slotId: Number(state.activeSlotId || selectedNodes[0]?.slot_id || selectedConnectors[0]?.slot_id || 0),
    nodes: selectedNodes,
    connectors: selectedConnectors,
    judgments: selectedJudgments,
    actions: selectedActions
  };
  return selectedNodes.length + selectedConnectors.length;
}

export function canPasteSoundSelection(state) {
  return Boolean((state.soundClipboard?.nodes || []).length || (state.soundClipboard?.connectors || []).length);
}

export function pasteSoundSelection(state, targetSlotId = state.activeSlotId, offset = {x: 40, y: 40}) {
  if (!canPasteSoundSelection(state)) {
    return {nodes: 0, connectors: 0};
  }
  const numericSlotId = Number(targetSlotId || state.activeSlotId || 1);
  ensureSoundProjectSummary(state, numericSlotId);
  const idMap = new Map();
  const keyMap = new Map();
  const nextNodes = [];
  for (const sourceNode of state.soundClipboard.nodes || []) {
    const nodeId = nextNodeIdForSlot(state, numericSlotId);
    const node = {
      ...sourceNode,
      node_id: nodeId,
      slot_id: numericSlotId,
      node_key: `${numericSlotId}:${nodeId}`,
      x: Number(sourceNode.x ?? sourceNode.Node_X ?? 0) + Number(offset.x || 0),
      y: Number(sourceNode.y ?? sourceNode.Node_Y ?? 0) + Number(offset.y || 0)
    };
    idMap.set(Number(sourceNode.node_id || 0), nodeId);
    keyMap.set(sourceNode.node_key, node.node_key);
    state.projectSummary.nodes.push(node);
    nextNodes.push(node);
  }
  let pastedConnectorCount = 0;
  const nextConnectorIds = [];
  const connectorIdMap = new Map();
  for (const sourceConnector of state.soundClipboard.connectors || []) {
    const sourceNodeId = idMap.get(Number(sourceConnector.source_node_id || 0));
    const targetNodeId = idMap.get(Number(sourceConnector.target_node_id || 0));
    if (sourceNodeId === undefined || targetNodeId === undefined) {
      continue;
    }
    const connectorId = nextConnectorId(state);
    const connector = {
      ...sourceConnector,
      connector_id: connectorId,
      slot_id: numericSlotId,
      source_node_id: sourceNodeId,
      target_node_id: targetNodeId,
      source_node_key: keyMap.get(sourceConnector.source_node_key) || `${numericSlotId}:${sourceNodeId}`,
      target_node_key: keyMap.get(sourceConnector.target_node_key) || `${numericSlotId}:${targetNodeId}`
    };
    connectorIdMap.set(Number(sourceConnector.connector_id || 0), connectorId);
    state.projectSummary.connectors.push(connector);
    nextConnectorIds.push(Number(connector.connector_id));
    pastedConnectorCount += 1;
  }
  state.projectSummary.judgments ||= [];
  for (const sourceJudgment of state.soundClipboard.judgments || []) {
    const connectorId = connectorIdMap.get(Number(sourceJudgment.connector_id || 0));
    if (!connectorId) {
      continue;
    }
    state.projectSummary.judgments.push({
      ...sourceJudgment,
      judgment_id: nextJudgmentId(state),
      connector_id: connectorId
    });
  }
  state.projectSummary.actions ||= [];
  for (const sourceAction of state.soundClipboard.actions || []) {
    const connectorId = connectorIdMap.get(Number(sourceAction.connector_id || 0));
    if (!connectorId) {
      continue;
    }
    state.projectSummary.actions.push({
      ...sourceAction,
      action_id: nextActionId(state),
      connector_id: connectorId
    });
  }
  setSoundSelection(state, nextNodes.map((node) => node.node_key), nextConnectorIds);
  refreshSoundProjectViewModel(state);
  markSoundEditorChanged(state);
  return {nodes: nextNodes.length, connectors: pastedConnectorCount};
}

export function deleteSoundSelection(state) {
  const selectedNodeKeys = effectiveSelectedNodeKeys(state);
  const selectedConnectorIds = effectiveSelectedConnectorIds(state);
  if (!selectedNodeKeys.size && !selectedConnectorIds.size) {
    return {nodes: 0, connectors: 0};
  }
  const selectedNodeIds = new Set((state.projectSummary?.nodes || [])
    .filter((node) => selectedNodeKeys.has(node.node_key))
    .map((node) => Number(node.node_id || 0)));
  const beforeNodes = (state.projectSummary?.nodes || []).length;
  const beforeConnectors = (state.projectSummary?.connectors || []).length;
  const deletedConnectorIds = new Set();
  state.projectSummary.nodes = (state.projectSummary?.nodes || [])
    .filter((node) => !selectedNodeKeys.has(node.node_key));
  state.projectSummary.connectors = (state.projectSummary?.connectors || [])
    .filter((connector) => {
      if (selectedConnectorIds.has(Number(connector.connector_id || 0))) {
        deletedConnectorIds.add(Number(connector.connector_id || 0));
        return false;
      }
      const deleteByNode = selectedNodeIds.has(Number(connector.source_node_id || 0))
        || selectedNodeIds.has(Number(connector.target_node_id || 0));
      if (deleteByNode) {
        deletedConnectorIds.add(Number(connector.connector_id || 0));
      }
      return !deleteByNode;
    });
  state.projectSummary.judgments = (state.projectSummary?.judgments || [])
    .filter((judgment) => !deletedConnectorIds.has(Number(judgment.connector_id || 0)));
  state.projectSummary.actions = (state.projectSummary?.actions || [])
    .filter((action) => !deletedConnectorIds.has(Number(action.connector_id || 0)));
  setSoundSelection(state, [], []);
  refreshSoundProjectViewModel(state);
  markSoundEditorChanged(state);
  return {
    nodes: beforeNodes - state.projectSummary.nodes.length,
    connectors: beforeConnectors - state.projectSummary.connectors.length
  };
}

export function saveSoundFileToLibrary(state, fileId, category) {
  const file = soundFileById(state, fileId);
  const normalizedCategory = String(category || "custom").trim() || "custom";
  if (!file) {
    return null;
  }
  const saved = {
    ...file,
    sound_id: `saved-sound-${Date.now()}-${Number(file.file_id || 0)}`,
    label: file.file_name || `音效 ${file.file_id}`,
    category: normalizedCategory,
    description: `从当前工程保存的音效 #${Number(file.file_id || 0)}`,
    audio_available: Boolean(file.content_base64),
    asset_source: "saved_project_sound",
    fileId: 0,
    fileName: file.file_name || `sound-${file.file_id}.wav`,
    contentBase64: file.content_base64 || "",
    contentEncoding: file.content_encoding || "",
    previewFormat: file.preview_format || null,
    pcmBytes: Number(file.pcm_bytes || 0)
  };
  state.savedSoundLibrary ||= [];
  state.savedSoundLibrary.push(saved);
  return saved;
}

export function defaultSlotLibraryCategories() {
  return [
    {category: "power_unit", label: "动力单元"},
    {category: "horn", label: "鸣笛"},
    {category: "mechanical_unit", label: "机械单元"},
    {category: "running_sound", label: "行驶音效"},
    {category: "radio_control", label: "联控音效"},
    {category: "announcement", label: "广播音效"},
  ];
}

export function saveActiveSlotToLibrary(state, category) {
  const slotId = Number(state.activeSlotId || 0);
  const slot = state.selectedSlots.find((entry) => Number(entry.slotId) === slotId)
    || selectedSlotForLibrary(state, slotId);
  if (!slotId || !slot) {
    return null;
  }
  const soundFileIds = soundFileIdsForSlot(state, slotId);
  const connectors = (state.projectSummary?.connectors || [])
    .filter((connector) => Number(connector.slot_id) === slotId)
    .map((connector) => ({...connector}));
  const connectorIds = new Set(connectors.map((connector) => Number(connector.connector_id || 0)));
  const entry = {
    slot_library_id: `slot-template-${Date.now()}-${slotId}`,
    category: String(category || "power_unit"),
    label: slot.slotName || slot.slot_name || `Slot ${slotId}`,
    source_slot_id: slotId,
    nodes: (state.projectSummary?.nodes || []).filter((node) => Number(node.slot_id) === slotId).map((node) => ({...node})),
    connectors,
    judgments: (state.projectSummary?.judgments || [])
      .filter((judgment) => connectorIds.has(Number(judgment.connector_id || 0)))
      .map((judgment) => ({...judgment})),
    actions: (state.projectSummary?.actions || [])
      .filter((action) => connectorIds.has(Number(action.connector_id || 0)))
      .map((action) => ({...action})),
    legacy_user_type: slot.legacyUserType ?? slot.legacy_user_type ?? null,
    legacy_user_volume: slot.legacyUserVolume ?? slot.legacy_user_volume ?? null,
    legacy_user_files: legacyUserFilesForSlot(summarySlotById(state, slotId) || slot),
    sound_file_ids: Array.from(soundFileIds),
    sound_files: projectSoundFiles(state)
      .filter((file) => soundFileIds.has(soundFileId(file.file_id)))
      .map((file) => ({...file}))
  };
  state.slotLibrary ||= {categories: defaultSlotLibraryCategories(), slots: []};
  state.slotLibrary.categories ||= defaultSlotLibraryCategories();
  state.slotLibrary.slots ||= [];
  state.slotLibrary.slots.push(entry);
  return entry;
}

export function filterSlotLibrary(state) {
  const category = String(state.slotLibraryFilter?.category || "").trim();
  const query = String(state.slotLibraryFilter?.query || "").trim().toLowerCase();
  return (state.slotLibrary?.slots || []).filter((entry) => {
    if (category && entry.category !== category) {
      return false;
    }
    if (!query) {
      return true;
    }
    return [
      entry.label,
      entry.category,
      entry.source_slot_id
    ].join(" ").toLowerCase().includes(query);
  });
}

export function applySlotLibraryEntry(state, entryId, targetSlotId = state.activeSlotId) {
  const entry = (state.slotLibrary?.slots || []).find((slot) => slot.slot_library_id === entryId);
  const numericSlotId = Number(targetSlotId || state.activeSlotId || 0);
  if (!entry || !numericSlotId) {
    return false;
  }
  clearSoundSlot(state, numericSlotId);
  ensureSoundProjectSummary(state, numericSlotId);
  const fileIdMap = restoreSlotLibrarySoundFiles(state, entry.sound_files || []);
  const nodeIdMap = new Map();
  const connectorIdMap = new Map();
  for (const sourceNode of entry.nodes || []) {
    const nodeId = nextNodeIdForSlot(state, numericSlotId);
    nodeIdMap.set(Number(sourceNode.node_id || 0), nodeId);
    state.projectSummary.nodes.push({
      ...sourceNode,
      slot_id: numericSlotId,
      node_id: nodeId,
      file_id: fileIdMap.get(soundFileId(sourceNode.file_id)) ?? sourceNode.file_id,
      node_key: `${numericSlotId}:${nodeId}`
    });
  }
  for (const sourceConnector of entry.connectors || []) {
    const sourceNodeId = nodeIdMap.get(Number(sourceConnector.source_node_id || 0));
    const targetNodeId = nodeIdMap.get(Number(sourceConnector.target_node_id || 0));
    if (sourceNodeId === undefined || targetNodeId === undefined) {
      continue;
    }
    const connectorId = nextConnectorId(state);
    connectorIdMap.set(Number(sourceConnector.connector_id || 0), connectorId);
    state.projectSummary.connectors.push({
      ...sourceConnector,
      connector_id: connectorId,
      slot_id: numericSlotId,
      source_node_id: sourceNodeId,
      target_node_id: targetNodeId,
      source_node_key: `${numericSlotId}:${sourceNodeId}`,
      target_node_key: `${numericSlotId}:${targetNodeId}`
    });
  }
  state.projectSummary.judgments ||= [];
  for (const sourceJudgment of entry.judgments || []) {
    const connectorId = connectorIdMap.get(Number(sourceJudgment.connector_id || 0));
    if (!connectorId) {
      continue;
    }
    state.projectSummary.judgments.push({
      ...sourceJudgment,
      judgment_id: nextJudgmentId(state),
      connector_id: connectorId
    });
  }
  state.projectSummary.actions ||= [];
  for (const sourceAction of entry.actions || []) {
    const connectorId = connectorIdMap.get(Number(sourceAction.connector_id || 0));
    if (!connectorId) {
      continue;
    }
    state.projectSummary.actions.push({
      ...sourceAction,
      action_id: nextActionId(state),
      connector_id: connectorId
    });
  }
  syncSelectedSlotSoundFromNode(state, numericSlotId, firstPlayableNodeForSlot(state, numericSlotId));
  const selectedSlot = state.selectedSlots.find((slot) => Number(slot.slotId) === numericSlotId);
  if (selectedSlot) {
    selectedSlot.slotName = entry.label || selectedSlot.slotName;
    selectedSlot.legacyUserType = entry.legacy_user_type ?? selectedSlot.legacyUserType;
    selectedSlot.legacyUserVolume = entry.legacy_user_volume ?? selectedSlot.legacyUserVolume;
    selectedSlot.legacyUserFiles = legacyUserFilesForSlot(entry);
  }
  const summarySlot = summarySlotById(state, numericSlotId);
  if (summarySlot) {
    summarySlot.slot_name = entry.label || summarySlot.slot_name;
    summarySlot.is_use = Boolean((entry.nodes || []).length);
    if (entry.legacy_user_type !== null && entry.legacy_user_type !== undefined) {
      summarySlot.legacy_user_type = entry.legacy_user_type;
      summarySlot.legacy_user_volume = entry.legacy_user_volume;
      summarySlot.legacy_user_files = legacyUserFilesForSlot(entry);
      summarySlot.legacy_file_ids = summarySlot.legacy_user_files.filter((fileId) => fileId !== null);
      summarySlot.is_use = Boolean(summarySlot.is_use || summarySlot.legacy_user_type || summarySlot.legacy_file_ids.length);
    }
  }
  refreshSoundProjectViewModel(state);
  markSoundEditorChanged(state);
  return true;
}

function restoreSlotLibrarySoundFiles(state, soundFiles) {
  const fileIdMap = new Map();
  const existingFiles = projectSoundFiles(state);
  for (const sourceFile of soundFiles || []) {
    const sourceFileId = soundFileId(sourceFile.file_id);
    if (sourceFileId === null) {
      continue;
    }
    const existing = existingFiles.find((file) => {
      return soundFileId(file.file_id) === sourceFileId
        || (file.file_name && file.file_name === sourceFile.file_name && file.content_base64 === sourceFile.content_base64);
    });
    if (existing) {
      fileIdMap.set(sourceFileId, soundFileId(existing.file_id) ?? sourceFileId);
      continue;
    }
    const nextFileId = nextSoundFileId(state);
    const restoredFile = {
      ...sourceFile,
      file_id: nextFileId,
      fileId: nextFileId
    };
    state.projectSummary.sound_files.push(restoredFile);
    existingFiles.push(normalizeProjectSoundFile(restoredFile, "dxsd"));
    fileIdMap.set(sourceFileId, nextFileId);
  }
  return fileIdMap;
}

export function setNodeSoundFile(state, nodeKey, fileId, options = {}) {
  const node = (state.projectSummary?.nodes || []).find((entry) => entry.node_key === nodeKey);
  if (!node) {
    return;
  }
  node.file_id = soundFileId(fileId) ?? 0;
  if (options.selectNode !== false) {
    state.selectedNodeKey = nodeKey;
  }
  state.projectViewModel = createSoundProjectViewModel(state.projectSummary);
  syncSelectedSlotSoundFromNode(state, Number(node.slot_id || 0), node);
  markSoundEditorChanged(state);
}

export function addSoundNode(state, slotId) {
  const numericSlotId = Number(slotId || state.activeSlotId || 1);
  ensureSoundProjectSummary(state, numericSlotId);
  const nodes = state.projectSummary.nodes.filter((node) => Number(node.slot_id) === numericSlotId);
  const nodeId = nextNodeIdForSlot(state, numericSlotId);
  const node = {
    node_key: `${numericSlotId}:${nodeId}`,
    node_id: nodeId,
    slot_id: numericSlotId,
    node_type: 1,
    file_id: defaultFileIdForNewNode(state, numericSlotId, nodeId, nodes.length),
    node_config: 0,
    repeat_amount: 1,
    sound_volume: 255,
    x: 80 + nodes.length * 160,
    y: 120 + (nodes.length % 3) * 56,
    width: 112,
    height: 64,
    node_name: nodeId === 0 ? "入口" : `节点 ${nodeId}`,
    start_address: 0
  };
  state.projectSummary.nodes.push(node);
  state.selectedNodeKey = node.node_key;
  state.selectedConnectorId = 0;
  refreshSoundProjectViewModel(state);
  markSoundEditorChanged(state);
  return node;
}

export function updateSoundNodeField(state, nodeKey, fieldName, value) {
  const node = (state.projectSummary?.nodes || []).find((entry) => entry.node_key === nodeKey);
  if (!node) {
    return;
  }
  const mapping = {
    nodeName: ["node_name", String(value || "")],
    nodeType: ["node_type", boundedNumber(value, 0, 999)],
    fileId: ["file_id", boundedNumber(value, 0, 9999)],
    nodeConfig: ["node_config", boundedNumber(value, 0, 999999)],
    repeatAmount: ["repeat_amount", boundedNumber(value, 0, 999)],
    soundVolume: ["sound_volume", boundedNumber(value, 0, 255)],
    x: ["x", boundedFloat(value, 20, 5000)],
    y: ["y", boundedFloat(value, 20, 5000)],
    width: ["width", boundedNumber(value, 80, 500)],
    height: ["height", boundedNumber(value, 56, 300)]
  };
  const entry = mapping[fieldName];
  if (!entry) {
    return;
  }
  const [targetField, nextValue] = entry;
  if (node[targetField] === nextValue) {
    return;
  }
  node[targetField] = nextValue;
  refreshSoundProjectViewModel(state);
  syncSelectedSlotSoundFromNode(state, Number(node.slot_id || 0), node);
  markSoundEditorChanged(state);
}

export function resizeSoundNode(state, nodeKey, width, height) {
  const node = (state.projectSummary?.nodes || []).find((entry) => entry.node_key === nodeKey);
  if (!node) {
    return;
  }
  const nextWidth = boundedNumber(width, 80, 500);
  const nextHeight = boundedNumber(height, 56, 300);
  if (Number(node.width ?? 96) === nextWidth && Number(node.height ?? 64) === nextHeight) {
    return;
  }
  node.width = nextWidth;
  node.height = nextHeight;
  refreshSoundProjectViewModel(state);
  markSoundEditorChanged(state);
}

export function moveSoundNode(state, nodeKey, x, y) {
  const node = (state.projectSummary?.nodes || []).find((entry) => entry.node_key === nodeKey);
  if (!node) {
    return;
  }
  const nextX = boundedNumber(x, 20, 5000);
  const nextY = boundedNumber(y, 20, 5000);
  if (Number(node.x || 0) === nextX && Number(node.y || 0) === nextY) {
    return;
  }
  node.x = nextX;
  node.y = nextY;
  refreshSoundProjectViewModel(state);
  markSoundEditorChanged(state);
}

export function addSoundConnector(state, slotId, sourceNodeKey = "", targetNodeKey = "") {
  const numericSlotId = Number(slotId || state.activeSlotId || 1);
  ensureSoundProjectSummary(state, numericSlotId);
  while (state.projectSummary.nodes.filter((node) => Number(node.slot_id) === numericSlotId).length < 2) {
    addSoundNode(state, numericSlotId);
  }
  const nodes = state.projectSummary.nodes.filter((node) => Number(node.slot_id) === numericSlotId);
  const source = nodes.find((node) => node.node_key === sourceNodeKey) || nodes[0];
  const target = nodes.find((node) => node.node_key === targetNodeKey && node.node_key !== source.node_key)
    || nodes.find((node) => node.node_key !== source.node_key);
  if (!source || !target) {
    return null;
  }
  const connector = {
    connector_id: nextConnectorId(state),
    connector_type: 0,
    slot_id: numericSlotId,
    source_node_id: Number(source.node_id || 0),
    source_node_key: source.node_key,
    source_port_index: 1,
    target_node_id: Number(target.node_id || 0),
    target_node_key: target.node_key,
    start_address: 0,
    judgment_count: 0,
    action_count: 0
  };
  state.projectSummary.connectors.push(connector);
  state.selectedConnectorId = connector.connector_id;
  state.selectedNodeKey = "";
  refreshSoundProjectViewModel(state);
  markSoundEditorChanged(state);
  return connector;
}

export function updateSoundConnectorField(state, connectorId, fieldName, value) {
  const connector = (state.projectSummary?.connectors || []).find((entry) => Number(entry.connector_id) === Number(connectorId));
  if (!connector) {
    return;
  }
  const nodes = (state.projectSummary?.nodes || []).filter((node) => Number(node.slot_id) === Number(connector.slot_id));
  if (fieldName === "sourceNodeKey" || fieldName === "targetNodeKey") {
    const node = nodes.find((entry) => entry.node_key === value);
    if (!node) {
      return;
    }
    if (fieldName === "sourceNodeKey") {
      connector.source_node_key = node.node_key;
      connector.source_node_id = Number(node.node_id || 0);
    } else {
      connector.target_node_key = node.node_key;
      connector.target_node_id = Number(node.node_id || 0);
    }
  } else if (fieldName === "sourcePortIndex") {
    connector.source_port_index = boundedNumber(value, 0, 999);
  } else if (fieldName === "connectorType") {
    connector.connector_type = boundedNumber(value, 0, 999);
  } else {
    return;
  }
  refreshSoundProjectViewModel(state);
  markSoundEditorChanged(state);
}

export function addSoundConnectorJudgment(state, connectorId) {
  ensureSoundProjectSummaryBase(state);
  const connector = (state.projectSummary.connectors || []).find((entry) => Number(entry.connector_id) === Number(connectorId));
  if (!connector) {
    return null;
  }
  const judgment = {
    judgment_id: nextJudgmentId(state),
    connector_id: Number(connector.connector_id || 0),
    register_type: 255,
    operation_type: 0,
    parameter_value: 0
  };
  state.projectSummary.judgments.push(judgment);
  refreshSoundProjectViewModel(state);
  markSoundEditorChanged(state);
  return judgment;
}

export function updateSoundConnectorJudgmentField(state, connectorId, judgmentId, fieldName, value) {
  const judgment = (state.projectSummary?.judgments || [])
    .find((entry) => Number(entry.connector_id) === Number(connectorId)
      && Number(entry.judgment_id) === Number(judgmentId));
  if (!judgment) {
    return;
  }
  const mapping = {
    registerType: ["register_type", boundedNumber(value, 0, 255)],
    operationType: ["operation_type", boundedNumber(value, 0, 255)],
    parameterValue: ["parameter_value", boundedNumber(value, 0, 65535)]
  };
  const entry = mapping[fieldName];
  if (!entry) {
    return;
  }
  const [targetField, nextValue] = entry;
  if (judgment[targetField] === nextValue) {
    return;
  }
  judgment[targetField] = nextValue;
  refreshSoundProjectViewModel(state);
  markSoundEditorChanged(state);
}

export function deleteSoundConnectorJudgment(state, connectorId, judgmentId) {
  if (!state.projectSummary?.judgments?.length) {
    return false;
  }
  const beforeCount = state.projectSummary.judgments.length;
  state.projectSummary.judgments = state.projectSummary.judgments.filter((entry) => {
    return Number(entry.connector_id) !== Number(connectorId) || Number(entry.judgment_id) !== Number(judgmentId);
  });
  const deleted = beforeCount !== state.projectSummary.judgments.length;
  if (deleted) {
    refreshSoundProjectViewModel(state);
    markSoundEditorChanged(state);
  }
  return deleted;
}

export function updateSoundConnectorEndpoint(state, connectorId, endpoint, nodeKey) {
  const fieldName = endpoint === "source" ? "sourceNodeKey" : endpoint === "target" ? "targetNodeKey" : "";
  if (!fieldName) {
    return;
  }
  updateSoundConnectorField(state, connectorId, fieldName, nodeKey);
}

export function addCustomSoundFiles(state, sounds) {
  if (!(sounds || []).length) {
    return;
  }
  let nextFileId = nextSoundFileId(state);
  for (const sound of sounds || []) {
    if (!Number(sound.fileId ?? sound.file_id ?? 0)) {
      sound.fileId = nextFileId;
      nextFileId += 1;
    }
    state.customSounds.push(sound);
  }
  markSoundEditorChanged(state);
}

export function applyDxsdSummary(state, summary) {
  state.projectSummary = summary;
  state.projectViewModel = createSoundProjectViewModel(summary);
  state.activeSlotId = state.projectViewModel.slots[0]?.slot_id || 0;
  state.selectedNodeKey = "";
  state.selectedConnectorId = 0;
  state.packageName = summary?.base_info?.sound_name || state.packageName || "新音效工程";
  state.chipId = chipIdForDecoderModule(state.chipProfiles, summary?.base_info?.decoder_module) || state.chipId;
  state.selectedSlots = state.projectViewModel.slots.slice(0, 12).map((slot) => ({
    slotId: slot.slot_id,
    slotName: slot.slot_name,
    functionNumber: functionNumberForViewSlot(slot),
    legacyUserType: legacyUserTypeForSlot(slot),
    legacyUserVolume: legacyUserVolumeForSlot(slot),
    legacyUserFiles: legacyUserFilesForSlot(slot),
    sound: soundForSlot(summary, state.projectViewModel, slot.slot_id)
  }));
  ensureFixedSoundSlotsForChip(state);
  hydrateSelectedSlotSounds(state);
  state.activeSlotId = state.projectViewModel.slots[0]?.slot_id || 0;
  markSoundEditorChanged(state);
}

export function chipIdForDecoderModule(chipProfiles, decoderModule) {
  const moduleText = String(decoderModule || "");
  return (chipProfiles || []).find((profile) => {
    return (profile.supported_decoder_modules || []).some((prefix) => moduleText.startsWith(prefix));
  })?.chip_id || "";
}

export function ensureDefaultSoundEditorSelection(state) {
  if (!state.chipId) {
    state.chipId = state.chipProfiles[0]?.chip_id || "";
  }
  ensureFixedSoundSlotsForChip(state);
  if (!state.activeSlotId && state.projectViewModel.slots[0]) {
    state.activeSlotId = state.projectViewModel.slots[0].slot_id;
  }
}

export function ensureFixedSoundSlotsForChip(state) {
  const fixedSlotCount = fixedSlotCountForState(state);
  if (!fixedSlotCount) {
    if (state.projectSummary) {
      refreshSoundProjectViewModel(state);
    }
    return;
  }
  ensureSoundProjectSummaryBase(state);
  trimSoundProjectToFixedSlots(state, fixedSlotCount);
  for (let slotId = 1; slotId <= fixedSlotCount; slotId += 1) {
    if (!summarySlotById(state, slotId)) {
      state.projectSummary.slots.push(createDefaultSoundSlot(slotId));
    }
    if (!state.selectedSlots.some((slot) => Number(slot.slotId) === slotId)) {
      const summarySlot = summarySlotById(state, slotId);
      const functionNumber = functionNumberForViewSlot(summarySlot);
      state.selectedSlots.push(createDefaultSelectedSoundSlot(slotId, summarySlot, functionNumber));
    }
  }
  state.projectSummary.slots.sort((left, right) => Number(left.slot_id) - Number(right.slot_id));
  state.selectedSlots.sort((left, right) => Number(left.slotId) - Number(right.slotId));
  if (!summarySlotById(state, state.activeSlotId)) {
    state.activeSlotId = 1;
  }
  refreshSoundProjectViewModel(state);
}

export function soundCapacityUsageForState(state) {
  const profile = currentSoundChipProfile(state);
  return soundCapacityUsageForProfile(state, profile);
}

export function soundExportCapacityProblemForState(state) {
  const usage = soundCapacityUsageForState(state);
  if (!usage.overflow) {
    return null;
  }
  return {
    type: "sound_capacity_overflow",
    message: `音效数据已用 ${formatBytes(usage.usedBytes)}，超过当前芯片容量 ${formatBytes(usage.totalBytes)}。请删除未使用或不需要的音效后再导出。`,
    used_bytes: usage.usedBytes,
    total_bytes: usage.totalBytes
  };
}

export function soundChipCompatibilityForState(state, targetChipId) {
  const targetProfile = soundChipProfileById(state, targetChipId);
  const targetFixedSlotCount = fixedSlotCountForProfile(targetProfile);
  const maxCurrentSlotId = maxEditableSlotId(state);
  const slotsToDeleteCount = targetFixedSlotCount && maxCurrentSlotId > targetFixedSlotCount
    ? maxCurrentSlotId - targetFixedSlotCount
    : 0;
  const capacity = soundCapacityUsageForProfile(state, targetProfile);
  const messages = [];
  if (slotsToDeleteCount > 0) {
    messages.push(
      `目标芯片只支持 ${targetFixedSlotCount} 个 Slot，强行转换会删除 Slot ${targetFixedSlotCount + 1}-Slot ${maxCurrentSlotId} 以及这些 Slot 内的节点、连接和功能键映射。`
    );
  }
  if (capacity.overflow) {
    messages.push(
      `当前音效数据已用 ${formatBytes(capacity.usedBytes)}，超过目标芯片容量 ${formatBytes(capacity.totalBytes)}；切换后必须删除音效才能导出。`
    );
  }
  return {
    targetChipId,
    targetFixedSlotCount,
    maxCurrentSlotId,
    slotsToDeleteCount,
    capacityOverflow: capacity.overflow,
    requiresConfirmation: messages.length > 0,
    message: messages.join("\n")
  };
}

export function changeSoundChipSelection(state, targetChipId, confirmFn = null) {
  if (!targetChipId || state.chipId === targetChipId) {
    return true;
  }
  const compatibility = soundChipCompatibilityForState(state, targetChipId);
  if (compatibility.requiresConfirmation) {
    const approved = typeof confirmFn === "function" ? confirmFn(compatibility.message) : true;
    if (!approved) {
      return false;
    }
  }
  state.chipId = targetChipId;
  ensureFixedSoundSlotsForChip(state);
  markSoundEditorChanged(state);
  return true;
}

function soundCapacityUsageForProfile(state, profile) {
  const totalBytes = Number(profile?.storage_bytes || 0);
  const totalBits = Number(profile?.storage_bits || totalBytes * 8 || 0);
  const usedBytes = projectSoundFiles(state).reduce((total, file) => {
    return total + Number(file.pcm_bytes || 0);
  }, 0);
  const usedBits = usedBytes * 8;
  const known = totalBytes > 0;
  return {
    known,
    totalBytes: known ? totalBytes : 0,
    usedBytes,
    remainingBytes: known ? Math.max(0, totalBytes - usedBytes) : 0,
    totalBits: known ? totalBits : 0,
    usedBits,
    remainingBits: known ? Math.max(0, totalBits - usedBits) : 0,
    overflow: known && usedBytes > totalBytes,
  };
}

function slotConnectorIds(state, slotId) {
  return new Set((state.projectSummary?.connectors || [])
    .filter((connector) => Number(connector.slot_id) === Number(slotId))
    .map((connector) => Number(connector.connector_id || 0)));
}

function normalizeRect(rect = {}) {
  const left = Math.min(Number(rect.x1 ?? rect.left ?? 0), Number(rect.x2 ?? rect.right ?? 0));
  const right = Math.max(Number(rect.x1 ?? rect.left ?? 0), Number(rect.x2 ?? rect.right ?? 0));
  const top = Math.min(Number(rect.y1 ?? rect.top ?? 0), Number(rect.y2 ?? rect.bottom ?? 0));
  const bottom = Math.max(Number(rect.y1 ?? rect.top ?? 0), Number(rect.y2 ?? rect.bottom ?? 0));
  return {left, right, top, bottom};
}

function rectIntersectsNode(rect, node) {
  const left = Number(node.x ?? node.Node_X ?? 0);
  const top = Number(node.y ?? node.Node_Y ?? 0);
  const right = left + Number(node.width ?? node.Node_W ?? 96);
  const bottom = top + Number(node.height ?? node.Node_H ?? 64);
  return left <= rect.right && right >= rect.left && top <= rect.bottom && bottom >= rect.top;
}

function effectiveSelectedNodeKeys(state) {
  const keys = new Set(state.selectedNodeKeys || []);
  if (state.selectedNodeKey) {
    keys.add(state.selectedNodeKey);
  }
  return keys;
}

function effectiveSelectedConnectorIds(state) {
  const ids = new Set((state.selectedConnectorIds || []).map(Number).filter(Boolean));
  if (state.selectedConnectorId) {
    ids.add(Number(state.selectedConnectorId));
  }
  return ids;
}

function soundPropertyItemKeys(state) {
  if (!Array.isArray(state.expandedPropertyItemKeys)) {
    state.expandedPropertyItemKeys = [];
  }
  state.expandedPropertyItemKeys = state.expandedPropertyItemKeys
    .map((itemKey) => String(itemKey || ""))
    .filter(Boolean);
  return state.expandedPropertyItemKeys;
}

function soundPropertySectionKeys(state) {
  if (!Array.isArray(state.expandedPropertySectionKeys)) {
    state.expandedPropertySectionKeys = [];
  }
  state.expandedPropertySectionKeys = state.expandedPropertySectionKeys
    .map((sectionKey) => String(sectionKey || ""))
    .filter(Boolean);
  return state.expandedPropertySectionKeys;
}

function selectedSlotForLibrary(state, slotId) {
  const summarySlot = summarySlotById(state, slotId);
  return summarySlot ? {
    slotId,
    slotName: summarySlot.slot_name || `Slot ${slotId}`,
    functionNumber: functionNumberForViewSlot(summarySlot),
    sound: {}
  } : null;
}

function clamp(value, minimum, maximum) {
  if (!Number.isFinite(value)) {
    return minimum;
  }
  return Math.min(maximum, Math.max(minimum, value));
}

export function selectSoundForSlot(state, slotId, sound) {
  const numericSlotId = Number(slotId || state.activeSlotId || 1);
  let slot = state.selectedSlots.find((entry) => Number(entry.slotId) === numericSlotId);
  if (!slot) {
    slot = {
      slotId: numericSlotId,
      slotName: `Slot ${numericSlotId}`,
      functionNumber: functionNumberForViewSlot(summarySlotById(state, numericSlotId) || {}),
      sound: {}
    };
    state.selectedSlots.push(slot);
  }
  const soundFile = ensureSoundFileEntry(state, sound);
  slot.sound = normalizeSelectedSound(soundFile || sound);
  const node = firstPlayableNodeForSlot(state, numericSlotId);
  if (node && soundFile) {
    node.file_id = Number(soundFile.file_id);
    state.projectViewModel = createSoundProjectViewModel(state.projectSummary);
    state.selectedNodeKey = node.node_key || "";
  }
  markSoundEditorChanged(state);
}

export function updateSelectedSlotField(state, slotId, fieldName, value) {
  const numericSlotId = Number(slotId || 0);
  ensureSoundProjectSummary(state, numericSlotId || 1);
  const slot = state.selectedSlots.find((entry) => Number(entry.slotId) === numericSlotId);
  if (!slot) {
    return;
  }
  if (fieldName === "slotName") {
    if (slot.slotName === value) {
      return;
    }
    slot.slotName = value;
    const summarySlot = summarySlotById(state, numericSlotId);
    if (summarySlot) {
      summarySlot.slot_name = value;
    }
  } else if (fieldName === "functionNumber") {
    const nextFunctionNumber = normalizeSlotFunctionNumber(value);
    if (slot.functionNumber === nextFunctionNumber) {
      return;
    }
    slot.functionNumber = nextFunctionNumber;
    upsertFunctionMapping(state, numericSlotId, nextFunctionNumber);
  } else {
    return;
  }
  refreshSoundProjectViewModel(state);
  markSoundEditorChanged(state);
}

export async function readCustomSoundFile(file, chipProfile = null) {
  validateWavFileName(file);
  const bytes = new Uint8Array(await file.arrayBuffer());
  const wavMetadata = parseWavMetadata(bytes);
  validateWavForChipProfile(wavMetadata, chipProfile);
  const contentBase64 = arrayBufferToBase64(bytes);
  return {
    sound_id: `custom-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    label: file.name,
    category: "custom",
    description: "用户上传音频",
    tags: ["自定义"],
    audio_available: true,
    asset_source: "user_upload",
    fileId: 0,
    fileName: file.name,
    contentBase64,
    contentEncoding: "wav",
    previewFormat: {
      sample_rate_hz: wavMetadata.sampleRateHz,
      bits: wavMetadata.bitsPerSample,
      channels: wavMetadata.channels
    },
    pcmBytes: wavMetadata.dataBytes,
    wavMetadata
  };
}

export function currentSoundChipProfile(state) {
  return soundChipProfileById(state, state.chipId);
}

export function soundChipProfileById(state, chipId) {
  return (state.chipProfiles || []).find((profile) => profile.chip_id === chipId) || null;
}

export function parseWavMetadata(bytes) {
  const view = bytes instanceof DataView
    ? bytes
    : new DataView(bytes.buffer || bytes, bytes.byteOffset || 0, bytes.byteLength || undefined);
  if (view.byteLength < 44 || ascii(view, 0, 4) !== "RIFF" || ascii(view, 8, 4) !== "WAVE") {
    throw new Error("音效文件必须是 WAV 格式");
  }
  let offset = 12;
  let fmt = null;
  let dataBytes = 0;
  while (offset + 8 <= view.byteLength) {
    const chunkId = ascii(view, offset, 4);
    const chunkSize = view.getUint32(offset + 4, true);
    const chunkData = offset + 8;
    if (chunkData + chunkSize > view.byteLength) {
      throw new Error("WAV 文件结构不完整");
    }
    if (chunkId === "fmt ") {
      if (chunkSize < 16) {
        throw new Error("WAV fmt chunk 不完整");
      }
      fmt = {
        audioFormat: view.getUint16(chunkData, true),
        channels: view.getUint16(chunkData + 2, true),
        sampleRateHz: view.getUint32(chunkData + 4, true),
        bitsPerSample: view.getUint16(chunkData + 14, true)
      };
    } else if (chunkId === "data") {
      dataBytes = chunkSize;
    }
    offset = chunkData + chunkSize + (chunkSize % 2);
  }
  if (!fmt || !dataBytes) {
    throw new Error("WAV 文件缺少 fmt 或 data chunk");
  }
  if (fmt.audioFormat !== 1) {
    throw new Error("仅支持 PCM WAV 音频");
  }
  return {...fmt, dataBytes};
}

export function validateWavForChipProfile(metadata, chipProfile) {
  const expected = chipProfile?.audio_format;
  if (!expected) {
    return;
  }
  if (Number(metadata.sampleRateHz) !== Number(expected.sample_rate_hz)
      || Number(metadata.bitsPerSample) !== Number(expected.bits)
      || Number(metadata.channels) !== Number(expected.channels)) {
    throw new Error(`WAV 格式必须是 ${expected.sample_rate_hz}Hz / ${expected.bits}bit / ${expected.channels}声道`);
  }
}

export function wireSoundEditorEvents({
  elements,
  state,
  importSoundDxsd,
  buildSoundPackage,
  setStatus,
  formatError,
  renderAll
}) {
  elements.soundImportDxsdButton?.addEventListener("click", () => {
    elements.soundDxsdFileInput?.click();
  });
  elements.soundDxsdFileInput?.addEventListener("change", async () => {
    const file = elements.soundDxsdFileInput.files?.[0];
    if (!file) {
      return;
    }
    try {
      setStatus("正在解析音效工程");
      const summary = await importSoundDxsd(file);
      applyDxsdSummary(state, summary);
      setStatus(`已导入 ${summary.counts?.slots || 0} 个 Slot、${summary.counts?.sound_files || 0} 个音频文件`);
      renderAll();
    } catch (error) {
      setStatus(formatError(error));
    } finally {
      elements.soundDxsdFileInput.value = "";
    }
  });
  elements.soundUploadInput?.addEventListener("change", async () => {
    const files = Array.from(elements.soundUploadInput.files || []);
    if (!files.length) {
      return;
    }
    try {
      const sounds = [];
      for (const file of files) {
        sounds.push(await readCustomSoundFile(file, currentSoundChipProfile(state)));
      }
      addCustomSoundFiles(state, sounds);
      setStatus(`已加入 ${sounds.length} 个自定义音频`);
      renderAll();
    } catch (error) {
      setStatus(formatError(error));
    } finally {
      elements.soundUploadInput.value = "";
    }
  });
  elements.soundReplaceUploadInput?.addEventListener("change", async () => {
    const file = elements.soundReplaceUploadInput.files?.[0];
    if (!file || state.editingSoundFileId === null) {
      return;
    }
    try {
      const sound = await readCustomSoundFile(file, currentSoundChipProfile(state));
      replaceSoundFile(state, state.editingSoundFileId, sound);
      closeSoundFileEditor(state);
      setStatus("已替换音效文件");
      renderAll();
    } catch (error) {
      setStatus(formatError(error));
    } finally {
      elements.soundReplaceUploadInput.value = "";
    }
  });
  elements.soundGeneratePackageButton?.addEventListener("click", async () => {
    try {
      const capacityProblem = soundExportCapacityProblemForState(state);
      if (capacityProblem) {
        state.packageWarnings = [capacityProblem];
        setStatus(capacityProblem.message);
        renderAll();
        return;
      }
      markSoundEditorExportStarted(state);
      const payload = buildSoundPackagePayload({
        chipId: state.chipId,
        packageName: state.packageName,
        selectedSlots: state.selectedSlots,
        state
      });
      const result = await buildSoundPackage(payload);
      state.packageWarnings = result.warnings || [];
      downloadPackage(result);
      markSoundEditorExported(state);
      setStatus(state.packageWarnings.length ? "音效工程已生成，存在警告" : "音效工程已生成");
      renderAll();
    } catch (error) {
      markSoundEditorExportFailed(state);
      setStatus(formatError(error));
    }
  });
  elements.soundChipSelect?.addEventListener("change", () => {
    if (state.chipId === elements.soundChipSelect.value) {
      return;
    }
    const changed = changeSoundChipSelection(state, elements.soundChipSelect.value, (message) => {
      return typeof globalThis.confirm === "function" ? globalThis.confirm(message) : true;
    });
    if (!changed) {
      elements.soundChipSelect.value = state.chipId || "";
      return;
    }
    renderAll();
  });
}

function packageSlotsForState(state, selectedSlots) {
  const selectedBySlotId = new Map((selectedSlots || state.selectedSlots || []).map((slot) => [
    Number(slot.slotId || slot.slot_id || 0),
    slot
  ]));
  const slots = state.projectViewModel.slots.length
    ? state.projectViewModel.slots
    : (selectedSlots || state.selectedSlots || []);
  return slots.map((slot) => {
    const slotId = Number(slot.slot_id || slot.slotId || 0);
    const selected = selectedBySlotId.get(slotId) || {};
    const node = firstPlayableNodeForSlot(state, slotId);
    const legacyFileIds = legacySoundFileIdsForSlot(selected, slot);
    const legacyFileId = legacyFileIds[0] ?? null;
    const projectFile = soundFileById(state, assignedSoundFileId(node?.file_id) ?? legacyFileId);
    const sound = projectFile ? normalizeSelectedSound(projectFile) : normalizeSelectedSound(selected.sound || {});
    const nodes = (state.projectSummary?.nodes || [])
      .filter((entry) => Number(entry.slot_id) === slotId)
      .map(packageNode);
    const connectors = (state.projectSummary?.connectors || [])
      .filter((entry) => Number(entry.slot_id) === slotId)
      .map(packageConnector);
    const connectorIds = new Set(connectors.map((entry) => Number(entry.connector_id || 0)));
    const judgments = (state.projectSummary?.judgments || [])
      .filter((entry) => connectorIds.has(Number(entry.connector_id || 0)))
      .map(packageJudgment);
    const actions = (state.projectSummary?.actions || [])
      .filter((entry) => connectorIds.has(Number(entry.connector_id || 0)))
      .map(packageAction);
    const referencedFileIds = new Set(nodes.map((entry) => assignedSoundFileId(entry.file_id)).filter((fileId) => fileId !== null));
    for (const fileId of legacyFileIds) {
      referencedFileIds.add(fileId);
    }
    const soundFiles = Array.from(referencedFileIds)
      .map((fileId) => soundFileById(state, fileId))
      .filter(Boolean)
      .map(packageSoundFile);
    return {
      slotId,
      slotName: selected.slotName || selected.slot_name || slot.slot_name || slot.slotName || `Slot ${slotId}`,
      functionNumber: normalizeSlotFunctionNumber(selected.functionNumber ?? selected.function_key ?? functionNumberForViewSlot(slot)),
      sound,
      nodes,
      connectors,
      judgments,
      actions,
      soundFiles,
      legacyUserType: selected.legacyUserType ?? slot.legacy_user_type ?? slot.legacyUserType ?? null,
      legacyUserVolume: selected.legacyUserVolume ?? slot.legacy_user_volume ?? slot.legacyUserVolume ?? null,
      legacyUserFiles: legacyUserFilesForSlot(selected, slot)
    };
  });
}

function functionNumberForViewSlot(slot) {
  const functionKey = slot.functionKey || slot.function_key || "";
  if (functionKey === "") {
    return null;
  }
  return normalizeSlotFunctionNumber(String(functionKey).replace(/^F/i, ""));
}

function packageNode(node) {
  return {
    node_id: Number(node.node_id || 0),
    node_name: node.node_name || "",
    node_type: Number(node.node_type || 0),
    file_id: Number(node.file_id || 0),
    node_config: Number(node.node_config || 0),
    repeat_amount: Number(node.repeat_amount || 0),
    sound_volume: Number(node.sound_volume || 0),
    x: Number(node.x ?? node.Node_X ?? 0),
    y: Number(node.y ?? node.Node_Y ?? 0),
    width: Number(node.width ?? node.Node_W ?? 96),
    height: Number(node.height ?? node.Node_H ?? 64),
    start_address: Number(node.start_address || 0)
  };
}

function packageConnector(connector) {
  return {
    connector_id: Number(connector.connector_id || 0),
    connector_type: Number(connector.connector_type || 0),
    source_node_id: Number(connector.source_node_id || 0),
    source_node_key: connector.source_node_key || "",
    source_port_index: Number(connector.source_port_index || 0),
    target_node_id: Number(connector.target_node_id || 0),
    target_node_key: connector.target_node_key || "",
    start_address: Number(connector.start_address || 0)
  };
}

function packageJudgment(judgment) {
  return {
    judgment_id: Number(judgment.judgment_id || 0),
    connector_id: Number(judgment.connector_id || 0),
    register_type: Number(judgment.register_type || 0),
    operation_type: Number(judgment.operation_type || 0),
    parameter_value: Number(judgment.parameter_value || 0)
  };
}

function packageAction(action) {
  return {
    action_id: Number(action.action_id || 0),
    connector_id: Number(action.connector_id || 0),
    register_type: Number(action.register_type || 0),
    operation_config: Number(action.operation_config || 0),
    parameter_value: Number(action.parameter_value || 0)
  };
}

function packageSoundFile(file) {
  return {
    file_id: soundFileId(file.file_id ?? file.fileId) ?? 0,
    file_name: file.file_name || "",
    content_base64: file.content_base64 || "",
    content_encoding: file.content_encoding || "",
    duration_seconds: Number(file.duration_seconds || 0),
    pcm_bytes: Number(file.pcm_bytes || 0)
  };
}

function soundPackageContentBase64(sound) {
  return sound?.contentBase64 || sound?.content_base64 || "";
}

function normalizeProjectSoundFile(file, source) {
  const fileId = soundFileId(file.file_id ?? file.fileId) ?? 0;
  return {
    file_id: fileId,
    file_name: file.file_name || file.fileName || `sound-${fileId}.wav`,
    duration_seconds: Number(file.duration_seconds ?? file.durationSeconds ?? 0),
    pcm_bytes: Number(file.pcm_bytes ?? file.pcmBytes ?? 0),
    has_audio_data: Boolean(file.has_audio_data || file.content_base64 || file.contentBase64),
    content_base64: file.content_base64 || file.contentBase64 || "",
    content_encoding: file.content_encoding || file.contentEncoding || "",
    preview_format: file.preview_format || file.previewFormat || null,
    sound_id: file.sound_id || file.libraryId || "",
    source,
    source_label: file.source_label || source
  };
}

function soundFileById(state, fileId) {
  const numericFileId = soundFileId(fileId);
  if (numericFileId === null) {
    return null;
  }
  return projectSoundFiles(state).find((file) => Number(file.file_id) === numericFileId) || null;
}

function ensureSoundUsageEntry(byId, fileId, sound) {
  if (byId.has(fileId)) {
    return;
  }
  byId.set(fileId, {
    ...normalizeProjectSoundFile({
      file_id: fileId,
      file_name: sound.fileName || sound.file_name || sound.label || `sound-${fileId}.wav`,
      content_base64: sound.contentBase64 || sound.content_base64 || "",
      content_encoding: sound.contentEncoding || sound.content_encoding || "",
      preview_format: sound.previewFormat || sound.preview_format || null,
      sound_id: sound.libraryId || sound.library_id || "",
      has_audio_data: Boolean(sound.contentBase64 || sound.content_base64)
    }, "custom"),
    used_by: []
  });
}

function nextSoundFileId(state) {
  const ids = [
    ...(state.projectSummary?.sound_files || []).map((file) => soundFileId(file.file_id)),
    ...(state.customSounds || []).map((sound) => soundFileId(sound.fileId ?? sound.file_id))
  ].filter((fileId) => fileId !== null);
  return Math.max(0, ...ids) + 1;
}

function ensureSoundFileEntry(state, sound) {
  const existingFileId = soundFileId(sound.file_id ?? sound.fileId);
  if (existingFileId !== null) {
    return soundFileById(state, existingFileId) || normalizeProjectSoundFile({
      ...sound,
      file_id: existingFileId,
      file_name: sound.fileName || sound.file_name || sound.label
    }, "custom");
  }
  const fileId = nextSoundFileId(state);
  const entry = {
    ...sound,
    fileId,
    fileName: sound.fileName || sound.file_name || sound.label || `sound-${fileId}.wav`,
    contentBase64: sound.contentBase64 || sound.content_base64 || "",
    contentEncoding: sound.contentEncoding || sound.content_encoding || "",
    previewFormat: sound.previewFormat || sound.preview_format || null
  };
  state.customSounds.push(entry);
  return normalizeProjectSoundFile({
    file_id: fileId,
    file_name: entry.fileName,
    content_base64: entry.contentBase64,
    content_encoding: entry.contentEncoding,
    preview_format: entry.previewFormat,
    has_audio_data: Boolean(entry.audio_available || entry.contentBase64),
    sound_id: entry.sound_id || entry.libraryId || ""
  }, "custom");
}

function firstPlayableNodeForSlot(state, slotId) {
  const nodes = state.projectSummary?.nodes || [];
  return nodes.find((node) => Number(node.slot_id) === Number(slotId) && Number(node.file_id || 0) > 0)
    || nodes.find((node) => Number(node.slot_id) === Number(slotId) && Number(node.node_id || 0) > 0)
    || null;
}

function fixedSlotCountForState(state) {
  return fixedSlotCountForProfile(currentSoundChipProfile(state));
}

function fixedSlotCountForProfile(profile) {
  const fixedSlotCount = Number(profile?.fixed_slot_count || 0);
  return Number.isInteger(fixedSlotCount) && fixedSlotCount > 0 ? fixedSlotCount : 0;
}

function maxEditableSlotId(state) {
  const slotIds = [
    ...(state.projectSummary?.slots || []).map((slot) => Number(slot.slot_id || 0)),
    ...(state.selectedSlots || []).map((slot) => Number(slot.slotId ?? slot.slot_id ?? 0)),
  ];
  return Math.max(0, ...slotIds);
}

function trimSoundProjectToFixedSlots(state, fixedSlotCount) {
  const withinFixedSlots = (slotId) => Number(slotId || 0) >= 1 && Number(slotId || 0) <= fixedSlotCount;
  state.projectSummary.slots = (state.projectSummary.slots || [])
    .filter((slot) => withinFixedSlots(slot.slot_id));
  state.projectSummary.nodes = (state.projectSummary.nodes || [])
    .filter((node) => withinFixedSlots(node.slot_id));
  state.projectSummary.connectors = (state.projectSummary.connectors || [])
    .filter((connector) => withinFixedSlots(connector.slot_id));
  state.projectSummary.function_mappings = (state.projectSummary.function_mappings || [])
    .filter((mapping) => withinFixedSlots(mapping.slot_id));
  state.selectedSlots = (state.selectedSlots || [])
    .filter((slot) => withinFixedSlots(slot.slotId ?? slot.slot_id));
}

function createDefaultSoundSlot(slotId) {
  return {
    slot_id: slotId,
    slot_priority: slotId,
    slot_start_node: 0,
    is_use: false,
    start_address: 0,
    slot_name: `Slot ${slotId}`
  };
}

function createDefaultSelectedSoundSlot(slotId, summarySlot = null, functionNumber = null) {
  return {
    slotId,
    slotName: summarySlot?.slot_name || `Slot ${slotId}`,
    functionNumber: normalizeSlotFunctionNumber(functionNumber),
    legacyUserType: legacyUserTypeForSlot(summarySlot),
    legacyUserVolume: legacyUserVolumeForSlot(summarySlot),
    legacyUserFiles: legacyUserFilesForSlot(summarySlot),
    sound: {}
  };
}

function ensureSoundProjectSummaryBase(state) {
  if (!state.projectSummary) {
    state.projectSummary = {
      file_name: "",
      base_info: {
        decoder_module: currentSoundChipProfile(state)?.decoder_module || state.chipId || "",
        sound_name: state.packageName || "新音效工程"
      },
      counts: {},
      slots: [],
      nodes: [],
      connectors: [],
      judgments: [],
      actions: [],
      sound_files: [],
      function_mappings: []
    };
  }
  state.projectSummary.slots ||= [];
  state.projectSummary.nodes ||= [];
  state.projectSummary.connectors ||= [];
  state.projectSummary.judgments ||= [];
  state.projectSummary.actions ||= [];
  state.projectSummary.sound_files ||= [];
  state.projectSummary.function_mappings ||= [];
}

function ensureSoundProjectSummary(state, slotId) {
  const numericSlotId = Number(slotId || 1);
  ensureSoundProjectSummaryBase(state);
  if (!summarySlotById(state, numericSlotId)) {
    const selected = state.selectedSlots.find((slot) => Number(slot.slotId) === numericSlotId);
    state.projectSummary.slots.push({
      slot_id: numericSlotId,
      slot_priority: numericSlotId,
      slot_start_node: 0,
      is_use: true,
      start_address: 0,
      slot_name: selected?.slotName || `Slot ${numericSlotId}`
    });
  }
  if (!state.selectedSlots.some((slot) => Number(slot.slotId) === numericSlotId)) {
    const summarySlot = summarySlotById(state, numericSlotId);
    const functionNumber = functionNumberForViewSlot(summarySlot);
    state.selectedSlots.push(createDefaultSelectedSoundSlot(numericSlotId, summarySlot, functionNumber));
  }
  refreshSoundProjectViewModel(state);
}

function summarySlotById(state, slotId) {
  return (state.projectSummary?.slots || []).find((slot) => Number(slot.slot_id) === Number(slotId)) || null;
}

function refreshSoundProjectViewModel(state) {
  if (state.projectSummary) {
    refreshConnectorCounts(state);
    state.projectSummary.counts = {
      ...(state.projectSummary.counts || {}),
      slots: (state.projectSummary.slots || []).length,
      nodes: (state.projectSummary.nodes || []).length,
      connectors: (state.projectSummary.connectors || []).length,
      judgments: (state.projectSummary.judgments || []).length,
      actions: (state.projectSummary.actions || []).length,
      sound_files: (state.projectSummary.sound_files || []).length,
      cv_entries: (state.projectSummary.cv_entries || []).length
    };
  }
  state.projectViewModel = createSoundProjectViewModel(state.projectSummary);
}

function refreshConnectorCounts(state) {
  const judgmentCounts = countByConnectorId(state.projectSummary?.judgments || []);
  const actionCounts = countByConnectorId(state.projectSummary?.actions || []);
  for (const connector of state.projectSummary?.connectors || []) {
    const connectorId = Number(connector.connector_id || 0);
    connector.judgment_count = judgmentCounts.get(connectorId) || 0;
    connector.action_count = actionCounts.get(connectorId) || 0;
  }
}

function countByConnectorId(entries) {
  const counts = new Map();
  for (const entry of entries || []) {
    const connectorId = Number(entry.connector_id || 0);
    counts.set(connectorId, (counts.get(connectorId) || 0) + 1);
  }
  return counts;
}

function upsertFunctionMapping(state, slotId, functionNumber) {
  state.projectSummary.function_mappings ||= [];
  const cvAddress = 170 + Number(slotId || 0);
  const mapping = state.projectSummary.function_mappings.find((entry) => Number(entry.slot_id) === Number(slotId));
  const normalizedFunctionNumber = normalizeSlotFunctionNumber(functionNumber);
  if (normalizedFunctionNumber === null) {
    state.projectSummary.function_mappings = state.projectSummary.function_mappings
      .filter((entry) => Number(entry.slot_id) !== Number(slotId));
    return;
  }
  if (mapping) {
    mapping.cv_address = cvAddress;
    mapping.function_number = normalizedFunctionNumber;
    mapping.function_key = `F${normalizedFunctionNumber}`;
    mapping.is_assigned = true;
  } else {
    state.projectSummary.function_mappings.push({
      cv_address: cvAddress,
      slot_id: Number(slotId || 0),
      function_number: normalizedFunctionNumber,
      function_key: `F${normalizedFunctionNumber}`,
      is_assigned: true,
    });
  }
}

function nextNodeIdForSlot(state, slotId) {
  const ids = (state.projectSummary?.nodes || [])
    .filter((node) => Number(node.slot_id) === Number(slotId))
    .map((node) => Number(node.node_id || 0));
  return Math.max(-1, ...ids) + 1;
}

function nextConnectorId(state) {
  const ids = (state.projectSummary?.connectors || []).map((connector) => Number(connector.connector_id || 0));
  return Math.max(0, ...ids) + 1;
}

function nextJudgmentId(state) {
  const ids = (state.projectSummary?.judgments || []).map((judgment) => Number(judgment.judgment_id || 0));
  return Math.max(0, ...ids) + 1;
}

function nextActionId(state) {
  const ids = (state.projectSummary?.actions || []).map((action) => Number(action.action_id || 0));
  return Math.max(0, ...ids) + 1;
}

function defaultFileIdForNewNode(state, slotId, nodeId, existingNodeCount) {
  if (Number(nodeId || 0) === 0) {
    return 0;
  }
  if (Number(existingNodeCount || 0) > 1) {
    return 0;
  }
  const slot = state.selectedSlots.find((entry) => Number(entry.slotId) === Number(slotId));
  return Number(slot?.sound?.fileId ?? slot?.sound?.file_id ?? 0);
}

function boundedNumber(value, minimum, maximum) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return minimum;
  }
  return Math.min(maximum, Math.max(minimum, Math.round(number)));
}

function boundedFloat(value, minimum, maximum) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return minimum;
  }
  return Math.min(maximum, Math.max(minimum, number));
}

function normalizeSlotFunctionNumber(value) {
  if (value === null || value === undefined || String(value).trim() === "") {
    return null;
  }
  const number = Number(String(value).trim().replace(/^F/i, ""));
  if (!Number.isFinite(number)) {
    return null;
  }
  const rounded = Math.round(number);
  if (rounded < 0) {
    return null;
  }
  return Math.min(68, rounded);
}

function serializedFunctionKey(value) {
  const normalized = normalizeSlotFunctionNumber(value);
  return normalized === null ? null : normalized;
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (!bytes) {
    return "0 B";
  }
  if (bytes >= 1024 * 1024) {
    return `${Math.round(bytes / 1024 / 1024)} MB`;
  }
  if (bytes >= 1024) {
    return `${Math.round(bytes / 1024)} KB`;
  }
  return `${bytes} B`;
}

function syncSelectedSlotSoundFromNode(state, slotId, node) {
  const slot = state.selectedSlots.find((entry) => Number(entry.slotId) === Number(slotId));
  if (!slot) {
    return;
  }
  const file = soundFileById(state, assignedSoundFileId(node?.file_id));
  slot.sound = file ? normalizeSelectedSound(file) : {};
}

function normalizeSelectedSound(sound) {
  if (!hasSelectedSoundPayload(sound)) {
    return {};
  }
  const fileId = soundFileId(sound.fileId ?? sound.file_id) ?? 0;
  return {
    libraryId: sound.sound_id || sound.libraryId || "",
    fileId,
    fileName: sound.fileName || sound.file_name || sound.label || "sound.pcm",
    contentBase64: sound.contentBase64 || sound.content_base64 || "",
    contentEncoding: sound.contentEncoding || sound.content_encoding || "",
    previewFormat: sound.previewFormat || sound.preview_format || null
  };
}

function hasSelectedSoundPayload(sound) {
  if (!sound || typeof sound !== "object") {
    return false;
  }
  return [
    sound.sound_id,
    sound.libraryId,
    sound.library_id,
    sound.fileId,
    sound.file_id,
    sound.fileName,
    sound.file_name,
    sound.label,
    sound.contentBase64,
    sound.content_base64
  ].some((value) => value !== null && value !== undefined && String(value).trim() !== "");
}

function hydrateSelectedSlotSounds(state) {
  for (const slot of state.selectedSlots || []) {
    const summarySlot = summarySlotById(state, slot.slotId);
    if (summarySlot) {
      slot.legacyUserType = legacyUserTypeForSlot(summarySlot);
      slot.legacyUserVolume = legacyUserVolumeForSlot(summarySlot);
      slot.legacyUserFiles = legacyUserFilesForSlot(summarySlot);
    }
    if (selectedSoundFileId(slot.sound) !== null) {
      continue;
    }
    const sound = soundForSlot(state.projectSummary, state.projectViewModel, slot.slotId);
    if (selectedSoundFileId(sound) !== null) {
      slot.sound = sound;
    }
  }
}

function soundForSlot(summary, viewModel, slotId) {
  const legacySlot = (summary?.slots || []).find((entry) => Number(entry.slot_id) === Number(slotId));
  const legacyFileId = firstLegacySoundFileId(legacySlot);
  if (legacyFileId !== null) {
    const legacyFile = viewModel.soundFilesById.get(legacyFileId);
    return normalizeSelectedSound(legacyFile || {file_id: legacyFileId, file_name: ""});
  }
  const node = (viewModel.nodesBySlot.get(Number(slotId)) || []).find((entry) => Number(entry.file_id) > 0);
  if (!node) {
    return {};
  }
  const file = viewModel.soundFilesById.get(Number(node.file_id));
  return file ? normalizeSelectedSound(file) : {};
}

function soundFileId(value) {
  if (value === null || value === undefined || String(value).trim() === "") {
    return null;
  }
  const numericFileId = Number(value);
  return Number.isFinite(numericFileId) ? numericFileId : null;
}

function assignedSoundFileId(value) {
  const fileId = soundFileId(value);
  return fileId === null || fileId === 255 ? null : fileId;
}

function firstLegacySoundFileId(slot) {
  return legacySoundFileIdsForSlot(slot)[0] ?? null;
}

function soundFileIdsForSlot(state, slotId) {
  const numericSlotId = Number(slotId || 0);
  const fileIds = new Set();
  for (const node of state.projectSummary?.nodes || []) {
    if (Number(node.slot_id) !== numericSlotId) {
      continue;
    }
    const fileId = assignedSoundFileId(node.file_id);
    if (fileId !== null) {
      fileIds.add(fileId);
    }
  }
  for (const legacyFileId of legacySoundFileIdsForSlot(summarySlotById(state, numericSlotId))) {
    fileIds.add(legacyFileId);
  }
  const selected = (state.selectedSlots || []).find((slot) => Number(slot.slotId) === numericSlotId);
  const selectedFileId = selectedSoundFileId(selected?.sound);
  if (selectedFileId !== null) {
    fileIds.add(selectedFileId);
  }
  return fileIds;
}

export function updateLegacyDxspSlotField(state, slotId, fieldName, value) {
  const numericSlotId = Number(slotId || state.activeSlotId || 0);
  const selected = (state.selectedSlots || []).find((slot) => Number(slot.slotId) === numericSlotId);
  const summarySlot = summarySlotById(state, numericSlotId);
  if (!selected && !summarySlot) {
    return;
  }
  if (fieldName === "legacyUserType") {
    const nextType = boundedNumber(value, 0, 255);
    const resetFiles = nextType === 0;
    if (selected) {
      selected.legacyUserType = nextType;
      if (resetFiles) {
        selected.legacyUserFiles = [null, null, null];
      }
    }
    if (summarySlot) {
      summarySlot.legacy_user_type = nextType;
      if (resetFiles) {
        summarySlot.legacy_user_files = [null, null, null];
        summarySlot.legacy_file_ids = [];
      }
      summarySlot.is_use = Boolean(nextType || legacySoundFileIdsForSlot(summarySlot).length);
    }
  } else if (fieldName === "legacyUserVolume") {
    const nextVolume = boundedNumber(value, 0, 255);
    if (selected) {
      selected.legacyUserVolume = nextVolume;
    }
    if (summarySlot) {
      summarySlot.legacy_user_volume = nextVolume;
    }
  } else {
    return;
  }
  refreshSoundProjectViewModel(state);
  markSoundEditorChanged(state);
}

export function setLegacyDxspSlotFile(state, slotId, fileIndex, fileId) {
  const numericSlotId = Number(slotId || state.activeSlotId || 0);
  const numericIndex = boundedNumber(fileIndex, 0, 2);
  const selected = (state.selectedSlots || []).find((slot) => Number(slot.slotId) === numericSlotId);
  const summarySlot = summarySlotById(state, numericSlotId);
  if (!selected && !summarySlot) {
    return;
  }
  const nextFileId = assignedSoundFileId(fileId);
  const nextFiles = legacyUserFilesForSlot(summarySlot || selected);
  nextFiles[numericIndex] = nextFileId;
  if (summarySlot) {
    summarySlot.legacy_user_files = nextFiles;
    summarySlot.legacy_file_ids = nextFiles.filter((entry) => entry !== null);
    summarySlot.is_use = Boolean((summarySlot.legacy_file_ids || []).length || legacyUserTypeForSlot(summarySlot));
  }
  if (selected) {
    selected.legacyUserFiles = nextFiles;
    selected.sound = soundForSlot(state.projectSummary, state.projectViewModel, numericSlotId);
  }
  hydrateSelectedSlotSounds(state);
  refreshSoundProjectViewModel(state);
  markSoundEditorChanged(state);
}

function legacySoundFileIdsForSlot(...slots) {
  const fileIds = new Set();
  for (const slot of slots) {
    const explicitUserType = slot?.legacyUserType ?? slot?.legacy_user_type;
    if (explicitUserType !== null && explicitUserType !== undefined && String(explicitUserType).trim() !== "" && boundedNumber(explicitUserType, 0, 255) === 0) {
      continue;
    }
    for (const fileId of legacyUserFilesForSlot(slot)) {
      if (fileId !== null) {
        fileIds.add(fileId);
      }
    }
    for (const value of slot?.legacy_file_ids || []) {
      const fileId = assignedSoundFileId(value);
      if (fileId !== null) {
        fileIds.add(fileId);
      }
    }
  }
  return Array.from(fileIds);
}

function legacyUserFilesForSlot(...slots) {
  for (const slot of slots) {
    const rawFiles = slot?.legacyUserFiles || slot?.legacy_user_files;
    if (Array.isArray(rawFiles)) {
      return normalizeLegacyUserFiles(rawFiles);
    }
  }
  for (const slot of slots) {
    const legacyFileIds = slot?.legacy_file_ids;
    if (Array.isArray(legacyFileIds) && legacyFileIds.length) {
      return normalizeLegacyUserFiles(legacyFileIds);
    }
  }
  return [null, null, null];
}

function normalizeLegacyUserFiles(values) {
  const normalized = [];
  for (const value of (values || []).slice(0, 3)) {
    normalized.push(assignedSoundFileId(value));
  }
  while (normalized.length < 3) {
    normalized.push(null);
  }
  return normalized;
}

function legacyUserTypeForSlot(slot) {
  const value = slot?.legacyUserType ?? slot?.legacy_user_type;
  if (value === null || value === undefined || String(value).trim() === "") {
    return legacySoundFileIdsForSlot(slot).length ? 1 : 0;
  }
  return boundedNumber(value, 0, 255);
}

function legacyUserVolumeForSlot(slot) {
  const value = slot?.legacyUserVolume ?? slot?.legacy_user_volume;
  if (value === null || value === undefined || String(value).trim() === "") {
    return legacyUserTypeForSlot(slot) ? 255 : 0;
  }
  return boundedNumber(value, 0, 255);
}

function selectedSoundFileId(sound) {
  if (!sound || typeof sound !== "object") {
    return null;
  }
  return assignedSoundFileId(sound.fileId ?? sound.file_id);
}

function validateWavFileName(file) {
  const name = String(file?.name || "").toLowerCase();
  if (!name.endsWith(".wav")) {
    throw new Error("只能上传 WAV 音效文件");
  }
}

function arrayBufferToBase64(bytes) {
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary);
}

function base64ToBytes(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function pcmWavBase64(pcmBytes, format = {}) {
  const sampleRate = Math.max(1, Number(format?.sample_rate_hz || format?.sampleRateHz || 44100));
  const channels = Math.max(1, Number(format?.channels || 1));
  const bits = Number(format?.bits || 16) <= 8 ? 8 : 16;
  const sampleWidth = bits <= 8 ? 1 : 2;
  const alignedLength = pcmBytes.length - (pcmBytes.length % sampleWidth);
  const dataBytes = pcmBytes.slice(0, alignedLength);
  const wavBytes = new Uint8Array(44 + dataBytes.length);
  const view = new DataView(wavBytes.buffer);
  writeAscii(wavBytes, 0, "RIFF");
  view.setUint32(4, 36 + dataBytes.length, true);
  writeAscii(wavBytes, 8, "WAVE");
  writeAscii(wavBytes, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, channels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * channels * sampleWidth, true);
  view.setUint16(32, channels * sampleWidth, true);
  view.setUint16(34, bits, true);
  writeAscii(wavBytes, 36, "data");
  view.setUint32(40, dataBytes.length, true);
  wavBytes.set(dataBytes, 44);
  return arrayBufferToBase64(wavBytes);
}

function writeAscii(bytes, offset, text) {
  for (let index = 0; index < text.length; index += 1) {
    bytes[offset + index] = text.charCodeAt(index);
  }
}

function asciiFromBytes(bytes, offset, length) {
  let text = "";
  for (let index = 0; index < length; index += 1) {
    text += String.fromCharCode(bytes[offset + index] || 0);
  }
  return text;
}

function ascii(view, offset, length) {
  let text = "";
  for (let index = 0; index < length; index += 1) {
    text += String.fromCharCode(view.getUint8(offset + index));
  }
  return text;
}

function downloadPackage(result) {
  const binary = atob(result.content_base64 || "");
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  const blob = new Blob([bytes], {type: result.mime_type || "application/xml"});
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = result.file_name || "digsight-sound.dxsd";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
