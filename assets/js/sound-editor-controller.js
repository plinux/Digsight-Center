export function createSoundEditorState() {
  return {
    chipProfiles: [],
    libraryCatalog: {categories: [], sounds: []},
    projectSummary: null,
    projectViewModel: createSoundProjectViewModel(null),
    activeSlotId: 0,
    selectedNodeKey: "",
    selectedConnectorId: 0,
    selectedSlots: [],
    customSounds: [],
    canvasViewport: {zoom: 1, offsetX: 0, offsetY: 0},
    editingSoundFileId: 0,
    pendingSoundExport: false,
    isExportingSoundPackage: false,
    changedDuringSoundExport: false,
    packageName: "新音效工程",
    chipId: "",
    libraryFilter: {category: "", query: ""},
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
      function_key: Number(slot.functionNumber ?? slot.function_key ?? 0),
      sound: {
        library_id: slot.sound?.libraryId || slot.sound?.library_id || "",
        file_name: slot.sound?.fileName || slot.sound?.file_name || "",
        content_base64: slot.sound?.contentBase64 || slot.sound?.content_base64 || ""
      },
      nodes: slot.nodes || [],
      connectors: slot.connectors || [],
      sound_files: slot.soundFiles || slot.sound_files || []
    }))
  };
}

export function projectSoundFiles(state) {
  const byId = new Map();
  for (const file of state.projectSummary?.sound_files || []) {
    const fileId = Number(file.file_id || 0);
    if (!fileId) {
      continue;
    }
    byId.set(fileId, normalizeProjectSoundFile(file, "dxsd"));
  }
  for (const sound of state.customSounds || []) {
    const fileId = Number(sound.fileId ?? sound.file_id ?? 0);
    if (!fileId) {
      continue;
    }
    byId.set(fileId, normalizeProjectSoundFile({
      file_id: fileId,
      file_name: sound.fileName || sound.file_name || sound.label || `sound-${fileId}.wav`,
      duration_seconds: sound.durationSeconds ?? sound.duration_seconds ?? 0,
      pcm_bytes: sound.pcmBytes ?? sound.pcm_bytes ?? 0,
      content_base64: sound.contentBase64 || sound.content_base64 || "",
      has_audio_data: Boolean(sound.audio_available || sound.contentBase64 || sound.content_base64),
      sound_id: sound.sound_id || sound.libraryId || "",
      source_label: sound.asset_source || "user_upload"
    }, "custom"));
  }
  return Array.from(byId.values()).sort((left, right) => Number(left.file_id) - Number(right.file_id));
}

export function openSoundFileEditor(state, fileId) {
  state.editingSoundFileId = Number(fileId || 0);
}

export function closeSoundFileEditor(state) {
  state.editingSoundFileId = 0;
}

export function deleteUnusedSoundFile(state, fileId) {
  const numericFileId = Number(fileId || 0);
  if (!numericFileId) {
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
  const numericFileId = Number(fileId || 0);
  if (!numericFileId || !sound) {
    return null;
  }
  const replacement = {
    ...sound,
    fileId: numericFileId,
    fileName: sound.fileName || sound.file_name || sound.label || `sound-${numericFileId}.wav`,
    contentBase64: sound.contentBase64 || sound.content_base64 || ""
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
        content_base64: replacement.contentBase64
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
    const fileId = Number(node.file_id || 0);
    if (!fileId) {
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
    for (const slot of state.selectedSlots || []) {
      const fileId = Number(slot.sound?.fileId ?? slot.sound?.file_id ?? 0);
      if (!fileId) {
        continue;
      }
      ensureSoundUsageEntry(byId, fileId, slot.sound);
      byId.get(fileId).used_by.push(`Slot ${Number(slot.slotId || slot.slot_id || 0)}`);
    }
  }
  return Array.from(byId.values()).sort((left, right) => Number(left.file_id) - Number(right.file_id));
}

export function setNodeSoundFile(state, nodeKey, fileId) {
  const node = (state.projectSummary?.nodes || []).find((entry) => entry.node_key === nodeKey);
  if (!node) {
    return;
  }
  node.file_id = Number(fileId || 0);
  state.selectedNodeKey = nodeKey;
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
    repeatAmount: ["repeat_amount", boundedNumber(value, 0, 9999)],
    soundVolume: ["sound_volume", boundedNumber(value, 0, 255)],
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
    functionNumber: Number(String(slot.functionKey || "").replace(/^F/i, "")) || slot.slot_id,
    sound: soundForSlot(summary, state.projectViewModel, slot.slot_id)
  }));
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
  if (!state.activeSlotId && state.projectViewModel.slots[0]) {
    state.activeSlotId = state.projectViewModel.slots[0].slot_id;
  }
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
      functionNumber: numericSlotId,
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
    const nextFunctionNumber = Number(value || 0);
    if (Number(slot.functionNumber || 0) === nextFunctionNumber) {
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
    wavMetadata
  };
}

