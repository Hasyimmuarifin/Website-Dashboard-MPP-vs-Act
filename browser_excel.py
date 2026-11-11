"""Session-local, read-only live Excel connection via File System Access API."""
import streamlit as st

_HTML = """
<div class="excel-connection">
  <button id="connect" type="button">Hubungkan Excel dari perangkat</button>
  <button id="disconnect" type="button" hidden>Putuskan koneksi</button>
  <p id="connection-status" role="status" aria-live="polite">Pilih satu file .xls atau .xlsx untuk mulai memantau.</p>
</div>
"""

_CSS = """
.excel-connection {font-family:var(--st-font); color:var(--st-text-color);}
button {font:inherit; width:100%; padding:0.65rem 0.75rem; cursor:pointer;
  border:1px solid var(--st-border-color); border-radius:var(--st-button-radius);
  background:var(--st-background-color); color:var(--st-text-color);}
#connect {background:var(--st-primary-color); color:#fff; border-color:var(--st-primary-color);}
#disconnect {margin-top:0.5rem;}
button:focus-visible {outline:3px solid #90CAF9; outline-offset:2px;}
button:disabled {cursor:not-allowed; opacity:0.65;}
p {font-size:0.85rem; line-height:1.5; margin:0.65rem 0 0; overflow-wrap:anywhere;}
"""

_JS = r"""
const instances = new WeakMap();
export default function(component) {
  const {parentElement, data, setStateValue} = component;
  let state = instances.get(parentElement);
  if (!state) {
    state = {handle:null, timer:null, busy:false, signature:null, lastGood:null,
             lastError:false, disposed:false, generation:0, nonce:data?.nonce ?? 0};
    instances.set(parentElement, state);
  }
  state.emit = setStateValue;
  state.nodes = {
    connect:parentElement.querySelector('#connect'),
    disconnect:parentElement.querySelector('#disconnect'),
    status:parentElement.querySelector('#connection-status')
  };
  const supported = window.isSecureContext && typeof window.showOpenFilePicker === 'function';
  const interval = Math.max(5000, Number(data?.interval ?? 5) * 1000);
  state.nodes.connect.disabled = !supported;
  state.nodes.disconnect.hidden = !state.handle;
  if (!supported) {
    state.nodes.status.textContent = 'Koneksi otomatis memerlukan Chrome/Edge desktop dan HTTPS atau localhost. Gunakan sumber Unggah Excel pada browser lain.';
  }
  async function readFile(force=false) {
    if (!state.handle || state.busy || state.disposed) return;
    state.busy = true;
    const generation = state.generation;
    try {
      const file = await state.handle.getFile();
      if (!/\.(xls|xlsx)$/i.test(file.name)) throw new Error('format');
      if (!file.size || file.size > 20 * 1024 * 1024) throw new Error('size');
      const signature = `${file.name}:${file.size}:${file.lastModified}`;
      if (force || signature !== state.signature || state.lastError) {
        const bytes = new Uint8Array(await file.arrayBuffer());
        const chunks = [];
        for (let i=0; i<bytes.length; i+=32768) {
          chunks.push(String.fromCharCode(...bytes.subarray(i,i+32768)));
        }
        if (state.disposed || generation !== state.generation) return;
        const payload = {status:'connected', name:file.name, content:btoa(chunks.join('')),
                         modified:file.lastModified};
        state.lastGood = payload;
        state.signature = signature;
        state.lastError = false;
        state.emit('file', payload);
      }
      if (state.disposed || generation !== state.generation) return;
      const time = new Date().toLocaleTimeString('id-ID');
      state.nodes.status.textContent = `${file.name} · diperiksa ${time}. Simpan perubahan di Excel; diperiksa setiap ${interval/1000} detik.`;
    } catch (error) {
      if (state.disposed || generation !== state.generation) return;
      state.nodes.status.textContent = error.message === 'size'
        ? 'File harus berisi data dan maksimal 20 MB. Pilih file lain.'
        : 'File belum dapat dibaca. Pastikan izin tersedia, file tidak dipindah, lalu hubungkan ulang. Data terakhir dipertahankan bila tersedia.';
      if (!state.lastError) {
        state.lastError = true;
        state.emit('file', {...(state.lastGood ?? {name:state.handle.name,content:''}), status:'error'});
      }
    } finally {state.busy=false;}
  }
  state.nodes.connect.onclick = async () => {
    try {
      const [handle] = await window.showOpenFilePicker({multiple:false, types:[{
        description:'Excel workbook', accept:{
          'application/vnd.ms-excel':['.xls'],
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':['.xlsx']
        }
      }]});
      state.generation++;
      state.handle=handle;
      state.signature=null;
      state.lastGood=null;
      state.lastError=false;
      state.nodes.disconnect.hidden=false;
      state.nodes.status.textContent='Membaca file yang dipilih…';
      await readFile(true);
    } catch (error) {
      if (error.name !== 'AbortError') {
        state.nodes.status.textContent='Izin file belum tersedia. Klik hubungkan dan pilih file kembali.';
      }
    }
  };
  state.nodes.disconnect.onclick = () => {
    state.generation++;
    state.handle=null;
    state.signature=null;
    state.lastGood=null;
    state.lastError=false;
    state.nodes.disconnect.hidden=true;
    state.nodes.status.textContent='Koneksi diputus. Pilih file untuk menghubungkan kembali.';
    state.emit('file',{status:'disconnected'});
  };
  clearInterval(state.timer);
  state.timer=setInterval(() => readFile(), interval);
  if ((data?.nonce ?? 0) !== state.nonce) {
    state.nonce=data.nonce;
    readFile(true);
  }
  return () => {
    state.disposed=true;
    state.generation++;
    clearInterval(state.timer);
    state.handle=null;
    state.lastGood=null;
    instances.delete(parentElement);
  };
}
"""

_COMPONENT = st.components.v2.component('nasmoco_live_excel', html=_HTML, css=_CSS, js=_JS)


def live_excel_connection(*, interval: int, nonce: int = 0):
    def file_changed():
        # A new permission/file event should be handled immediately, including
        # recovery of the same workbook after a temporary read failure.
        status = st.session_state.get('data_status')
        if status is not None:
            status.update(failures=0, next_retry=0.0)
    return _COMPONENT(key='browser_excel_connection', data={'interval': interval, 'nonce': nonce},
                      default={'file': None}, on_file_change=file_changed)
