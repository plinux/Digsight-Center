import assert from "node:assert/strict";
import {importSourceModule} from "./module_import_helpers.mjs";

const controller = await importSourceModule("assets/js/sound-editor-controller.js");

function wavBytes({sampleRate = 44100, bits = 16, channels = 1, data = [0, 0, 1, 0]} = {}) {
  const fmtSize = 16;
  const dataSize = data.length;
  const bytes = new Uint8Array(44 + dataSize);
  const view = new DataView(bytes.buffer);
  const writeAscii = (offset, text) => {
    for (let index = 0; index < text.length; index += 1) {
      bytes[offset + index] = text.charCodeAt(index);
    }
  };
  writeAscii(0, "RIFF");
  view.setUint32(4, 36 + dataSize, true);
  writeAscii(8, "WAVE");
  writeAscii(12, "fmt ");
  view.setUint32(16, fmtSize, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, channels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * channels * bits / 8, true);
  view.setUint16(32, channels * bits / 8, true);
  view.setUint16(34, bits, true);
  writeAscii(36, "data");
  view.setUint32(40, dataSize, true);
  bytes.set(data, 44);
  return bytes;
}

function dataUriBytes(url) {
  return Buffer.from(String(url).split(",", 2)[1] || "", "base64");
}

const state = controller.createSoundEditorState();
assert.equal(state.activeSlotId, 0);
assert.deepEqual(state.customSounds, []);
assert.equal(controller.hasPendingSoundExport(state), false);
assert.equal(state.pendingSoundExport, false);
assert.equal(Object.hasOwn(state, "editRevision"), false);
assert.equal(Object.hasOwn(state, "lastExportedRevision"), false);

state.chipProfiles = [
  {
    chip_id: "digsight_8004",
    label: "动芯 8004",
    storage_bytes: 128 * 1024 * 1024 / 8,
    fixed_slot_count: 64,
    audio_format: {sample_rate_hz: 44100, bits: 16, channels: 1},
  },
  {
    chip_id: "digsight_6003",
    label: "动芯 6003",
    storage_bytes: 64 * 1024 * 1024 / 8,
    fixed_slot_count: 16,
    audio_format: {sample_rate_hz: 44100, bits: 12, channels: 1},
  },
  {
    chip_id: "digsight_5313",
    label: "动芯 5313",
    storage_bytes: 32,
    fixed_slot_count: 28,
    audio_format: {sample_rate_hz: 11025, bits: 8, channels: 1},
  },
];
state.chipId = "digsight_8004";
controller.ensureDefaultSoundEditorSelection(state);
assert.equal(state.projectViewModel.slots.length, 64);
assert.equal(state.activeSlotId, 1);
assert.equal(state.projectSummary.counts.slots, 64);

const sixSeriesState = controller.createSoundEditorState();
sixSeriesState.chipProfiles = state.chipProfiles;
sixSeriesState.chipId = "digsight_6003";
controller.ensureDefaultSoundEditorSelection(sixSeriesState);
assert.equal(sixSeriesState.projectViewModel.slots.length, 16);
assert.equal(sixSeriesState.activeSlotId, 1);
assert.equal(sixSeriesState.projectSummary.counts.slots, 16);

const summary = {
  base_info: {decoder_module: "8004", sound_name: "Digsight"},
  slots: [
    {slot_id: 1, slot_name: "短风笛", is_use: true},
    {slot_id: 2, slot_name: "空压机", is_use: false},
  ],
  nodes: [
    {node_key: "1:0", slot_id: 1, node_id: 0, node_name: "入口", file_id: 0, x: 40, y: 60, width: 80, height: 60},
    {node_key: "1:1", slot_id: 1, node_id: 1, node_name: "播放短风笛", file_id: 6, x: 180, y: 60, width: 80, height: 60},
  ],
  connectors: [
    {connector_id: 7, slot_id: 1, source_node_key: "1:0", target_node_key: "1:1", judgment_count: 1, action_count: 0},
  ],
  sound_files: [
    {
      file_id: 6,
      file_name: "短风笛.wav",
      duration_seconds: 1.25,
      pcm_bytes: 22050,
      content_base64: "DDDD",
      content_encoding: "pcm",
      preview_format: {sample_rate_hz: 44100, bits: 16, channels: 1},
    },
    {file_id: 9, file_name: "长风笛.wav", duration_seconds: 2.5, pcm_bytes: 44100},
  ],
  function_mappings: [
    {slot_id: 1, function_number: 2, function_key: "F2"},
  ],
};

