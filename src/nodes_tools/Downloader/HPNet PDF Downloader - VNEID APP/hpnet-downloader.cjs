const fs = require("node:fs");
const fsp = require("node:fs/promises");
const path = require("node:path");
const crypto = require("node:crypto");

const MAIN_URL = "https://qlvb.hpnet.vn/?action=101";
const LIST_URL = "https://qlvb.hpnet.vn/vpdt/xaphuong/VanbanDiListChuyenvien.aspx";
const DETAIL_URL = "https://qlvb.hpnet.vn/vpdt/xaphuong/Ajax/LoadVanBanDiInfo.aspx";

function fail(message, code = 1) {
  console.error(`[LỖI] ${message}`);
  process.exitCode = code;
}

function cleanJsonText(text) {
  return text.replace(/^\uFEFF/, "");
}

function isHpnetUrl(value) {
  try {
    const host = new URL(String(value)).hostname.toLowerCase();
    return host === "qlvb.hpnet.vn" || host === "qlvb2.hpnet.vn";
  } catch {
    return false;
  }
}

function isHpnetLoginUrl(value) {
  return isHpnetUrl(value) && /\/Login\.aspx(?:[?#]|$)/i.test(String(value));
}

function normalizeTitle(value) {
  return String(value ?? "")
    .normalize("NFC")
    .replace(/<[^>]*>/g, " ")
    .replace(/[–—−]/g, "-")
    .replace(/\s*-\s*/g, " - ")
    .replace(/\s+/g, " ")
    .trim()
    .toLocaleUpperCase("vi-VN");
}

function normalizeCommuneCode(value) {
  const code = String(value ?? "").normalize("NFC").trim();
  if (!/^\d{5}$/.test(code)) {
    throw new Error("Mã xã phải gồm đúng 5 chữ số, ví dụ: 10930.");
  }
  return code;
}

function buildValidPdfNamePattern(communeCode, allowMissingCommuneCode = true) {
  const code = normalizeCommuneCode(communeCode);
  const prefix = allowMissingCommuneCode ? `(?:${code}_)?` : `${code}_`;
  return new RegExp(`^CHUACOGIAY_${prefix}([0-9]+(?:\\.[0-9]+)*)_([0-9]+(?:\\.[0-9]+)*)-TBXN\\.(signed|ldsigned|lsigned)\\.pdf$`, "i");
}

function parseNotificationNumbers(value, { maxRangeSize = 10000 } = {}) {
  const input = String(value ?? "").normalize("NFC").trim();
  if (!input) throw new Error("Vui lòng nhập ít nhất một số thông báo.");
  const numbers = new Set();
  for (const rawPart of input.split(/[,;\r\n]+/)) {
    const part = rawPart.trim();
    if (!part) continue;
    const single = part.match(/^\d+$/);
    if (single) {
      numbers.add(Number(single[0]));
      continue;
    }
    const range = part.match(/^(\d+)\s*[-–—]\s*(\d+)$/);
    if (!range) throw new Error(`Định dạng số thông báo không hợp lệ: ${part}. Ví dụ đúng: 1712, 1715, 1720-1725`);
    const start = Number(range[1]);
    const end = Number(range[2]);
    if (end < start) throw new Error(`Khoảng số thông báo phải tăng dần: ${part}`);
    if (end - start + 1 > maxRangeSize) throw new Error(`Khoảng số thông báo quá lớn: ${part}`);
    for (let number = start; number <= end; number += 1) numbers.add(number);
  }
  if (!numbers.size) throw new Error("Không nhận diện được số thông báo nào.");
  return [...numbers].sort((a, b) => a - b);
}

function extractNotificationNumber(value) {
  const text = String(value ?? "").normalize("NFC").replace(/\s+/g, " ").trim();
  if (!text) return null;
  const patterns = [
    /(?:^|\b)SỐ\s*:?\s*(\d+)(?=\s*(?:\/|[-–—]|$))/iu,
    /^\s*(\d+)(?=\s*(?:\/|[-–—]|$))/u,
  ];
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match) return Number(match[1]);
  }
  return null;
}

function getRecordNotificationNumber(record) {
  const fields = [
    record?.OrderIndex, record?.orderIndex,
    record?.SoVanBan, record?.SoVanban, record?.soVanBan, record?.sovanban,
    record?.SoKyHieu, record?.soKyHieu, record?.KyHieu, record?.kyHieu,
    record?.Name, record?.name,
  ];
  for (const field of fields) {
    const number = extractNotificationNumber(field);
    if (number !== null) return number;
  }
  return null;
}

function parseTextValues(value) {
  const source = Array.isArray(value) ? value : String(value ?? "").split(/[,;\r\n]+/);
  return [...new Set(source.map((item) => String(item ?? "").normalize("NFC").trim()).filter(Boolean))];
}

function normalizeDocumentSymbol(value) {
  return String(value ?? "")
    .normalize("NFC")
    .replace(/<[^>]*>/g, " ")
    .replace(/^\s*SỐ\s*:?\s*/iu, "")
    .replace(/^\s*\d+\s*\/\s*/u, "")
    .replace(/[–—−]/g, "-")
    .replace(/\s*-\s*/g, "-")
    .replace(/\s+/g, "")
    .trim()
    .toLocaleUpperCase("vi-VN");
}

function getRecordDocumentSymbol(record) {
  const fields = [
    "Name", "name", "KyHieu", "kyHieu", "KYHIEU",
    "SoKyHieu", "soKyHieu", "SoKyhieu", "soKyhieu",
    "LoaiVanBan", "loaiVanBan", "LoaiVB", "loaiVB",
  ];
  for (const field of fields) {
    if (!Object.prototype.hasOwnProperty.call(record || {}, field)) continue;
    const raw = String(record[field] ?? "").normalize("NFC").trim();
    const normalized = normalizeDocumentSymbol(raw);
    if (normalized && !/^\d+$/u.test(normalized)) return { raw, normalized, field };
  }
  return { raw: "", normalized: "", field: "" };
}

function datePartsToInfo(year, month, day, raw, field = "") {
  const y = Number(year); const m = Number(month); const d = Number(day);
  const check = new Date(Date.UTC(y, m - 1, d));
  if (!Number.isInteger(y) || y < 1900 || y > 2200 || check.getUTCFullYear() !== y || check.getUTCMonth() + 1 !== m || check.getUTCDate() !== d) return null;
  return { year: y, month: m, day: d, ordinal: y * 10000 + m * 100 + d, iso: `${String(y).padStart(4, "0")}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`, raw, field };
}

