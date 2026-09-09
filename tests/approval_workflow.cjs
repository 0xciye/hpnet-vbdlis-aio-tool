const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../src/nodes_tools/Duyet/HPNet Duyet VB Du Thao - VNEID APP/hpnet-approve-draft.cjs'), 'utf8');
const delays = [];
const sandbox = { require, console, URL, setTimeout: (fn, ms) => { delays.push(ms); fn(); } };
vm.createContext(sandbox);
vm.runInContext(source.slice(0, source.lastIndexOf('main().catch')), sandbox);
const record = (id, status = 'pending') => ({ VanbanDiId: id, TrichYeu: 'title', TinhTrangXuly: status });
function contextFor(pages) {
  const calls = [];
  return { calls, request: { post: async (url, options) => {
    calls.push({ url, options });
    assert.ok(pages.length, 'unexpected extra list request');
    const payload = pages.shift();
    return { ok: () => true, headers: () => ({}), json: async () => payload };
  } } };
}
const page = (records, total = records.length) => ({ Result: 'OK', Records: records, TotalRecordCount: total });
(async () => {
  let ctx = contextFor([page([record('wanted')], 500)]);
  assert.equal((await sandbox.findRecordById(ctx, 'wanted', 'title')).VanbanDiId, 'wanted');
  assert.equal(ctx.calls.length, 1);
  ctx = contextFor([page([record('other')], 2), page([record('wanted')], 2)]);
  assert.equal((await sandbox.findRecordById(ctx, 'wanted', 'title')).VanbanDiId, 'wanted');
  assert.equal(ctx.calls.length, 2);
  ctx = contextFor([page([]), page([record('wanted')], 500)]);
  assert.equal((await sandbox.findRecordById(ctx, 'wanted', 'title')).VanbanDiId, 'wanted');
  assert.equal(ctx.calls[1].options.form.key, '');
  ctx = contextFor([page([record('a')], 2), page([record('b')], 2)]);
  assert.equal((await sandbox.queryRecords(ctx)).length, 2, 'scan must still read every page');
  ctx = contextFor([page([record('wanted')]), page([record('wanted', 'done')])]);
  assert.equal((await sandbox.waitForStatusChange(ctx, 'wanted', 'title', 'pending')).changed, true);
  assert.deepEqual(delays.splice(0), [250]);
  ctx = contextFor(Array.from({length: 15}, () => page([record('wanted')])));
  assert.equal((await sandbox.waitForStatusChange(ctx, 'wanted', 'title', 'pending')).changed, false);
  assert.equal(delays.reduce((a,b) => a+b, 0), 23750, 'retain slow-server allowance');
  ctx = contextFor([{Result: 'ERROR', Message: 'expired'}]);
  await assert.rejects(() => sandbox.waitForStatusChange(ctx, 'wanted', 'title', 'pending'), /expired/);

  // Exercise the real approveOne flow with a browser double: never send twice,
  // require status confirmation, and refuse mismatched status before opening UI.
  let sends = 0;
  const locator = { waitFor: async () => {}, click: async () => {} };
  const frame = { locator: (selector) => selector.includes('type="submit"') ?
    { click: async () => { sends++; } } : locator };
  const browser = {
    url: () => 'https://qlvb.hpnet.vn/?action=901', evaluate: async () => true,
    waitForFunction: async () => {}, locator: () => locator, frameLocator: () => frame,
    on: () => {}, off: () => {}, waitForTimeout: () => new Promise(() => {}),
  };
  sandbox.selectPersonExact = async () => 'Reviewer';
  ctx = contextFor([page([record('wanted')]), page([record('wanted', 'done')])]);
  assert.equal((await sandbox.approveOne(browser, ctx, {id:'wanted'}, 'title', 'pending', 'Reviewer', () => {})).result, 'ĐÃ DUYỆT');
  assert.equal(sends, 1);
  ctx = contextFor([page([record('wanted', 'done')])]);
  assert.equal((await sandbox.approveOne(browser, ctx, {id:'wanted'}, 'title', 'pending', 'Reviewer', () => {})).result, 'BỎ QUA');
  assert.equal(sends, 1);
  ctx = contextFor([page([record('wanted')]), ...Array.from({length:15}, () => page([record('wanted')]))]);
  await assert.rejects(() => sandbox.approveOne(browser, ctx, {id:'wanted'}, 'title', 'pending', 'Reviewer', () => {}), /tình trạng chưa đổi/);
  assert.equal(sends, 2, 'failed confirmation must not resubmit');
  console.log('APPROVAL_WORKFLOW_TEST_OK');
})().catch(error => { console.error(error); process.exitCode = 1; });