const viewModel = controller.createSoundProjectViewModel(summary);
assert.equal(viewModel.slots.length, 2);
assert.equal(viewModel.slots[0].functionKey, "F2");
assert.equal(viewModel.nodesBySlot.get(1).length, 2);
assert.equal(viewModel.connectorsBySlot.get(1).length, 1);
assert.equal(viewModel.soundFilesById.get(6).file_name, "短风笛.wav");

controller.applyDxsdSummary(state, summary);
assert.equal(state.chipId, "digsight_8004");
assert.equal(state.projectViewModel.slots.length, 64);
assert.equal(state.projectSummary.counts.slots, 64);
assert.equal(
  dataUriBytes(controller.soundPreviewUrl(state.selectedSlots.find((slot) => Number(slot.slotId) === 1).sound)).subarray(0, 4).toString("ascii"),
  "RIFF"
);
const capacityUsage8004 = controller.soundCapacityUsageForState(state);
assert.deepEqual(
  {
    totalBytes: capacityUsage8004.totalBytes,
    usedBytes: capacityUsage8004.usedBytes,
    remainingBytes: capacityUsage8004.remainingBytes,
    totalBits: capacityUsage8004.totalBits,
    usedBits: capacityUsage8004.usedBits,
    remainingBits: capacityUsage8004.remainingBits,
    known: capacityUsage8004.known,
  },
  {
    totalBytes: 128 * 1024 * 1024 / 8,
    usedBytes: 66150,
    remainingBytes: 128 * 1024 * 1024 / 8 - 66150,
    totalBits: 128 * 1024 * 1024,
    usedBits: 66150 * 8,
    remainingBits: 128 * 1024 * 1024 - 66150 * 8,
    known: true,
  }
);
assert.equal(controller.formatBitCount(123456789), "123,456,789");
assert.equal(controller.formatMegabitCount(128 * 1024 * 1024), "128.00Mb");
state.chipId = "digsight_6003";
controller.ensureDefaultSoundEditorSelection(state);
assert.equal(controller.soundCapacityUsageForState(state).totalBytes, 64 * 1024 * 1024 / 8);
assert.equal(state.projectViewModel.slots.length, 16);
state.chipId = "digsight_8004";
controller.ensureDefaultSoundEditorSelection(state);
assert.equal(controller.hasPendingSoundExport(state), true);
controller.markSoundEditorExported(state);
assert.equal(controller.hasPendingSoundExport(state), false);
controller.markSoundEditorExportStarted(state);
assert.equal(controller.hasPendingSoundExport(state), true);
controller.markSoundEditorChanged(state);
controller.markSoundEditorExported(state);
assert.equal(controller.hasPendingSoundExport(state), true);
controller.markSoundEditorExportStarted(state);
controller.markSoundEditorExported(state);
assert.equal(controller.hasPendingSoundExport(state), false);
controller.updateSelectedSlotField(state, 1, "slotName", "短风笛更新");
assert.equal(state.projectSummary.slots[0].slot_name, "短风笛更新");
assert.equal(controller.hasPendingSoundExport(state), true);
controller.updateSelectedSlotField(state, 1, "functionNumber", "99");
assert.equal(
  state.projectSummary.function_mappings.find((entry) => Number(entry.slot_id) === 1).function_number,
  68
);
assert.equal(state.projectViewModel.slots[0].functionKey, "F68");
controller.updateSelectedSlotField(state, 1, "functionNumber", "0");
assert.equal(
  state.projectSummary.function_mappings.find((entry) => Number(entry.slot_id) === 1).function_number,
  0
);
assert.equal(state.projectViewModel.slots[0].functionKey, "F0");
controller.updateSelectedSlotField(state, 1, "functionNumber", "-1");
assert.equal(
  state.projectSummary.function_mappings.find((entry) => Number(entry.slot_id) === 1),
  undefined
);
assert.equal(state.projectViewModel.slots[0].functionKey, "");
controller.updateSelectedSlotField(state, 1, "functionNumber", "");
assert.equal(
  state.projectSummary.function_mappings.find((entry) => Number(entry.slot_id) === 1),
  undefined
);
const slotCompatibility = controller.soundChipCompatibilityForState(state, "digsight_5313");
assert.equal(slotCompatibility.requiresConfirmation, true);
assert.equal(slotCompatibility.slotsToDeleteCount, 36);
assert.equal(slotCompatibility.capacityOverflow, true);
assert.match(slotCompatibility.message, /Slot 29/);
let confirmCalled = false;
assert.equal(controller.changeSoundChipSelection(state, "digsight_5313", () => {
  confirmCalled = true;
  return false;
}), false);
assert.equal(confirmCalled, true);
assert.equal(state.chipId, "digsight_8004");
assert.equal(state.projectViewModel.slots.length, 64);
assert.equal(controller.changeSoundChipSelection(state, "digsight_5313", () => true), true);
assert.equal(state.chipId, "digsight_5313");
assert.equal(state.projectViewModel.slots.length, 28);
assert.equal(controller.soundExportCapacityProblemForState(state)?.type, "sound_capacity_overflow");
assert.equal(controller.changeSoundChipSelection(state, "digsight_8004", () => true), true);
controller.markSoundEditorExported(state);
const addedNode = controller.addSoundNode(state, 1);
assert.equal(addedNode.slot_id, 1);
assert.equal(addedNode.node_id, 2);
assert.equal(addedNode.node_key, "1:2");
assert.equal(state.projectViewModel.nodesBySlot.get(1).length, 3);
assert.equal(controller.hasPendingSoundExport(state), true);
controller.markSoundEditorExported(state);
controller.updateSoundNodeField(state, "1:2", "nodeName", "播放新音效");
controller.updateSoundNodeField(state, "1:2", "soundVolume", "180");
assert.equal(state.projectSummary.nodes.find((node) => node.node_key === "1:2").node_name, "播放新音效");
assert.equal(state.projectSummary.nodes.find((node) => node.node_key === "1:2").sound_volume, 180);
controller.resizeSoundNode(state, "1:2", 168, 96);
assert.deepEqual(
  {
    width: state.projectSummary.nodes.find((node) => node.node_key === "1:2").width,
    height: state.projectSummary.nodes.find((node) => node.node_key === "1:2").height,
  },
  {width: 168, height: 96}
);
controller.moveSoundNode(state, "1:2", 320, 140);
assert.deepEqual(
  {
    x: state.projectSummary.nodes.find((node) => node.node_key === "1:2").x,
    y: state.projectSummary.nodes.find((node) => node.node_key === "1:2").y,
  },
  {x: 320, y: 140}
);
const addedConnector = controller.addSoundConnector(state, 1, "1:1", "1:2");
assert.equal(addedConnector.slot_id, 1);
assert.equal(addedConnector.source_node_key, "1:1");
assert.equal(addedConnector.target_node_key, "1:2");
assert.equal(state.projectViewModel.connectorsBySlot.get(1).length, 2);
controller.updateSoundConnectorField(state, addedConnector.connector_id, "sourceNodeKey", "1:0");
controller.updateSoundConnectorField(state, addedConnector.connector_id, "targetNodeKey", "1:2");
controller.updateSoundConnectorEndpoint(state, addedConnector.connector_id, "source", "1:1");
controller.updateSoundConnectorEndpoint(state, addedConnector.connector_id, "target", "1:2");
assert.equal(
  state.projectSummary.connectors.find((connector) => connector.connector_id === addedConnector.connector_id).source_node_key,
  "1:1"
);
assert.equal(
  state.projectSummary.connectors.find((connector) => connector.connector_id === addedConnector.connector_id).target_node_key,
  "1:2"
);
assert.equal(controller.hasPendingSoundExport(state), true);
const selectedInRect = controller.selectSoundItemsInRect(state, 1, {x1: 170, y1: 50, x2: 520, y2: 220});
assert.deepEqual(selectedInRect.nodeKeys.sort(), ["1:1", "1:2"]);
assert.equal(selectedInRect.connectorIds.includes(addedConnector.connector_id), true);
assert.equal(controller.copySoundSelection(state), selectedInRect.nodeKeys.length + selectedInRect.connectorIds.length);
assert.equal(controller.canPasteSoundSelection(state), true);
const pastedSelection = controller.pasteSoundSelection(state, 1, {x: 40, y: 40});
assert.equal(pastedSelection.nodes, selectedInRect.nodeKeys.length);
assert.equal(pastedSelection.connectors >= 1, true);
assert.equal(state.selectedNodeKeys.length, pastedSelection.nodes);
const deletedSelection = controller.deleteSoundSelection(state);
assert.equal(deletedSelection.nodes, pastedSelection.nodes);
assert.equal(deletedSelection.connectors >= pastedSelection.connectors, true);
controller.setSoundPanelWidth(state, "slots", 480);
controller.setSoundPanelWidth(state, "properties", 180);
assert.equal(state.slotListWidthPx, 480);
assert.equal(state.propertyPanelWidthPx, 180);
const wavMetadata = controller.parseWavMetadata(wavBytes());
assert.deepEqual(wavMetadata, {
  audioFormat: 1,
  channels: 1,
  sampleRateHz: 44100,
  bitsPerSample: 16,
  dataBytes: 4,
});
controller.validateWavForChipProfile(wavMetadata, {audio_format: {sample_rate_hz: 44100, bits: 16, channels: 1}});
const sixSeriesWavMetadata = controller.parseWavMetadata(wavBytes({bits: 12, data: [0, 1]}));
assert.deepEqual(sixSeriesWavMetadata, {
  audioFormat: 1,
  channels: 1,
  sampleRateHz: 44100,
  bitsPerSample: 12,
  dataBytes: 2,
});
controller.validateWavForChipProfile(sixSeriesWavMetadata, {audio_format: {sample_rate_hz: 44100, bits: 12, channels: 1}});
assert.throws(
  () => controller.validateWavForChipProfile(wavMetadata, {audio_format: {sample_rate_hz: 44100, bits: 12, channels: 1}}),
  /44100Hz \/ 12bit/
);
assert.throws(
  () => controller.validateWavForChipProfile(wavMetadata, {audio_format: {sample_rate_hz: 11025, bits: 8, channels: 1}}),
  /WAV 格式必须是 11025Hz/
);
const uploadedSound = await controller.readCustomSoundFile(
  new File([wavBytes()], "ok.wav", {type: "audio/wav"}),
  {audio_format: {sample_rate_hz: 44100, bits: 16, channels: 1}}
);
assert.equal(uploadedSound.fileName, "ok.wav");
assert.equal(uploadedSound.wavMetadata.dataBytes, 4);
await assert.rejects(
  () => controller.readCustomSoundFile(new File([wavBytes()], "bad.mp3", {type: "audio/mpeg"})),
  /WAV/
);
await assert.rejects(
  () => controller.readCustomSoundFile(new File([wavBytes()], "bad.mp3", {type: "audio/wav"})),
  /WAV/
);
controller.setSoundCanvasZoom(state, 3);
assert.equal(state.canvasViewport.zoom, 2.5);
controller.setSoundCanvasZoom(state, 0.1);
assert.equal(state.canvasViewport.zoom, 0.5);
controller.setSoundCanvasZoom(state, 1.4);
controller.panSoundCanvas(state, 20, 12);
assert.deepEqual(state.canvasViewport, {zoom: 1.4, offsetX: 20, offsetY: 12});
controller.panSoundCanvas(state, -50, -50);
assert.deepEqual(state.canvasViewport, {zoom: 1.4, offsetX: 0, offsetY: 0});
controller.resetSoundCanvasViewport(state);
assert.deepEqual(state.canvasViewport, {zoom: 1, offsetX: 0, offsetY: 0});
assert.deepEqual(controller.soundCanvasBoundsForSlot(state, 1), {width: 760, height: 420});
const customWavBase64 = Buffer.from(wavBytes()).toString("base64");
state.customSounds.push({
  sound_id: "custom-horn",
  label: "上传风笛.wav",
  fileName: "上传风笛.wav",
  fileId: 20,
  contentBase64: customWavBase64,
  contentEncoding: "wav",
  audio_available: true,
});