export function currentSoundChipProfile(state) {
  return (state.chipProfiles || []).find((profile) => profile.chip_id === state.chipId) || null;
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
      setStatus("正在解析 DXSD 音效工程");
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
    if (!file || !state.editingSoundFileId) {
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
    markSoundEditorExportStarted(state);
    try {
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
    state.chipId = elements.soundChipSelect.value;
    markSoundEditorChanged(state);
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
    const projectFile = soundFileById(state, Number(node?.file_id || 0));
    const sound = projectFile ? normalizeSelectedSound(projectFile) : normalizeSelectedSound(selected.sound || {});
    const nodes = (state.projectSummary?.nodes || [])
      .filter((entry) => Number(entry.slot_id) === slotId)
      .map(packageNode);
    const connectors = (state.projectSummary?.connectors || [])
      .filter((entry) => Number(entry.slot_id) === slotId)
      .map(packageConnector);
    const referencedFileIds = new Set(nodes.map((entry) => Number(entry.file_id || 0)).filter(Boolean));
    const soundFiles = Array.from(referencedFileIds)
      .map((fileId) => soundFileById(state, fileId))
      .filter(Boolean)
      .map(packageSoundFile);
    return {
      slotId,
      slotName: selected.slotName || selected.slot_name || slot.slot_name || slot.slotName || `Slot ${slotId}`,
      functionNumber: Number(selected.functionNumber ?? selected.function_key ?? functionNumberForViewSlot(slot) ?? slotId),
      sound,
      nodes,
      connectors,
      soundFiles
    };
  });
}

function functionNumberForViewSlot(slot) {
  const functionKey = slot.functionKey || slot.function_key || "";
  return Number(String(functionKey).replace(/^F/i, "")) || 0;
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

function packageSoundFile(file) {
  return {
    file_id: Number(file.file_id || 0),
    file_name: file.file_name || "",
    content_base64: file.content_base64 || "",
    duration_seconds: Number(file.duration_seconds || 0),
    pcm_bytes: Number(file.pcm_bytes || 0)
  };
}

function normalizeProjectSoundFile(file, source) {
  const fileId = Number(file.file_id || file.fileId || 0);
  return {
    file_id: fileId,
    file_name: file.file_name || file.fileName || `sound-${fileId}.wav`,
    duration_seconds: Number(file.duration_seconds ?? file.durationSeconds ?? 0),
    pcm_bytes: Number(file.pcm_bytes ?? file.pcmBytes ?? 0),
    has_audio_data: Boolean(file.has_audio_data || file.content_base64 || file.contentBase64),
    content_base64: file.content_base64 || file.contentBase64 || "",
    sound_id: file.sound_id || file.libraryId || "",
    source,
    source_label: file.source_label || source
  };
}

function soundFileById(state, fileId) {
  return projectSoundFiles(state).find((file) => Number(file.file_id) === Number(fileId)) || null;
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
      sound_id: sound.libraryId || sound.library_id || "",
      has_audio_data: Boolean(sound.contentBase64 || sound.content_base64)
    }, "custom"),
    used_by: []
  });
}

