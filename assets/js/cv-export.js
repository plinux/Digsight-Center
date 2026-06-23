export function cvExportFileName(cvList, extension) {
  const manufacturer = (cvList.manufacturer_name || "decoder").replace(/[^A-Za-z0-9_-]+/g, "-");
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  return `cv-list-${manufacturer}-${stamp}.${extension}`;
}

export function buildCvMarkdown(cvList) {
  const rows = cvList.rows || [];
  const manufacturer = cvList.manufacturer_id === null || cvList.manufacturer_id === undefined
    ? (cvList.manufacturer_name || "未知厂家")
    : `${cvList.manufacturer_name} (${cvList.manufacturer_id})`;
  const lines = [
    "# CV值列表",
    "",
    `- 生产厂家：${manufacturer}`,
    `- 读取时间：${cvList.readAt || ""}`,
    "",
    "| CV地址 | 含义 | 值 |",
    "| --- | --- | --- |"
  ];
  for (const row of rows) {
    lines.push(`| ${row.cv} | ${escapeMarkdownCell(row.meaning)} | ${row.ok ? row.value : `读取失败：${escapeMarkdownCell(row.error || "")}`} |`);
  }
  return `${lines.join("\n")}\n`;
}

export function buildCvCsv(cvList) {
  const rows = cvList.rows || [];
  const lines = [["CV地址", "含义", "值"].map(csvEscape).join(",")];
  for (const row of rows) {
    lines.push([row.cv, row.meaning, row.ok ? row.value : `读取失败：${row.error || ""}`].map(csvEscape).join(","));
  }
  return `${lines.join("\n")}\n`;
}

export function escapeMarkdownCell(value) {
  return String(value ?? "").replaceAll("|", "\\|").replace(/\r?\n/g, " ");
}

export function csvEscape(value) {
  const text = String(value ?? "");
  if (/[",\r\n]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}