assert.equal(controller.projectSoundFiles(state).length, 3);
assert.deepEqual(controller.soundUsageForProject(state).find((entry) => entry.file_id === 6).used_by, ["Slot 1 / 节点 1"]);
assert.equal(
  controller.soundPreviewUrl(controller.projectSoundFiles(state).find((entry) => Number(entry.file_id) === 20)),
  `data:audio/wav;base64,${customWavBase64}`
);
assert.equal(
  controller.soundPreviewUrl(controller.projectSoundFiles(state).find((entry) => Number(entry.file_id) === 9)),
  ""
);
controller.openSoundFileEditor(state, 9);
assert.equal(state.editingSoundFileId, 9);
controller.closeSoundFileEditor(state);
assert.equal(state.editingSoundFileId, 0);
assert.equal(controller.deleteUnusedSoundFile(state, 9), true);
assert.equal(controller.hasPendingSoundExport(state), true);
controller.markSoundEditorExported(state);
assert.equal(controller.projectSoundFiles(state).some((entry) => Number(entry.file_id) === 9), false);
controller.setNodeSoundFile(state, "1:1", 20);
assert.equal(state.projectSummary.nodes[1].file_id, 20);
assert.equal(controller.hasPendingSoundExport(state), true);
controller.markSoundEditorExported(state);
assert.deepEqual(controller.soundUsageForProject(state).find((entry) => entry.file_id === 20).used_by, ["Slot 1 / 节点 1"]);
assert.equal(controller.deleteUnusedSoundFile(state, 20), false);
assert.equal(controller.hasPendingSoundExport(state), false);
state.projectSummary.sound_files.push(
  {file_id: 30, file_name: "未用 A.wav", duration_seconds: 1, pcm_bytes: 10},
  {file_id: 31, file_name: "未用 B.wav", duration_seconds: 2, pcm_bytes: 20}
);
assert.equal(controller.deleteUnusedSoundFiles(state), 3);
assert.equal(controller.projectSoundFiles(state).some((entry) => Number(entry.file_id) === 6), false);
assert.equal(controller.projectSoundFiles(state).some((entry) => Number(entry.file_id) === 30), false);
const sortedBySizeDesc = controller.sortSoundFiles([
  {file_id: 1, file_name: "A.wav", pcm_bytes: 1},
  {file_id: 2, file_name: "B.wav", pcm_bytes: 3},
], {field: "size_bits", direction: "desc"});
assert.deepEqual(sortedBySizeDesc.map((entry) => entry.file_id), [2, 1]);
controller.replaceSoundFile(state, 20, {
  sound_id: "library-replacement",
  label: "替换风笛.wav",
  fileName: "替换风笛.wav",
  contentBase64: "CCCC",
  audio_available: true,
});
assert.equal(controller.projectSoundFiles(state).find((entry) => Number(entry.file_id) === 20).file_name, "替换风笛.wav");
assert.equal(controller.hasPendingSoundExport(state), true);
controller.markSoundEditorExported(state);
assert.deepEqual(controller.soundUsageForProject(state).find((entry) => entry.file_id === 20).used_by, ["Slot 1 / 节点 1"]);
const savedSound = controller.saveSoundFileToLibrary(state, 20, "horn");
assert.equal(savedSound.category, "horn");
assert.equal(state.savedSoundLibrary.at(-1).fileName, "替换风笛.wav");
const slotTemplate = controller.saveActiveSlotToLibrary(state, "horn");
assert.equal(slotTemplate.category, "horn");
assert.equal(slotTemplate.nodes.length >= 2, true);
assert.equal(controller.filterSlotLibrary(state).some((entry) => entry.slot_library_id === slotTemplate.slot_library_id), true);
assert.equal(controller.applySlotLibraryEntry(state, slotTemplate.slot_library_id, 2), true);
assert.equal(state.projectViewModel.nodesBySlot.get(2).length, slotTemplate.nodes.length);
const appliedSlot = state.selectedSlots.find((entry) => Number(entry.slotId) === 2);
assert.equal(appliedSlot.sound.fileName, "替换风笛.wav");
assert.equal(controller.clearSoundSlot(state, 2), true);
assert.equal(state.projectViewModel.nodesBySlot.get(2)?.length || 0, 0);
assert.equal(state.projectViewModel.connectorsBySlot.get(2)?.length || 0, 0);
assert.equal(state.projectSummary.function_mappings.some((mapping) => Number(mapping.slot_id) === 2), false);

