"""Headless UI checks for live data, caching, stale data and source isolation."""
import json
from io import BytesIO
from pathlib import Path
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
        self.app.session_state['source'] = 'Google Sheets'

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
        self.app.selectbox(key='source').select('Unggah Excel').run()
        self.check_no_crash()
        self.assertFalse(self.app.metric)
        self.assertIsNone(self.app.session_state.data_status['snapshot'])
        self.assertEqual(len(self.app.get('file_uploader')), 1)

    def test_upload_is_default_and_local_source_is_removed(self):
        del self.app.session_state['source']
        self.app.run()
        self.check_no_crash()
        self.assertEqual(self.app.selectbox(key='source').options, ['Unggah Excel', 'Google Sheets'])
        self.assertEqual(self.app.selectbox(key='source').value, 'Unggah Excel')
        self.assertEqual(self.loader.call_count, 0)
        self.assertFalse(self.app.metric)
        self.assertFalse(self.app.select_slider)
        self.assertEqual(len(self.app.get('file_uploader')), 1)
        self.assertEqual([item.label for item in self.app.text_input], ['Nama sheet Excel'])

    def test_previous_local_source_falls_back_to_upload(self):
        self.app.session_state['source'] = 'Excel lokal'
        self.app.run()
        self.check_no_crash()
        self.assertEqual(self.app.selectbox(key='source').value, 'Unggah Excel')
        self.assertFalse(self.app.metric)

    @staticmethod
    def workbook(actual):
        buffer = BytesIO()
        pd.DataFrame([[None, None] + row for row in sample_rows(actual)]).to_excel(
            buffer, sheet_name=SHEET_NAME, header=False, index=False)
        buffer.name = 'sales.xlsx'
        return buffer

    def test_uploaded_workbooks_update_and_clear_without_leaking_between_sessions(self):
        self.app.session_state['source'] = 'Unggah Excel'
        with patch.object(type(st.sidebar), 'file_uploader') as upload:
            upload.return_value = self.workbook(8)
            self.app.run()
            self.check_no_crash()
            self.assertEqual(self.app.metric[1].value, '176')
            upload.return_value = self.workbook(9)
            self.app.run()
            self.check_no_crash()
            self.assertEqual(self.app.metric[1].value, '198')
            second = AppTest.from_file(APP, default_timeout=30)
            second.secrets['google_sheets'] = {}
            second.secrets['gcp_service_account'] = {}
            upload.return_value = self.workbook(7)
            second.run()
            self.assertFalse(second.exception)
            self.assertEqual(second.metric[1].value, '154')
            self.assertEqual(self.app.metric[1].value, '198')
            upload.return_value = None
            self.app.run()
            self.check_no_crash()
            self.assertFalse(self.app.metric)
            self.assertIsNone(self.app.session_state.data_status['snapshot'])

    def test_invalid_upload_replaces_old_data_with_actionable_error(self):
        self.app.session_state['source'] = 'Unggah Excel'
        with patch.object(type(st.sidebar), 'file_uploader') as upload:
            upload.return_value = self.workbook(8)
            self.app.run()
            self.app.text_input(key='excel_worksheet').set_value('missing sheet').run()
            self.check_no_crash()
            self.assertFalse(self.app.metric)
            self.assertTrue(self.app.warning)
            self.assertTrue(any('unggah ulang atau klik Sinkronkan' in item.value for item in self.app.caption))

    def test_area_gaps_follow_actual_values_and_filters(self):
        for actual in (8, 10, 12):
            self.loader.return_value = parse_sales(pd.DataFrame(sample_rows(actual=actual)))
            st.cache_data.clear()
            self.app.run()
            self.check_no_crash()
            charts = self.app.get('plotly_chart')
            area = json.loads(charts[0].proto.spec)
            summary = self.app.dataframe[1].value
            annotations = area['layout']['annotations']
            self.assertEqual([a['x'] for a in annotations], summary['Area'].tolist())
            self.assertEqual([a['text'] for a in annotations], [f'<b>Gap {v:+,.0f}</b>' for v in summary['Gap']])
            self.assertTrue(all(a['font']['color'] == '#C62828' for a in annotations))
            self.assertNotIn('annotations', json.loads(charts[1].proto.spec)['layout'])
        self.app.selectbox(key='area_filter').select('Area 2').run()
        self.app.radio[0].set_value('Mitra').run()
        self.check_no_crash()
        area = json.loads(self.app.get('plotly_chart')[0].proto.spec)
        self.assertEqual(len(area['layout']['annotations']), 1)
        annotation = area['layout']['annotations'][0]
        self.assertEqual(annotation['x'], 'Area 2')
        self.assertEqual(annotation['text'], f"<b>Gap {self.app.dataframe[1].value['Gap'].iloc[0]:+,.0f}</b>")


if __name__ == '__main__':
    unittest.main()
