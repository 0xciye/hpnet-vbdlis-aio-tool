const fs = require("node:fs");
const fsp = require("node:fs/promises");
const path = require("node:path");

const MAIN_URL = "https://qlvb.hpnet.vn/?action=901";
const LIST_URL = "https://qlvb.hpnet.vn/vpdt/dungchung/DuthaoVanbanQuanhuyenV2/VanbanDiListDuthao.aspx";

function cleanJsonText(text) {
  return String(text).replace(/^\uFEFF/, "");
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

function htmlDecodeSimple(value) {
  return String(value ?? "")
    .replace(/&nbsp;|&#160;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">");
}

function normalizeText(value) {
  return htmlDecodeSimple(value)
    .normalize("NFC")
    .replace(/<[^>]*>/g, " ")
    .replace(/[–—−]/g, "-")
    .replace(/\s+/g, " ")
    .trim()
    .toLocaleUpperCase("vi-VN");
}

function normalizePersonName(value) {
  return normalizeText(value);
}

function expectedStatusFor(submitter) {
  return `Đang trình [${String(submitter ?? "").trim()}] duyệt`;
}

function findUniqueNormalizedPerson(items, targetName) {
  const target = normalizePersonName(targetName);
  if (!target) throw new Error("Tên người cần tìm đang trống.");
  const matches = items
    .map((item, index) => ({ index, text: String(item?.text ?? item ?? "").replace(/\s+/g, " ").trim(), disabled: Boolean(item?.disabled) }))
    .filter((item) => !item.disabled && normalizePersonName(item.text) === target);
  if (!matches.length) {
    const available = items.map((item) => String(item?.text ?? item ?? "").replace(/\s+/g, " ").trim()).filter(Boolean).slice(0, 20);
    throw new Error(`Không tìm thấy người duyệt: ${String(targetName).trim()} trong danh sách hiện tại trên hệ thống.${available.length ? ` Danh sách đang thấy: ${available.join(" | ")}` : ""}`);
  }
  if (matches.length > 1) {
    throw new Error(`Có ${matches.length} người trùng tên ${String(targetName).trim()} trong danh sách. Công cụ dừng để không chọn nhầm; vui lòng kiểm tra lại trên HPNet.`);
  }
  return matches[0];
}

async function selectPersonExact(selectLocator, targetName, log) {
  const options = await selectLocator.locator("option").evaluateAll((nodes) => nodes.map((node) => ({
    text: node.textContent || "",
    disabled: Boolean(node.disabled),
  })));
  const match = findUniqueNormalizedPerson(options, targetName);
  await selectLocator.selectOption({ index: match.index });
  const selectedText = String(await selectLocator.locator("option:checked").textContent() ?? "").replace(/\s+/g, " ").trim();
  if (normalizePersonName(selectedText) !== normalizePersonName(targetName)) {
    throw new Error(`HPNet không giữ đúng lựa chọn người duyệt ${String(targetName).trim()}.`);
  }
  log(`[MATCH NGƯỜI] Yêu cầu: ${String(targetName).trim()} | Trên HPNet: ${selectedText}`);
  return selectedText;
}

function unwrapPayload(data) {
  let value = data;
  if (value && Object.prototype.hasOwnProperty.call(value, "d")) value = value.d;
  if (typeof value === "string") value = JSON.parse(value);
  return value;
}

function timestamp() {
  const d = new Date();
  const two = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}${two(d.getMonth() + 1)}${two(d.getDate())}_${two(d.getHours())}${two(d.getMinutes())}${two(d.getSeconds())}`;
}

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function getRecordId(record) {
  return String(record?.VanbanDiId ?? record?.VanBanDiId ?? record?.ID ?? record?.Id ?? "").trim();
}

function exactCandidate(record, exactTitle, expectedStatus) {
  return getRecordId(record)
    && normalizeText(record?.TrichYeu) === normalizeText(exactTitle)
    && normalizeText(record?.TinhTrangXuly) === normalizeText(expectedStatus);
}

function runSelfTest() {
  const title = "THÔNG BÁO KẾT QUẢ XÁC NHẬN ĐĂNG KÝ ĐẤT ĐAI - CẨM ĐÔNG";
  const submitter = "  Nguyễn   Văn A ";
  const expectedStatus = expectedStatusFor(submitter);
  const good = { VanbanDiId: "abc", TrichYeu: `  ${title.toLowerCase()}  `, TinhTrangXuly: "Đang trình [NGUYỄN VĂN A] duyệt" };
  if (!exactCandidate(good, title, expectedStatus)) throw new Error("Self-test: không nhận đúng trích yếu/tình trạng động.");
  if (exactCandidate({ ...good, TrichYeu: `${title} 1` }, title, expectedStatus)) throw new Error("Self-test: nhận nhầm trích yếu gần giống.");
  if (exactCandidate({ ...good, TinhTrangXuly: "Đã duyệt" }, title, expectedStatus)) throw new Error("Self-test: nhận nhầm văn bản đã duyệt.");
  if (normalizePersonName("  Nguyễn   Văn A ") !== normalizePersonName("nguyễn văn a")) throw new Error("Self-test: chuẩn hóa tên không đúng.");
  if (findUniqueNormalizedPerson(["Trần Thị B", "Nguyễn Văn A"], " nguyễn  văn a ").index !== 1) throw new Error("Self-test: không match đúng tên động.");
  if (!String((() => { try { findUniqueNormalizedPerson(["Nguyễn Văn A"], "Người Không Có"); } catch (error) { return error.message; } return ""; })()).includes("Không tìm thấy")) throw new Error("Self-test: tên không tồn tại không dừng an toàn.");
  if (!String((() => { try { findUniqueNormalizedPerson(["Nguyễn Văn A", "NGUYỄN VĂN A"], "Nguyễn Văn A"); } catch (error) { return error.message; } return ""; })()).includes("trùng tên")) throw new Error("Self-test: tên trùng không dừng an toàn.");
  if (!isHpnetUrl("https://qlvb.hpnet.vn/?action=901") || !isHpnetUrl("https://qlvb2.hpnet.vn/Login.aspx")) throw new Error("Self-test: nhận diện máy chủ HPNet không đúng.");
  if (isHpnetUrl("https://id.vneid.gov.vn/oauth2/authorize") || isHpnetLoginUrl("https://id.vneid.gov.vn/Login.aspx")) throw new Error("Self-test: nhận nhầm trang VNeID là HPNet.");
  if (!isHpnetLoginUrl("https://qlvb.hpnet.vn/Login.aspx?ReturnUrl=%2f")) throw new Error("Self-test: không nhận ra trang đăng nhập HPNet.");
  console.log("NODE_SELF_TEST_OK");
}

async function queryRecords(context, { key = "", allPages = true, pageSize = 100, onPage = null } = {}) {
  let startIndex = 0;
  let total = null;
  const records = [];
  do {
    const response = await context.request.post(`${LIST_URL}?jtStartIndex=${startIndex}&jtPageSize=${pageSize}`, {
      form: { key, all: "false", status: "0" },
      timeout: 60000,
    });
    if (!response.ok()) throw new Error(`Không đọc được danh sách VB dự thảo: HTTP ${response.status()}.`);
    const contentType = response.headers()["content-type"] || "";
    if (/text\/html/i.test(contentType)) throw new Error("Phiên đăng nhập HPNet đã hết hạn.");
    const payload = unwrapPayload(await response.json());
    if (payload.Result && String(payload.Result).toUpperCase() !== "OK") {
      throw new Error(payload.Message || "HPNet trả về lỗi khi đọc danh sách VB dự thảo.");
    }
    const batch = Array.isArray(payload.Records) ? payload.Records : [];
    total = Number(payload.TotalRecordCount ?? batch.length);
    records.push(...batch);
    startIndex += batch.length;
    if (onPage) onPage(Math.min(startIndex, total), total);
    if (!allPages || !batch.length) break;
  } while (startIndex < total);
  return records;
}

async function ensureLoggedIn(page, context, log) {
  await page.goto(MAIN_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.bringToFront();
  const deadline = Date.now() + 20 * 60 * 1000;
  let announced = false;
  while (true) {
    const pages = context.pages();
    const ready = pages.find((item) => isHpnetUrl(item.url()) && !isHpnetLoginUrl(item.url()) && /[?&]action=901(?:&|$)/i.test(item.url()));
    if (ready && await ready.locator("#SoVanbanDiTableContainer").count()) return ready;

    if (!announced) {
      log("Hãy chọn Đăng nhập bằng VNeID trong Edge và hoàn tất xác thực. Công cụ sẽ tự tiếp tục khi quay lại HPNet.");
      announced = true;
    }
    if (Date.now() > deadline) throw new Error("Hết thời gian chờ đăng nhập VNeID/HPNet (20 phút).");

    const returned = pages.find((item) => isHpnetUrl(item.url()) && !isHpnetLoginUrl(item.url()));
    if (returned) {
      page = returned;
      if (!/[?&]action=901(?:&|$)/i.test(page.url())) {
        await page.goto(MAIN_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
      }
    } else {
      const authPage = pages.find((item) => !isHpnetUrl(item.url()) && !/^about:blank$/i.test(item.url()));
      if (authPage) page = authPage;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

async function findRecordById(context, id, exactTitle) {
  const byTitle = await queryRecords(context, { key: exactTitle, allPages: true, pageSize: 100 });
  let record = byTitle.find((item) => getRecordId(item) === id);
  if (record) return record;
  const all = await queryRecords(context, { key: "", allPages: true, pageSize: 100 });
  return all.find((item) => getRecordId(item) === id) || null;
}

async function waitForStatusChange(context, id, exactTitle, expectedStatus, attempts = 12) {
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const record = await findRecordById(context, id, exactTitle);
    if (!record) return { changed: true, newStatus: "Không còn trong danh sách đang xử lý" };
    const newStatus = String(record.TinhTrangXuly ?? "").trim();
    if (normalizeText(newStatus) !== normalizeText(expectedStatus)) return { changed: true, newStatus };
    if (attempt < attempts) await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  return { changed: false, newStatus: expectedStatus };
}

async function approveOne(page, context, candidate, exactTitle, expectedStatus, nextReviewer, log) {
  const id = String(candidate.id);
  const current = await findRecordById(context, id, exactTitle);
  if (!current) return { result: "BỎ QUA", newStatus: "Không còn trong danh sách", note: "Văn bản không còn tồn tại trong danh sách trước khi duyệt." };
  if (normalizeText(current.TrichYeu) !== normalizeText(exactTitle)) {
    return { result: "BỎ QUA", newStatus: current.TinhTrangXuly, note: "Trích yếu đã thay đổi; không duyệt." };
  }
  if (normalizeText(current.TinhTrangXuly) !== normalizeText(expectedStatus)) {
    return { result: "BỎ QUA", newStatus: current.TinhTrangXuly, note: "Tình trạng không còn đúng; có thể văn bản đã được duyệt." };
  }

  await page.goto(MAIN_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForFunction(() => typeof window.TrinhDuyetVanbanDi === "function", null, { timeout: 30000 });
  await page.evaluate((recordId) => window.TrinhDuyetVanbanDi(recordId), id);
  const modal = page.locator("#myModal");
  await modal.waitFor({ state: "visible", timeout: 30000 });
  const frame = page.frameLocator("iframe#frm");
  const openApproval = frame.locator('button[data-id="btnDuyenTrinh"]');
  await openApproval.waitFor({ state: "visible", timeout: 30000 });
  await openApproval.click();

  const approvalForm = frame.locator("#formTrinhduyet");
  await approvalForm.waitFor({ state: "visible", timeout: 15000 });
  const reviewer = frame.locator("#dataLanhdaoId");
  const matchedReviewer = await selectPersonExact(reviewer, nextReviewer, log);

  let dialogText = "";
  const dialogHandler = async (dialog) => {
    dialogText = dialog.message();
    try { await dialog.accept(); } catch {}
  };
  page.on("dialog", dialogHandler);
  try {
    log(`[GỬI DUYỆT] ${id} -> ${matchedReviewer}`);
    await frame.locator('#formTrinhduyet input#btnDuyenTrinh[type="submit"]').click({ noWaitAfter: true, timeout: 30000 });
    await Promise.race([
      modal.waitFor({ state: "hidden", timeout: 45000 }).catch(() => null),
      page.waitForTimeout(45000),
    ]);
  } finally {
    page.off("dialog", dialogHandler);
  }

  if (/lỗi|không thể|vui lòng|thất bại/i.test(normalizeText(dialogText))) {
    throw new Error(`HPNet báo lỗi: ${dialogText}`);
  }
  const verification = await waitForStatusChange(context, id, exactTitle, expectedStatus);
  if (!verification.changed) {
    throw new Error("Đã bấm duyệt nhưng tình trạng chưa đổi. Công cụ dừng để không bấm lặp lại văn bản này.");
  }
  return { result: "ĐÃ DUYỆT", newStatus: verification.newStatus, matchedReviewer, note: dialogText || `Đã chuyển duyệt tiếp cho ${matchedReviewer}.` };
}

async function main() {
  if (process.argv.includes("--self-test")) {
    runSelfTest();
    return;
  }
  const configPath = process.argv[2];
  if (!configPath) throw new Error("Thiếu tệp cấu hình.");
  const config = JSON.parse(cleanJsonText(await fsp.readFile(configPath, "utf8")));
  const mode = String(config.mode ?? "scan").toLowerCase();
  if (!new Set(["scan", "approve"]).has(mode)) throw new Error("Chế độ không hợp lệ.");
  const exactTitle = String(config.exactTitle ?? "").trim();
  if (!exactTitle) throw new Error("Trích yếu đang trống.");
  const submitter = String(config.submitter ?? "").replace(/\s+/g, " ").trim();
  const nextReviewer = String(config.nextReviewer ?? "").replace(/\s+/g, " ").trim();
  if (!normalizePersonName(submitter)) throw new Error("Vui lòng nhập Người trình duyệt hiện tại.");
  if (!normalizePersonName(nextReviewer)) throw new Error("Vui lòng nhập Người nhận chuyển tiếp.");
  const expectedStatus = expectedStatusFor(submitter);

  const toolRoot = path.dirname(configPath);
  const scanReportPath = path.join(toolRoot, "ket_qua_quet_moi_nhat.json");
  const logDir = path.join(toolRoot, "nhat_ky");
  await fsp.mkdir(logDir, { recursive: true });
  const stamp = timestamp();
  const textLogPath = path.join(logDir, `NHAT_KY_${mode === "scan" ? "QUET" : "DUYET"}_${stamp}.txt`);
  const csvLogPath = path.join(logDir, `NHAT_KY_${mode === "scan" ? "QUET" : "DUYET"}_${stamp}.csv`);
  const logLines = [];
  const resultRows = [];
  const log = (message) => {
    const line = `[${new Date().toLocaleString("vi-VN")}] ${message}`;
    logLines.push(line);
    console.log(line);
  };

  const modulesRoot = process.env.HPNET_NODE_MODULES;
  const edgeExe = process.env.HPNET_EDGE_EXE;
  if (!modulesRoot || !edgeExe) throw new Error("Không xác định được bộ chạy trình duyệt.");
  const { chromium } = require(path.join(modulesRoot, "playwright"));
  const profileDir = path.join(toolRoot, "du_lieu_dang_nhap_vneid");
  const context = await chromium.launchPersistentContext(profileDir, {
    executablePath: edgeExe,
    headless: false,
    acceptDownloads: false,
    viewport: null,
    args: ["--start-maximized"],
  });

  let page = context.pages()[0] || await context.newPage();
  let fatalError = null;
  try {
    log(`Chế độ: ${mode === "scan" ? "CHỈ QUÉT - KHÔNG DUYỆT" : "DUYỆT CÁC MỤC ĐÃ XÁC NHẬN"}`);
    log(`Trích yếu khớp chính xác: ${exactTitle}`);
    log(`Người trình duyệt hiện tại: ${submitter}`);
    log(`Tình trạng bắt buộc: ${expectedStatus}`);
    log(`Người nhận chuyển tiếp: ${nextReviewer}`);
    page = await ensureLoggedIn(page, context, log);
    log("Đăng nhập HPNet thành công. Đang quét toàn bộ các trang...");
    const records = await queryRecords(context, {
      key: "",
      allPages: true,
      pageSize: 100,
      onPage: (done, total) => log(`Đã kiểm tra ${done}/${total} văn bản...`),
    });
    const candidates = records.filter((record) => exactCandidate(record, exactTitle, expectedStatus)).map((record) => ({
      id: getRecordId(record),
      title: String(record.TrichYeu ?? "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim(),
      status: String(record.TinhTrangXuly ?? "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim(),
      createDate: String(record.CreateDate ?? ""),
    }));
    const unique = [];
    const seen = new Set();
    for (const item of candidates) {
      if (!seen.has(item.id)) { seen.add(item.id); unique.push(item); }
    }
    log(`Tìm thấy ${unique.length} văn bản khớp chính xác cả trích yếu và tình trạng.`);

    if (mode === "scan") {
      const report = {
        createdAt: new Date().toISOString(), exactTitle, expectedStatus,
        submitter, nextReviewer, totalRecordsScanned: records.length,
        candidateCount: unique.length, candidates: unique,
      };
      const temp = `${scanReportPath}.tmp`;
      await fsp.writeFile(temp, JSON.stringify(report, null, 2), "utf8");
      await fsp.rename(temp, scanReportPath).catch(async () => {
        await fsp.rm(scanReportPath, { force: true });
        await fsp.rename(temp, scanReportPath);
      });
      for (const item of unique) resultRows.push([new Date().toISOString(), resultRows.length + 1, item.id, item.title, item.status, submitter, nextReviewer, "", "KHỚP - CHƯA DUYỆT", "", item.createDate]);
      log("Đã quét xong. Chưa bấm duyệt bất kỳ văn bản nào.");
      console.log(`SCAN_REPORT=${scanReportPath}`);
    } else {
      const report = JSON.parse(cleanJsonText(await fsp.readFile(scanReportPath, "utf8")));
      if (normalizeText(report.exactTitle) !== normalizeText(exactTitle)
        || normalizeText(report.expectedStatus) !== normalizeText(expectedStatus)
        || normalizePersonName(report.submitter) !== normalizePersonName(submitter)
        || normalizePersonName(report.nextReviewer) !== normalizePersonName(nextReviewer)) {
        throw new Error("Kết quả quét không còn khớp cấu hình hiện tại. Hãy quét lại trước khi duyệt.");
      }
      const approvedIds = new Set((report.candidates || []).map((item) => String(item.id)));
      const approvedCandidates = unique.filter((item) => approvedIds.has(item.id));
      log(`Số mục đã xác nhận ở lần quét: ${approvedIds.size}. Số mục vẫn đủ điều kiện lúc này: ${approvedCandidates.length}.`);
      let completed = 0;
      for (let index = 0; index < approvedCandidates.length; index += 1) {
        const candidate = approvedCandidates[index];
        log(`(${index + 1}/${approvedCandidates.length}) Kiểm tra lại ${candidate.id}`);
        const result = await approveOne(page, context, candidate, exactTitle, expectedStatus, nextReviewer, log);
        resultRows.push([new Date().toISOString(), resultRows.length + 1, candidate.id, candidate.title, candidate.status, submitter, nextReviewer, result.matchedReviewer || "", result.result, result.newStatus, result.note]);
        if (result.result === "ĐÃ DUYỆT") completed += 1;
        log(`[${result.result}] ${candidate.id} - ${result.newStatus}`);
      }
      for (const item of report.candidates || []) {
        if (!unique.some((current) => current.id === String(item.id))) {
          resultRows.push([new Date().toISOString(), resultRows.length + 1, item.id, item.title, item.status, submitter, nextReviewer, "", "BỎ QUA", "Đã đổi tình trạng hoặc không còn trong danh sách", "Không bấm duyệt."]);
        }
      }
      log(`Hoàn tất. Đã duyệt và xác nhận đổi tình trạng: ${completed}/${approvedIds.size}.`);
      log("Công cụ tự dừng vì đã xử lý hết các mục trong lần quét được xác nhận.");
    }
  } catch (error) {
    fatalError = error;
    log(`[LỖI DỪNG AN TOÀN] ${error.message}`);
  } finally {
    const rows = [["Thời gian", "STT", "Mã văn bản", "Trích yếu", "Tình trạng trước", "Người trình duyệt", "Người nhận chuyển tiếp", "Người thực tế được match", "Kết quả", "Tình trạng sau", "Ghi chú"], ...resultRows];
    await fsp.writeFile(textLogPath, `\uFEFF${logLines.join("\r\n")}\r\n`, "utf8");
    await fsp.writeFile(csvLogPath, `\uFEFF${rows.map((row) => row.map(csvCell).join(",")).join("\r\n")}\r\n`, "utf8");
    console.log(`Nhật ký TXT: ${textLogPath}`);
    console.log(`Nhật ký CSV: ${csvLogPath}`);
    await context.close();
  }
  if (fatalError) throw fatalError;
}

main().catch((error) => {
  console.error(`[LỖI] ${error.stack || error.message || String(error)}`);
  process.exitCode = 1;
});
