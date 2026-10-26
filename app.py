"""Nasmoco HCM | MPP vs MP Actual — Streamlit dashboard."""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import time
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from data_loader import load_sales, summarize, SHEET_NAME
from google_sheets_loader import load_google_sales, GoogleSheetsError

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_FILE = BASE_DIR / 'Excell' / 'Sales.xls'
FILE_PATH = Path(os.environ.get('SALES_EXCEL_PATH', str(DEFAULT_FILE)))
WIB = timezone(timedelta(hours=7))

st.set_page_config(page_title='MPP vs Actual | Nasmoco HCM', page_icon=':material/monitoring:', layout='wide', initial_sidebar_state='auto')
st.html(BASE_DIR / 'dashboard.css')

@st.cache_data(show_spinner=False, ttl=60, max_entries=8)
def read_cached(path: str, mtime_ns: int, size: int):
    return load_sales(path)


@st.cache_data(show_spinner=False, ttl=5, max_entries=8, refresh_mode='background')
def read_google_cached(source: str, worksheet: str, credentials: dict):
    # Cache results (including safe failures) across viewers to limit API use.
    # Credentials are part of the cache key; the cache is only held in memory.
    # Refresh warm entries in the background so API latency doesn't fade charts
    # on every five-second tick. Explicit manual sync still clears the entry.
    try:
        df, warnings = load_google_sales(source, worksheet, credentials)
        return {'df': df, 'warnings': warnings, 'read_at': datetime.now(WIB), 'error': None}
    except (GoogleSheetsError, ValueError) as error:
        return {'df': None, 'error': str(error)}


def format_time(value: datetime) -> str:
    return value.astimezone(WIB).strftime('%d %b %Y, %H:%M:%S WIB')


def chart(agg: pd.DataFrame, category: str, title: str, height: int = 470, horizontal: bool = False):
    fig = go.Figure()
    colors = [('MPP', '#8291A8'), ('Actual', '#D82743')]
    for series, color in colors:
        fig.add_trace(go.Bar(
            name=series, x=agg[series] if horizontal else agg[category],
            y=agg[category] if horizontal else agg[series],
            orientation='h' if horizontal else 'v', marker_color=color,
            text=agg[series].astype(int).astype(str), textposition='outside', cliponaxis=False,
            hovertemplate='%{x}: %{y}<extra>'+series+'</extra>' if not horizontal else '%{y}: %{x}<extra>'+series+'</extra>',
        ))
    # Let Streamlit theme axis text/grid colors in both light and dark modes.
    # The section heading names the chart; avoid repeating it inside the plot.
    fig.update_layout(barmode='group', height=height, bargap=0.3, bargroupgap=0.12,
                      barcornerradius=4, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      margin=dict(l=8, r=36, t=42, b=35),
                      legend=dict(orientation='h', y=1.12, x=0, xanchor='left'),
                      font=dict(size=12), hovermode='closest')
    maximum = max(float(agg['MPP'].max()), float(agg['Actual'].max()), 1)
    if horizontal:
        fig.update_yaxes(categoryorder='array', categoryarray=list(reversed(agg[category].tolist())), showgrid=False)
        fig.update_xaxes(range=[0, maximum * 1.18], zeroline=False, title=None)
    else:
        fig.update_xaxes(showgrid=False, tickangle=0, categoryorder='array', categoryarray=agg[category].tolist(), title=None)
        fig.update_yaxes(range=[0, maximum * 1.2], zeroline=False, title=None)
    return fig

with st.sidebar.container(gap='small'):
    st.subheader('NASMOCO · HCM')
    st.caption('Manpower & recruitment analytics')
try:
    secrets = st.secrets.to_dict()
except FileNotFoundError:
    secrets = {}
except Exception:
    st.error('Format Streamlit Secrets tidak valid. Periksa format TOML pada pengaturan Secrets.')
    st.stop()
sheet_config = secrets.get('google_sheets', {})
credentials = secrets.get('gcp_service_account', {})
if not isinstance(sheet_config, dict) or not isinstance(credentials, dict):
    st.error('Konfigurasi [google_sheets] dan [gcp_service_account] harus berupa tabel TOML.')
    st.stop()
