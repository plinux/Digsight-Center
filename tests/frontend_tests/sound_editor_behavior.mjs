import assert from "node:assert/strict";
import {importSourceModule} from "./module_import_helpers.mjs";

const controller = await importSourceModule("assets/js/sound-editor-controller.js");

const state = controller.createSoundEditorState();
assert.equal(state.activeSlotId, 0);
assert.deepEqual(state.customSounds, []);

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
    {file_id: 6, file_name: "短风笛.wav", duration_seconds: 1.25, pcm_bytes: 22050},
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
state.customSounds.push({
  sound_id: "custom-horn",
  label: "上传风笛.wav",
  fileName: "上传风笛.wav",
  fileId: 20,
  contentBase64: "AAAA",
  audio_available: true,
});

assert.equal(controller.projectSoundFiles(state).length, 3);
assert.deepEqual(controller.soundUsageForProject(state).find((entry) => entry.file_id === 6).used_by, ["Slot 1 / Node 1"]);
controller.setNodeSoundFile(state, "1:1", 20);
assert.equal(state.projectSummary.nodes[1].file_id, 20);
assert.deepEqual(controller.soundUsageForProject(state).find((entry) => entry.file_id === 20).used_by, ["Slot 1 / Node 1"]);

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
assert.equal(payload.slots[0].function_key, 2);
assert.equal(payload.slots[0].sound.file_name, "上传风笛.wav");
assert.equal(payload.slots[0].sound.content_base64, "AAAA");

const fallbackState = controller.createSoundEditorState();
fallbackState.customSounds.push({
  sound_id: "custom-bell",
  label: "上传铃声.wav",
  fileName: "上传铃声.wav",
  fileId: 3,
  contentBase64: "BBBB",
  audio_available: true,
});
controller.selectSoundForSlot(fallbackState, 1, fallbackState.customSounds[0]);
const fallbackUsage = controller.soundUsageForProject(fallbackState).find((entry) => entry.file_id === 3);
assert.deepEqual(fallbackUsage.used_by, ["Slot 1"]);
const fallbackPayload = controller.buildSoundPackagePayload({
  chipId: "digsight_8004",
  packageName: "新建包",
  state: fallbackState,
});
assert.equal(fallbackPayload.slots[0].sound.file_name, "上传铃声.wav");
assert.equal(fallbackPayload.slots[0].sound.content_base64, "BBBB");

console.log("sound editor behavior ok");
