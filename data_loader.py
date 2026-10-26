"""Source adapter for Nasmoco Sales manpower. Reads the original workbook, never edits it."""
from pathlib import Path
import pandas as pd

SHEET_NAME = 'template bider (okt)'
AREAS = {
    'Area 1': ['KALIGAWE', 'PEMUDA', 'GOMBEL', 'MAJAPAHIT', 'SILIWANGI', 'PATI', 'DEMAK', 'KARANGJATI'],
    'Area 2': ['BANTUL', 'JANTI', 'MLATI', 'PURWOKERTO', 'MAGELANG', 'CILACAP', 'WONOSOBO'],
    'Area 3': ['SOLO BARU', 'SLAMET RIYADI', 'RING ROAD', 'PEKALONGAN', 'TEGAL', 'KLATEN', 'SALATIGA'],
}
AREA_FOR = {branch: area for area, branches in AREAS.items() for branch in branches}
BRANCH_ORDER = [name for names in AREAS.values() for name in names]
METRICS = ['mpp_total', 'mpp_reguler', 'mpp_mitra', 'actual_total', 'actual_reguler', 'actual_mitra']


def load_sales(path: str | Path) -> tuple[pd.DataFrame, list[str]]:
    """Read C/K/L/M/P/Q/R by position; exclude area subtotal & total rows.

    Formula cells in .xls are read from last Excel-saved cached values. Save
    workbook with automatic calculation enabled before expecting new results.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f'File Excel tidak ditemukan: {path}')
    if path.suffix.lower() not in ('.xls', '.xlsx'):
        raise ValueError('Format sumber harus .xls atau .xlsx')
    engine = 'xlrd' if path.suffix.lower() == '.xls' else 'openpyxl'
    raw = pd.read_excel(path, sheet_name=SHEET_NAME, header=None, engine=engine,
                        usecols='C:R', dtype=object)
    return parse_sales(raw)


def parse_sales(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Normalize a C:R matrix from Excel or Sheets using the same business rules.

    Sheets omits trailing empty cells/columns; pad them before positional reads.
    """
    raw = raw.reset_index(drop=True)
    # read_excel(usecols='C:R') keeps original labels 2..17; API uses 0..15.
    raw.columns = range(raw.shape[1])
    raw = raw.reindex(columns=range(16))
    # C is first col of the selection; K/L/M=8/9/10, P/Q/R=13/14/15.
    result = pd.DataFrame({
        'Cabang': raw.iloc[:, 0].astype('string').str.strip().str.upper(),
        'mpp_total': raw.iloc[:, 8],
        'mpp_reguler': raw.iloc[:, 9],
        'mpp_mitra': raw.iloc[:, 10],
        'actual_total': raw.iloc[:, 13],
        'actual_reguler': raw.iloc[:, 14],
        'actual_mitra': raw.iloc[:, 15],
    })
    result = result[result['Cabang'].isin(AREA_FOR)].copy()
    if result.empty:
        raise ValueError('Tidak ada cabang yang dikenali. Periksa tab dan posisi nama cabang di kolom C.')
    if result['Cabang'].duplicated().any():
        duplicates = result.loc[result['Cabang'].duplicated(), 'Cabang'].tolist()
        raise ValueError(f'Cabang duplikat dalam sumber: {duplicates}')
    warnings = []
    missing = sorted(set(BRANCH_ORDER) - set(result['Cabang']))
    if missing:
        warnings.append('Cabang belum ditemukan: ' + ', '.join(missing))
    for col in METRICS:
        result[col] = result[col].map(lambda value: None if isinstance(value, str) and not value.strip() else value)
        values = pd.to_numeric(result[col], errors='coerce')
        bad = result[col].notna() & values.isna()
        if bad.any():
            warnings.append(f'Nilai bukan angka pada {col}: ' + ', '.join(result.loc[bad, 'Cabang'].tolist()))
        result[col] = values.fillna(0)
    result['Area'] = result['Cabang'].map(AREA_FOR)
    result['Urutan'] = result['Cabang'].map({x: i for i, x in enumerate(BRANCH_ORDER)})
    for top, left, right in [('mpp_total','mpp_reguler','mpp_mitra'),('actual_total','actual_reguler','actual_mitra')]:
        invalid = (result[top] - result[left] - result[right]).abs() > 0.001
        if invalid.any():
            warnings.append(f'{top} tidak sama dengan Reguler + Mitra pada: ' + ', '.join(result.loc[invalid,'Cabang'].tolist()))
    result = result.sort_values('Urutan').reset_index(drop=True)
    return result, warnings


def summarize(df: pd.DataFrame, group: str, segment: str = 'Total') -> pd.DataFrame:
    suffix = {'Total': 'total', 'Reguler': 'reguler', 'Mitra': 'mitra'}[segment]
    aggregated = df.groupby(group, sort=False, as_index=False)[[f'mpp_{suffix}', f'actual_{suffix}']].sum()
    aggregated = aggregated.rename(columns={f'mpp_{suffix}': 'MPP', f'actual_{suffix}': 'Actual'})
    aggregated['Gap'] = aggregated['Actual'] - aggregated['MPP']
    aggregated['Fulfillment'] = (100 * aggregated['Actual'] / aggregated['MPP'].replace(0, float('nan'))).round(1)
    return aggregated
