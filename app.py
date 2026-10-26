"""Nasmoco HCM | MPP vs MP Actual — Streamlit dashboard."""
from pathlib import Path
from datetime import datetime
import os
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from data_loader import load_sales, summarize, BRANCH_ORDER

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_FILE = BASE_DIR / 'Excell' / 'Sales.xls'
FILE_PATH = Path(os.environ.get('SALES_EXCEL_PATH', str(DEFAULT_FILE)))

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

@st.cache_data(show_spinner=False, ttl=60)
def read_cached(path: str, mtime_ns: int, size: int):
    return load_sales(path)


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
segment = st.sidebar.radio('Jenis Sales', ['Total', 'Reguler', 'Mitra'], index=0)
area_selection = st.sidebar.selectbox('Area', ['Seluruh Area', 'Area 1', 'Area 2', 'Area 3'])
refresh = st.sidebar.select_slider('Refresh otomatis', options=[5, 10, 15, 30, 60], value=10, format_func=lambda v: f'{v} detik')
st.sidebar.caption('Perubahan file baru dibaca setelah disimpan. Jangan mengubah nama file atau sheet tanpa menyesuaikan konfigurasi.')
st.sidebar.divider()
st.sidebar.caption('Sumber: `Excell/Sales.xls` · sheet `template bider (okt)`')
st.title('MPP vs MP Actual Sales')
st.caption('Human Capital Management · Nasmoco Group | Monitoring kebutuhan dan realisasi manpower')

@st.fragment(run_every=f'{refresh}s')
def live_dashboard():
    try:
        stat = FILE_PATH.stat()
        df, warnings = read_cached(str(FILE_PATH), stat.st_mtime_ns, stat.st_size)
    except Exception as error:
        st.error(f'Gagal membaca sumber data: {error}')
        st.info('Pastikan file Excel berada di folder Excell, memiliki sheet yang sesuai, dan dapat dibaca. Jalankan ulang dashboard setelah perbaikan.')
        return
    if df.empty:
        st.warning('Tidak ada cabang yang dikenali di sumber Excel.')
        return
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
    modified = datetime.fromtimestamp(stat.st_mtime).strftime('%d %b %Y, %H:%M:%S')
    st.caption(f'🟢 Sumber tersimpan terakhir: {modified} · Pemeriksaan otomatis setiap {refresh} detik · {len(selected)} cabang')
    k1, k2, k3, k4 = st.columns(4)
    k1.metric('Total MPP', f'{mpp:,.0f}')
    k2.metric('MP Actual', f'{actual:,.0f}')
    k3.metric('Gap (Actual − MPP)', f'{gap:+,.0f}', delta=f'{gap:+,.0f}', delta_color='normal')
    k4.metric('Fulfillment', f'{fill:.1f}%')
    st.progress(min(fill/100, 1.0), text=f'Pemenuhan kebutuhan tenaga Sales: {fill:.1f}%')
    st.markdown('### Perbandingan per Area')
    st.plotly_chart(chart(summary, 'Area', 'MPP vs Actual · Area', height=370), use_container_width=True, key='area_chart')
    st.markdown('### Perbandingan per Cabang')
    st.plotly_chart(chart(by_branch, 'Cabang', f'MPP vs Actual · {area_selection}', height=max(450, 25 * len(by_branch) + 180), horizontal=True), use_container_width=True, key='branch_chart')
    tab1, tab2 = st.tabs(['Detail Cabang', 'Ringkasan Area'])
    with tab1:
        detailed = by_branch.copy()
        detailed['Pemenuhan (%)'] = detailed.pop('Fulfillment')
        st.dataframe(detailed, hide_index=True, use_container_width=True, column_config={'MPP':st.column_config.NumberColumn(format='%d'),'Actual':st.column_config.NumberColumn(format='%d'),'Gap':st.column_config.NumberColumn(format='%+d'),'Pemenuhan (%)':st.column_config.ProgressColumn(min_value=0,max_value=120,format='%.1f%%')})
        st.download_button('Unduh detail cabang (CSV)', detailed.to_csv(index=False).encode('utf-8-sig'), file_name='mpp_vs_actual_cabang.csv', mime='text/csv', key='download_branch')
    with tab2:
        st.dataframe(summary.rename(columns={'Fulfillment':'Pemenuhan (%)'}), hide_index=True, use_container_width=True)
    with st.expander('Validasi dan kualitas data'):
        if warnings:
            for item in warnings:
                st.warning(item)
        else:
            st.success('Semua baris cabang yang ditemukan konsisten: Total = Reguler + Mitra.')
        st.caption('Hanya 22 nama cabang yang diakui; baris subtotal Area dan Grand Total tidak dibaca sebagai cabang.')

live_dashboard()
