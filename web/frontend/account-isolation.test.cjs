// Focused component-state regression; no browser or new dependencies required.
const { readFileSync } = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const ts = require('typescript');
const source = process.env.GROWTH_TEST_SOURCE || 'src/growth/GrowthApp.tsx';
const input = process.env.GROWTH_TEST_BASELINE || readFileSync(source, 'utf8');
const compiled = ts.transpileModule(input, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const slots = []; let cursor = 0; const pending = [];
const react = {
  useState(initial) { const i = cursor++; if (!(i in slots)) slots[i] = typeof initial === 'function' ? initial() : initial;
    return [slots[i], v => { slots[i] = typeof v === 'function' ? v(slots[i]) : v; }]; },
  useRef(initial) { const i = cursor++; return slots[i] ||= { current: initial }; },
  useCallback(fn) { return fn; }, useEffect() {},
};
const jsx = (type, props) => ({ type, props });
const context = { exports: {}, location: { hash: '#/account' }, localStorage: { getItem: () => 'A', setItem() {} },
  require(name) {
    if (name === 'react') return react;
    if (name === 'react/jsx-runtime') return { jsx, jsxs: jsx, Fragment: 'fragment' };
    if (name === './api') return { request: () => new Promise(resolve => pending.push(resolve)) };
    return { __esModule: true, default: name };
  },
};
vm.runInNewContext(compiled, context);
function render() { cursor = 0; return context.exports.default(); }
function find(node, predicate) {
  if (!node || typeof node !== 'object') return undefined;
  if (Array.isArray(node)) return node.map(v => find(v, predicate)).find(Boolean);
  return predicate(node) ? node : find(node.props?.children, predicate);
}
const state = id => ({ account: { id }, accounts: [{ id: 'A', name: 'A' }, { id: 'B', name: 'B' }],
  projections: [], runs: [{ id: 'run', stage: 'diagnosis', status: 'succeeded', started_at: '2026-01-01' }] });
async function main() {
  render(); slots[2] = state('A');
  let tree = render();
  find(tree, n => n.type === 'button' && n.props.children === '＋ 新建账号').props.onClick();
  for (const page of ['research', 'topics', 'studio']) {
    slots[0] = page; tree = render();
    assert(!find(tree, n => n.type === `./${{ research: 'ResearchPage', topics: 'TopicsPage', studio: 'StudioPage' }[page]}`), 'new-account mode must not mount old account pages');
  }
  slots[0] = 'account'; slots[3] = false; tree = render();
  find(tree, n => n.type === 'button' && n.props.children === '刷新任务状态').props.onClick();
  find(tree, n => n.type === 'select' && n.props['aria-label'] === '当前账号').props.onChange({ target: { value: 'B' } });
  assert.equal(slots[2], null, 'switch must clear old state immediately');
  pending.shift()(state('A')); await new Promise(setImmediate);
  assert.equal(slots[2], null, 'late A refresh must not replace B');
  slots[2] = state('B'); slots[0] = 'research'; tree = render();
  assert.equal(find(tree, n => n.type === './ResearchPage').props.accountId, 'B');
  console.log('PASS: unsaved account isolation, immediate reset, late-response rejection, B page binding');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
