import {runCvListRead} from "./cv-read-runner.js";

export function newCvReadSessionId(globalScope = globalThis) {
  if (globalScope.crypto?.randomUUID) {
    return globalScope.crypto.randomUUID();
  }
  return `cv-read-${Date.now()}-${Math.round(Math.random() * 1000000)}`;
}

export function buildCvRuntimeActions({
  appState,
  cvState,
  cvDomain,
  currentProgrammingTarget,
  normalizeProgrammingTarget,
  userVisibleWarnings,
  syncControllerEndpoint,
  readControllerInfo,
  refreshState,
  readChipInfoFromController,
  cvProgrammingRequest,
  readAddress,
  writeAddress,
  writeCv,
  readCv,
  setStatus,
  formatError,
  renderAll,
  showDetailDialog,
  globalScope = globalThis,
  documentRef = document,
  urlApi = URL
}) {
  async function refreshCvSafety(operationName, programmingTarget = currentProgrammingTarget(), options = {}) {
    await syncControllerEndpoint();
    const target = normalizeProgrammingTarget(programmingTarget);
    if (target === "main_track") {
      if (options.force) {
        setStatus(`主轨${operationName}状态未确认，正在重新读取控制器信息`);
        await readControllerInfo();
        await refreshState();
      }
      setStatus(`主轨${operationName}已选择车辆，正在等待后端校验 POM 协议状态`);
      return true;
    }
    const warningMessages = userVisibleWarnings(appState.controllerInfo?.cv_safety_warnings || []);
    if (!appState.controllerInfo?.safe_for_cv || options.force) {
      setStatus(`控制器安全状态未确认，正在重新读取控制器信息：${warningMessages.join("，") || "等待 0x23 状态"}`);
      const result = await readControllerInfo();
      await refreshState();
      if (!result.safe_for_cv) {
        const nextWarningMessages = userVisibleWarnings(result.warnings || []);
        setStatus(`控制器安全状态仍未确认：${nextWarningMessages.join("，") || "CV 安全状态未确认"}`);
      }
      return Boolean(result.safe_for_cv);
    }
    setStatus(`控制器安全状态已确认，正在执行${operationName}`);
    return true;
  }

  async function runCvRequestWithSafetyRetry(operationName, programmingTarget, requestFn) {
    try {
      return await requestFn();
    } catch (error) {
      if (!isRetryableCvSafetyError(error)) {
        throw error;
      }
      const safetyReady = await refreshCvSafety(operationName, programmingTarget, {force: true});
      if (!safetyReady && normalizeProgrammingTarget(programmingTarget) !== "main_track") {
        throw error;
      }
      return await requestFn();
    }
  }

  function isRetryableCvSafetyError(error) {
    const warningSet = new Set(error.payload?.debug?.warnings || []);
    return error.payload?.error?.type === "protocol_not_ready"
      && (
        warningSet.has("programming_track_status_unconfirmed")
        || warningSet.has("programming_track_status_stale")
        || warningSet.has("booster_status_unconfirmed")
        || warningSet.has("booster_status_stale")
      );
  }

  async function runPreparedCvAction(operationName, targetPayload, requestFn) {
    if (!targetPayload) {
      return {completed: false, targetPayload: null, result: null};
    }
    const safetyReady = await refreshCvSafety(operationName, targetPayload.programming_target);
    if (!safetyReady) {
      return {completed: false, targetPayload, result: null};
    }
    const result = await runCvRequestWithSafetyRetry(
      operationName,
      targetPayload.programming_target,
      () => requestFn(targetPayload)
    );
    return {completed: true, targetPayload, result};
  }

  async function runTargetedCvAction(operationName, requestFn) {
    const targetPayload = cvProgrammingRequest(operationName);
    return await runPreparedCvAction(operationName, targetPayload, requestFn);
  }

  async function readChipInfo() {
    cvState.results = {};
    cvState.chipInfo = null;
    try {
      const actionResult = await runTargetedCvAction("芯片信息读取", (targetPayload) => readChipInfoFromController(targetPayload));
      if (!actionResult.completed) {
        return;
      }
      const chipInfo = actionResult.result;
      for (const [cvNumber, result] of Object.entries(chipInfo.cvs || {})) {
        cvState.results[Number(cvNumber)] = result.value;
      }
      cvState.chipInfo = chipInfo;
      setStatus("芯片信息已读取");
    } catch (error) {
      cvState.chipInfo = null;
      setStatus(formatError(error));
    } finally {
      renderAll();
    }
  }

  async function resetDecoder() {
    const resetMethod = cvDomain.resolveDecoderResetMethod();
    const resetCommand = `CV${resetMethod.cv}=${resetMethod.value}`;
    const sourceText = resetMethod.source ? `来源：${resetMethod.source}` : "来源：通用 DCC 复位约定";
    const methodText = resetMethod.configured
      ? `已按 ${resetMethod.profileName} 厂商 CV 表选择复位方法：${resetCommand}。`
      : `未读取到可匹配的厂商 CV 表，将使用通用复位方法：${resetCommand}。`;
    const manufacturerText = formatResetManufacturerText(resetMethod);
    const message = [
      "确认重置编程轨上的当前芯片？",
      manufacturerText,
      methodText,
      sourceText,
      `地址通常会变为 ${resetMethod.defaultAddress || 3}，当前 CV、功能映射、速度曲线和声音/厂家设置可能被恢复。`,
      "少数厂家不使用通用复位值，请先确认该芯片手册。"
    ].join("\n");
    const confirmed = typeof globalScope.confirm === "function" ? globalScope.confirm(message) : false;
    if (!confirmed) {
      return;
    }
    try {
      const targetPayload = cvProgrammingRequest("芯片重置");
      if (!targetPayload) {
        return;
      }
      const actionResult = await runPreparedCvAction(
        "芯片重置",
        targetPayload,
        (targetPayload) => writeCv(resetMethod.cv, resetMethod.value, true, targetPayload)
      );
      if (!actionResult.completed) {
        return;
      }
      cvState.chipInfo = null;
      cvState.results = {};
      cvState.cvList = {
        manufacturer_id: null,
        manufacturer_name: "",
        rows: [],
        readAt: ""
      };
      cvState.address = null;
      setStatus(`芯片重置命令已发送：${resetCommand}；请按芯片手册等待或重新上下电后再读取地址/芯片信息`);
      renderAll();
    } catch (error) {
      setStatus(formatError(error));
      renderAll();
    }
  }

  function buildCvAddressHandlers() {
    return {
      onReadAddress: async () => {
        try {
          const actionResult = await runTargetedCvAction(
            "地址读取",
            (targetPayload) => readAddress(targetPayload.vehicle_id, targetPayload)
          );
          if (!actionResult.completed) {
            return;
          }
          const result = actionResult.result;
          cvState.address = result.address;
          setStatus(`地址：${result.address}`);
          await refreshState();
        } catch (error) {
          setStatus(formatError(error));
        }
      },
      onWriteAddress: async (address) => {
        try {
          const targetPayload = cvProgrammingRequest("地址写入");
          if (!targetPayload) {
            return;
          }
          const confirmed = typeof globalScope.confirm === "function" ? globalScope.confirm(`确认写入车辆地址 ${address}？`) : false;
          if (!confirmed) {
            return;
          }
          const actionResult = await runPreparedCvAction(
            "地址写入",
            targetPayload,
            (targetPayload) => writeAddress(targetPayload.vehicle_id, address, true, targetPayload)
          );
          if (!actionResult.completed) {
            return;
          }
          const result = actionResult.result;
          cvState.address = result.address;
          setStatus(`地址 ${result.address} 已写入`);
          await refreshState();
        } catch (error) {
          setStatus(formatError(error));
        }
      }
    };
  }

  function buildSingleCvHandlers() {
    return {
      onReadCv: async (cvNumber) => {
        cvState.cvNumber = cvNumber;
        try {
          const actionResult = await runTargetedCvAction(
            "CV 读取",
            (targetPayload) => readCv(cvNumber, targetPayload)
          );
          if (!actionResult.completed) {
            return;
          }
          const result = actionResult.result;
          cvState.results[cvNumber] = result.value;
          cvState.value = Number(result.value);
          setStatus(`CV${cvNumber}: ${result.value}`);
          renderAll();
        } catch (error) {
          setStatus(formatError(error));
        }
      },
      onWriteCv: async (cvNumber, value) => {
        cvState.cvNumber = cvNumber;
        cvState.value = value;
        try {
          const targetPayload = cvProgrammingRequest("CV 写入");
          if (!targetPayload) {
            return;
          }
          const confirmed = typeof globalScope.confirm === "function" ? globalScope.confirm(`确认写入 CV${cvNumber}=${value}？`) : false;
          if (!confirmed) {
            return;
          }
          const actionResult = await runPreparedCvAction(
            "CV 写入",
            targetPayload,
            (targetPayload) => writeCv(cvNumber, value, true, targetPayload)
          );
          if (!actionResult.completed) {
            return;
          }
          setStatus(`CV${cvNumber} 写入完成`);
        } catch (error) {
          setStatus(formatError(error));
        }
      }
    };
  }

  function finishCvListRead(operationName) {
    const manufacturer = formatCvListManufacturer(cvState.cvList);
    setStatus(cvState.cvList.cancelled
      ? `CV 读取已中止：${cvDomain.cvListProgressText()}`
      : `${operationName}完成：${cvDomain.cvListProgressText()}，${manufacturer}`);
  }

  async function readKnownCvList() {
    await readCvListWithMode("known");
  }

  async function readFullCvList() {
    const confirmed = typeof globalScope.confirm === "function"
      ? globalScope.confirm("完整扫描会逐个读取 CV1-CV1024，耗时明显更长。确认开始完整扫描？")
      : false;
    if (!confirmed) {
      return;
    }
    await readCvListWithMode("full");
  }

  async function cancelCurrentCvRead() {
    if (!cvState.cvReadSessionId || !cvState.cvListReading) {
      return;
    }
    cvState.cvReadCancelling = true;
    setStatus("正在中止 CV 读取");
    renderAll();
  }

  async function readCvListWithMode(readMode) {
    try {
      const operationName = readMode === "full" ? "完整 CV 扫描" : "已知 CV 读取";
      const targetPayload = cvProgrammingRequest(operationName);
      if (!targetPayload) {
        return;
      }
      const safetyReady = await refreshCvSafety(operationName, targetPayload.programming_target);
      if (!safetyReady) {
        return;
      }
      let manufacturerId = cvDomain.currentDecoderManufacturerId();
      const cvNumbers = cvDomain.cvNumbersForReadMode(readMode, manufacturerId);
      const readNumbers = new Set();
      cvDomain.startCvListRead(readMode, cvNumbers, manufacturerId);
      renderAll();
      const readResult = await runCvListRead({
        cvNumbers,
        shouldCancel: () => cvState.cvReadCancelling,
        readOne: async (cvNumber) => {
          if (readNumbers.has(cvNumber)) {
            return null;
          }
          readNumbers.add(cvNumber);
          try {
            const result = await runCvRequestWithSafetyRetry(
              operationName,
              targetPayload.programming_target,
              () => readCv(cvNumber, targetPayload)
            );
            return cvDomain.cvListRowFromResult(cvNumber, result, manufacturerId);
          } catch (error) {
            if (!cvDomain.isCvReadListRowError(error)) {
              throw error;
            }
            return cvDomain.cvListRowFromError(cvNumber, error, manufacturerId);
          }
        },
        onRow: (row, cvNumber) => {
          const listUpdate = cvDomain.appendCvListRow(row, cvNumbers, readNumbers);
          manufacturerId = listUpdate.manufacturerId;
          const progressText = listUpdate.progressText;
          if (row.ok) {
            setStatus(`${operationName}进行中：${progressText}`);
          } else {
            setStatus({summary: `CV${cvNumber}：${row.error}`, detail: row.error_detail});
          }
          renderAll();
        }
      });
      cvState.cvList.cancelled = readResult.cancelled;
      finishCvListRead(operationName);
    } catch (error) {
      setStatus(formatError(error));
    } finally {
      cvState.cvListReading = false;
      cvState.cvReadSessionId = "";
      cvState.cvReadCancelling = false;
      renderAll();
    }
  }

  function downloadTextFile(fileName, content, mimeType) {
    const blob = new Blob([content], {type: mimeType});
    const url = urlApi.createObjectURL(blob);
    const link = documentRef.createElement("a");
    link.href = url;
    link.download = fileName;
    documentRef.body.append(link);
    link.click();
    link.remove();
    urlApi.revokeObjectURL(url);
  }

  function buildCvReadAllHandlers() {
    return {
      onReadKnownCv: readKnownCvList,
      onReadFullCv: readFullCvList,
      onCancelCvRead: cancelCurrentCvRead,
      onShowCvErrorDetail: showDetailDialog
    };
  }

  function buildCvChipHandlers() {
    return {
      onReadChipInfo: readChipInfo,
      onResetDecoder: resetDecoder
    };
  }

  return {
    refreshCvSafety,
    runCvRequestWithSafetyRetry,
    readChipInfo,
    resetDecoder,
    readKnownCvList,
    readFullCvList,
    cancelCurrentCvRead,
    downloadTextFile,
    buildCvReadAllHandlers,
    buildCvChipHandlers,
    buildCvAddressHandlers,
    buildSingleCvHandlers
  };
}

function formatResetManufacturerText(resetMethod) {
  if (!resetMethod.manufacturerName) {
    return "当前尚未读取芯片厂商信息。";
  }
  const idSuffix = resetMethod.manufacturerId === null ? "" : ` (${resetMethod.manufacturerId})`;
  return `当前芯片厂商：${resetMethod.manufacturerName}${idSuffix}`;
}

function formatCvListManufacturer(cvList) {
  if (cvList.manufacturer_id === null || cvList.manufacturer_id === undefined) {
    return cvList.manufacturer_name;
  }
  return `${cvList.manufacturer_name} (${cvList.manufacturer_id})`;
}