configured_id = str(sheet_config.get('spreadsheet_id', '')).strip()
worksheet = str(sheet_config.get('worksheet', SHEET_NAME)).strip()
st.sidebar.caption('FILTER DASHBOARD')
source = st.sidebar.selectbox('Sumber data', ['Google Sheets', 'Excel lokal'], index=0 if configured_id else 1, key='source')
segment = st.sidebar.radio('Jenis sales', ['Total', 'Reguler', 'Mitra'], index=0, horizontal=True)
area_selection = st.sidebar.selectbox('Area', ['Seluruh Area', 'Area 1', 'Area 2', 'Area 3'], key='area_filter')
with st.sidebar.expander('Pembaruan & sumber', icon=':material/tune:'):
    refresh = st.select_slider('Refresh otomatis', options=[5, 10, 15, 30, 60], value=5, format_func=lambda v: f'{v} detik', key='refresh_interval')
    st.caption(f'Tab: {worksheet if source == "Google Sheets" else SHEET_NAME}')
    if source == 'Google Sheets':
        st.caption('Perubahan yang tersimpan dibaca otomatis. Cache API bersama berlaku selama 5 detik.')
    else:
        st.caption(f'File: {FILE_PATH.name}. Perubahan dibaca setelah Excel disimpan di server dashboard.')
st.sidebar.caption(f':material/sync: Pembaruan otomatis · {refresh} detik')
if source == 'Google Sheets' and not configured_id:
    st.sidebar.info('Isi Spreadsheet ID dan kredensial pada Streamlit Secrets. Panduan tersedia di PANDUAN_GOOGLE_SHEETS_DEPLOY.md.')
with st.container(gap=None):
    st.title('MPP vs MP Actual Sales')
    st.caption('Nasmoco Group · Kebutuhan dan realisasi tenaga sales')

# A new source or changed credentials must never inherit another source's data.
source_key = (source, configured_id, worksheet,
              hashlib.sha256(json.dumps(credentials, sort_keys=True).encode()).hexdigest(), str(FILE_PATH))
if st.session_state.get('data_source_key') != source_key:
    st.session_state.data_source_key = source_key
    st.session_state.data_status = {'snapshot': None, 'failures': 0, 'next_retry': 0.0, 'error': None}


@st.fragment(run_every=refresh)
def poll_source():
    state = st.session_state.data_status
    previous_snapshot = state['snapshot']
    previous_error = state['error']
    with st.container(horizontal=True, vertical_alignment='center', gap='small'):
        status_line = st.container(width='stretch')
        sync_now = st.button('Sinkronkan', key='sync_now', icon=':material/sync:', help='Baca ulang sumber data sekarang tanpa menunggu interval otomatis.')
    if sync_now:
        if source == 'Google Sheets':
            read_google_cached.clear(configured_id, worksheet, credentials)
        else:
            read_cached.clear()
        state.update(failures=0, next_retry=0.0)
    if time.time() >= state['next_retry']:
        try:
            if source == 'Google Sheets':
                result = read_google_cached(configured_id, worksheet, credentials)
                if result['error']:
                    raise GoogleSheetsError(result['error'])
            else:
                stat = FILE_PATH.stat()
                df, warnings = read_cached(str(FILE_PATH), stat.st_mtime_ns, stat.st_size)
                result = {'df': df, 'warnings': warnings, 'read_at': datetime.now(WIB),
                          'modified': datetime.fromtimestamp(stat.st_mtime, tz=WIB)}
            state.update(snapshot=result, failures=0, next_retry=0.0, error=None)
        except Exception as error:
            # Never expose raw authentication/HTTP exceptions or secret contents.
            safe_error = str(error) if isinstance(error, (GoogleSheetsError, ValueError)) else 'Sumber belum dapat dibaca. Periksa koneksi dan konfigurasi sumber.'
            state['failures'] = min(state['failures'] + 1, 4)
            delay = min(60, 10 * 2 ** (state['failures'] - 1))
            state.update(error=safe_error, next_retry=time.time() + delay)
    snapshot = state['snapshot']
    data_changed = snapshot is not None and (
        previous_snapshot is None
        or not snapshot['df'].equals(previous_snapshot['df'])
        or snapshot['warnings'] != previous_snapshot['warnings']
    )
    # Poll only the compact status fragment. Redraw the full page after a real
    # data/status change; the next run reads the warm cache, keeping charts steady.
    if data_changed or previous_error != state['error']:
        st.rerun()
    if state['error']:
        st.warning(f'Sinkronisasi gagal: {state["error"]}')
        remaining = max(0, int(state['next_retry'] - time.time()))
        st.caption(f'Mencoba lagi otomatis dalam sekitar {remaining} detik; mengikuti interval pemeriksaan dashboard.')
    result = state['snapshot']
    if result is None:
        status_line.caption(':orange-badge[Menunggu data] Sumber belum berhasil dibaca')
        if source == 'Google Sheets':
            st.info('Konversikan Excel menjadi Google Sheets, aktifkan Sheets API, lalu isi Secrets sesuai PANDUAN_GOOGLE_SHEETS_DEPLOY.md. Tidak perlu membuat spreadsheet publik.')
        else:
            st.info('Pastikan file Excel tersedia, sheet sesuai, dan file dapat dibaca. Pembacaan akan dicoba lagi otomatis.')
        return
    df, warnings = result['df'], result['warnings']
    if state['error']:
        status_line.caption(':orange-badge[Data tersimpan] Pembaruan tertunda')
        st.warning(f'Menampilkan data terakhir yang berhasil dibaca pada {format_time(result["read_at"])}. Data mungkin belum terbaru.')
    else:
        status_line.caption(f':green-badge[Terhubung] · {result["read_at"]:%H:%M:%S} WIB')


