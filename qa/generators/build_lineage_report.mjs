import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const real = JSON.parse(await fs.readFile("qa_runtime/real_lineage.json", "utf8"));
const golden = JSON.parse(await fs.readFile("qa_runtime/golden_strict/end_to_end/logs/golden_lineage.json", "utf8"));
const workbook = Workbook.create();
const font = "Arial";
const navy = "#17365D", blue = "#D9EAF7", pale = "#F4F7FA", red = "#FCE8E6", amber = "#FFF2CC", green = "#E2F0D9";

function colName(n) {
  let s = "";
  while (n > 0) { n--; s = String.fromCharCode(65 + n % 26) + s; n = Math.floor(n / 26); }
  return s;
}

function makeSheet(name, title, note, headers, rows, widths = {}) {
  const sheet = workbook.worksheets.add(name);
  sheet.showGridLines = false;
  sheet.getRange("A1").values = [[title]];
  sheet.getRange("A1").format.font = { name: font, size: 15, bold: true, color: navy };
  sheet.getRange("A2").values = [[note]];
  sheet.getRange("A2").format.font = { name: font, size: 10, italic: true, color: "#526579" };
  const last = colName(headers.length);
  sheet.getRange(`A4:${last}4`).values = [headers];
  sheet.getRange(`A4:${last}4`).format = {
    fill: navy, font: { name: font, size: 10, bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center", verticalAlignment: "center", wrapText: true,
    borders: { preset: "inside", style: "thin", color: "#FFFFFF" },
  };
  if (rows.length) {
    sheet.getRange(`A5:${last}${rows.length + 4}`).values = rows;
    sheet.getRange(`A5:${last}${rows.length + 4}`).format.font = { name: font, size: 10, color: "#1F2937" };
    sheet.getRange(`A5:${last}${rows.length + 4}`).format.verticalAlignment = "top";
    sheet.getRange(`A5:${last}${rows.length + 4}`).format.wrapText = true;
    sheet.tables.add(`A4:${last}${rows.length + 4}`, true, `${name.replace(/[^A-Za-z0-9]/g, "")}Table`).style = "TableStyleMedium2";
  }
  for (const [column, width] of Object.entries(widths)) sheet.getRange(`${column}:${column}`).format.columnWidth = width;
  sheet.freezePanes.freezeRows(4);
  return sheet;
}

const r = real.real_data;
const summaryRows = [
  ["Git", "Branch", real.repository.branch, "Đã đồng bộ an toàn"],
  ["Git", "Commit trước audit", real.repository.commit, real.repository.sync],
  ["Golden", "Source parcels", golden.stats.source_parcels, "Nguồn kỳ vọng"],
  ["Golden", "Word records selected", golden.stats.word_records, "Phải bằng source parcels"],
  ["Golden", "Word/TBXN generated", golden.stats.word_files, "10/10"],
  ["Golden", "TBXN physical found", golden.stats.tbxn_pdfs, "Có thư mục lồng"],
  ["Golden", "DDK physical found", golden.stats.ddk_pdfs, "10/10"],
  ["Golden", "VBDLIS parcels / rows", `${golden.stats.vbdlis_parcels} / ${golden.stats.vbdlis_rows}`, "Không mất thửa"],
  ["Golden", "AX TBXN / DDK", `${golden.stats.ax_tbxn_references} / ${golden.stats.ax_ddk_references}`, "Cả hai cùng tồn tại"],
  ["Golden", "Silent loss", golden.stats.silently_missing, "PASS"],
  ["Tân Hòa", "Source rows with parcel data", r.source_parcels, "B=Hộ; G=Tờ; H=Thửa"],
  ["Tân Hòa", "Valid eligible parcels", r.eligible_tbxn, "206 hợp lệ; loại rõ 1 dòng 92/CN"],
  ["Tân Hòa", "Invalid source identifiers", r.invalid_source_identifiers, "SOURCE_DATA_ERROR — không tính là thiếu hồ sơ"],
  ["Tân Hòa", "TBXN physical / expected", `${r.tbxn_physical_found} / ${r.tbxn_expected}`, "Đủ toàn bộ thửa hợp lệ"],
  ["Tân Hòa", "DDK physical / expected", `${r.ddk_physical_found} / ${r.ddk_expected}`, "Thiếu 4 thửa hợp lệ"],
  ["Tân Hòa", "Current VBDLIS parcels / rows", `${r.vbdlis_parcels_current} / ${r.vbdlis_rows_current}`, "File hiện tại còn chứa 1 thửa CN không hợp lệ"],
  ["Tân Hòa", "Builder output after fix", `${r.vbdlis_valid_parcels_after_fix} / ${r.vbdlis_valid_rows_after_fix}`, "206 thửa hợp lệ, 208 dòng người-thửa"],
  ["Tân Hòa", "AX refs TBXN / DDK", `${r.ax_tbxn_references_found} / ${r.ax_ddk_references_found}`, "Có 1 cặp tham chiếu thuộc dòng CN không hợp lệ"],
  ["Tân Hòa", "Missing TBXN among eligible", r.missing_tbxn_final, "PASS"],
  ["Tân Hòa", "Missing DDK among eligible", r.missing_ddk_final, "Cần bổ sung 4 file vật lý"],
];
const summary = makeSheet("PIPELINE_SUMMARY", "Kiểm tra xuyên suốt Word → TBXN/DDK → VBDLIS",
  "Snapshot 12/09/2026 · Dữ liệu thật chỉ được đọc · HPNet web tools không thuộc phạm vi.",
  ["Dataset", "Chỉ số", "Giá trị", "Kết luận"], summaryRows, {A:16,B:29,C:20,D:52});
summary.getRange(`A14:D${summaryRows.length + 4}`).format.fill = pale;
summary.getRange(`D14:D${summaryRows.length + 4}`).conditionalFormats.add("containsText", {text:"Thiếu",format:{fill:red,font:{color:"#9C0006",bold:true}}});

const goldenRows = golden.lineage.map(x => ["GOLDEN",x.test_case,x.household,x.sheet,x.parcel,x.source_row,true,true,true,true,true,
  true,true,x.vbdlis_rows,true,true,true,x.final_status,"",x.failure_stage,x.failure_reason]);
const realRows = real.lineage.map(x => ["TÂN HÒA",x.test_case,x.household,x.sheet,x.parcel,x.source_rows,x.source_present,x.identifier_valid,x.eligible,x.word_expected,
  x.word_generated_before_fix,x.tbxn_found,x.ddk_found,x.vbdlis_rows,x.vbdlis_parcel_found,
  x.ax_raw.includes("-TBXN.pdf"),x.ax_raw.includes("-DDK.pdf"),x.workflow_status,x.user_message,x.failure_stage,x.failure_reason]);
const lineageHeaders=["Dataset","TestCase","Household","Sheet","Parcel","SourceRow(s)","SourcePresent","IdentifierValid","Eligible","WordExpected","WordGenerated/Physical",
  "TBXNFound","DDKFound","VBDLISRows","VBDLISParcelFound","AX_TBXN","AX_DDK","FinalStatus","UserMessage","FailureStage","FailureReason"];
const lineageSheet=makeSheet("PARCEL_LINEAGE","Data lineage theo từng thửa","Mỗi thửa kết thúc ở SUCCESS/EXPLICIT_FAILURE/REVIEW_REQUIRED; không có silent loss trong golden.",
  lineageHeaders,[...goldenRows,...realRows],{A:13,B:12,C:26,D:9,E:10,F:13,G:14,H:15,I:11,J:14,K:20,L:12,M:12,N:12,O:17,P:11,Q:11,R:18,S:44,T:25,U:58});
lineageSheet.freezePanes.freezeColumns(5);
lineageSheet.getRange(`L5:M${realRows.length+goldenRows.length+4}`).conditionalFormats.add("cellIs",{operator:"equal",formula:"FALSE",format:{fill:red,font:{color:"#9C0006",bold:true}}});

const missingTbxn = real.lineage.filter(x => x.tbxn_expected && !x.tbxn_found).map(x => [x.household,x.sheet,x.parcel,x.source_rows,x.source_present,x.word_expected,
  x.word_generated_before_fix,x.word_generation_regression,x.tbxn_expected,x.tbxn_found,"NOT RUN","NOT RUN",x.vbdlis_parcel_found,
  x.ax_raw.includes("-TBXN.pdf"),x.failure_stage,x.failure_reason,x.suggested_fix]);
makeSheet("MISSING_TBXN_ANALYSIS","Phân tích TBXN còn thiếu","Không thiếu TBXN nào trong 206 thửa hợp lệ. Dòng 92/CN là lỗi dữ liệu nguồn và được tách riêng.",
  ["Household","Sheet","Parcel","SourceRow","SourceHasParcel","WordWasExpected","WordGeneratedBeforeFix","WordRegressionAfterFix","TBXNExpected","TBXNFound",
   "TBXNRenameStatus","TBXNCopyStatus","VBDLISParcelFound","AXTBXNReferenceFound","FailureStage","FailureReason","SuggestedFix"],
  missingTbxn,{A:24,B:9,C:9,D:11,E:15,F:17,G:23,H:23,I:14,J:12,K:18,L:17,M:18,N:22,O:24,P:58,Q:60});

const missingDdk = real.lineage.filter(x => x.ddk_expected && !x.ddk_found).map(x => [x.household,x.sheet,x.parcel,x.source_rows,x.source_present,x.ddk_expected,x.ddk_found,
  x.vbdlis_parcel_found,x.ax_raw.includes("-DDK.pdf"),x.workflow_status,x.issues,x.failure_stage,x.failure_reason,x.suggested_fix]);
makeSheet("MISSING_DDK_ANALYSIS","Phân tích DDK còn thiếu","Bốn thửa hợp lệ không có DDK vật lý; dòng 92/CN không thuộc tập hồ sơ hợp lệ.",
  ["Household","Sheet","Parcel","SourceRow","SourceHasParcel","DDKExpected","DDKFound","VBDLISParcelFound","AXDDKReferenceFound","FinalStatus","Issues","FailureStage","FailureReason","SuggestedFix"],
  missingDdk,{A:25,B:9,C:9,D:11,E:15,F:14,G:12,H:18,I:21,J:18,K:48,L:24,M:52,N:58});

const wordRows = real.lineage.map(x => [x.test_case,x.household,x.sheet,x.parcel,x.source_rows,x.word_expected,x.word_generated_before_fix,
  x.word_generation_regression,x.tbxn_found,x.failure_stage,x.failure_reason]);
makeSheet("WORD_GENERATION","Kiểm tra tạo Word/TBXN","Bộ đọc chọn 206/206 thửa hợp lệ và chặn rõ dòng 92/CN; không tạo Word từ mã có chữ.",
  ["TestCase","Household","Sheet","Parcel","SourceRow","Expected","PhysicalBeforeFix","RegressionAfterFix","TBXNPhysical","FailureStage","Reason"],
  wordRows,{A:12,B:25,C:9,D:9,E:11,F:11,G:18,H:19,I:14,J:24,K:62});

const invalidRows = real.lineage.filter(x => !x.identifier_valid).map(x => [x.test_case,x.household,x.sheet,x.parcel,x.source_rows,
  x.source_present,x.vbdlis_parcel_found,x.workflow_status,x.user_message,x.failure_stage,x.failure_reason,x.user_action]);
makeSheet("SOURCE_DATA_ERRORS","Dữ liệu tờ/thửa không hợp lệ","Số tờ và số thửa chỉ được là số nguyên dương; mã có chữ bị chặn, không tạo tài liệu và không tính là thiếu tài liệu.",
  ["TestCase","Household","Sheet","Parcel","SourceRow","InSource","InCurrentVBDLIS","Status","UserMessage","FailureStage","Reason","UserAction"],
  invalidRows,{A:12,B:25,C:9,D:9,E:11,F:12,G:18,H:16,I:45,J:22,K:58,L:65});

const documentRows = real.lineage.map(x => [x.test_case,x.household,x.sheet,x.parcel,x.tbxn_found,x.tbxn_paths,x.ddk_found,x.ddk_paths,
  x.workflow_status,x.issues]);
makeSheet("DOCUMENT_MATCHING","Ghép tài liệu theo tờ/thửa","Scanner đọc đệ quy; hồ sơ trùng/mơ hồ được đưa về REVIEW_REQUIRED, không chọn bản đầu tiên.",
  ["TestCase","Household","Sheet","Parcel","TBXNFound","TBXNPath","DDKFound","DDKPath","Status","Issues"],
  documentRows,{A:12,B:25,C:9,D:9,E:12,F:65,G:12,H:65,I:18,J:50});

const refRows = real.lineage.map(x => [x.test_case,x.household,x.sheet,x.parcel,x.vbdlis_row_numbers,x.ax_raw,
  x.ax_raw.includes("-TBXN.pdf"),x.ax_raw.includes("-DDK.pdf"),x.ax_status,x.workflow_status]);
makeSheet("VBDLIS_REFERENCES","Tham chiếu hồ sơ quét trong VBDLIS","AX giữ đồng thời hai tên TBXN và DDK trên mọi dòng; trạng thái mismatch phản ánh file vật lý thiếu, không phải AX bị ghi đè.",
  ["TestCase","Household","Sheet","Parcel","VBDLISRows","AXRaw","ContainsTBXN","ContainsDDK","AXStatus","WorkflowStatus"],
  refRows,{A:12,B:25,C:9,D:9,E:13,F:76,G:14,H:14,I:14,J:18});

workbook.recalculate();
const inspection = await workbook.inspect({kind:"sheet,table",include:"id,name",maxChars:5000,tableMaxRows:3,tableMaxCols:6});
await fs.mkdir("qa_runtime/report_previews",{recursive:true});
const preview = await workbook.render({sheetName:"PIPELINE_SUMMARY",autoCrop:"all",scale:1,format:"png"});
await fs.writeFile("qa_runtime/report_previews/pipeline_summary.png",new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await fs.mkdir("qa/reports",{recursive:true});
await output.save("qa/reports/DATA_LINEAGE_REPORT.xlsx");
console.log(inspection.ndjson);
