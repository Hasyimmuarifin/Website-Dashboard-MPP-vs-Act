import base64
from io import BytesIO
from pathlib import Path
import tempfile
import unittest

import pandas as pd
from data_loader import SHEET_NAME, load_sales_bytes
from excel_sources import decode_browser_file, normalize_excel_path
from test_sources import sample_rows


class ExcelConnectionTests(unittest.TestCase):
    def test_explorer_quotes_and_spaces(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'Sales Team.xlsx'
            self.assertEqual(normalize_excel_path(f'  "{file}"  '), file.resolve())
        for value in ('', 'Sales.xlsx', 'https://example.com/sales.xlsx', 'C:\\sales.txt', 'file.xlsx\nfile2.xlsx'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_excel_path(value)

    def test_browser_transfer_parses_same_workbook_and_custom_tab(self):
        buffer = BytesIO()
        pd.DataFrame([[None, None] + row for row in sample_rows()]).to_excel(buffer, sheet_name='Sales November', header=False, index=False)
        payload = {'status': 'connected', 'name': 'sales.xlsx', 'content': base64.b64encode(buffer.getvalue()).decode()}
        content, name, error = decode_browser_file(payload)
        self.assertIsNone(error)
        frame, warnings = load_sales_bytes(content, name, 'Sales November')
        self.assertEqual(frame['actual_total'].sum(), 176)
        self.assertFalse(warnings)

    def test_revoked_permission_retains_data_but_sets_safe_error(self):
        content, name, error = decode_browser_file({'status': 'error', 'name': 'sales.xlsx',
                                                   'content': base64.b64encode(b'test-bytes').decode(),
                                                   'message': 'DO_NOT_DISPLAY_ARBITRARY_MESSAGE'})
        self.assertEqual(content, b'test-bytes')
        self.assertIsNotNone(error)
        self.assertNotIn('DO_NOT_DISPLAY', error)
        self.assertEqual(decode_browser_file({'status': 'disconnected'}), (b'', '', None))

    def test_malformed_transfer_and_non_excel_files_are_rejected(self):
        for payload in ({'status': 'connected', 'name': 'secrets.toml', 'content': 'QUJD'},
                        {'status': 'connected', 'name': 'sales.xlsx', 'content': '$bad'},
                        {'status': 'connected', 'name': 'sales.xlsx', 'content': ''}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                decode_browser_file(payload)
