"""Validate local paths and the per-session browser Excel transfer contract."""
import base64
import binascii
from pathlib import Path

MAX_FILE_BYTES = 20 * 1024 * 1024


def normalize_excel_path(value: str) -> Path:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1].strip()
    if not value or '\n' in value or '\r' in value or '\x00' in value:
        raise ValueError('Tempel path lengkap satu file Excel dari Windows Explorer.')
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError('Gunakan path lengkap ke file Excel, bukan folder atau alamat website.')
    if path.suffix.lower() not in ('.xls', '.xlsx'):
        raise ValueError('Pilih file .xls atau .xlsx, bukan folder atau shortcut.')
    return path.resolve()


def decode_browser_file(payload: dict | None) -> tuple[bytes, str, str | None]:
    """Return bytes/name/safe error; never persist browser files globally."""
    if not isinstance(payload, dict) or payload.get('status') == 'disconnected':
        return b'', '', None
    name = payload.get('name', '')
    if not isinstance(name, str) or Path(name).suffix.lower() not in ('.xls', '.xlsx'):
        raise ValueError('File dari browser harus berformat .xls atau .xlsx.')
    encoded = payload.get('content', '')
    if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_FILE_BYTES + 2) // 3):
        raise ValueError('File Excel maksimal 20 MB.')
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError('Transfer Excel belum lengkap. Hubungkan ulang file dari browser.') from None
    if not content or len(content) > MAX_FILE_BYTES:
        raise ValueError('File Excel kosong atau lebih besar dari 20 MB.')
    # Do not echo arbitrary browser messages. Only the known status is trusted.
    error = 'File perangkat belum dapat diperiksa. Periksa izin browser atau hubungkan ulang file.' if payload.get('status') == 'error' else None
    return content, Path(name).name, error