function parseDocumentDate(value, field = "") {
  if (value instanceof Date && !Number.isNaN(value.getTime())) return datePartsToInfo(value.getFullYear(), value.getMonth() + 1, value.getDate(), value, field);
  const raw = String(value ?? "").normalize("NFC").trim();
  if (!raw) return null;
  const dotNet = raw.match(/^\/Date\((-?\d+)(?:[+-]\d{4})?\)\/$/u);
  if (dotNet) {
    const date = new Date(Number(dotNet[1]));
    if (!Number.isNaN(date.getTime())) return datePartsToInfo(date.getFullYear(), date.getMonth() + 1, date.getDate(), raw, field);
  }
  let match = raw.match(/^(\d{1,2})[\/-](\d{1,2})[\/-](\d{4})(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?$/u);
  if (match) return datePartsToInfo(match[3], match[2], match[1], raw, field);
  match = raw.match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T].*)?$/u);
  if (match) return datePartsToInfo(match[1], match[2], match[3], raw, field);
  return null;
}

function getRecordDocumentDate(record) {
  const fields = [
    "NgayVanBan", "NgayVanban", "ngayVanBan", "ngayvanban",
    "NgayBanhanh", "NgayBanHanh", "Ngaybanhanh", "ngayBanHanh", "ngaybanhanh",
    "NgayKy", "ngayKy", "ngayky", "NgayPhatHanh", "ngayPhatHanh",
    "NgayTao", "ngayTao", "CreatedDate", "CreateDate", "NgayGui", "ngayGui",
  ];
  let firstNonBlank = null;
  for (const field of fields) {
    if (!Object.prototype.hasOwnProperty.call(record || {}, field)) continue;
    const raw = record[field];
    if (raw === null || raw === undefined || String(raw).trim() === "") continue;
    if (!firstNonBlank) firstNonBlank = { raw, field };
    const parsed = parseDocumentDate(raw, field);
    if (parsed) return { ...parsed, parseFailed: false };
  }
  return { raw: firstNonBlank?.raw ?? "", field: firstNonBlank?.field ?? "", parseFailed: true };
}

function parseConfigDate(value, label) {
  const parsed = parseDocumentDate(value, label);
  if (!parsed) throw new Error(`${label} không hợp lệ. Hãy dùng ngày dạng dd/MM/yyyy.`);
  return parsed;
}

function buildFilters(config) {
  const hasNewFlags = ["titleFilterEnabled", "notificationFilterEnabled", "symbolFilterEnabled", "dateFilterEnabled"].some((key) => Object.prototype.hasOwnProperty.call(config, key));
  const legacyMode = String(config.downloadMode ?? "titles").toLowerCase();
  const titleEnabled = hasNewFlags ? Boolean(config.titleFilterEnabled) : legacyMode !== "numbers";
  const notificationEnabled = hasNewFlags ? Boolean(config.notificationFilterEnabled) : legacyMode === "numbers";
  const symbolEnabled = hasNewFlags ? Boolean(config.symbolFilterEnabled) : false;
  const dateEnabled = hasNewFlags ? Boolean(config.dateFilterEnabled) : false;
  const titles = parseTextValues(config.allowedTitles).map(normalizeTitle).filter(Boolean);
  if (titleEnabled && !titles.length) throw new Error("Bộ lọc trích yếu đang bật nhưng chưa có nội dung.");
  const numberList = notificationEnabled ? parseNotificationNumbers(config.notificationNumbers) : [];
  const symbols = parseTextValues(config.documentSymbols ?? config.documentSymbol).map(normalizeDocumentSymbol).filter(Boolean);
  if (symbolEnabled && !symbols.length) throw new Error("Bộ lọc ký hiệu VB đang bật nhưng chưa có ký hiệu.");
  const readFilter = String(config.readFilter ?? (config.onlyUnread ? "unread" : "all")).toLowerCase();
  if (!["all", "unread", "read"].includes(readFilter)) throw new Error("Bộ lọc trạng thái chữ đậm không hợp lệ.");
  const dateMode = dateEnabled ? String(config.dateMode ?? "exact").toLowerCase() : "none";
  if (!["none", "exact", "range"].includes(dateMode)) throw new Error("Chế độ lọc ngày không hợp lệ.");
  let startDate = null; let endDate = null;
  if (dateMode === "exact") startDate = endDate = parseConfigDate(config.exactDate, "Ngày chính xác");
  if (dateMode === "range") {
    startDate = parseConfigDate(config.startDate, "Ngày bắt đầu");
    endDate = parseConfigDate(config.endDate, "Ngày kết thúc");
    if (startDate.ordinal > endDate.ordinal) throw new Error("Ngày bắt đầu phải nhỏ hơn hoặc bằng ngày kết thúc.");
  }
  if (![titleEnabled, notificationEnabled, symbolEnabled, dateEnabled].some(Boolean)) throw new Error("Hãy bật ít nhất một bộ lọc: trích yếu, số thông báo, ký hiệu VB hoặc ngày văn bản.");
  return {
    titleEnabled, titles: new Set(titles), notificationEnabled, numberList, numbers: new Set(numberList),
    symbolEnabled, symbols: new Set(symbols), dateEnabled, dateMode, startDate, endDate, readFilter,
  };
}

function buildDocumentRecord(record, pageNumber) {
  const symbol = getRecordDocumentSymbol(record);
  return {
    record, pageNumber,
    documentId: record?.VanbanDiId || record?.vanbandiid || record?.Id || "",
    notificationNumber: getRecordNotificationNumber(record),
    title: String(record?.TrichYeu ?? record?.trichYeu ?? ""),
    normalizedTitle: normalizeTitle(record?.TrichYeu ?? record?.trichYeu ?? ""),
    symbol, date: getRecordDocumentDate(record), isUnread: isUnread(record?.IsNew),
  };
}

function recordFilterReasons(entry, filters) {
  const reasons = [];
  if (!recordPassesReadFilter(entry.record, filters.readFilter)) reasons.push("Không khớp trạng thái đã xem/chưa xem");
  if (filters.titleEnabled && ![...filters.titles].some((query) => entry.normalizedTitle.includes(query))) reasons.push("Trích yếu không chứa nội dung đã chọn");
  if (filters.notificationEnabled && !filters.numbers.has(entry.notificationNumber)) reasons.push("Số thông báo không nằm trong danh sách đã chọn");
  if (filters.symbolEnabled && !filters.symbols.has(entry.symbol.normalized)) reasons.push("Ký hiệu văn bản không khớp");
  if (filters.dateEnabled) {
    if (entry.date.parseFailed) reasons.push("Ngày văn bản trống hoặc không đọc được");
    else if (entry.date.ordinal < filters.startDate.ordinal || entry.date.ordinal > filters.endDate.ordinal) reasons.push("Ngày văn bản ngoài ngày/khoảng ngày đã chọn");
  }
  return reasons;
}