const catalog = {
  sounds: [
    {sound_id: "a", label: "短风笛", category: "horn", tags: ["喇叭"]},
    {sound_id: "b", label: "空压机", category: "traction_engine", tags: ["空气"]},
  ],
};
assert.deepEqual(controller.filterSoundLibrary(catalog, {category: "horn"}).map((entry) => entry.sound_id), ["a"]);
assert.deepEqual(controller.filterSoundLibrary(catalog, {query: "空气"}).map((entry) => entry.sound_id), ["b"]);

const payload = controller.buildSoundPackagePayload({
  chipId: "digsight_8004",
  packageName: "测试包",
  state,
});
assert.equal(payload.chip_id, "digsight_8004");
assert.equal(payload.slots[0].slot_id, 1);
assert.equal(payload.slots[0].function_key, null);
assert.equal(payload.slots[0].sound.file_name, "替换风笛.wav");
assert.equal(payload.slots[0].sound.content_base64, "CCCC");
assert.equal(payload.slots[0].nodes.some((node) => node.node_id === 2 && node.node_name === "播放新音效"), true);
assert.equal(payload.slots[0].nodes.some((node) => node.node_id === 2 && node.width === 168 && node.height === 96), true);
assert.equal(payload.slots[0].connectors.some((connector) => connector.target_node_id === 2), true);
assert.equal(payload.slots[0].sound_files.some((file) => Number(file.file_id) === 20), true);

