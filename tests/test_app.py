"""Headless UI checks for live data, caching, stale data and source isolation."""
import os
import base64
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from data_loader import SHEET_NAME, parse_sales
from google_sheets_loader import GoogleSheetsError
from test_sources import sample_rows

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.local_mode = patch.dict(os.environ, {'DASHBOARD_ALLOW_LOCAL_PATHS': '1'})
        self.local_mode.start()
        self.addCleanup(self.local_mode.stop)
        st.cache_data.clear()
        self.loader_patch = patch('google_sheets_loader.load_google_sales')
        self.loader = self.loader_patch.start()
        self.addCleanup(self.loader_patch.stop)
        self.loader.return_value = parse_sales(pd.DataFrame(sample_rows()))
        self.app = AppTest.from_file(APP, default_timeout=30)
        self.app.secrets['google_sheets'] = {'spreadsheet_id': 'test-sheet', 'worksheet': SHEET_NAME}
        self.app.secrets['gcp_service_account'] = {'client_email': 'test@example.test'}

    def check_no_crash(self):
        self.assertFalse(self.app.exception, [item.message for item in self.app.exception])

    def test_refresh_defaults_to_five_seconds_and_allows_slower_options(self):
        self.app.run()
        self.check_no_crash()
        self.assertEqual(self.app.select_slider(key='refresh_interval').value, 5)
        self.app.select_slider(key='refresh_interval').set_value(10).run()
        self.check_no_crash()
        self.assertEqual(self.app.select_slider(key='refresh_interval').value, 10)

    def test_changed_values_update_metrics_charts_and_csv_table(self):
        self.app.run()
        self.check_no_crash()
        self.assertEqual(self.app.metric[1].value, '176')
        self.assertEqual(len(self.app.get('plotly_chart')), 2)
        self.app.run()  # Interaction/rerun within TTL must reuse shared data.
        self.assertEqual(self.loader.call_count, 1)
        self.loader.return_value = parse_sales(pd.DataFrame(sample_rows(actual=9)))
        self.app.button(key='sync_now').click().run()
        self.check_no_crash()
        self.assertEqual(self.loader.call_count, 2)
        self.assertEqual(self.app.metric[1].value, '198')
        self.assertEqual(self.app.dataframe[0].value['Actual'].sum(), 198)
        self.app.selectbox[1].select('Area 1').run()
        self.check_no_crash()
        self.assertEqual(self.app.metric[1].value, '72')
        self.app.radio[0].set_value('Mitra').run()
        self.check_no_crash()
        self.assertEqual(self.app.metric[1].value, '24')

    def test_stale_snapshot_warning_backoff_and_recovery(self):
        self.app.run()
        self.loader.side_effect = GoogleSheetsError('Koneksi terputus')
        self.app.button(key='sync_now').click().run()
        self.check_no_crash()
        self.assertEqual(self.app.metric[1].value, '176')
        self.assertTrue(any('Data mungkin belum terbaru' in item.value for item in self.app.warning))
        self.app.run()  # Backoff prevents another immediate request.
        self.assertEqual(self.loader.call_count, 2)
        self.loader.side_effect = None
        self.loader.return_value = parse_sales(pd.DataFrame(sample_rows(actual=9)))
        self.app.button(key='sync_now').click().run()
        self.check_no_crash()
        self.assertEqual(self.app.metric[1].value, '198')
        self.assertFalse(self.app.warning)

    def test_new_session_failure_does_not_show_fabricated_metrics(self):
        self.loader.side_effect = GoogleSheetsError('Akses ditolak')
        self.app.run()
        self.check_no_crash()
        self.assertFalse(self.app.metric)
        self.assertTrue(self.app.warning)

    def test_source_change_discards_previous_snapshot(self):
        self.app.run()
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'SALES_EXCEL_PATH': str(Path(folder) / 'missing.xls')}):
            self.app.selectbox(key='source').select('Excel lokal').run()
        self.check_no_crash()
        self.assertFalse(self.app.metric)
        self.assertIsNone(self.app.session_state.data_status['snapshot'])

    def test_local_workbook_still_renders(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sales.xlsx'
            pd.DataFrame([[None, None] + row for row in sample_rows()]).to_excel(path, sheet_name=SHEET_NAME, header=False, index=False)
            with patch.dict(os.environ, {'SALES_EXCEL_PATH': str(path)}):
                self.app.secrets.clear()
                # Override local Secrets explicitly; clear() alone falls back
                # to a developer's real secrets.toml if one exists.
                self.app.secrets['google_sheets'] = {}
                self.app.secrets['gcp_service_account'] = {}
                self.app.run()
                self.check_no_crash()
                self.assertEqual(self.app.selectbox(key='source').value, 'Excel lokal')
                self.assertEqual(self.app.metric[1].value, '176')
                self.assertEqual(self.loader.call_count, 0)

    def test_pasted_explorer_path_updates_after_save_and_isolates_new_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'File Sales kolaborasi.xlsx'
            source_env = patch.dict(os.environ, {'SALES_EXCEL_PATH': str(path)})
            source_env.start()
            self.addCleanup(source_env.stop)
            def save(actual):
                pd.DataFrame([[None, None] + row for row in sample_rows(actual)]).to_excel(path, sheet_name=SHEET_NAME, header=False, index=False)
            save(8)
            self.app.run()
            self.app.selectbox(key='source').select('Excel lokal').run()
            self.app.text_input(key='local_path_input').set_value(f'"{path}"')
            self.app.button(key='connect_path').click().run()
            self.check_no_crash()
            self.assertEqual(self.app.metric[1].value, '176')
            save(9)
            self.app.run()  # Same path, changed file timestamp and contents.
            self.check_no_crash()
            self.assertEqual(self.app.metric[1].value, '198')
            self.app.text_input(key='local_path_input').set_value(str(Path(folder) / 'missing.xlsx'))
            self.app.button(key='connect_path').click().run()
            self.check_no_crash()
            self.assertFalse(self.app.metric)

    def test_online_browser_files_update_per_session_and_clear_on_disconnect(self):
        def payload(actual):
            buffer = BytesIO()
            pd.DataFrame([[None, None] + row for row in sample_rows(actual)]).to_excel(buffer, sheet_name=SHEET_NAME, header=False, index=False)
            return {'status': 'connected', 'name': 'sales.xlsx',
                    'content': base64.b64encode(buffer.getvalue()).decode()}
        with patch('browser_excel.live_excel_connection') as connect:
            connect.return_value = SimpleNamespace(file=payload(8))
            self.app.session_state['excel_mode'] = 'Dari browser (otomatis)'
            self.app.run()
            self.app.selectbox(key='source').select('Excel lokal').run()
            self.check_no_crash()
            self.assertEqual(self.app.metric[1].value, '176')
            connect.return_value = SimpleNamespace(file=payload(9))
            self.app.run()
            self.check_no_crash()
            self.assertEqual(self.app.metric[1].value, '198')
            # Another viewer receives their own workbook, not the first viewer's.
            second = AppTest.from_file(APP, default_timeout=30)
            second.secrets['google_sheets'] = {}
            second.secrets['gcp_service_account'] = {}
            second.session_state['excel_mode'] = 'Dari browser (otomatis)'
            connect.return_value = SimpleNamespace(file=payload(7))
            second.run()
            self.assertFalse(second.exception)
            self.assertEqual(second.metric[1].value, '154')
            connect.return_value = SimpleNamespace(file={'status': 'disconnected'})
            self.app.run()
            self.check_no_crash()
            self.assertFalse(self.app.metric)

    def test_online_path_input_cannot_read_server_files(self):
        with patch.dict(os.environ, {'DASHBOARD_ALLOW_LOCAL_PATHS': '0'}), patch('browser_excel.live_excel_connection', return_value=SimpleNamespace(file=None)):
            self.app.session_state['excel_mode'] = 'Tempel path (server lokal)'
            self.app.run()
            self.app.selectbox(key='source').select('Excel lokal').run()
            self.check_no_crash()
            self.assertTrue(self.app.text_input(key='local_path_input').disabled)
            self.assertFalse(self.app.metric)


if __name__ == '__main__':
    unittest.main()