function recordMatchesFilters(entry, filters) {
  return recordFilterReasons(entry, filters).length === 0;
}

function recordKey(record) {
  const id = String(record?.VanbanDiId ?? record?.vanbandiid ?? record?.Id ?? "").trim();
  return id ? `ID:${id}` : `DATA:${JSON.stringify(record)}`;
}

async function scanDocumentPages(fetchPage, { pageSize = 100, onBatch = () => {}, log = () => {} } = {}) {
  let startIndex = 0;
  let pageNumber = 0;
  let total = null;
  const seen = new Set();
  let duplicates = 0;
  // Request one empty page after the last non-empty page, even when the total
  // is absent/stale. A repeated page is an error, never a successful full scan.
  while (true) {
    pageNumber += 1;
    const payload = unwrapPayload(await fetchPage(startIndex, pageSize));
    if (!payload || !Array.isArray(payload.Records)) throw new Error(`Trang ${pageNumber}: phản hồi thiếu danh sách Records; chưa thể xác nhận quét hết.`);
    if (payload.Result && String(payload.Result).toUpperCase() !== "OK") throw new Error(payload.Message || "HPNet trả về lỗi danh sách.");
    const rawTotal = payload.TotalRecordCount;
    const reported = Number(rawTotal);
    if (rawTotal !== null && rawTotal !== undefined && String(rawTotal).trim() !== "" && Number.isSafeInteger(reported) && reported >= 0) {
      if (total !== null && reported !== total) log(`[CẢNH BÁO] Tổng trên HPNet thay đổi từ ${total} thành ${reported}; nên tránh thao tác cập nhật trong lúc quét.`);
      total = total === null ? reported : Math.max(total, reported);
    }
    const batch = payload.Records;
    if (!batch.length) {
      if (total !== null && seen.size < total) throw new Error(`Quét chưa đủ: HPNet báo ${total} văn bản nhưng chỉ đọc được ${seen.size} mã riêng biệt (${duplicates} dòng lặp). Trang ${pageNumber} trả rỗng; hãy quét lại và kiểm tra phạm vi tài khoản.`);
      log(`Đã gặp trang cuối rỗng. Đọc ${startIndex} dòng, ${seen.size} văn bản riêng biệt; tổng HPNet: ${total ?? "không cung cấp"}.`);
      return { rows: startIndex, unique: seen.size, duplicates, total, pages: pageNumber - 1 };
    }
    let added = 0;
    for (const record of batch) {
      if (!record || typeof record !== "object" || Array.isArray(record)) throw new Error(`Trang ${pageNumber} có dòng văn bản sai cấu trúc.`);
      const key = recordKey(record);
      if (seen.has(key)) duplicates += 1;
      else { seen.add(key); added += 1; }
    }
    await onBatch(batch, pageNumber);
    startIndex += batch.length;
    log(`Đã đọc ${startIndex} dòng / tổng HPNet ${total ?? "chưa rõ"}; ${seen.size} văn bản riêng biệt, ${duplicates} dòng lặp (trang ${pageNumber}).`);
    if (!added) throw new Error(`Trang ${pageNumber} chỉ lặp lại văn bản đã đọc. Dừng để tránh đếm trùng; chưa xác nhận quét hết. Hãy quét lại khi danh sách ổn định.`);
  }
}

function classifyEntries(entries, filters) {
  const seen = new Set();
  const matched = [];
  const reasonCounts = new Map();
  let excluded = 0; let duplicates = 0;
  for (const entry of entries) {
    entry.filterReasons = recordFilterReasons(entry, filters);
    const key = recordKey(entry.record);
    entry.duplicate = seen.has(key);
    if (entry.duplicate) { duplicates += 1; continue; }
    seen.add(key);
    if (entry.filterReasons.length) {
      excluded += 1;
      for (const reason of entry.filterReasons) reasonCounts.set(reason, (reasonCounts.get(reason) || 0) + 1);
    } else matched.push(entry);
  }
  return { matched, excluded, duplicates, unique: seen.size, reasonCounts };
}

function auditRows(entries, filters) {
  return [["Trang", "Mã văn bản HPNet", "Số thông báo", "Ký hiệu", "Trích yếu", "Ngày đọc được", "Trường ngày trên HPNet", "Giá trị ngày gốc", "Trạng thái xem", "Kết quả đối soát", "Lý do / kết quả file"],
    ...entries.map((entry) => {
      const reasons = entry.filterReasons ?? recordFilterReasons(entry, filters);
      const outcomes = entry.outcomes || [];
      const status = entry.duplicate ? "DÒNG LẶP" : reasons.length ? "BỊ LỌC" : outcomes.length ? "ĐÃ XỬ LÝ" : "KHỚP BỘ LỌC - CHƯA TẢI";
      return [entry.pageNumber, entry.documentId, entry.notificationNumber ?? "", entry.symbol.raw, entry.title,
        entry.date.iso ?? "", entry.date.field, entry.date.raw, entry.isUnread ? "Chưa xem" : "Đã xem", status,
        entry.duplicate ? "Cùng mã nội bộ đã xuất hiện ở dòng trước; không tính thêm văn bản." : [...reasons, ...outcomes].join(" | ")];
    })];
}

function recordPassesReadFilter(record, readFilter) {
  if (readFilter === "unread") return isUnread(record?.IsNew);
  if (readFilter === "read") return !isUnread(record?.IsNew);
  return true;
}

function unwrapPayload(data) {
  let value = data;
  if (value && Object.prototype.hasOwnProperty.call(value, "d")) value = value.d;
  if (typeof value === "string") value = JSON.parse(value);
  return value;
}

