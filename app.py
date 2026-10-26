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

st.set_page_config(page_title='MPP vs Actual | Nasmoco HCM', page_icon='📊', layout='wide', initial_sidebar_state='expanded')
st.markdown('''<style>
.stApp {background: #f6f8fb; color: #18243a;}
.block-container {padding-top: 1.5rem; max-width: 1550px;}
[data-testid="stMetric"] {background: white; border: 1px solid #e3e9f0; border-radius: 14px; padding: 18px; box-shadow: 0 3px 12px #132c4709;}
[data-testid="stSidebar"] {background: #10263b;}
[data-testid="stSidebar"] * {color: #f6f9ff;}
[data-testid="stSidebar"] [data-baseweb="select"] * {color:#1b2d42;}
h1,h2,h3 {letter-spacing: -0.5px;}
</style>''', unsafe_allow_html=True)

@st.cache_data(show_spinner=False, ttl=60, max_entries=8)
def read_cached(path: str, mtime_ns: int, size: int):
    return load_sales(path)


@st.cache_data(show_spinner=False, ttl=5, max_entries=8)
def read_google_cached(source: str, worksheet: str, credentials: dict):
    # Cache results (including safe failures) across viewers to limit API use.
    # Credentials are part of the cache key; the cache is only held in memory.
    try:
        df, warnings = load_google_sales(source, worksheet, credentials)
        return {'df': df, 'warnings': warnings, 'read_at': datetime.now(WIB), 'error': None}
    except (GoogleSheetsError, ValueError) as error:
        return {'df': None, 'error': str(error)}


def format_time(value: datetime) -> str:
    return value.astimezone(WIB).strftime('%d %b %Y, %H:%M:%S WIB')


def chart(agg: pd.DataFrame, category: str, title: str, height: int = 470, horizontal: bool = False):
    fig = go.Figure()
    colors = [('MPP', '#7B8BA3'), ('Actual', '#D92034')]
    for series, color in colors:
        fig.add_trace(go.Bar(
            name=series, x=agg[series] if horizontal else agg[category],
            y=agg[category] if horizontal else agg[series],
            orientation='h' if horizontal else 'v', marker_color=color,
            text=agg[series].astype(int).astype(str), textposition='outside',
            hovertemplate='%{x}: %{y}<extra>'+series+'</extra>' if not horizontal else '%{y}: %{x}<extra>'+series+'</extra>',
        ))
    fig.update_layout(title=dict(text=title, font=dict(size=18, color='#192D45')),
                      barmode='group', height=height, paper_bgcolor='white', plot_bgcolor='white',
                      margin=dict(l=18, r=22, t=65, b=55), legend=dict(orientation='h', y=1.12, x=0.7),
                      font=dict(color='#33465e', size=12))
    if horizontal:
        fig.update_yaxes(categoryorder='array', categoryarray=list(reversed(agg[category].tolist())), showgrid=False)
        fig.update_xaxes(gridcolor='#edf0f6')
    else:
        fig.update_xaxes(showgrid=False, tickangle=-35, categoryorder='array', categoryarray=agg[category].tolist())
        fig.update_yaxes(gridcolor='#edf0f6')
    return fig

st.sidebar.markdown('## NASMOCO · HCM')
st.sidebar.caption('RECRUITMENT ANALYTICS')
st.sidebar.divider()
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
source = st.sidebar.selectbox('Sumber data', ['Google Sheets', 'Excel lokal'], index=0 if configured_id else 1, key='source')
segment = st.sidebar.radio('Jenis Sales', ['Total', 'Reguler', 'Mitra'], index=0)
area_selection = st.sidebar.selectbox('Area', ['Seluruh Area', 'Area 1', 'Area 2', 'Area 3'])
refresh = st.sidebar.select_slider('Refresh otomatis', options=[5, 10, 15, 30, 60], value=5, format_func=lambda v: f'{v} detik', key='refresh_interval')
if source == 'Google Sheets':
    st.sidebar.caption('Perubahan yang tersimpan di Google Sheets dibaca otomatis saat dashboard terbuka. Cache API dibagikan antar pengguna selama 5 detik.')
else:
    st.sidebar.caption('Perubahan Excel dibaca setelah file disimpan di komputer tempat dashboard berjalan.')
st.sidebar.divider()
st.sidebar.caption(f'Tab sumber: {worksheet if source == "Google Sheets" else SHEET_NAME}')
if source == 'Google Sheets' and not configured_id:
    st.sidebar.info('Isi Spreadsheet ID dan kredensial pada Streamlit Secrets. Panduan tersedia di PANDUAN_GOOGLE_SHEETS_DEPLOY.md.')
if source == 'Excel lokal':
    st.sidebar.caption(f'File sumber: {FILE_PATH.name}')
st.title('MPP vs MP Actual Sales')
st.caption('Human Capital Management · Nasmoco Group | Monitoring kebutuhan dan realisasi manpower')