function nextSoundFileId(state) {
  const ids = [
    ...(state.projectSummary?.sound_files || []).map((file) => Number(file.file_id || 0)),
    ...(state.customSounds || []).map((sound) => Number(sound.fileId ?? sound.file_id ?? 0))
  ];
  return Math.max(0, ...ids) + 1;
}

function ensureSoundFileEntry(state, sound) {
  const existingFileId = Number(sound.file_id ?? sound.fileId ?? 0);
  if (existingFileId) {
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
    contentBase64: sound.contentBase64 || sound.content_base64 || ""
  };
  state.customSounds.push(entry);
  return normalizeProjectSoundFile({
    file_id: fileId,
    file_name: entry.fileName,
    content_base64: entry.contentBase64,
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

function ensureSoundProjectSummary(state, slotId) {
  const numericSlotId = Number(slotId || 1);
  if (!state.projectSummary) {
    state.projectSummary = {
      file_name: "",
      base_info: {
        decoder_module: state.chipId || "",
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
  state.projectSummary.function_mappings ||= [];
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
    state.selectedSlots.push({
      slotId: numericSlotId,
      slotName: summarySlot?.slot_name || `Slot ${numericSlotId}`,
      functionNumber: Number(String(functionKeyForSlot(state.projectSummary, numericSlotId)).replace(/^F/i, "")) || numericSlotId,
      sound: {}
    });
  }
  refreshSoundProjectViewModel(state);
}

function summarySlotById(state, slotId) {
  return (state.projectSummary?.slots || []).find((slot) => Number(slot.slot_id) === Number(slotId)) || null;
}

function refreshSoundProjectViewModel(state) {
  if (state.projectSummary) {
    state.projectSummary.counts = {
      ...(state.projectSummary.counts || {}),
      slots: (state.projectSummary.slots || []).length,
      nodes: (state.projectSummary.nodes || []).length,
      connectors: (state.projectSummary.connectors || []).length,
      sound_files: (state.projectSummary.sound_files || []).length,
      cv_entries: (state.projectSummary.cv_entries || []).length
    };
  }
  state.projectViewModel = createSoundProjectViewModel(state.projectSummary);
}

function upsertFunctionMapping(state, slotId, functionNumber) {
  state.projectSummary.function_mappings ||= [];
  const cvAddress = 170 + Number(slotId || 0);
  const mapping = state.projectSummary.function_mappings.find((entry) => Number(entry.slot_id) === Number(slotId));
  if (mapping) {
    mapping.cv_address = cvAddress;
    mapping.function_number = Number(functionNumber || 0);
    mapping.function_key = `F${Number(functionNumber || 0)}`;
  } else {
    state.projectSummary.function_mappings.push({
      cv_address: cvAddress,
      slot_id: Number(slotId || 0),
      function_number: Number(functionNumber || 0),
      function_key: `F${Number(functionNumber || 0)}`,
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

function syncSelectedSlotSoundFromNode(state, slotId, node) {
  const slot = state.selectedSlots.find((entry) => Number(entry.slotId) === Number(slotId));
  if (!slot) {
    return;
  }
  const file = soundFileById(state, Number(node?.file_id || 0));
  slot.sound = file ? normalizeSelectedSound(file) : {};
}

function normalizeSelectedSound(sound) {
  return {
    libraryId: sound.sound_id || sound.libraryId || "",
    fileId: Number(sound.fileId ?? sound.file_id ?? 0),
    fileName: sound.fileName || sound.file_name || sound.label || "sound.pcm",
    contentBase64: sound.contentBase64 || sound.content_base64 || ""
  };
}

function soundForSlot(summary, viewModel, slotId) {
  const node = (viewModel.nodesBySlot.get(Number(slotId)) || []).find((entry) => Number(entry.file_id) > 0);
  const file = viewModel.soundFilesById.get(Number(node?.file_id || 0));
  return {
    libraryId: "",
    fileId: Number(file?.file_id || 0),
    fileName: file?.file_name || "",
    contentBase64: ""
  };
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
