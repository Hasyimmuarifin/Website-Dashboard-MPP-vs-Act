"""Gap cell colors shared by branch and area tables; numeric data stays intact."""
import math

import pandas as pd


def gap_cell_style(value: float, scale: float) -> str:
    """Blend red/green over white; equal magnitudes use equal tint strength."""
    if pd.isna(value) or not math.isfinite(float(value)) or value == 0:
        background = '#FFFFFF'
    else:
        strength = min(abs(float(value)) / max(float(scale), 1.0), 1.0)
        alpha = 0.12 + 0.48 * strength
        base = (211, 47, 47) if value < 0 else (46, 125, 50)
        # Opaque pre-blending works consistently in Streamlit's canvas table.
        rgb = [round(255 * (1 - alpha) + channel * alpha) for channel in base]
        background = '#' + ''.join(f'{channel:02X}' for channel in rgb)
    return f'background-color: {background}; color: #173653;'


def style_gap_cells(data: pd.DataFrame):
    """Use one symmetric scale for all signed gaps in the visible table."""
    magnitudes = pd.to_numeric(data['Gap'], errors='coerce').abs()
    scale = max(float(magnitudes.max()), 1.0) if magnitudes.notna().any() else 1.0
    return data.style.map(lambda value: gap_cell_style(value, scale), subset=['Gap'])