# A new source or changed credentials must never inherit another source's data.
source_key = (source, configured_id, worksheet,
              hashlib.sha256(json.dumps(credentials, sort_keys=True).encode()).hexdigest(), str(FILE_PATH))
if st.session_state.get('data_source_key') != source_key:
    st.session_state.data_source_key = source_key
    st.session_state.data_status = {'snapshot': None, 'failures': 0, 'next_retry': 0.0, 'error': None}


@st.fragment(run_every=refresh)
def live_dashboard():
    state = st.session_state.data_status
    if st.button('Sinkronkan sekarang', key='sync_now', icon=':material/sync:'):
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
    if state['error']:
        st.warning(f'Sinkronisasi gagal: {state["error"]}')
        remaining = max(0, int(state['next_retry'] - time.time()))
        st.caption(f'Mencoba lagi otomatis dalam sekitar {remaining} detik; mengikuti interval pemeriksaan dashboard.')
    result = state['snapshot']
    if result is None:
        if source == 'Google Sheets':
            st.info('Konversikan Excel menjadi Google Sheets, aktifkan Sheets API, lalu isi Secrets sesuai PANDUAN_GOOGLE_SHEETS_DEPLOY.md. Tidak perlu membuat spreadsheet publik.')
        else:
            st.info('Pastikan file Excel tersedia, sheet sesuai, dan file dapat dibaca. Pembacaan akan dicoba lagi otomatis.')
        return
    df, warnings = result['df'], result['warnings']
    if state['error']:
        st.warning(f'Menampilkan data terakhir yang berhasil dibaca pada {format_time(result["read_at"])}. Data mungkin belum terbaru.')
    else:
        st.caption(f'Sinkronisasi berhasil · {format_time(result["read_at"])} · {source} · Pemeriksaan setiap {refresh} detik')
    if source == 'Excel lokal':
        st.caption(f'File disimpan terakhir: {format_time(result["modified"])}')
    selected = df if area_selection == 'Seluruh Area' else df[df['Area'] == area_selection]
    if selected.empty:
        st.warning('Area yang dipilih tidak memiliki data.')
        return
    summary = summarize(selected, 'Area', segment)
    by_branch = summarize(selected, 'Cabang', segment)
    mpp = float(summary['MPP'].sum())
    actual = float(summary['Actual'].sum())
    gap = actual - mpp
    fill = 100 * actual / mpp if mpp else 0
    st.caption(f'{len(selected)} cabang dalam pilihan area')
    k1, k2, k3, k4 = st.columns(4)
    k1.metric('Total MPP', f'{mpp:,.0f}')
    k2.metric('MP Actual', f'{actual:,.0f}')
    k3.metric('Gap (Actual − MPP)', f'{gap:+,.0f}', delta=f'{gap:+,.0f}', delta_color='normal')
    k4.metric('Fulfillment', f'{fill:.1f}%')
    st.progress(max(0.0, min(fill/100, 1.0)), text=f'Pemenuhan kebutuhan tenaga Sales: {fill:.1f}%')
    st.markdown('### Perbandingan per Area')
    st.plotly_chart(chart(summary, 'Area', 'MPP vs Actual · Area', height=370), width='stretch', key='area_chart')
    st.markdown('### Perbandingan per Cabang')
    st.plotly_chart(chart(by_branch, 'Cabang', f'MPP vs Actual · {area_selection}', height=max(450, 25 * len(by_branch) + 180), horizontal=True), width='stretch', key='branch_chart')
    tab1, tab2 = st.tabs(['Detail Cabang', 'Ringkasan Area'])
    with tab1:
        detailed = by_branch.copy()
        detailed['Pemenuhan (%)'] = detailed.pop('Fulfillment')
        st.dataframe(detailed, hide_index=True, width='stretch', column_config={'MPP':st.column_config.NumberColumn(format='%d'),'Actual':st.column_config.NumberColumn(format='%d'),'Gap':st.column_config.NumberColumn(format='%+d'),'Pemenuhan (%)':st.column_config.ProgressColumn(min_value=0,max_value=120,format='%.1f%%')})
        st.download_button('Unduh detail cabang (CSV)', detailed.to_csv(index=False).encode('utf-8-sig'), file_name='mpp_vs_actual_cabang.csv', mime='text/csv', key='download_branch')
    with tab2:
        st.dataframe(summary.rename(columns={'Fulfillment':'Pemenuhan (%)'}), hide_index=True, width='stretch')
    with st.expander('Validasi dan kualitas data'):
        if warnings:
            for item in warnings:
                st.warning(item)
        else:
            st.success('Semua baris cabang yang ditemukan konsisten: Total = Reguler + Mitra.')
        st.caption('Hanya 22 nama cabang yang diakui; baris subtotal Area dan Grand Total tidak dibaca sebagai cabang.')

live_dashboard()
