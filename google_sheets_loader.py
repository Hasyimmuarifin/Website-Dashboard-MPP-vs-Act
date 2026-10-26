"""Read a private Google Sheet using the Sheets v4 API; never write to it."""
from collections.abc import Mapping
import base64
import binascii
import re
import textwrap
from urllib.parse import quote, urlparse

import pandas as pd

from data_loader import parse_sales

READ_SCOPE = 'https://www.googleapis.com/auth/spreadsheets.readonly'


class GoogleSheetsError(ValueError):
    """Safe, actionable error message for display without credential details."""


def prepare_service_account_info(info: Mapping) -> dict:
    """Restore PEM formatting lost when JSON keys are pasted into TOML.

    Only formatting is changed: decode escaped newlines, remove body whitespace,
    and wrap the same base64 bytes at 64 columns. Never log or rewrite Secrets.
    """
    result = dict(info)
    missing = [name for name in ('client_email', 'private_key', 'token_uri')
               if not isinstance(result.get(name), str) or not result[name].strip()]
    if missing:
        raise GoogleSheetsError('Secrets [gcp_service_account] belum lengkap. Isi field: ' + ', '.join(missing) + '.')
    if result.get('type', 'service_account') != 'service_account':
        raise GoogleSheetsError('Gunakan JSON key service account, bukan kredensial OAuth Client atau API key.')
    if any('GANTI_DENGAN' in result[name] for name in ('client_email', 'private_key', 'token_uri')):
        raise GoogleSheetsError('Secrets masih berisi nilai contoh. Ganti dengan nilai asli dari JSON service account.')
    for name in ('client_email', 'token_uri'):
        result[name] = result[name].strip()
    if not re.fullmatch(r'[^@\s]+@[^@\s]+', result['client_email']):
        raise GoogleSheetsError('Format client_email tidak valid. Salin client_email dari JSON service account.')
    # Support literal \n and double-escaped \\n from copied JSON/TOML.
    key = re.sub(r'\\+r\\+n|\\+n|\\+r', '\n', result['private_key']).strip()
    match = re.fullmatch(
        r'-----BEGIN (?P<kind>(?:RSA )?PRIVATE KEY)-----(?P<body>.*?)-----END (?P=kind)-----',
        key, re.DOTALL,
    )
    if not match:
        raise GoogleSheetsError('Format private_key tidak lengkap. Salin seluruh key dari JSON, termasuk baris BEGIN PRIVATE KEY dan END PRIVATE KEY.')
    body = ''.join(match['body'].split())
    try:
        if not body:
            raise ValueError
        base64.b64decode(body, validate=True)
    except (ValueError, binascii.Error):
        raise GoogleSheetsError('Isi private_key rusak atau terpotong. Salin ulang private_key lengkap dari JSON service account.') from None
    kind = match['kind']
    result['private_key'] = f'-----BEGIN {kind}-----\n' + '\n'.join(textwrap.wrap(body, 64)) + f'\n-----END {kind}-----\n'
    return result


def spreadsheet_id(value: str) -> str:
    """Accept an ID or an ordinary docs.google.com/spreadsheets/d/... URL."""
    value = value.strip()
    if value.startswith(('https://', 'http://')):
        parsed = urlparse(value)
        match = re.match(r'^/spreadsheets/(?:u/\d+/)?d/([A-Za-z0-9_-]+)(?:/|$)', parsed.path)
        if parsed.hostname != 'docs.google.com' or not match or '/d/e/' in parsed.path:
            raise GoogleSheetsError('Gunakan URL Google Sheets atau Spreadsheet ID yang valid.')
        value = match.group(1)
    if not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise GoogleSheetsError('Spreadsheet ID belum diisi atau tidak valid.')
    return value


