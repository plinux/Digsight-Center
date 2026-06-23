import {cvNumbersFromSource, sortedUniqueCvNumbers} from "./cv-domain.js";
import {buildCvCsv, buildCvMarkdown, cvExportFileName as buildCvExportFileName} from "./cv-export.js";

export function createCvDomainModel({appState, cvState, formatError, newCvReadSessionId}) {
  function resolveDecoderResetMethod() {
    const manufacturerId = currentDecoderManufacturerId();
    const catalog = appState.cvMetadata?.cv_catalog || {};
    const profileName = manufacturerId === null || manufacturerId === undefined
      ? null
      : catalog.profile_map?.[String(manufacturerId)];
    const profile = profileName ? catalog.vendor_profiles?.[profileName] : null;
    const configuredMethod = profile?.reset_method || null;
    const registry = appState.cvMetadata?.manufacturer_registry?.known_ids || {};
    const unassigned = appState.cvMetadata?.manufacturer_registry?.unassigned_notes || {};
    const manufacturerKey = manufacturerId === null || manufacturerId === undefined ? "" : String(manufacturerId);
    const manufacturerName = cvState.chipInfo?.manufacturer_name
      || cvState.cvList?.manufacturer_name
      || profile?.manufacturer_name
      || profile?.profile_name
      || registry[manufacturerKey]
      || unassigned[manufacturerKey]
      || null;
    if (isValidResetMethod(configuredMethod)) {
      return {
        cv: Number(configuredMethod.cv),
        value: Number(configuredMethod.value),
        label: configuredMethod.label || "恢复出厂设置",
        source: configuredMethod.source || profile?.source || "",
        defaultAddress: Number(configuredMethod.default_address || 3),
        requiresPowerCycle: Boolean(configuredMethod.requires_power_cycle),
        notes: configuredMethod.notes || [],
        configured: true,
        manufacturerId,
        manufacturerName,
        profileName
      };
    }
    return {
      cv: 8,
      value: 8,
      label: "恢复出厂设置",
      source: "",
      defaultAddress: 3,
      requiresPowerCycle: true,
      notes: [],
      configured: false,
      manufacturerId,
      manufacturerName,
      profileName
    };
  }

  function currentDecoderManufacturerId() {
    if (cvState.chipInfo?.manufacturer_id !== null && cvState.chipInfo?.manufacturer_id !== undefined) {
      return Number(cvState.chipInfo.manufacturer_id);
    }
    if (cvState.cvList?.manufacturer_id !== null && cvState.cvList?.manufacturer_id !== undefined) {
      return Number(cvState.cvList.manufacturer_id);
    }
    const cv8Value = Number(cvState.results?.[8]);
    return Number.isInteger(cv8Value) ? cv8Value : null;
  }

  function isValidResetMethod(method) {
    if (!method) {
      return false;
    }
    const cvNumber = Number(method.cv);
    const value = Number(method.value);
    return Number.isInteger(cvNumber)
      && cvNumber >= 1
      && cvNumber <= 1024
      && Number.isInteger(value)
      && value >= 0
      && value <= 255;
  }

  function cvNumbersForReadMode(readMode, manufacturerId) {
    if (readMode === "full") {
      return Array.from({length: 1024}, (_, index) => index + 1);
    }
    const catalog = appState.cvMetadata?.cv_catalog || {};
    const standardNumbers = cvNumbersFromSource(catalog.standard_explicit_numbers || catalog.standard_definitions);
    const cvNumbers = sortedUniqueCvNumbers(standardNumbers);
    if (!cvNumbers.includes(8)) {
      cvNumbers.push(8);
    }
    appendVendorCvNumbers(cvNumbers, manufacturerId, new Set());
    const orderedNumbers = sortedUniqueCvNumbers(cvNumbers);
    return manufacturerId === null || manufacturerId === undefined
      ? [8, ...orderedNumbers.filter((cvNumber) => cvNumber !== 8)]
      : orderedNumbers;
  }

  function appendVendorCvNumbers(cvNumbers, manufacturerId, readNumbers) {
    if (manufacturerId === null || manufacturerId === undefined) {
      return;
    }
    const catalog = appState.cvMetadata?.cv_catalog || {};
    const profileName = catalog.profile_map?.[String(Number(manufacturerId))];
    if (!profileName) {
      return;
    }
    const vendorNumbers = cvNumbersFromSource(
      catalog.vendor_explicit_numbers?.[profileName] || catalog.vendor_profiles?.[profileName]?.cv_definitions
    );
    const existingNumbers = new Set([...cvNumbers, ...readNumbers]);
    for (const cvNumber of sortedUniqueCvNumbers(vendorNumbers)) {
      if (!existingNumbers.has(cvNumber)) {
        cvNumbers.push(cvNumber);
        existingNumbers.add(cvNumber);
      }
    }
  }

  function manufacturerNameForCvList(manufacturerId) {
    if (manufacturerId === null || manufacturerId === undefined || manufacturerId === "") {
      return "未知厂家";
    }
    const catalog = appState.cvMetadata?.cv_catalog || {};
    const registry = appState.cvMetadata?.manufacturer_registry?.known_ids || {};
    const unassigned = appState.cvMetadata?.manufacturer_registry?.unassigned_notes || {};
    const key = String(Number(manufacturerId));
    const profileName = catalog.profile_map?.[key];
    const profile = profileName ? catalog.vendor_profiles?.[profileName] : null;
    return profile?.manufacturer_name
      || registry[key]
      || unassigned[key]
      || `厂家 ID ${Number(manufacturerId)}`;
  }

  function updateCvListManufacturer(manufacturerId) {
    const numericManufacturerId = Number(manufacturerId);
    if (!Number.isInteger(numericManufacturerId)) {
      return;
    }
    cvState.cvList.manufacturer_id = numericManufacturerId;
    cvState.cvList.manufacturer_name = manufacturerNameForCvList(numericManufacturerId);
  }

  function cvMeaningForNumber(cvNumber, manufacturerId) {
    const catalog = appState.cvMetadata?.cv_catalog || {};
    const numericCv = Number(cvNumber);
    const profileName = manufacturerId === null || manufacturerId === undefined
      ? null
      : catalog.profile_map?.[String(Number(manufacturerId))];
    const profile = profileName ? catalog.vendor_profiles?.[profileName] : null;
    return profile?.cv_definitions?.[String(numericCv)]
      || catalog.standard_definitions?.[String(numericCv)]
      || "未知/厂家自定义";
  }

  function cvListRowFromResult(cvNumber, result, manufacturerId) {
    return {
      cv: cvNumber,
      meaning: cvMeaningForNumber(cvNumber, manufacturerId),
      value: Number(result.value),
      ok: true,
      error: "",
      error_detail: ""
    };
  }

  function cvListRowFromError(cvNumber, error, manufacturerId) {
    const formatted = formatError(error);
    const summary = typeof formatted === "object" ? formatted.summary : String(formatted);
    const detail = typeof formatted === "object" ? formatted.detail : String(error?.stack || summary);
    return {
      cv: cvNumber,
      meaning: cvMeaningForNumber(cvNumber, manufacturerId),
      value: null,
      ok: false,
      error: summary,
      error_detail: detail
    };
  }

  function isCvReadListRowError(error) {
    const type = String(error?.payload?.error?.type || "");
    return type.startsWith("cv_read_");
  }

  function cvListProgressText() {
    const totalCount = cvState.cvList?.total_count || cvState.cvList?.read_count || 0;
    return `${cvState.cvList?.read_count || 0}/${totalCount}`;
  }

  function startCvListRead(readMode, cvNumbers, manufacturerId) {
    cvState.cvListReading = true;
    cvState.cvReadCancelling = false;
    cvState.cvReadSessionId = newCvReadSessionId();
    cvState.cvList = {
      manufacturer_id: manufacturerId,
      manufacturer_name: manufacturerNameForCvList(manufacturerId),
      rows: [],
      readAt: new Date().toISOString(),
      read_mode: readMode,
      session_id: cvState.cvReadSessionId,
      ok_count: 0,
      read_count: 0,
      total_count: cvNumbers.length,
      cancelled: false
    };
  }

  function appendCvListRow(row, cvNumbers, readNumbers) {
    let manufacturerId = cvState.cvList?.manufacturer_id ?? null;
    if (row.ok) {
      cvState.results[Number(row.cv)] = Number(row.value);
      if (Number(row.cv) === 8) {
        manufacturerId = Number(row.value);
        updateCvListManufacturer(manufacturerId);
        appendVendorCvNumbers(cvNumbers, manufacturerId, readNumbers);
      }
    }
    cvState.cvList.rows.push(row);
    cvState.cvList.read_count = cvState.cvList.rows.length;
    cvState.cvList.ok_count = cvState.cvList.rows.filter((item) => item.ok).length;
    cvState.cvList.total_count = cvNumbers.length;
    return {manufacturerId, progressText: cvListProgressText()};
  }

  function cvExportFileName(extension) {
    return buildCvExportFileName(cvState.cvList, extension);
  }

  return {
    resolveDecoderResetMethod,
    currentDecoderManufacturerId,
    cvNumbersForReadMode,
    appendVendorCvNumbers,
    cvListRowFromResult,
    cvListRowFromError,
    isCvReadListRowError,
    cvListProgressText,
    startCvListRead,
    appendCvListRow,
    cvExportFileName,
    buildCvMarkdown,
    buildCvCsv
  };
}

export function buildCvPanelHandlers(context) {
  return {
    ...context.programmingVehicleHandlers(),
    ...context.chipHandlers(),
    ...context.readAllHandlers(),
    ...context.exportHandlers(),
    ...context.addressHandlers(),
    ...context.singleCvHandlers()
  };
}