const fallbackState = controller.createSoundEditorState();
assert.equal(controller.hasPendingSoundExport(fallbackState), false);
fallbackState.customSounds.push({
  sound_id: "custom-bell",
  label: "上传铃声.wav",
  fileName: "上传铃声.wav",
  fileId: 3,
  contentBase64: "BBBB",
  audio_available: true,
});
controller.selectSoundForSlot(fallbackState, 1, fallbackState.customSounds[0]);
assert.equal(controller.hasPendingSoundExport(fallbackState), true);
controller.markSoundEditorExported(fallbackState);
assert.equal(controller.hasPendingSoundExport(fallbackState), false);
controller.updateSelectedSlotField(fallbackState, 1, "slotName", "更新后的 Slot");
assert.equal(controller.hasPendingSoundExport(fallbackState), true);
const fallbackNode = controller.addSoundNode(fallbackState, 1);
assert.equal(fallbackNode.node_key, "1:0");
const fallbackSecondNode = controller.addSoundNode(fallbackState, 1);
assert.equal(fallbackSecondNode.node_key, "1:1");
const fallbackConnector = controller.addSoundConnector(fallbackState, 1, fallbackNode.node_key, fallbackSecondNode.node_key);
assert.equal(fallbackConnector.source_node_key, "1:0");
const fallbackUsage = controller.soundUsageForProject(fallbackState).find((entry) => entry.file_id === 3);
assert.deepEqual(fallbackUsage.used_by, ["Slot 1 / 节点 1"]);
const fallbackPayload = controller.buildSoundPackagePayload({
  chipId: "digsight_8004",
  packageName: "新建包",
  state: fallbackState,
});
assert.equal(fallbackPayload.slots[0].sound.file_name, "上传铃声.wav");
assert.equal(fallbackPayload.slots[0].sound.content_base64, "BBBB");
controller.updateSelectedSlotField(fallbackState, 1, "functionNumber", "0");
const f0Payload = controller.buildSoundPackagePayload({
  chipId: "digsight_8004",
  packageName: "F0 包",
  state: fallbackState,
});
assert.equal(f0Payload.slots[0].function_key, 0);

console.log("sound editor behavior ok");