def _forbidden_message(response) -> str:
    """Classify Google 403 errors without exposing the remote response body."""
    try:
        error = response.json().get('error', {})
        entries = error.get('details', []) + error.get('errors', [])
        reasons = {entry.get('reason') for entry in entries if isinstance(entry, dict)}
        message = str(error.get('message', '')).lower()
    except (ValueError, TypeError, AttributeError):
        reasons, message = set(), ''
    if reasons & {'SERVICE_DISABLED', 'accessNotConfigured'} or 'has not been used' in message or 'it is disabled' in message:
        return 'Google Sheets API belum aktif pada project service account. Buka Google Cloud Console > APIs & Services > Library > Google Sheets API > Enable.'
    if reasons & {'RATE_LIMIT_EXCEEDED', 'quotaExceeded', 'dailyLimitExceeded'}:
        return 'Kuota Google Sheets API sedang penuh. Tunggu percobaan ulang otomatis atau tambah interval refresh.'
    if 'caller does not have permission' in message:
        return 'Service account berhasil diautentikasi, tetapi tidak memiliki izin membaca spreadsheet ini. Bagikan dokumen ke client_email dari Secrets sebagai Viewer dan pastikan Spreadsheet ID benar.'
    return 'Akses ditolak (HTTP 403). Aktifkan Google Sheets API pada project service account dan bagikan spreadsheet ke client_email dari Secrets sebagai Viewer.'


def load_google_sales(source: str, worksheet: str, service_account_info: Mapping):
    """Fetch calculated numeric values in C:R, unaffected by display locale.

    Authentication and reads have timeouts. Dependencies are imported lazily so
    Excel mode remains usable without the optional Google packages installed.
    """
    source_id = spreadsheet_id(source)
    if not worksheet.strip():
        raise GoogleSheetsError('Nama tab Google Sheets belum diisi.')
    if not service_account_info:
        raise GoogleSheetsError('Isi bagian [gcp_service_account] pada Streamlit Secrets terlebih dahulu.')
    service_account_info = prepare_service_account_info(service_account_info)
    try:
        from google.auth.exceptions import GoogleAuthError
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2.service_account import Credentials
        from requests.exceptions import RequestException
    except ImportError:
        raise GoogleSheetsError('Library Google belum terpasang. Jalankan pip install -r requirements.txt.') from None

    try:
        credentials = Credentials.from_service_account_info(
            dict(service_account_info), scopes=[READ_SCOPE],
        )
    except (ValueError, KeyError, TypeError, GoogleAuthError):
        raise GoogleSheetsError('Kredensial service account tidak dapat dibaca setelah format key dirapikan. Isi private_key mungkin rusak atau terpotong; salin ulang dari JSON key service account yang sama.') from None

    a1_range = "'" + worksheet.strip().replace("'", "''") + "'!C:R"
    url = f'https://sheets.googleapis.com/v4/spreadsheets/{source_id}/values/{quote(a1_range, safe="")}'
    try:
        with AuthorizedSession(credentials, refresh_timeout=15, max_refresh_attempts=1) as session:
            response = session.get(
                url, params={'majorDimension': 'ROWS', 'valueRenderOption': 'UNFORMATTED_VALUE'},
                timeout=15,
            )
    except (GoogleAuthError, RequestException):
        raise GoogleSheetsError('Koneksi atau autentikasi Google gagal. Periksa internet dan validitas service account.') from None

    messages = {
        400: 'Rentang/tab tidak valid. Periksa nama tab persis seperti di Google Sheets dan konversi file Excel ke format Google Sheets.',
        401: 'Autentikasi Google ditolak. Periksa kembali kredensial service account.',
        404: 'Spreadsheet tidak ditemukan atau belum dibagikan ke service account. Periksa Spreadsheet ID.',
        429: 'Kuota Google Sheets API sedang penuh. Dashboard akan mencoba kembali dengan jeda bertahap.',
    }
    if response.status_code == 403:
        raise GoogleSheetsError(_forbidden_message(response))
    if not response.ok:
        raise GoogleSheetsError(messages.get(response.status_code, f'Google Sheets API belum tersedia (HTTP {response.status_code}).'))
    try:
        payload = response.json()
        rows = payload.get('values', [])
        if not isinstance(rows, list) or any(not isinstance(row, list) for row in rows):
            raise ValueError
        raw = pd.DataFrame(rows)
    except (ValueError, TypeError, AttributeError):
        raise GoogleSheetsError('Respons Google Sheets API tidak valid. Coba lagi pada pemeriksaan berikutnya.') from None
    return parse_sales(raw)