function fileNameFromUrl(url) {
  const withoutQuery = String(url).split(/[?#]/, 1)[0];
  const raw = withoutQuery.slice(withoutQuery.lastIndexOf("/") + 1);
  try { return decodeURIComponent(raw); } catch { return raw; }
}

function absoluteHpnetUrl(value) {
  const url = String(value ?? "").trim();
  if (!url) return "";
  if (url.startsWith("//")) return `https:${url}`;
  if (/^https?:\/\//i.test(url)) return url;
  return new URL(url, "https://qlvb.hpnet.vn/").href;
}

function sha256(buffer) {
  return crypto.createHash("sha256").update(buffer).digest("hex");
}

function buildDuplicateFileName(fileName, index) {
  const safeName = path.basename(String(fileName ?? ""));
  const extension = path.extname(safeName);
  const baseName = path.basename(safeName, extension);
  if (!safeName || !baseName || !Number.isInteger(index) || index < 2) throw new Error("Không thể tạo tên file trùng hợp lệ.");
  return `${baseName}_${index}${extension}`;
}

async function saveNameCollision(outputDir, fileName, buffer) {
  const duplicateDir = path.join(outputDir, "Trùng");
  await fsp.mkdir(duplicateDir, { recursive: true });
  const incomingHash = sha256(buffer);
  for (let index = 2; index <= 999999; index += 1) {
    const duplicateName = buildDuplicateFileName(fileName, index);
    const destination = path.join(duplicateDir, duplicateName);
    if (fs.existsSync(destination)) {
      const existing = await fsp.readFile(destination);
      if (sha256(existing) === incomingHash) return { status: "exists", duplicateName, destination, index };
      continue;
    }
    const tempPath = `${destination}.part`;
    await fsp.writeFile(tempPath, buffer);
    await fsp.rename(tempPath, destination);
    const saved = await fsp.stat(destination);
    if (saved.size <= 0 || path.extname(destination).toLowerCase() !== ".pdf" || fs.existsSync(tempPath)) {
      throw new Error(`${duplicateName} không vượt qua kiểm tra file sau khi tải.`);
    }
    return { status: "saved", duplicateName, destination, index };
  }
  throw new Error(`Có quá nhiều file trùng tên ${path.basename(fileName)} trong thư mục Trùng.`);
}

function timestamp() {
  const d = new Date();
  const two = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${two(d.getMonth() + 1)}${two(d.getDate())}_${two(d.getHours())}${two(d.getMinutes())}${two(d.getSeconds())}`;
}

function csvCell(value) {
  let text = String(value ?? "");
  // Text from HPNet must not execute as an Excel formula when opening the log.
  if (/^[\s\uFEFF]*[=+@-]/u.test(text)) text = `'${text}`;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function isUnread(value) {
  return value === true || value === 1 || /^(true|1)$/i.test(String(value ?? "").trim());
}

async function runSelfTest() {
  const pattern = buildValidPdfNamePattern("10930");
  const accepted = [
    "CHUACOGIAY_10930_114_203-TBXN.signed.pdf",
    "CHUACOGIAY_10930_12.1_45.2-TBXN.ldsigned.pdf",
    "CHUACOGIAY_10930_49_88-TBXN.lsigned.pdf",
  ];
  const rejected = [
    "CHUACOGIAY_10930_114_203-TBXN.pdf",
    "CHUACOGIAY_10931_114_203-TBXN.signed.pdf",
    "DAGIAY_10930_114_203-TBXN.signed.pdf",
    "CHUACOGIAY_10930_114_203-TBXN.signed.docx",
  ];
  if (!accepted.every((name) => pattern.test(name))) throw new Error("Self-test: mẫu tên hợp lệ bị từ chối.");
  if (!rejected.every((name) => !pattern.test(name))) throw new Error("Self-test: mẫu tên sai bị chấp nhận.");
  if (normalizeTitle(" Thông báo   xác nhận – kết quả ") !== "THÔNG BÁO XÁC NHẬN - KẾT QUẢ") {
    throw new Error("Self-test: chuẩn hóa trích yếu không đúng.");
  }
  if (![true, 1, "true", "1"].every(isUnread) || [false, 0, "false", "0", null].some(isUnread)) {
    throw new Error("Self-test: nhận diện chữ đậm không đúng.");
  }
  if (parseNotificationNumbers("1712").join(",") !== "1712") throw new Error("Self-test: parse một số không đúng.");
  if (parseNotificationNumbers("1712,1715,1720").join(",") !== "1712,1715,1720") throw new Error("Self-test: parse nhiều số không đúng.");
  if (parseNotificationNumbers("1712-1715").join(",") !== "1712,1713,1714,1715") throw new Error("Self-test: parse khoảng số không đúng.");
  const parsed = parseNotificationNumbers("1712, 1715, 1720-1723,1712");
  if (parsed.join(",") !== "1712,1715,1720,1721,1722,1723") throw new Error("Self-test: parse kết hợp/loại duplicate không đúng.");
  if (!String((() => { try { parseNotificationNumbers("1712,x"); } catch (error) { return error.message; } return ""; })()).includes("không hợp lệ")) throw new Error("Self-test: format sai không bị từ chối.");
  if (extractNotificationNumber("Số: 1712/TB-ĐKĐĐ") !== 1712 || extractNotificationNumber("1712/TB-ĐKĐĐ") !== 1712) throw new Error("Self-test: không tách được số thông báo đầy đủ.");
  if (extractNotificationNumber("11712/TB-ĐKĐĐ") === 1712 || extractNotificationNumber("17120/TB-ĐKĐĐ") === 1712) throw new Error("Self-test: match nhầm số thông báo dạng substring.");
  if (extractNotificationNumber("Văn bản 1712/TB-ĐKĐĐ") !== null) throw new Error("Self-test: tách số từ vị trí mơ hồ.");
  if (getRecordNotificationNumber({ OrderIndex: 1712, Name: "TB-ĐKĐĐ" }) !== 1712) throw new Error("Self-test: không đọc được trường Số VB OrderIndex của HPNet.");
  if (!isHpnetUrl("https://qlvb.hpnet.vn/?action=101") || isHpnetUrl("https://id.vneid.gov.vn/oauth2/authorize")) throw new Error("Self-test: nhận diện HPNet/VNeID không đúng.");
  if (!isHpnetLoginUrl("https://qlvb.hpnet.vn/Login.aspx?ReturnUrl=%2f") || isHpnetLoginUrl("https://id.vneid.gov.vn/Login.aspx")) throw new Error("Self-test: nhận diện trang đăng nhập không đúng.");
  if (!String((() => { try { normalizeCommuneCode("1093"); } catch (error) { return error.message; } return ""; })()).includes("5 chữ số")) throw new Error("Self-test: mã xã sai không bị từ chối.");
  const makeConfig = (overrides = {}) => ({
    titleFilterEnabled: false, notificationFilterEnabled: false, symbolFilterEnabled: false, dateFilterEnabled: true,
    dateMode: "exact", exactDate: "2026-08-31", readFilter: "all", ...overrides,
  });
  const makeEntry = (overrides = {}) => buildDocumentRecord({
    VanbanDiId: 1, OrderIndex: 1712, Name: "TB-ĐKĐĐ", TrichYeu: "Thông báo xác nhận kết quả", NgayVanBan: "31/08/2026 08:30", IsNew: true,
    ...overrides,
  }, 1);
  const assert = (condition, name) => { if (!condition) throw new Error(`Self-test bộ lọc: ${name}`); };
  assert(recordMatchesFilters(makeEntry(), buildFilters(makeConfig())), "01 lọc đúng một ngày");
  assert(!recordMatchesFilters(makeEntry({ NgayVanBan: "30/08/2026" }), buildFilters(makeConfig())), "02 loại ngày không khớp");
  assert(recordMatchesFilters(makeEntry({ NgayVanBan: "30-08-2026" }), buildFilters(makeConfig({ dateMode: "range", startDate: "2026-08-30", endDate: "2026-08-31" }))), "03 khoảng ngày gồm hai biên");
  assert(!recordMatchesFilters(makeEntry({ NgayVanBan: "29/08/2026" }), buildFilters(makeConfig({ dateMode: "range", startDate: "2026-08-30", endDate: "2026-08-31" }))), "04 loại ngoài khoảng");
  assert(!recordMatchesFilters(makeEntry({ NgayVanBan: "31/02/2026" }), buildFilters(makeConfig())), "05 ngày record sai bị bỏ qua");
  assert(recordMatchesFilters(makeEntry({ TrichYeu: "V/v THÔNG BÁO   xác nhận kết quả hồ sơ" }), buildFilters(makeConfig({ titleFilterEnabled: true, allowedTitles: ["thông báo xác nhận"], notificationFilterEnabled: false }))), "06 trích yếu contains chuẩn hóa");
  assert(recordMatchesFilters(makeEntry(), buildFilters(makeConfig({ notificationFilterEnabled: true, notificationNumbers: "1712" }))), "07 số thông báo đúng");
  assert(!recordMatchesFilters(makeEntry({ OrderIndex: 17120 }), buildFilters(makeConfig({ notificationFilterEnabled: true, notificationNumbers: "1712" }))), "08 số không khớp substring");
  assert(recordMatchesFilters(makeEntry(), buildFilters(makeConfig({ symbolFilterEnabled: true, documentSymbols: "TB-ĐKĐĐ" }))), "09 ký hiệu đúng");
  assert(!recordMatchesFilters(makeEntry({ Name: "QĐ-UBND" }), buildFilters(makeConfig({ symbolFilterEnabled: true, documentSymbols: "TB-ĐKĐĐ" }))), "10 không tải nhầm ký hiệu khác");
  assert(recordMatchesFilters(makeEntry(), buildFilters(makeConfig({ titleFilterEnabled: true, allowedTitles: ["xác nhận"], notificationFilterEnabled: true, notificationNumbers: "1712", symbolFilterEnabled: true, documentSymbols: "TB-ĐKĐĐ" }))), "11 AND đủ điều kiện");
  assert(!recordMatchesFilters(makeEntry({ Name: "CV-UBND" }), buildFilters(makeConfig({ titleFilterEnabled: true, allowedTitles: ["xác nhận"], notificationFilterEnabled: true, notificationNumbers: "1712", symbolFilterEnabled: true, documentSymbols: "TB-ĐKĐĐ" }))), "12 AND thiếu một điều kiện");
  assert(recordMatchesFilters(makeEntry(), buildFilters(makeConfig({ readFilter: "unread" }))), "13 lọc chữ đậm");
  assert(!recordMatchesFilters(makeEntry({ IsNew: false }), buildFilters(makeConfig({ readFilter: "unread" }))), "14 loại văn bản không đậm");
  assert(parseDocumentDate("31-08-2026 23:59").iso === "2026-08-31" && parseDocumentDate("2026-08-31T09:15:00").iso === "2026-08-31", "15 parser nhiều định dạng và thời gian");
  assert(getRecordDocumentDate({ NgayBanhanh: "22/08/2026" }).iso === "2026-08-22" && getRecordDocumentSymbol({ Name: "TB-ĐKĐĐ" }).normalized === "TB-ĐKĐĐ", "15b đúng trường HPNet thực tế");
  const legacy = buildFilters({ downloadMode: "numbers", notificationNumbers: "1712", readFilter: "all" });
  assert(legacy.notificationEnabled && !legacy.titleEnabled && !legacy.dateEnabled && !legacy.symbolEnabled, "16 tương thích cấu hình cũ");
  assert(buildDuplicateFileName("van-ban.pdf", 2) === "van-ban_2.pdf" && buildDuplicateFileName("van-ban.signed.pdf", 12) === "van-ban.signed_12.pdf", "17 tạo hậu tố file trùng");
  const os = require("node:os");
  const duplicateTestRoot = await fsp.mkdtemp(path.join(os.tmpdir(), "hpnet-duplicate-test-"));
  try {
    const first = await saveNameCollision(duplicateTestRoot, "van-ban.pdf", Buffer.from("%PDF-first"));
    const second = await saveNameCollision(duplicateTestRoot, "van-ban.pdf", Buffer.from("%PDF-second"));
    const repeated = await saveNameCollision(duplicateTestRoot, "van-ban.pdf", Buffer.from("%PDF-first"));
    assert(first.status === "saved" && first.duplicateName === "van-ban_2.pdf", "18 file trùng đầu tiên mang hậu tố _2");
    assert(second.status === "saved" && second.duplicateName === "van-ban_3.pdf", "19 file trùng tiếp theo mang hậu tố _3");
    assert(repeated.status === "exists" && repeated.duplicateName === "van-ban_2.pdf", "20 nội dung trùng không tạo thêm file");
  } finally {
    await fsp.rm(duplicateTestRoot, { recursive: true, force: true });
  }
  console.log("NODE_SELF_TEST_OK: 20/20 tình huống bộ lọc, trường HPNet và xử lý file trùng tên");
}

async function ensureLoggedIn(page, context, log) {
  await page.goto(MAIN_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.bringToFront();
  const deadline = Date.now() + 20 * 60 * 1000;
  let announced = false;
  while (true) {
    const pages = context.pages();
    const ready = pages.find((item) => isHpnetUrl(item.url()) && !isHpnetLoginUrl(item.url()) && /[?&]action=101(?:&|$)/i.test(item.url()));
    if (ready) return ready;

    if (!announced) {
      log("Hãy chọn Đăng nhập bằng VNeID trong Edge và hoàn tất xác thực. Công cụ sẽ tự tiếp tục khi quay lại HPNet.");
      announced = true;
    }
    if (Date.now() > deadline) throw new Error("Hết thời gian chờ đăng nhập VNeID/HPNet (20 phút).");

    const returned = pages.find((item) => isHpnetUrl(item.url()) && !isHpnetLoginUrl(item.url()));
    if (returned) {
      page = returned;
      if (!/[?&]action=101(?:&|$)/i.test(page.url())) {
        await page.goto(MAIN_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
      }
    } else {
      const authPage = pages.find((item) => !isHpnetUrl(item.url()) && !/^about:blank$/i.test(item.url()));
      if (authPage) page = authPage;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

async function main({ configPath = process.argv[2], chromium: suppliedChromium } = {}) {
  if (process.argv.includes("--self-test")) {
    await runSelfTest();
    return;
  }
  if (!configPath) throw new Error("Thiếu tệp cấu hình.");
  const config = JSON.parse(cleanJsonText(await fsp.readFile(configPath, "utf8")));
  const communeCode = normalizeCommuneCode(config.communeCode ?? "10930");
  const allowMissingCommuneCode = config.allowMissingCommuneCode !== false;
  const filters = buildFilters(config);
  const targetNumberList = filters.numberList;
  const readFilter = filters.readFilter;

  const outputDir = path.resolve(String(config.outputDir ?? ""));
  await fsp.mkdir(outputDir, { recursive: true });
  const runStamp = `${timestamp()}_${crypto.randomBytes(3).toString("hex")}`;
  const logPath = path.join(outputDir, `NHAT_KY_TAI_PDF_${runStamp}.txt`);
  const csvLogPath = path.join(outputDir, `NHAT_KY_TAI_PDF_${runStamp}.csv`);
  const auditPath = path.join(outputDir, `DOI_SOAT_TOAN_BO_VAN_BAN_${runStamp}.csv`);
  const recordEntries = [];
  let activeEntry = null;
  const csvText = (rows) => `${rows.map((row) => row.map(csvCell).join(",")).join("\r\n")}\r\n`;
  fs.writeFileSync(logPath, "\uFEFF", { encoding: "utf8", flag: "wx" });
  fs.writeFileSync(csvLogPath, `\uFEFF${csvText([["Thời gian", "Số thông báo", "Thông tin record", "Trang tìm thấy", "Tên file", "Đường dẫn", "Trạng thái", "Lỗi/Ghi chú"]])}`, { encoding: "utf8", flag: "wx" });
  const log = (message) => {
    const line = `[${new Date().toLocaleString("vi-VN")}] ${message}`;
    fs.appendFileSync(logPath, `${line}\r\n`, "utf8");
    console.log(line);
  };
  const addResult = (row) => {
    fs.appendFileSync(csvLogPath, csvText([[new Date().toISOString(), ...row]]), "utf8");
    if (activeEntry) {
      activeEntry.outcomes ??= [];
      activeEntry.outcomes.push(`${row[5]}: ${row[3] || "không có tên file"}${row[6] ? ` (${row[6]})` : ""}`);
    }
  };
  const saveAudit = () => fs.writeFileSync(auditPath, `\uFEFF${csvText(auditRows(recordEntries, filters))}`, "utf8");

  let context;
  try {
  const modulesRoot = process.env.HPNET_NODE_MODULES;
  const edgeExe = process.env.HPNET_EDGE_EXE;
  if (!suppliedChromium && (!modulesRoot || !edgeExe)) throw new Error("Không xác định được bộ chạy trình duyệt đi kèm công cụ.");
  const chromium = suppliedChromium || require(path.join(modulesRoot, "playwright")).chromium;
  const profileDir = path.join(path.dirname(configPath), "du_lieu_dang_nhap_vneid");
  context = await chromium.launchPersistentContext(profileDir, {
    executablePath: edgeExe,
    headless: false,
    acceptDownloads: true,
    viewport: null,
    args: ["--start-maximized"],
  });

  let page = context.pages()[0] || await context.newPage();
    log("Mở HPNet...");
    page = await ensureLoggedIn(page, context, log);
    log("Đăng nhập VNeID/HPNet thành công.");

    const pageSize = Math.floor(Math.max(10, Math.min(100, Number(config.listPageSize) || 100)));
    log("Cách kết hợp bộ lọc: AND giữa các nhóm đã bật; OR giữa nhiều giá trị trong cùng một nhóm.");
    log("Phạm vi: danh sách VĂN BẢN ĐI tài khoản được xem (all=false, status=0); không phải danh sách đã upload/dự thảo. Không tự đổi phạm vi hoặc quyền xem.");
    log(`Mã xã dùng để kiểm tra tên PDF: ${communeCode}`);
    log(`Nhận tên thiếu mã xã: ${allowMissingCommuneCode ? "CÓ; giữ nguyên tên, không tự thêm mã xã" : "KHÔNG"}.`);
    log(`Bộ lọc chữ đậm: ${readFilter === "unread" ? "CHỈ CHỮ ĐẬM" : readFilter === "read" ? "CHỈ KHÔNG ĐẬM" : "TẤT CẢ"}`);
    if (filters.titleEnabled) log(`Trích yếu chứa một trong ${filters.titles.size} nội dung: ${[...filters.titles].join(" | ")}`);
    if (filters.notificationEnabled) log(`Số thông báo yêu cầu (${targetNumberList.length}): ${targetNumberList.join(", ")}`);
    if (filters.symbolEnabled) log(`Ký hiệu VB chính xác (${filters.symbols.size}): ${[...filters.symbols].join(", ")}`);
    if (filters.dateEnabled) log(`Ngày văn bản: ${filters.dateMode === "exact" ? filters.startDate.iso : `${filters.startDate.iso} đến ${filters.endDate.iso}`} (tính cả hai đầu).`);

    const scan = await scanDocumentPages(async (startIndex, requestedSize) => {
      const response = await context.request.post(`${LIST_URL}?jtStartIndex=${startIndex}&jtPageSize=${requestedSize}`, {
        form: { key: "", all: "false", status: "0" },
        timeout: 60000,
      });
      if (!response.ok()) throw new Error(`Không đọc được danh sách VB đi: HTTP ${response.status()}.`);
      const contentType = response.headers()["content-type"] || "";
      if (/text\/html/i.test(contentType)) throw new Error("Phiên đăng nhập hết hạn khi đọc danh sách VB đi.");
      return response.json();
    }, { pageSize, log, onBatch: (batch, pageNumber) => {
      recordEntries.push(...batch.map((record) => buildDocumentRecord(record, pageNumber)));
      classifyEntries(recordEntries, filters);
      saveAudit();
    } });

    let dateParseFailures = 0;
    if (filters.dateEnabled) {
      for (const entry of recordEntries) {
        if (!entry.date.parseFailed) continue;
        dateParseFailures += 1;
        if (dateParseFailures <= 20) {
          const label = entry.notificationNumber ?? entry.documentId ?? "không rõ";
          log(`[CẢNH BÁO NGÀY] Bỏ qua văn bản ${label}: không đọc được ngày từ trường ${entry.date.field || "không xác định"} (${String(entry.date.raw || "trống")}).`);
        }
      }
      if (dateParseFailures > 20) log(`[CẢNH BÁO NGÀY] Còn ${dateParseFailures - 20} văn bản lỗi ngày không liệt kê chi tiết.`);
    }
    const classified = classifyEntries(recordEntries, filters);
    const uniqueEntries = classified.matched;
    log(`ĐỐI SOÁT: ${recordEntries.length} dòng = ${classified.duplicates} dòng lặp + ${classified.excluded} văn bản bị lọc + ${uniqueEntries.length} văn bản khớp.`);
    for (const [reason, count] of classified.reasonCounts) log(`[BỊ LỌC] ${count}: ${reason}.`);
    log("Một văn bản có thể không khớp nhiều bộ lọc; không cộng các lý do để tính tổng. Xem CSV ĐỐI SOÁT để biết trích yếu, ngày gốc và lý do của TỪNG văn bản.");
    if (filters.dateEnabled) log("Lưu ý: lọc NGÀY VĂN BẢN trên HPNet, không phải ngày bạn upload. Muốn đối chiếu nhiều ngày, mở rộng khoảng ngày hoặc bỏ chọn bộ lọc ngày.");
    const foundNumbers = new Set(uniqueEntries.map((entry) => entry.notificationNumber).filter((value) => value !== null));
    const notFoundNumbers = targetNumberList.filter((number) => !foundNumbers.has(number));
    log(`Có ${uniqueEntries.length} văn bản khớp bộ lọc.`);
    if (filters.notificationEnabled && notFoundNumbers.length) log(`[KHÔNG TÌM THẤY SAU KHI ÁP DỤNG TOÀN BỘ BỘ LỌC] ${notFoundNumbers.join(", ")}`);

    const validNamePattern = buildValidPdfNamePattern(communeCode, allowMissingCommuneCode);
    const strictNamePattern = buildValidPdfNamePattern(communeCode, false);
    const seenUrls = new Set();
    let downloaded = 0;
    let existed = 0;
    let badFormat = 0;
    let noFiles = 0;
    let sharedFiles = 0;
    let renamedDuplicates = 0;
    let errors = 0;

    const downloadedNumbers = new Set();
    const existingNumbers = new Set();
    const errorNumbers = new Set();

    for (let index = 0; index < uniqueEntries.length; index += 1) {
      const entry = uniqueEntries[index];
      activeEntry = entry;
      const record = entry.record;
      const notificationNumber = entry.notificationNumber;
      const documentId = record.VanbanDiId || record.vanbandiid || record.Id;
      const label = `${record.SoVanBan || record.SoVanban || record.OrderIndex || "?"}/${record.Name || ""}`;
      if (!documentId) {
        errors += 1;
        log(`[BỎ QUA] ${label}: không có mã nội bộ VanbanDiId.`);
        if (notificationNumber !== null) errorNumbers.add(notificationNumber);
        addResult([notificationNumber ?? "", label, entry.pageNumber, "", "", "LỖI", "Không có mã nội bộ VanbanDiId"]);
        continue;
      }

      try {
        const detailUrl = new URL(DETAIL_URL);
        detailUrl.searchParams.set("VanbanDiId", documentId);
        const detailResponse = await context.request.get(detailUrl.href, { timeout: 60000 });
        if (!detailResponse.ok()) throw new Error(`HTTP ${detailResponse.status()} khi đọc chi tiết.`);
        const detail = unwrapPayload(await detailResponse.json());
        if (!detail || typeof detail !== "object") throw new Error("Phản hồi chi tiết không hợp lệ; không thể xác định file đính kèm.");
        if (detail.Result && String(detail.Result).toUpperCase() !== "OK") throw new Error(detail.Message || "HPNet trả lỗi khi đọc file đính kèm.");
        const candidates = [];
        if (detail.file) candidates.push({ url: detail.file, name: fileNameFromUrl(detail.file) });
        for (const item of Array.isArray(detail.files) ? detail.files : []) {
          const fileUrl = item.FilePath || item.filePath || item.Path || item.path;
          const fileName = item.FileName || item.fileName || fileNameFromUrl(fileUrl);
          if (fileUrl) candidates.push({ url: fileUrl, name: fileName });
        }

        const candidatesByUrl = new Map();
        for (const candidate of candidates) {
          const absolute = absoluteHpnetUrl(candidate.url);
          if (!absolute) continue;
          candidate.url = absolute;
          // A URL may use a generated name; prefer the explicit attachment name.
          const previous = candidatesByUrl.get(absolute);
          if (!previous || (!validNamePattern.test(previous.name) && validNamePattern.test(candidate.name))) candidatesByUrl.set(absolute, candidate);
        }
        const uniqueCandidates = [...candidatesByUrl.values()];
        if (!uniqueCandidates.length) {
          noFiles += 1;
          if (notificationNumber !== null) errorNumbers.add(notificationNumber);
          log(`[KHÔNG CÓ FILE] ${label}: HPNet không trả liên kết đính kèm.`);
          addResult([notificationNumber ?? "", label, entry.pageNumber, "", "", "KHÔNG CÓ FILE", "Kiểm tra file đính kèm/quyền xem trên HPNet; đây không phải lỗi tên file"]);
          continue;
        }

        const validCandidates = uniqueCandidates.filter((candidate) => validNamePattern.test(candidate.name));
        if (!validCandidates.length) {
          badFormat += 1;
          const names = uniqueCandidates.map((item) => item.name).filter(Boolean).join(", ") || "không có file";
          log(`[SAI MẪU TÊN] ${label}: ${names}`);
          if (notificationNumber !== null) errorNumbers.add(notificationNumber);
          addResult([notificationNumber ?? "", label, entry.pageNumber, names, "", "SAI MẪU TÊN", "Không có PDF đúng mẫu tên cho phép"]);
          continue;
        }

        const invalidNames = uniqueCandidates.filter((candidate) => !validNamePattern.test(candidate.name)).map((candidate) => candidate.name);
        if (invalidNames.length) addResult([notificationNumber ?? "", label, entry.pageNumber, invalidNames.join(", "), "", "FILE KHÔNG KHỚP MẪU", "Văn bản còn file hợp lệ sẽ được xử lý riêng"]);
        if (validCandidates.every((candidate) => seenUrls.has(candidate.url))) sharedFiles += 1;

        for (const candidate of validCandidates) {
          const safeName = path.basename(candidate.name);
          const destination = path.join(outputDir, safeName);
          if (seenUrls.has(candidate.url)) {
            addResult([notificationNumber ?? "", label, entry.pageNumber, safeName, "", "BỎ QUA TRÙNG", "Cùng liên kết đã được tải hoặc kiểm tra nội dung thành công trong lần chạy này"]);
            if (notificationNumber !== null) existingNumbers.add(notificationNumber);
            continue;
          }
          if (!strictNamePattern.test(candidate.name)) log(`[NGOẠI LỆ THIẾU MÃ XÃ] ${safeName}: chấp nhận và giữ nguyên tên.`);
          try {
          const fileResponse = await context.request.get(candidate.url, { timeout: 120000 });
          if (!fileResponse.ok()) throw new Error(`HTTP ${fileResponse.status()} khi tải ${safeName}.`);
          const buffer = await fileResponse.body();
          if (buffer.length < 5 || buffer.subarray(0, 5).toString("ascii") !== "%PDF-") {
            throw new Error(`${safeName} không phải dữ liệu PDF hợp lệ.`);
          }

          if (fs.existsSync(destination)) {
            const existing = await fsp.readFile(destination);
            if (sha256(existing) === sha256(buffer)) {
              existed += 1;
              if (notificationNumber !== null) existingNumbers.add(notificationNumber);
              log(`[ĐÃ CÓ] ${safeName}`);
              addResult([notificationNumber ?? "", label, entry.pageNumber, safeName, destination, "ĐÃ CÓ", "File hiện có giống hệt nội dung trên HPNet"]);
              seenUrls.add(candidate.url);
              continue;
            }
            const collision = await saveNameCollision(outputDir, safeName, buffer);
            if (collision.status === "exists") {
              existed += 1;
              if (notificationNumber !== null) existingNumbers.add(notificationNumber);
              log(`[ĐÃ CÓ TRONG THƯ MỤC TRÙNG] ${collision.duplicateName}`);
              addResult([notificationNumber ?? "", label, entry.pageNumber, collision.duplicateName, collision.destination, "ĐÃ CÓ", "File trùng tên và nội dung đã có trong thư mục Trùng"]);
            } else {
              renamedDuplicates += 1;
              downloaded += 1;
              if (notificationNumber !== null) downloadedNumbers.add(notificationNumber);
              log(`[ĐÃ LƯU FILE TRÙNG TÊN] ${safeName} -> Trùng\\${collision.duplicateName}`);
              addResult([notificationNumber ?? "", label, entry.pageNumber, collision.duplicateName, collision.destination, "ĐÃ LƯU TRÙNG TÊN", `Tên gốc: ${safeName}; tự thêm hậu tố _${collision.index}`]);
            }
            seenUrls.add(candidate.url);
            continue;
          }

          const tempPath = `${destination}.part`;
          await fsp.writeFile(tempPath, buffer);
          await fsp.rename(tempPath, destination);
          const saved = await fsp.stat(destination);
          if (saved.size <= 0 || path.extname(destination).toLowerCase() !== ".pdf" || fs.existsSync(tempPath)) {
            throw new Error(`${safeName} không vượt qua kiểm tra file sau khi tải.`);
          }
          downloaded += 1;
          if (notificationNumber !== null) downloadedNumbers.add(notificationNumber);
          log(`[ĐÃ TẢI] ${safeName}`);
          addResult([notificationNumber ?? "", label, entry.pageNumber, safeName, destination, "ĐÃ TẢI", ""]);
          seenUrls.add(candidate.url);
          } catch (error) {
            errors += 1;
            if (notificationNumber !== null) errorNumbers.add(notificationNumber);
            log(`[LỖI FILE] ${label} / ${safeName}: ${error.message}. Tiếp tục kiểm tra file khác.`);
            addResult([notificationNumber ?? "", label, entry.pageNumber, safeName, "", "LỖI", error.message]);
          }
        }
      } catch (error) {
        errors += 1;
        if (notificationNumber !== null) errorNumbers.add(notificationNumber);
        log(`[LỖI] ${label}: ${error.message}`);
        addResult([notificationNumber ?? "", label, entry.pageNumber, "", "", "LỖI", error.message]);
      } finally {
        saveAudit();
      }
    }

    log("--- TỔNG KẾT ---");
    log(`Tổng văn bản đã quét: ${recordEntries.length}`);
    log(`Văn bản riêng biệt theo mã HPNet: ${scan.unique}; dòng lặp: ${classified.duplicates}; bị lọc: ${classified.excluded}.`);
    log(`Văn bản khớp bộ lọc: ${uniqueEntries.length}`);
    if (filters.notificationEnabled) {
      log(`Yêu cầu: ${targetNumberList.length} thông báo`);
      log(`Tìm thấy: ${foundNumbers.size}`);
      log(`Tải mới thành công: ${downloadedNumbers.size}`);
      log(`Đã tồn tại giống hệt: ${existingNumbers.size}`);
      log(`Không tìm thấy: ${notFoundNumbers.length}${notFoundNumbers.length ? ` (${notFoundNumbers.join(", ")})` : ""}`);
      log(`Số có lỗi tải/xử lý: ${errorNumbers.size}${errorNumbers.size ? ` (${[...errorNumbers].sort((a, b) => a - b).join(", ")})` : ""}`);
    }
    log(`PDF tải mới: ${downloaded}`);
    log(`PDF đã tồn tại giống hệt: ${existed}`);
    log(`PDF trùng tên khác nội dung đã lưu vào thư mục Trùng với hậu tố: ${renamedDuplicates}`);
    log(`Văn bản không có file đúng mẫu: ${badFormat}`);
    log(`Văn bản không có liên kết file: ${noFiles}`);
    log(`Văn bản có toàn bộ file hợp lệ dùng chung liên kết đã xử lý: ${sharedFiles}`);
    log("Số PDF và số văn bản là hai đơn vị khác nhau: một văn bản có thể có nhiều file hoặc dùng chung file.");
    if (filters.dateEnabled) log(`Văn bản bị bỏ qua do ngày trống/sai định dạng: ${dateParseFailures}`);
    log(`Lỗi: ${errors}`);
    if (errors) process.exitCode = 2;
  } catch (error) {
    log(`[CHƯA HOÀN TẤT] ${error.message}. Nhật ký giữ lại những văn bản đã đọc/xử lý; không coi đây là kết quả đầy đủ.`);
    throw error;
  } finally {
    try {
      saveAudit();
      console.log(`Nhật ký TXT: ${logPath}`);
      console.log(`Nhật ký CSV: ${csvLogPath}`);
      console.log(`Đối soát TOÀN BỘ văn bản (kể cả bị lọc): ${auditPath}`);
    } finally {
      if (context) await context.close();
    }
  }
}

module.exports = { buildValidPdfNamePattern, buildFilters, buildDocumentRecord, recordFilterReasons, recordMatchesFilters, scanDocumentPages, classifyEntries, auditRows, csvCell, main };

if (require.main === module) {
  main().catch((error) => {
    fail(error.stack || error.message || String(error));
  });
}
