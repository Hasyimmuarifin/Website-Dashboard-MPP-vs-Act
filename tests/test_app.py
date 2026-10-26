"""Headless UI checks for live data, caching, stale data and source isolation."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest

from data_loader import SHEET_NAME, parse_sales
from google_sheets_loader import GoogleSheetsError
from test_sources import sample_rows

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


class DashboardTests(unittest.TestCase):
    def setUp(self):
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


if __name__ == '__main__':
    unittest.main()
