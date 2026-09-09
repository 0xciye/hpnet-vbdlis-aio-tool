const fs = require("node:fs");
const fsp = require("node:fs/promises");
const path = require("node:path");
const crypto = require("node:crypto");

const MAIN_URL = "https://qlvb.hpnet.vn/?action=901";
const FORM_URL = "https://qlvb.hpnet.vn/vpdt/dungchung/DuthaoVanbanQuanhuyenV2/DuthaoVanbandi.aspx";
const LIST_URL = "https://qlvb.hpnet.vn/vpdt/dungchung/DuthaoVanbanQuanhuyenV2/VanbanDiListDuthao.aspx";

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

function findUniqueNormalizedPerson(items, targetName) {
  const target = normalizePersonName(targetName);
  if (!target) throw new Error("Tên người duyệt đang trống.");
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

function documentKey(fileName) {
  let name = path.basename(String(fileName ?? "")).normalize("NFC");
  name = name.replace(/\.(?:docx?|pdf)$/i, "");
  name = name.replace(/\.(?:ld)?signed$/i, "");
  return normalizeText(name);
}

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function recordContainsKey(record, key) {
  if (!key) return false;
  const text = normalizeText(JSON.stringify(record ?? {}));
  const pattern = new RegExp(`(^|[^\\p{L}\\p{N}_-])${escapeRegex(key)}(?=$|[^\\p{L}\\p{N}_-])`, "u");
  return pattern.test(text);
}

function recordMatchesFile(record, file) {
  if (!recordContainsKey(record, file.key)) return false;
  const abstract = normalizeText(file.abstract);
  if (!abstract) return true;
  const title = normalizeText(record?.TrichYeu);
  if (title === abstract) return true;
  if (!title.startsWith(abstract)) return false;
  const suffix = title.slice(abstract.length).trim();
  return suffix === file.key || suffix.startsWith(`${file.key}.`);
}

function parseHpnetDate(value) {
  const text = String(value ?? "").trim();
  const asp = text.match(/^\/Date\((\d+)/i);
  if (asp) return Number(asp[1]);
  const vi = text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2}))?/);
  if (vi) return new Date(Number(vi[3]), Number(vi[2]) - 1, Number(vi[1]), Number(vi[4] || 0), Number(vi[5] || 0)).getTime();
  const parsed = Date.parse(text);
  return Number.isFinite(parsed) ? parsed : null;
}

function recordIsCurrentVersion(record, file, reuploadModified) {
  if (!recordMatchesFile(record, file)) return false;
  if (!reuploadModified) return true;
  const created = parseHpnetDate(record?.CreateDate);
  if (created === null) return false;
  // HPNet chỉ hiển thị thời gian đến phút, nên cho phép sai số 2 phút.
  return created >= file.mtimeMs - 2 * 60 * 1000;
}