poll_source()
result = st.session_state.data_status['snapshot']
if result is None:
    st.stop()
df, warnings = result['df'], result['warnings']
selected = df if area_selection == 'Seluruh Area' else df[df['Area'] == area_selection]
if selected.empty:
    st.warning('Area yang dipilih tidak memiliki data.')
    st.stop()
summary = summarize(selected, 'Area', segment)
by_branch = summarize(selected, 'Cabang', segment)
mpp = float(summary['MPP'].sum())
actual = float(summary['Actual'].sum())
gap = actual - mpp
fill = 100 * actual / mpp if mpp else 0
# Native metrics retain accessibility and theme behavior. A scoped grid
# responds to available content width, including an expanded sidebar.
with st.container(key='kpi_grid'):
    k1, k2, k3, k4 = st.columns(4, gap='small')
    k1.metric('Total MPP', f'{mpp:,.0f}', border=True, height=136, help='Kebutuhan tenaga sales sesuai MPP.')
    k2.metric('MP actual', f'{actual:,.0f}', border=True, height=136, help='Jumlah tenaga sales yang tersedia.')
    k3.metric('Gap manpower', f'{gap:+,.0f}', border=True, height=136, help='Actual − MPP. Nilai negatif menunjukkan kekurangan tenaga sales.')
    k4.metric('Pemenuhan', f'{fill:.1f}%', border=True, height=136, help='MP actual dibagi MPP × 100%.')
st.progress(max(0.0, min(fill/100, 1.0)), text=f'Pemenuhan {fill:.1f}% · {area_selection} · {segment} · {len(selected)} cabang')
with st.container(border=True):
    st.subheader('Perbandingan per area')
    st.plotly_chart(chart(summary, 'Area', 'MPP dan actual per area', height=330), width='stretch', key='area_chart', alt='Perbandingan kebutuhan MPP dan manpower actual per area.', config={'displayModeBar': False})
with st.container(border=True):
    st.subheader('Perbandingan per cabang')
    st.plotly_chart(chart(by_branch, 'Cabang', f'MPP dan actual · {area_selection}', height=max(420, 32 * len(by_branch) + 120), horizontal=True), width='stretch', key='branch_chart', alt='Perbandingan kebutuhan MPP dan manpower actual per cabang.', config={'displayModeBar': False})
tab1, tab2 = st.tabs(['Detail Cabang', 'Ringkasan Area'])
with tab1:
    detailed = by_branch.copy()
    detailed['Pemenuhan (%)'] = detailed.pop('Fulfillment')
    st.dataframe(detailed, hide_index=True, width='stretch', column_config={'MPP':st.column_config.NumberColumn(format='%d'),'Actual':st.column_config.NumberColumn(format='%d'),'Gap':st.column_config.NumberColumn(format='%+d'),'Pemenuhan (%)':st.column_config.ProgressColumn(min_value=0,max_value=120,format='%.1f%%')})
    st.download_button('Unduh detail cabang (CSV)', detailed.to_csv(index=False).encode('utf-8-sig'), file_name='mpp_vs_actual_cabang.csv', mime='text/csv', key='download_branch')
with tab2:
    st.dataframe(summary.rename(columns={'Fulfillment':'Pemenuhan (%)'}), hide_index=True, width='stretch')
with st.expander('Validasi dan kualitas data'):
    st.caption(f'Terakhir dibaca: {format_time(result["read_at"])} · Sumber: {source}')
    if source == 'Excel lokal':
        st.caption(f'File disimpan: {format_time(result["modified"])}')
    if warnings:
        for item in warnings:
            st.warning(item)
    else:
        st.success('Semua baris cabang yang ditemukan konsisten: Total = Reguler + Mitra.')
    st.caption('Hanya 22 nama cabang yang diakui; baris subtotal Area dan Grand Total tidak dibaca sebagai cabang.')
