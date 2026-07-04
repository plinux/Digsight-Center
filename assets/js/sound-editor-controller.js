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
    packageName: "新音效工程",
    chipId: "",
    libraryFilter: {category: "", query: ""},
    packageWarnings: [],
    statusMessage: ""
  };
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
      }
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
    byId.get(fileId).used_by.push(`Slot ${Number(node.slot_id || 0)} / Node ${Number(node.node_id || 0)}`);
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
}

export function addCustomSoundFiles(state, sounds) {
  let nextFileId = nextSoundFileId(state);
  for (const sound of sounds || []) {
    if (!Number(sound.fileId ?? sound.file_id ?? 0)) {
      sound.fileId = nextFileId;
      nextFileId += 1;
    }
    state.customSounds.push(sound);
  }
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

export function selectSoundForSlot(state, slotId, sound) {
  const numericSlotId = Number(slotId || state.activeSlotId || 1);
  let slot = state.selectedSlots.find((entry) => Number(entry.slotId) === numericSlotId);
  if (!slot) {
    slot = {
      slotId: numericSlotId,
      slotName: `Sound slot ${numericSlotId}`,
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
}

export function updateSelectedSlotField(state, slotId, fieldName, value) {
  const slot = state.selectedSlots.find((entry) => Number(entry.slotId) === Number(slotId));
  if (!slot) {
    return;
  }
  if (fieldName === "slotName") {
    slot.slotName = value;
  } else if (fieldName === "functionNumber") {
    slot.functionNumber = Number(value || 0);
  }
}

export async function readCustomSoundFile(file) {
  const contentBase64 = await fileToBase64(file);
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
    contentBase64
  };
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
      setStatus(`已导入 ${summary.counts?.slots || 0} 个 slot、${summary.counts?.sound_files || 0} 个音频文件`);
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
        sounds.push(await readCustomSoundFile(file));
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
  elements.soundGeneratePackageButton?.addEventListener("click", async () => {
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
      setStatus(state.packageWarnings.length ? "音效工程已生成，存在警告" : "音效工程已生成");
      renderAll();
    } catch (error) {
      setStatus(formatError(error));
    }
  });
  elements.soundChipSelect?.addEventListener("change", () => {
    state.chipId = elements.soundChipSelect.value;
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
    return {
      slotId,
      slotName: selected.slotName || selected.slot_name || slot.slot_name || slot.slotName || `Sound slot ${slotId}`,
      functionNumber: Number(selected.functionNumber ?? selected.function_key ?? functionNumberForViewSlot(slot) ?? slotId),
      sound
    };
  });
}

function functionNumberForViewSlot(slot) {
  const functionKey = slot.functionKey || slot.function_key || "";
  return Number(String(functionKey).replace(/^F/i, "")) || 0;
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

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => {
      const value = String(reader.result || "");
      resolve(value.includes(",") ? value.split(",", 2)[1] : value);
    });
    reader.addEventListener("error", () => reject(reader.error || new Error("音频读取失败")));
    reader.readAsDataURL(file);
  });
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
