// Frontend contract tests with an in-memory file handle and simulated DOM.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const python = await readFile(new URL('../browser_excel.py', import.meta.url), 'utf8');
const js = python.match(/_JS = r"""([\s\S]*?)"""/)[1];
const {default: render} = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));

test('read-only file watcher reconnects, sends changed bytes, and cleans up', async t => {
  const timers = [];
  t.mock.method(globalThis, 'setInterval', callback => {timers.push(callback); return timers.length;});
  const clear = t.mock.method(globalThis, 'clearInterval', () => {});
  const nodes = {'#connect':{}, '#disconnect':{}, '#connection-status':{}};
  const parentElement = {querySelector: selector => nodes[selector]};
  const events = [];
  let text = 'ABC';
  let modified = 1;
  let fail = false;
  const handle = {name:'Sales.xlsx', getFile:async () => {
    if (fail) throw new Error('read permission revoked');
    const bytes = new TextEncoder().encode(text);
    return {name:'Sales.xlsx',size:bytes.length,lastModified:modified,arrayBuffer:async()=>bytes.buffer};
  }};
  globalThis.window = {isSecureContext:true,showOpenFilePicker:async()=>[handle]};
  const emit = (name,value) => events.push({name,value});
  render({parentElement,data:{interval:5,nonce:0},setStateValue:emit});
  await nodes['#connect'].onclick();
  assert.equal(events.at(-1).value.status,'connected');
  assert.equal(events.at(-1).value.content,'QUJD');
  await timers.at(-1)();
  assert.equal(events.length,1,'unchanged file must not be retransmitted');
  // Streamlit rerenders must preserve the user's permission/handle.
  const cleanup = render({parentElement,data:{interval:10,nonce:0},setStateValue:emit});
  text='DEF'; modified++;
  await timers.at(-1)();
  assert.equal(events.at(-1).value.content,'REVG');
  fail=true;
  await timers.at(-1)();
  assert.equal(events.at(-1).value.status,'error');
  assert.equal(events.at(-1).value.content,'REVG','last good bytes survive a transient read failure');
  const count=events.length;
  await timers.at(-1)();
  assert.equal(events.length,count,'repeated errors do not cause rerun storms');
  fail=false;
  await timers.at(-1)();
  assert.equal(events.at(-1).value.status,'connected');
  nodes['#disconnect'].onclick();
  assert.deepEqual(events.at(-1).value,{status:'disconnected'});
  const disconnectedCount=events.length;
  await timers.at(-1)();
  assert.equal(events.length,disconnectedCount);
  cleanup();
  assert.ok(clear.mock.callCount()>0);
  delete globalThis.window;
});

test('unsupported browser disables automatic connection with a usable fallback', t => {
  t.mock.method(globalThis,'setInterval',()=>1);
  t.mock.method(globalThis,'clearInterval',()=>{});
  globalThis.window={isSecureContext:false};
  const nodes={'#connect':{},'#disconnect':{},'#connection-status':{}};
  const cleanup=render({parentElement:{querySelector:s=>nodes[s]},data:{interval:5},setStateValue:()=>{}});
  assert.equal(nodes['#connect'].disabled,true);
  assert.match(nodes['#connection-status'].textContent,/Unggah Excel/);
  cleanup();
  delete globalThis.window;
});
