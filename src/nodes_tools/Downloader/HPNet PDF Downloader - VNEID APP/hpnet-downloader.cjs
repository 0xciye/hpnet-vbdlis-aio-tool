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

function normalizeDocumentScope(value) {
  const scope = String(value ?? "filtered").normalize("NFC").trim().toLowerCase();
  if (!["filtered", "all_visible"].includes(scope)) {
    throw new Error("Phạm vi văn bản không hợp lệ. Hãy chọn Theo bộ lọc hoặc Toàn bộ Văn bản đi được quyền xem.");
  }
  return scope;
}

function parseFileSuffixes(value) {
  const source = Array.isArray(value) ? value : String(value ?? "").split(/[,;\r\n]+/u);
  const suffixes = [];
  const seen = new Set();
  for (const rawValue of source) {
    let suffix = String(rawValue ?? "").normalize("NFC").trim();
    if (!suffix) continue;
    if (/\.pdf$/iu.test(suffix)) suffix = suffix.slice(0, -4).trim();
    if (!suffix.startsWith(".")) suffix = `.${suffix}`;
    if (/^[\s.]*$/u.test(suffix)) throw new Error("Hậu tố tên file không được để trống hoặc chỉ gồm dấu chấm.");
    if (/[\u0000-\u001F\u007F<>:"/\\|?*\[\]{}()+^$]/u.test(suffix)) {
      throw new Error(`Hậu tố không hợp lệ: ${rawValue}. Không dùng đường dẫn, wildcard hoặc ký tự regex.`);
    }
    if (/[. ]$/u.test(suffix)) throw new Error(`Hậu tố không hợp lệ: ${rawValue}. Không được kết thúc bằng dấu chấm hoặc khoảng trắng.`);
    const key = suffix.toLocaleLowerCase("vi-VN");
    if (!seen.has(key)) {
      seen.add(key);
      suffixes.push(suffix);
    }
  }
  if (!suffixes.length) throw new Error("Hãy chọn hoặc nhập ít nhất một hậu tố tên file, ví dụ: .signed");
  return suffixes;
}

function buildFileNamePolicy(config = {}) {
  const mode = String(config.fileNameMode ?? "legacy").normalize("NFC").trim().toLowerCase();
  if (mode === "legacy") {
    const communeCode = normalizeCommuneCode(config.communeCode ?? "10930");
    const allowMissingCommuneCode = config.allowMissingCommuneCode !== false;
    return {
      mode, communeCode, allowMissingCommuneCode,
      pattern: buildValidPdfNamePattern(communeCode, allowMissingCommuneCode),
      strictPattern: buildValidPdfNamePattern(communeCode, false),
      description: `Mẫu CHUACOGIAY; mã xã ${communeCode}; thiếu mã xã: ${allowMissingCommuneCode ? "cho phép" : "không cho phép"}`,
    };
  }
  if (mode === "suffix") {
    const suffixes = parseFileSuffixes(config.fileSuffixes ?? [".signed"]);
    return { mode, suffixes, description: `Hậu tố ngay trước .pdf: ${suffixes.join(", ")}` };
  }
  throw new Error("Chế độ tên file không hợp lệ. Hãy chọn Mẫu hồ sơ CHUACOGIAY hoặc Theo hậu tố tên file.");
}

function validateWindowsFileName(value) {
  const name = String(value ?? "").normalize("NFC");
  if (!name) return { valid: false, reason: "Tên file trống" };
  if (name !== name.trim()) return { valid: false, reason: "Tên file có khoảng trắng ở đầu hoặc cuối" };
  if (/[\u0000-\u001F\u007F<>:"/\\|?*]/u.test(name)) return { valid: false, reason: "Tên file chứa ký tự không an toàn trên Windows" };
  if (/[. ]$/u.test(name)) return { valid: false, reason: "Tên file kết thúc bằng dấu chấm hoặc khoảng trắng" };
  const deviceStem = name.split(".", 1)[0].replace(/[. ]+$/u, "").toUpperCase();
  if (/^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$/u.test(deviceStem)) return { valid: false, reason: "Tên file trùng tên thiết bị dành riêng của Windows" };
  return { valid: true, safeName: name };
}

function matchPdfFileName(fileName, policy) {
  const checked = validateWindowsFileName(fileName);
  if (!checked.valid) return { matched: false, code: "unsafe_name", reason: checked.reason, safeName: "" };
  const name = checked.safeName;
  if (!/\.pdf$/iu.test(name)) return { matched: false, code: "not_pdf", reason: "Không phải tên file PDF", safeName: name };
  if (policy.mode === "legacy") {
    return policy.pattern.test(name)
      ? { matched: true, code: "matched", reason: "Đúng mẫu hồ sơ CHUACOGIAY", safeName: name }
      : { matched: false, code: "legacy_mismatch", reason: "Không đúng mẫu tên CHUACOGIAY/TBXN đã chọn", safeName: name };
  }
  const foldedName = name.toLocaleLowerCase("vi-VN");
  for (const suffix of policy.suffixes) {
    const ending = `${suffix}.pdf`.toLocaleLowerCase("vi-VN");
    if (!foldedName.endsWith(ending)) continue;
    const documentName = name.slice(0, name.length - ending.length).trim();
    if (!documentName) return { matched: false, code: "missing_stem", reason: "Thiếu tên văn bản trước hậu tố", safeName: name };
    return { matched: true, code: "matched", reason: `Khớp hậu tố ${suffix}`, safeName: name, suffix };
  }
  return { matched: false, code: "suffix_mismatch", reason: `Không khớp hậu tố đã chọn (${policy.suffixes.join(", ")})`, safeName: name };
}

function deduplicateCandidates(candidates, policy) {
  const byUrl = new Map();
  for (const rawCandidate of candidates) {
    const absolute = absoluteHpnetUrl(rawCandidate.url);
    if (!absolute) continue;
    const candidate = { ...rawCandidate, url: absolute };
    candidate.nameMatch = matchPdfFileName(candidate.name, policy);
    const previous = byUrl.get(absolute);
    const shouldReplace = !previous
      || (candidate.explicitName && !previous.explicitName)
      || (candidate.explicitName === previous.explicitName && candidate.nameMatch.matched && !previous.nameMatch.matched);
    if (shouldReplace) byUrl.set(absolute, candidate);
  }
  return [...byUrl.values()];
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
  const documentScope = normalizeDocumentScope(config.documentScope);
  if (documentScope === "all_visible") {
    return {
      documentScope, titleEnabled: false, titles: new Set(), notificationEnabled: false, numberList: [], numbers: new Set(),
      symbolEnabled: false, symbols: new Set(), dateEnabled: false, dateMode: "none", startDate: null, endDate: null, readFilter: "all",
    };
  }
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
    documentScope,
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

async function scanDocumentPages(fetchPage, { pageSize = 100, maxPages = 10000, onBatch = () => {}, log = () => {} } = {}) {
  if (!Number.isSafeInteger(pageSize) || pageSize <= 0) throw new Error("Kích thước trang phải là số nguyên dương.");
  if (!Number.isSafeInteger(maxPages) || maxPages <= 0) throw new Error("Giới hạn số trang phải là số nguyên dương.");
  let startIndex = 0;
  let pageNumber = 0;
  let total = null;
  const seen = new Set();
  let duplicates = 0;
  while (true) {
    if (pageNumber >= maxPages) throw new Error(`Đã đạt giới hạn an toàn ${maxPages} trang nhưng chưa xác nhận quét hết.`);
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
      return { rows: startIndex, apiRows: startIndex, unique: seen.size, duplicates, total, pages: pageNumber - 1, dataPages: pageNumber - 1, terminationReason: "empty_page" };
    }
    let added = 0;
    const newRecords = [];
    for (const record of batch) {
      if (!record || typeof record !== "object" || Array.isArray(record)) throw new Error(`Trang ${pageNumber} có dòng văn bản sai cấu trúc.`);
      const key = recordKey(record);
      if (seen.has(key)) duplicates += 1;
      else { seen.add(key); added += 1; newRecords.push(record); }
    }
    await onBatch(newRecords, pageNumber);
    startIndex += batch.length;
    log(`Đã đọc ${startIndex} dòng / tổng HPNet ${total ?? "chưa rõ"}; ${seen.size} văn bản riêng biệt, ${duplicates} dòng lặp (trang ${pageNumber}).`);
    if (total !== null && seen.size >= total) {
      log(`Đã quét đủ ${seen.size}/${total} văn bản riêng biệt theo tổng HPNet sau ${pageNumber} trang. Không yêu cầu trang thừa.`);
      return { rows: startIndex, apiRows: startIndex, unique: seen.size, duplicates, total, pages: pageNumber, dataPages: pageNumber, terminationReason: "reported_total" };
    }
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
      const status = entry.duplicate ? "DÒNG LẶP" : reasons.length ? "BỊ LỌC" : outcomes.length ? "ĐÃ XỬ LÝ" : "THUỘC PHẠM VI - CHƯA TẢI";
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

function safeOutputPath(outputDir, fileName) {
  const checked = validateWindowsFileName(fileName);
  if (!checked.valid) throw new Error(checked.reason);
  const root = path.resolve(outputDir);
  const destination = path.resolve(root, checked.safeName);
  const relative = path.relative(root, destination);
  if (!relative || relative.startsWith("..") || path.isAbsolute(relative)) throw new Error("Tên file có thể thoát khỏi thư mục lưu đã chọn.");
  return destination;
}

async function writePdfAtomic(destination, buffer) {
  const tempPath = `${destination}.part`;
  let tempCreated = false;
  try {
    const handle = await fsp.open(tempPath, "wx");
    tempCreated = true;
    try { await handle.writeFile(buffer); } finally { await handle.close(); }
    if (fs.existsSync(destination)) throw new Error(`${path.basename(destination)} đã xuất hiện trong lúc tải; không ghi đè.`);
    await fsp.rename(tempPath, destination);
    tempCreated = false;
    const saved = await fsp.stat(destination);
    if (saved.size <= 0 || path.extname(destination).toLowerCase() !== ".pdf") throw new Error(`${path.basename(destination)} không vượt qua kiểm tra file sau khi tải.`);
  } finally {
    if (tempCreated) await fsp.rm(tempPath, { force: true }).catch(() => {});
  }
}

async function saveNameCollision(outputDir, fileName, buffer) {
  const duplicateDir = path.resolve(outputDir, "Trùng");
  await fsp.mkdir(duplicateDir, { recursive: true });
  const incomingHash = sha256(buffer);
  for (let index = 2; index <= 999999; index += 1) {
    const duplicateName = buildDuplicateFileName(fileName, index);
    const destination = safeOutputPath(duplicateDir, duplicateName);
    if (fs.existsSync(destination)) {
      const existing = await fsp.readFile(destination);
      if (sha256(existing) === incomingHash) return { status: "exists", duplicateName, destination, index };
      continue;
    }
    await writePdfAtomic(destination, buffer);
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
  const allVisible = buildFilters({ documentScope: "all_visible", readFilter: "invalid-but-ignored", exactDate: "invalid" });
  assert(allVisible.documentScope === "all_visible" && allVisible.readFilter === "all" && !allVisible.titleEnabled && !allVisible.dateEnabled, "16b toàn bộ văn bản bỏ qua mọi bộ lọc");
  assert(String((() => { try { buildFilters({ documentScope: "unknown" }); } catch (error) { return error.message; } return ""; })()).includes("Phạm vi"), "16c chặn phạm vi lạ");

  const parsedSuffixes = parseFileSuffixes(["signed", " .SIGNED.pdf ", ".ldsigned", "lsigned.pdf"]);
  assert(parsedSuffixes.join("|") === ".signed|.ldsigned|.lsigned", "16d chuẩn hóa và loại hậu tố trùng");
  for (const invalidSuffix of ["", ".pdf", "../signed", "*.signed", "[signed]", "signed?"]) {
    assert(String((() => { try { parseFileSuffixes(invalidSuffix); } catch (error) { return error.message; } return ""; })()).length > 0, `16e chặn hậu tố nguy hiểm ${invalidSuffix || "rỗng"}`);
  }
  const suffixPolicy = buildFileNamePolicy({ fileNameMode: "suffix", fileSuffixes: [".signed"] });
  const suffixAccepted = ["Kế Hoạch.signed.pdf", "Thông báo 01.SIGNED.PDF", "CHUACOGIAY_10930_10_20-TBXN.signed.pdf"];
  const suffixRejected = ["Kế Hoạch.pdf", "Kế Hoạch.ldsigned.pdf", "Kế Hoạch.signed.bak.pdf", "Kế Hoạch.signed.pdf.docx", "signed.pdf", ".signed.pdf"];
  assert(suffixAccepted.every((name) => matchPdfFileName(name, suffixPolicy).matched), "16f nhận đúng tên theo hậu tố");
  assert(suffixRejected.every((name) => !matchPdfFileName(name, suffixPolicy).matched), "16g loại đúng tên không khớp hậu tố");
  assert(matchPdfFileName("Kế Hoạch.signed.pdf", suffixPolicy).matched, "16h hỗ trợ Unicode tổ hợp");
  for (const unsafeName of ["../Kế Hoạch.signed.pdf", "CON.signed.pdf", "A?.signed.pdf", "A.signed.pdf "]) {
    assert(matchPdfFileName(unsafeName, suffixPolicy).code === "unsafe_name", `16i chặn tên Windows nguy hiểm ${unsafeName}`);
  }
  const legacyPolicy = buildFileNamePolicy({ communeCode: "10930", allowMissingCommuneCode: true });
  assert(matchPdfFileName("CHUACOGIAY_10930_10_20-TBXN.signed.pdf", legacyPolicy).matched, "16j cấu hình v3 mặc định legacy");
  assert(String((() => { try { buildFileNamePolicy({ fileNameMode: "other" }); } catch (error) { return error.message; } return ""; })()).includes("Chế độ tên file"), "16k chặn chế độ tên lạ");
  const sameUrl = deduplicateCandidates([
    { url: "/files/generated.signed.pdf", name: "generated.signed.pdf", explicitName: false },
    { url: "/files/generated.signed.pdf", name: "Tên thật.pdf", explicitName: true },
  ], suffixPolicy);
  assert(sameUrl.length === 1 && sameUrl[0].name === "Tên thật.pdf" && !sameUrl[0].nameMatch.matched, "16l ưu tiên tên đính kèm thật dù URL có vẻ khớp");

  const makeRecords = (count, offset = 0) => Array.from({ length: count }, (_, index) => ({ VanbanDiId: offset + index + 1, OrderIndex: offset + index + 1, Name: "TB-ĐKĐĐ" }));
  const expectScanError = async (action, messagePart, name) => {
    let errorMessage = "";
    try { await action(); } catch (error) { errorMessage = error.message; }
    assert(errorMessage.includes(messagePart), name);
  };

  const noticeNumbersText = "397, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 543, 735, 777, 778, 799, 813, 836, 865, 867, 889, 903, 912, 1001, 1002, 1575, 1576, 1577, 1578, 1579, 1582, 1583, 1584, 1585, 1586, 1588, 1589, 1590, 1591, 1593, 1594, 1595, 1596, 1597, 1598, 1599, 1600, 1601, 1602, 1603, 1604, 1605, 1606, 1608, 1609, 1610, 1611, 1612, 1613, 1614, 1615, 1616, 1618, 1619, 1621, 1622, 1624, 1625, 1626, 1627, 1628, 1629, 1630, 1632, 1633, 1634, 1635, 1637, 1640, 1645";
  const noticeNumbers = parseNotificationNumbers(noticeNumbersText);
  assert(noticeNumbers.length === 80 && new Set(noticeNumbers).size === 80, "16m parser đọc đúng 80 số thông báo không trùng");
  assert(!noticeNumbers.includes(3970) && extractNotificationNumber("3970/TB-ĐKĐĐ") === 3970, "16n số thông báo không match kiểu substring");

  const records2699 = makeRecords(2699);
  records2699.forEach((record, index) => { record.OrderIndex = 100000 + index; });
  noticeNumbers.forEach((number, index) => { records2699[index].OrderIndex = number; });
  let calls2699 = 0;
  let filterRuns2699 = 0;
  const transferred2699 = [];
  const filters80 = buildFilters({ downloadMode: "numbers", notificationNumbers: noticeNumbersText, readFilter: "all" });
  const scan2699 = await scanDocumentPages(async (start, requestedSize) => {
    calls2699 += 1;
    const records = start >= 2699 ? records2699.slice(2600) : records2699.slice(start, start + requestedSize);
    return { Result: "OK", TotalRecordCount: 2699, Records: records };
  }, { pageSize: 100, onBatch: (batch, page) => {
    transferred2699.push(...batch.map((record) => buildDocumentRecord(record, page)));
    classifyEntries(transferred2699, filters80);
    filterRuns2699 += 1;
  } });
  const matched80 = classifyEntries(transferred2699, filters80).matched;
  assert(scan2699.unique === 2699 && scan2699.pages === 27 && scan2699.rows === 2699 && scan2699.terminationReason === "reported_total", "16o quét đúng 2699 văn bản trong 27 trang");
  assert(calls2699 === 27, "16p không gọi trang 28 lặp sau khi đạt 2699/2699");
  assert(transferred2699.length === 2699 && filterRuns2699 === 27 && matched80.length === 80, "16q chuyển dữ liệu sang lọc và khớp đúng 80 số");

  for (const count of [1001, 2700]) {
    const records = makeRecords(count);
    let calls = 0;
    const result = await scanDocumentPages(async (start, requestedSize) => {
      calls += 1;
      return { Result: "OK", TotalRecordCount: count, Records: records.slice(start, start + requestedSize) };
    }, { pageSize: 100 });
    const expectedPages = Math.ceil(count / 100);
    assert(result.unique === count && result.pages === expectedPages && calls === expectedPages && result.terminationReason === "reported_total", `16r dừng đúng tổng ${count} không gọi trang thừa`);
  }

  const records2500 = makeRecords(2500);
  let repeatedTransferred = 0;
  await expectScanError(() => scanDocumentPages(async (start, requestedSize) => ({
    Result: "OK", TotalRecordCount: 2699,
    Records: start < 2500 ? records2500.slice(start, start + requestedSize) : records2500.slice(2400),
  }), { pageSize: 100, onBatch: (batch) => { repeatedTransferred += batch.length; } }), "chỉ lặp", "16s trang lặp trước 2500/2699 vẫn bị chặn");
  assert(repeatedTransferred === 2500, "16t không chuyển dòng lặp sang bước tải");

  await expectScanError(() => scanDocumentPages(async (start, requestedSize) => ({
    Result: "OK", TotalRecordCount: 2699, Records: start < 2500 ? records2500.slice(start, start + requestedSize) : [],
  }), { pageSize: 100 }), "Quét chưa đủ", "16u trang rỗng trước 2500/2699 vẫn bị chặn");

  const recordsWithoutTotal = makeRecords(205);
  let callsWithoutTotal = 0;
  const scanWithoutTotal = await scanDocumentPages(async (start, requestedSize) => {
    callsWithoutTotal += 1;
    return { Result: "OK", Records: recordsWithoutTotal.slice(start, start + requestedSize) };
  }, { pageSize: 100 });
  assert(scanWithoutTotal.unique === 205 && scanWithoutTotal.pages === 3 && callsWithoutTotal === 4 && scanWithoutTotal.terminationReason === "empty_page", "16v thiếu tổng thì kết thúc bằng trang rỗng");
  await expectScanError(() => scanDocumentPages(async (start, requestedSize) => ({
    Result: "OK", Records: start < 200 ? recordsWithoutTotal.slice(start, start + requestedSize) : recordsWithoutTotal.slice(100, 200),
  }), { pageSize: 100 }), "chỉ lặp", "16w thiếu tổng thì trang lặp vẫn bị chặn");

  const increasingRecords = makeRecords(2699);
  const totalWarnings = [];
  const increasingTotalScan = await scanDocumentPages(async (start, requestedSize) => ({
    Result: "OK", TotalRecordCount: start === 0 ? 2600 : 2699, Records: increasingRecords.slice(start, start + requestedSize),
  }), { pageSize: 100, log: (message) => totalWarnings.push(message) });
  assert(increasingTotalScan.total === 2699 && increasingTotalScan.unique === 2699 && totalWarnings.some((message) => message.includes("2600") && message.includes("2699")), "16x tổng tăng thì giữ giá trị lớn nhất và cảnh báo");

  const mixedPages = [makeRecords(100), makeRecords(100, 50), makeRecords(50, 150)];
  const mixedStarts = [];
  const mixedTransferred = [];
  const mixedScan = await scanDocumentPages(async (start) => {
    mixedStarts.push(start);
    return { Result: "OK", TotalRecordCount: 200, Records: mixedPages[mixedStarts.length - 1] };
  }, { pageSize: 100, onBatch: (batch) => mixedTransferred.push(...batch) });
  assert(mixedStarts.join(",") === "0,100,200" && mixedScan.rows === 250, "16y startIndex tăng theo số dòng API");
  assert(mixedScan.unique === 200 && mixedScan.duplicates === 50 && mixedTransferred.length === 200, "16z trang xen lặp chỉ chuyển mã mới và thống kê đúng");

  await expectScanError(() => scanDocumentPages(async (start) => ({ Result: "OK", Records: [{ VanbanDiId: start + 1 }] }), { pageSize: 1, maxPages: 3 }), "giới hạn an toàn", "16za giới hạn trang chống vòng lặp vô hạn");
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
  console.log("NODE_SELF_TEST_OK: bộ lọc, 80 số thông báo, phân trang tổng hợp lệ/thiếu tổng/tổng thay đổi, khử dòng lặp, Unicode, an toàn tên file và xử lý trùng tên");
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
  const fileNamePolicy = buildFileNamePolicy(config);
  const filters = buildFilters(config);
  const documentScope = filters.documentScope;
  const targetNumberList = filters.numberList;
  const readFilter = filters.readFilter;

  if (!String(config.outputDir ?? "").trim()) throw new Error("Thiếu thư mục lưu PDF.");
  const outputDir = path.resolve(String(config.outputDir).trim());
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
    log("Phạm vi kỹ thuật: danh sách VĂN BẢN ĐI tài khoản được xem (all=false, status=0); không phải danh sách đã upload/dự thảo. Không tự đổi endpoint hoặc quyền xem.");
    log(`Phạm vi người dùng chọn: ${documentScope === "all_visible" ? "TOÀN BỘ VĂN BẢN ĐI ĐƯỢC QUYỀN XEM; bỏ qua các bộ lọc và trạng thái xem" : "THEO BỘ LỌC"}.`);
    log(`Chế độ tên file: ${fileNamePolicy.description}. Đây là lọc tên, không xác thực chữ ký số.`);
    if (documentScope === "filtered") log("Cách kết hợp bộ lọc: AND giữa các nhóm đã bật; OR giữa nhiều giá trị trong cùng một nhóm.");
    if (fileNamePolicy.mode === "legacy") {
      log(`Mã xã dùng để kiểm tra tên PDF: ${fileNamePolicy.communeCode}`);
      log(`Nhận tên thiếu mã xã: ${fileNamePolicy.allowMissingCommuneCode ? "CÓ; giữ nguyên tên, không tự thêm mã xã" : "KHÔNG"}.`);
    }
    if (documentScope === "filtered") log(`Bộ lọc chữ đậm: ${readFilter === "unread" ? "CHỈ CHỮ ĐẬM" : readFilter === "read" ? "CHỈ KHÔNG ĐẬM" : "TẤT CẢ"}`);
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
    log(`ĐỐI SOÁT QUÉT: ${scan.rows} dòng API = ${scan.duplicates} dòng lặp + ${scan.unique} mã văn bản riêng biệt; tổng HPNet: ${scan.total ?? "không cung cấp"}; ${scan.pages} trang dữ liệu; kết thúc: ${scan.terminationReason}.`);
    log(`ĐỐI SOÁT LỌC: ${recordEntries.length} văn bản riêng biệt = ${classified.excluded} văn bản bị lọc + ${uniqueEntries.length} văn bản khớp.`);
    for (const [reason, count] of classified.reasonCounts) log(`[BỊ LỌC] ${count}: ${reason}.`);
    log("Một văn bản có thể không khớp nhiều bộ lọc; không cộng các lý do để tính tổng. Xem CSV ĐỐI SOÁT để biết trích yếu, ngày gốc và lý do của TỪNG văn bản.");
    if (filters.dateEnabled) log("Lưu ý: lọc NGÀY VĂN BẢN trên HPNet, không phải ngày bạn upload. Muốn đối chiếu nhiều ngày, mở rộng khoảng ngày hoặc bỏ chọn bộ lọc ngày.");
    const foundNumbers = new Set(uniqueEntries.map((entry) => entry.notificationNumber).filter((value) => value !== null));
    const notFoundNumbers = targetNumberList.filter((number) => !foundNumbers.has(number));
    log(`Có ${uniqueEntries.length} văn bản khớp bộ lọc.`);
    if (filters.notificationEnabled && notFoundNumbers.length) log(`[KHÔNG TÌM THẤY SAU KHI ÁP DỤNG TOÀN BỘ BỘ LỌC] ${notFoundNumbers.join(", ")}`);

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
        if (detail.file) candidates.push({ url: detail.file, name: fileNameFromUrl(detail.file), explicitName: false });
        for (const item of Array.isArray(detail.files) ? detail.files : []) {
          const fileUrl = item.FilePath || item.filePath || item.Path || item.path;
          const explicitFileName = item.FileName || item.fileName;
          const fileName = explicitFileName || fileNameFromUrl(fileUrl);
          if (fileUrl) candidates.push({ url: fileUrl, name: fileName, explicitName: Boolean(explicitFileName) });
        }

        const uniqueCandidates = deduplicateCandidates(candidates, fileNamePolicy);
        if (!uniqueCandidates.length) {
          noFiles += 1;
          if (notificationNumber !== null) errorNumbers.add(notificationNumber);
          log(`[KHÔNG CÓ FILE] ${label}: HPNet không trả liên kết đính kèm.`);
          addResult([notificationNumber ?? "", label, entry.pageNumber, "", "", "KHÔNG CÓ FILE", "Kiểm tra file đính kèm/quyền xem trên HPNet; đây không phải lỗi tên file"]);
          continue;
        }

        const validCandidates = uniqueCandidates.filter((candidate) => candidate.nameMatch.matched);
        const invalidCandidates = uniqueCandidates.filter((candidate) => !candidate.nameMatch.matched);
        for (const candidate of invalidCandidates) {
          const displayName = candidate.name || "không có tên file";
          const status = candidate.nameMatch.code === "suffix_mismatch" ? "KHÔNG KHỚP HẬU TỐ" : candidate.nameMatch.code === "unsafe_name" ? "TÊN FILE KHÔNG AN TOÀN" : "FILE KHÔNG KHỚP MẪU";
          addResult([notificationNumber ?? "", label, entry.pageNumber, displayName, "", status, candidate.nameMatch.reason]);
          log(`[${status}] ${label} / ${displayName}: ${candidate.nameMatch.reason}.`);
        }
        if (!validCandidates.length) {
          badFormat += 1;
          const names = uniqueCandidates.map((item) => item.name).filter(Boolean).join(", ") || "không có file";
          log(`[KHÔNG CÓ FILE KHỚP QUY TẮC TÊN] ${label}: ${names}`);
          if (notificationNumber !== null) errorNumbers.add(notificationNumber);
          continue;
        }

        if (validCandidates.every((candidate) => seenUrls.has(candidate.url))) sharedFiles += 1;

        for (const candidate of validCandidates) {
          const safeName = candidate.nameMatch.safeName;
          const destination = safeOutputPath(outputDir, safeName);
          if (seenUrls.has(candidate.url)) {
            addResult([notificationNumber ?? "", label, entry.pageNumber, safeName, "", "BỎ QUA TRÙNG", "Cùng liên kết đã được tải hoặc kiểm tra nội dung thành công trong lần chạy này"]);
            if (notificationNumber !== null) existingNumbers.add(notificationNumber);
            continue;
          }
          if (fileNamePolicy.mode === "legacy" && !fileNamePolicy.strictPattern.test(candidate.name)) log(`[NGOẠI LỆ THIẾU MÃ XÃ] ${safeName}: chấp nhận và giữ nguyên tên.`);
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

          await writePdfAtomic(destination, buffer);
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
    log(`Tổng dòng API đã đọc: ${scan.rows}; số trang dữ liệu: ${scan.pages}; lý do kết thúc: ${scan.terminationReason}.`);
    log(`Văn bản riêng biệt theo mã HPNet: ${scan.unique}; dòng lặp đã loại: ${scan.duplicates}; bị lọc: ${classified.excluded}.`);
    log(`Văn bản thuộc phạm vi xử lý: ${uniqueEntries.length}`);
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
    log(`Văn bản không có file khớp quy tắc tên đã chọn: ${badFormat}`);
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

module.exports = {
  buildValidPdfNamePattern, normalizeDocumentScope, parseFileSuffixes, buildFileNamePolicy, validateWindowsFileName,
  matchPdfFileName, deduplicateCandidates, buildFilters, buildDocumentRecord, recordFilterReasons, recordMatchesFilters,
  scanDocumentPages, classifyEntries, auditRows, csvCell, safeOutputPath, writePdfAtomic, main,
};

if (require.main === module) {
  main().catch((error) => {
    fail(error.stack || error.message || String(error));
  });
}