async function sha256File(filePath) {
  const data = await fsp.readFile(filePath);
  return crypto.createHash("sha256").update(data).digest("hex");
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
  let text = String(value ?? "");
  if (/^[\s\uFEFF]*[=+@-]/u.test(text)) text = `'${text}`;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function runSelfTest() {
  const local = documentKey("CHUACOGIAY_10930_112_54-TBXN.docx");
  const variants = [
    "CHUACOGIAY_10930_112_54-TBXN.doc",
    "CHUACOGIAY_10930_112_54-TBXN.pdf",
    "CHUACOGIAY_10930_112_54-TBXN.signed.pdf",
    "CHUACOGIAY_10930_112_54-TBXN.ldsigned.pdf",
  ];
  if (!variants.every((item) => documentKey(item) === local)) {
    throw new Error("Self-test: khóa chống trùng không đồng nhất giữa DOC/DOCX/PDF đã ký.");
  }
  if (documentKey("CHUACAPGIAY_10930_112_54-TBXN.pdf") !== documentKey("CHUACAPGIAY_10930_112_54-TBXN.docx")) {
    throw new Error("Self-test: chưa hỗ trợ tiền tố CHUACAPGIAY.");
  }
  const record = { TrichYeu: "THÔNG BÁO<br/>CHUACOGIAY_10930_112_54-TBXN.ldsigned.pdf" };
  if (!recordContainsKey(record, local)) throw new Error("Self-test: không nhận ra file đã có.");
  if (recordContainsKey(record, documentKey("CHUACOGIAY_10930_112_5-TBXN.docx"))) {
    throw new Error("Self-test: nhận nhầm tên gần giống.");
  }
  if (normalizePersonName("  Nguyễn   Văn A ") !== normalizePersonName("nguyễn văn a")) throw new Error("Self-test: chuẩn hóa tên không đúng.");
  if (findUniqueNormalizedPerson(["Trần Thị B", "Nguyễn Văn A"], " nguyễn  văn a ").index !== 1) throw new Error("Self-test: không match đúng người duyệt động.");
  if (!String((() => { try { findUniqueNormalizedPerson(["Nguyễn Văn A"], "Người Không Có"); } catch (error) { return error.message; } return ""; })()).includes("Không tìm thấy")) throw new Error("Self-test: tên không tồn tại không dừng an toàn.");
  if (!String((() => { try { findUniqueNormalizedPerson(["Nguyễn Văn A", "NGUYỄN VĂN A"], "Nguyễn Văn A"); } catch (error) { return error.message; } return ""; })()).includes("trùng tên")) throw new Error("Self-test: tên trùng không dừng an toàn.");
  const oldRecord = { TrichYeu: `${local}.pdf`, CreateDate: "29/08/2026 17:04" };
  const newRecord = { TrichYeu: `${local}.pdf`, CreateDate: "30/08/2026 09:10" };
  const testFile = { key: local, mtimeMs: new Date(2026, 7, 30, 8, 56).getTime() };
  if (recordIsCurrentVersion(oldRecord, testFile, true)) throw new Error("Self-test: bản cũ chặn nhầm bản đã sửa.");
  if (!recordIsCurrentVersion(newRecord, testFile, true)) throw new Error("Self-test: không nhận ra bản mới đã up.");
  const scopedFile = { ...testFile, abstract: "Trích yếu A" };
  if (recordIsCurrentVersion({ TrichYeu: `Trích yếu B ${local}.pdf`, CreateDate: "30/08/2026 09:10" }, scopedFile, false)) {
    throw new Error("Self-test: nhận nhầm bản ghi cùng tên nhưng khác trích yếu.");
  }
  if (!recordIsCurrentVersion({ TrichYeu: `Trích yếu A ${local}.pdf`, CreateDate: "30/08/2026 09:10" }, scopedFile, false)) {
    throw new Error("Self-test: không nhận ra bản ghi đúng tên và trích yếu.");
  }
  if (recordIsCurrentVersion({ TrichYeu: `Trích yếu A bổ sung ${local}.pdf`, CreateDate: "30/08/2026 09:10" }, scopedFile, false)) {
    throw new Error("Self-test: nhận nhầm trích yếu là tiền tố của trích yếu khác.");
  }
  if (!isHpnetUrl("https://qlvb.hpnet.vn/?action=901") || isHpnetUrl("https://id.vneid.gov.vn/oauth2/authorize")) throw new Error("Self-test: nhận diện HPNet/VNeID không đúng.");
  if (!isHpnetLoginUrl("https://qlvb.hpnet.vn/Login.aspx?ReturnUrl=%2f") || isHpnetLoginUrl("https://id.vneid.gov.vn/Login.aspx")) throw new Error("Self-test: nhận diện trang đăng nhập không đúng.");
  if (!csvCell("=HYPERLINK(1)").startsWith("'=")) throw new Error("Self-test: CSV chưa chặn công thức Excel.");
  console.log("NODE_SELF_TEST_OK");
}

async function listWordFiles(folder) {
  const entries = await fsp.readdir(folder, { withFileTypes: true });
  const collator = new Intl.Collator("vi", { numeric: true, sensitivity: "base" });
  const files = [];
  for (const entry of entries) {
    if (!entry.isFile() || entry.name.startsWith("~$")) continue;
    if (!/\.docx?$/i.test(entry.name)) continue;
    const fullPath = path.join(folder, entry.name);
    const stat = await fsp.stat(fullPath);
    files.push({ name: entry.name, fullPath, size: stat.size, mtimeMs: stat.mtimeMs, key: documentKey(entry.name) });
  }
  files.sort((a, b) => collator.compare(a.name, b.name));
  return files;
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
      throw new Error(payload.Message || "HPNet trả về lỗi danh sách VB dự thảo.");
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

async function waitForRecord(context, page, file, reuploadModified, attempts = 8) {
  const searchTerms = [file.key, file.name];
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    for (const term of searchTerms) {
      const found = await queryRecords(context, { key: term, allPages: false, pageSize: 100 });
      if (found.some((record) => recordIsCurrentVersion(record, file, reuploadModified))) return true;
    }
    const newest = await queryRecords(context, { key: "", allPages: false, pageSize: 100 });
    if (newest.some((record) => recordIsCurrentVersion(record, file, reuploadModified))) return true;
    await page.waitForTimeout(attempt < 4 ? 1000 : 2000);
  }
  return false;
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

async function submitOne(page, context, file, abstract, reviewerLevel1, reuploadModified, log) {
  let lastDialog = "";
  let modalClosed = false;
  let selectedLeader = "";
  const dialogHandler = async (dialog) => {
    lastDialog = dialog.message();
    try { await dialog.accept(); } catch {}
  };
  page.on("dialog", dialogHandler);
  let submitError = null;
  try {
    await page.goto(MAIN_URL, { waitUntil: "domcontentloaded", timeout: 60000 });
    const createButton = page.locator("a.btn.btn-danger", { hasText: "Dự thảo VB" }).first();
    await createButton.waitFor({ state: "visible", timeout: 30000 });
    await createButton.click();

    const frame = page.frameLocator("iframe#frm");
    const modal = page.locator("#myModal");
    await modal.waitFor({ state: "visible", timeout: 30000 });
    await frame.locator("#txtTrichYeu").waitFor({ state: "visible", timeout: 30000 });
    await frame.locator("#txtTrichYeu").fill(abstract);
    selectedLeader = await selectPersonExact(frame.locator("#drpLanhDao"), reviewerLevel1, log);

    // Khóa cứng: chỉ dùng ô “Văn bản trình duyệt”, tuyệt đối không dùng txtFilePhieutrinh.
    await frame.locator("#txtFileTrinh").setInputFiles(file.fullPath);
    const chosenFiles = await frame.locator("#txtFileTrinh").evaluate((element) =>
      Array.from(element.files || []).map((item) => item.name)
    );
    if (chosenFiles.length !== 1 || normalizeText(chosenFiles[0]) !== normalizeText(file.name)) {
      throw new Error("File chưa được chọn đúng vào ô Văn bản trình duyệt.");
    }

    try {
      await frame.locator("#btnUpdate").click({ timeout: 180000 });
      try {
        // HPNet gọi CloseDialog() sau khi lưu thành công. Đây là tín hiệu đáng tin cậy
        // hơn tên file trong danh sách, vì một số bản ghi không trả lại tên tệp gốc.
        await modal.waitFor({ state: "hidden", timeout: 45000 });
        modalClosed = true;
      } catch {}
    } catch (error) {
      submitError = error;
    }
  } finally {
    page.off("dialog", dialogHandler);
  }

  const successDialog = /thành công|da thanh cong|cập nhật thành công/i.test(normalizeText(lastDialog));
  const errorDialog = /lỗi|vui lòng|không thể|thất bại|quá dài|không được/i.test(normalizeText(lastDialog));
  if ((modalClosed || successDialog) && !errorDialog) {
    return { success: true, matchedReviewer: selectedLeader, message: lastDialog || "HPNet đã đóng hộp dự thảo sau khi Cập nhật." };
  }

  // Only wait briefly before the fallback list check; a hidden modal/success dialog
  // already confirms the server accepted the upload.
  await page.waitForTimeout(300);
  const appeared = await waitForRecord(context, page, file, reuploadModified);
  if (appeared) return { success: true, matchedReviewer: selectedLeader, message: lastDialog || "HPNet đã ghi nhận văn bản." };

  const detail = lastDialog || submitError?.message || "Không thấy văn bản trong danh sách sau khi bấm Cập nhật.";
  log(`[CHƯA XÁC NHẬN] ${file.name}: ${detail}`);
  return { success: false, uncertain: true, message: detail };
}

async function main() {
  if (process.argv.includes("--self-test")) {
    runSelfTest();
    return;
  }

  const configPath = process.argv[2];
  if (!configPath) throw new Error("Thiếu tệp cấu hình.");
  const config = JSON.parse(cleanJsonText(await fsp.readFile(configPath, "utf8")));
  const abstract = String(config.abstract ?? "").trim();
  const batches = Array.isArray(config.batches) ? config.batches : [{ folder: config.sourceFolder, abstract }];
  if (!batches.length) throw new Error("Chưa cấu hình thư mục upload.");
  const reviewerLevel1 = String(config.reviewerLevel1 ?? "").replace(/\s+/g, " ").trim();
  if (!normalizePersonName(reviewerLevel1)) throw new Error("Vui lòng nhập Người duyệt cấp 1 / lãnh đạo.");
  const resolvedBatches = batches.map((batch) => ({ folder: path.resolve(String(batch.folder ?? "")), abstract: String(batch.abstract ?? "").trim() }));
  for (const batch of resolvedBatches) {
    if (!batch.abstract) throw new Error(`Trích yếu đang trống ở thư mục: ${batch.folder}`);
    const stat = await fsp.stat(batch.folder).catch(() => null);
    if (!stat?.isDirectory()) throw new Error(`Không tìm thấy thư mục Word: ${batch.folder}`);
  }
  const files = (await Promise.all(resolvedBatches.map(async (batch) =>
    (await listWordFiles(batch.folder)).map((file) => ({ ...file, abstract: batch.abstract }))
  ))).flat();
  if (!files.length) throw new Error("Thư mục không có file .doc hoặc .docx.");
  const duplicateLocalKeys = new Set();
  for (const file of files) {
    if (!file.key) throw new Error(`Không tạo được khóa tên cho file: ${file.name}`);
    const localKey = `${file.key}|${normalizeText(file.abstract)}`;
    if (duplicateLocalKeys.has(localKey)) throw new Error(`Trong các thư mục có hai file trùng tên và trích yếu: ${file.name}`);
    duplicateLocalKeys.add(localKey);
  }
  if (process.argv.includes("--validate-config")) {
    console.log(JSON.stringify({ folderCount: resolvedBatches.length, fileCount: files.length, files: files.map(({ name, abstract }) => ({ name, abstract })) }));
    return;
  }

  const toolRoot = path.dirname(configPath);
  const ledgerPath = path.join(toolRoot, "trang_thai_da_up.json");
  let ledger = {};
  try { ledger = JSON.parse(cleanJsonText(await fsp.readFile(ledgerPath, "utf8"))); } catch { ledger = {}; }
  for (const file of files) file.sha256 = await sha256File(file.fullPath);
  const ledgerKey = (file) => `${file.key}|${file.sha256}|${normalizeText(file.abstract)}|${normalizePersonName(reviewerLevel1)}`;
  const saveLedger = async () => {
    const temp = `${ledgerPath}.tmp`;
    await fsp.writeFile(temp, JSON.stringify(ledger, null, 2), "utf8");
    await fsp.rename(temp, ledgerPath).catch(async () => {
      await fsp.rm(ledgerPath, { force: true });
      await fsp.rename(temp, ledgerPath);
    });
  };
  const logDir = path.join(toolRoot, "nhat_ky");
  await fsp.mkdir(logDir, { recursive: true });
  const runStamp = timestamp();
  const textLogPath = path.join(logDir, `NHAT_KY_UP_VB_DU_THAO_${runStamp}.txt`);
  const csvLogPath = path.join(logDir, `NHAT_KY_UP_VB_DU_THAO_${runStamp}.csv`);
  const logLines = [];
  const resultRows = [];
  const log = (message) => {
    const line = `[${new Date().toLocaleString("vi-VN")}] ${message}`;
    logLines.push(line);
    console.log(line);
  };
  const addResult = (file, status, matchedReviewer = "", note = "") => {
    resultRows.push([new Date().toISOString(), resultRows.length + 1, file.name, file.key, reviewerLevel1, matchedReviewer, status, note]);
  };

  const modulesRoot = process.env.HPNET_NODE_MODULES;
  const edgeExe = process.env.HPNET_EDGE_EXE;
  if (!modulesRoot || !edgeExe) throw new Error("Không xác định được bộ chạy trình duyệt đi kèm công cụ.");
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
    log(`Số thư mục: ${resolvedBatches.length}`);
    resolvedBatches.forEach((batch, index) => log(`Thư mục ${index + 1}: ${batch.folder} | Trích yếu: ${batch.abstract}`));
    log(`Người duyệt cấp 1 / lãnh đạo: ${reviewerLevel1}`);
    log(`Chế độ up lại file đã sửa: ${config.reuploadModified ? "CÓ" : "KHÔNG"}`);
    log(`Tìm thấy ${files.length} file Word.`);
    page = await ensureLoggedIn(page, context, log);
    log("Đăng nhập HPNet thành công. Đang quét toàn bộ danh sách VB dự thảo...");

    const records = await queryRecords(context, {
      key: "",
      allPages: true,
      pageSize: 100,
      onPage: (done, total) => log(`Đã kiểm tra ${done}/${total} văn bản trên HPNet...`),
    });
    log(`Đã đọc ${records.length} văn bản để chống tải trùng.`);

    let uploaded = 0;
    let skipped = 0;
    const uploadDurations = [];
    for (let index = 0; index < files.length; index += 1) {
      const file = files[index];
      log(`(${index + 1}/${files.length}) Kiểm tra ${file.name}`);
      if (file.name.length > 100) {
        addResult(file, "BỎ QUA", "", "Tên file dài quá 100 ký tự.");
        log(`[BỎ QUA] Tên file dài quá 100 ký tự: ${file.name}`);
        skipped += 1;
        continue;
      }
      if (file.size <= 0) {
        addResult(file, "BỎ QUA", "", "File rỗng.");
        log(`[BỎ QUA] File rỗng: ${file.name}`);
        skipped += 1;
        continue;
      }
      const uploadedByThisTool = Boolean(ledger[ledgerKey(file)]);
      let currentOnHpnet = records.some((record) => recordIsCurrentVersion(record, file, Boolean(config.reuploadModified)));
      // Đọc lại 100 bản mới nhất ngay trước mỗi file để tránh trùng nếu người dùng vừa up thủ công.
      if (!uploadedByThisTool && !currentOnHpnet) {
        const newestNow = await queryRecords(context, { key: "", allPages: false, pageSize: 100 });
        currentOnHpnet = newestNow.some((record) => recordIsCurrentVersion(record, file, Boolean(config.reuploadModified)));
        if (currentOnHpnet) records.unshift(...newestNow);
      }
      if (uploadedByThisTool || currentOnHpnet) {
        const reason = uploadedByThisTool
          ? "Công cụ đã ghi nhận đúng nội dung file này ở lần chạy trước."
          : (config.reuploadModified ? "HPNet đã có bản cùng tên được up sau khi file được sửa." : "HPNet đã có văn bản cùng khóa tên.");
        addResult(file, "ĐÃ CÓ", "", reason);
        log(`[ĐÃ CÓ BẢN MỚI - KHÔNG UP LẠI] ${file.name}`);
        skipped += 1;
        continue;
      }

      if (config.dryRun) {
        addResult(file, "SẼ UP", "", "Chế độ chỉ kiểm tra.");
        log(`[SẼ UP] ${file.name}`);
        continue;
      }

      const uploadStartedAt = Date.now();
      const result = await submitOne(page, context, file, file.abstract, reviewerLevel1, Boolean(config.reuploadModified), log);
      const uploadSeconds = (Date.now() - uploadStartedAt) / 1000;
      uploadDurations.push(uploadSeconds);
      log(`[TỐC ĐỘ UPLOAD] ${file.name}: ${uploadSeconds.toFixed(1)} giây`);
      if (!result.success) {
        addResult(file, "DỪNG - CHƯA XÁC NHẬN", result.matchedReviewer || "", result.message);
        throw new Error(`Dừng tại ${file.name}. Có thể HPNet đã nhận nhưng danh sách chưa xác nhận; hãy chạy lại để công cụ kiểm tra và bỏ qua nếu đã có.`);
      }
      records.unshift({ TrichYeu: `${file.abstract} ${file.name}` });
      ledger[ledgerKey(file)] = { fileName: file.name, sha256: file.sha256, abstract: file.abstract, reviewerLevel1, uploadedAt: new Date().toISOString() };
      await saveLedger();
      addResult(file, "ĐÃ UP", result.matchedReviewer || "", result.message);
      uploaded += 1;
      log(`[ĐÃ UP VÀ XÁC NHẬN] ${file.name}`);
    }

    log("--- TỔNG KẾT ---");
    log(`Tổng file Word: ${files.length}`);
    log(`Đã up mới: ${uploaded}`);
    log(`Đã có/bỏ qua: ${skipped}`);
    if (uploadDurations.length) {
      const average = uploadDurations.reduce((sum, value) => sum + value, 0) / uploadDurations.length;
      log(`[TỐC ĐỘ TRUNG BÌNH] ${average.toFixed(1)} giây/file (${uploadDurations.length} file đã upload).`);
    }
    if (config.dryRun) log("Đây là chế độ chỉ kiểm tra, chưa có file nào được tải lên.");
  } catch (error) {
    fatalError = error;
    log(`[LỖI DỪNG] ${error.message}`);
  } finally {
    const csvRows = [
      ["Thời gian", "STT", "Tên file", "Khóa chống trùng", "Người duyệt cấu hình", "Người thực tế được match", "Kết quả", "Ghi chú"],
      ...resultRows,
    ];
    await fsp.writeFile(textLogPath, `\uFEFF${logLines.join("\r\n")}\r\n`, "utf8");
    await fsp.writeFile(csvLogPath, `\uFEFF${csvRows.map((row) => row.map(csvCell).join(",")).join("\r\n")}\r\n`, "utf8");
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
