"""Source contract tests; use synthetic data and mocked HTTP, never real keys."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import unquote

from google.auth.exceptions import RefreshError
from google.oauth2.service_account import Credentials
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
import pandas as pd
from requests.exceptions import Timeout

from data_loader import BRANCH_ORDER, SHEET_NAME, load_sales, parse_sales, summarize
from google_sheets_loader import GoogleSheetsError, READ_SCOPE, load_google_sales, spreadsheet_id, prepare_service_account_info


def sample_rows(actual=8):
    rows = []
    for branch in BRANCH_ORDER:
        row = [''] * 16
        row[0] = branch.lower() + ' '
        row[8:11] = [10, 6, 4]
        row[13:16] = [actual, actual - 3, 3]
        rows.append(row)
    subtotal = [''] * 16
    subtotal[0] = 'Grand Total'
    subtotal[8] = 9999
    return rows + [subtotal]


class ParserTests(unittest.TestCase):
    def test_excel_and_sheets_produce_identical_results(self):
        rows = sample_rows()
        expected, expected_warnings = parse_sales(pd.DataFrame(rows))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'sales.xlsx'
            pd.DataFrame([[None, None] + row for row in rows]).to_excel(
                path, sheet_name=SHEET_NAME, header=False, index=False,
            )
            actual, warnings = load_sales(path)
        pd.testing.assert_frame_equal(actual, expected, check_dtype=False)
        self.assertEqual(warnings, expected_warnings)
        self.assertEqual(len(actual), 22)
        self.assertFalse(warnings)
        summary = summarize(actual, 'Area')
        self.assertEqual(summary['MPP'].sum(), 220)
        self.assertEqual(summary['Actual'].sum(), 176)
        self.assertEqual(summary['Gap'].sum(), -44)

    def test_trailing_blanks_are_padded(self):
        row = sample_rows()[0][:11]  # API omits all trailing empty cells.
        frame, warnings = parse_sales(pd.DataFrame([row]))
        self.assertEqual(frame.iloc[0]['actual_total'], 0)
        self.assertEqual(frame.iloc[0]['mpp_total'], 10)
        self.assertTrue(any('Cabang belum ditemukan' in item for item in warnings))

    def test_invalid_numbers_and_formulas_are_visible(self):
        rows = sample_rows()
        rows[0][13] = '#REF!'
        _, warnings = parse_sales(pd.DataFrame(rows))
        self.assertTrue(any('Nilai bukan angka pada actual_total' in item for item in warnings))
        self.assertTrue(any('actual_total tidak sama' in item for item in warnings))

    def test_duplicate_and_empty_sources_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplikat'):
            parse_sales(pd.DataFrame(sample_rows() + [sample_rows()[0]]))
        for rows in ([], [['Unrecognized branch']]):
            with self.subTest(rows=rows), self.assertRaisesRegex(ValueError, 'Tidak ada cabang'):
                parse_sales(pd.DataFrame(rows))


class CredentialFormattingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Generate a disposable key in memory. No real credentials or network.
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.pem = cls.key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption()).decode()

    def info(self, key):
        return {'client_email': 'reader@example.test', 'private_key': key,
                'token_uri': 'https://oauth2.googleapis.com/token'}

    def test_copied_key_formats_preserve_the_actual_signing_key(self):
        body = ''.join(self.pem.splitlines()[1:-1])
        variants = [self.pem, self.pem.replace('\n', '\r\n'),
                    self.pem.replace('\n', r'\n'), self.pem.replace('\n', r'\\n'),
                    self.pem.replace('\n', r'\r\n'),
                    '-----BEGIN PRIVATE KEY-----' + body + '-----END PRIVATE KEY-----',
                    '-----BEGIN PRIVATE KEY-----\n' + body + '\n-----END PRIVATE KEY-----',
                    '-----BEGIN PRIVATE KEY-----\n' + body + r'\n-----END PRIVATE KEY-----']
        for index, value in enumerate(variants):
            with self.subTest(format=index):
                source = self.info(value)
                normalized = prepare_service_account_info(source)
                self.assertEqual(normalized['private_key'], self.pem)
                self.assertEqual(source['private_key'], value)
                credentials = Credentials.from_service_account_info(normalized, scopes=[READ_SCOPE])
                payload = b'credential-format-regression'
                signature = credentials.sign_bytes(payload)
                self.key.public_key().verify(signature, payload, padding.PKCS1v15(), hashes.SHA256())

    def test_missing_fields_report_names_only(self):
        info = self.info(self.pem)
        del info['token_uri']
        with self.assertRaisesRegex(GoogleSheetsError, 'token_uri') as error:
            prepare_service_account_info(info)
        self.assertNotIn('BEGIN PRIVATE KEY', str(error.exception))

    def test_incomplete_or_corrupt_key_is_rejected_without_leaking_it(self):
        variants = ['PRIVATE_KEY_CONTENT_SHOULD_NOT_APPEAR',
                    '-----BEGIN PRIVATE KEY-----\nPRIVATE_KEY_CONTENT_SHOULD_NOT_APPEAR!\n-----END PRIVATE KEY-----']
        for value in variants:
            with self.subTest(format=value.startswith('-----')), self.assertRaises(GoogleSheetsError) as error:
                prepare_service_account_info(self.info(value))
            self.assertNotIn('PRIVATE_KEY_CONTENT_SHOULD_NOT_APPEAR', str(error.exception))

    def test_example_and_oauth_credentials_have_actionable_errors(self):
        with self.assertRaisesRegex(GoogleSheetsError, 'nilai contoh'):
            prepare_service_account_info(self.info('GANTI_DENGAN_ISI_PRIVATE_KEY'))
        info = self.info(self.pem)
        info['type'] = 'authorized_user'
        with self.assertRaisesRegex(GoogleSheetsError, 'OAuth'):
            prepare_service_account_info(info)


class GoogleApiTests(unittest.TestCase):
    def setUp(self):
        self.auth_patch = patch('google.oauth2.service_account.Credentials.from_service_account_info')
        self.auth = self.auth_patch.start()
        self.addCleanup(self.auth_patch.stop)
        self.session_patch = patch('google.auth.transport.requests.AuthorizedSession')
        self.session_factory = self.session_patch.start()
        self.addCleanup(self.session_patch.stop)
        self.session = self.session_factory.return_value.__enter__.return_value
        self.response = Mock(ok=True, status_code=200)
        self.response.json.return_value = {'values': sample_rows()}
        self.session.get.return_value = self.response
        self.credentials = {'client_email': 'reader@example.test',
                            'private_key': '-----BEGIN PRIVATE KEY-----\nQUJD\n-----END PRIVATE KEY-----\n',
                            'token_uri': 'https://oauth2.googleapis.com/token'}

    def test_id_url_validation(self):
        self.assertEqual(spreadsheet_id(' test-id_1 '), 'test-id_1')
        self.assertEqual(spreadsheet_id('https://docs.google.com/spreadsheets/d/test-id_1/edit#gid=1'), 'test-id_1')
        for invalid in ('', 'https://evil.test/spreadsheets/d/id/edit', 'a/b', 'https://docs.google.com/spreadsheets/d/e/public-id/pubhtml'):
            # Published-to-web URLs do not identify an editable source document.
            with self.subTest(invalid=invalid), self.assertRaises(GoogleSheetsError):
                spreadsheet_id(invalid)

    def test_reads_only_numeric_values_and_escapes_tab(self):
        frame, warnings = load_google_sales('test-id', "Sales O'Brien", self.credentials)
        self.assertEqual(len(frame), 22)
        self.assertFalse(warnings)
        self.auth.assert_called_once_with(self.credentials, scopes=[READ_SCOPE])
        self.session_factory.assert_called_once_with(self.auth.return_value, refresh_timeout=15, max_refresh_attempts=1)
        args, kwargs = self.session.get.call_args
        self.assertTrue(unquote(args[0]).endswith("/values/'Sales O''Brien'!C:R"))
        self.assertEqual(kwargs['params']['valueRenderOption'], 'UNFORMATTED_VALUE')
        self.assertEqual(kwargs['timeout'], 15)

    def test_actionable_http_errors_without_response_body(self):
        for status, expected in [(400, 'tab'), (401, 'Autentikasi'), (403, 'Viewer'), (404, 'ID'), (429, 'Kuota'), (503, 'HTTP 503')]:
            with self.subTest(status=status):
                self.response.ok = False
                self.response.status_code = status
                self.response.text = 'DO_NOT_EXPOSE_REMOTE_BODY'
                with self.assertRaisesRegex(GoogleSheetsError, expected) as error:
                    load_google_sales('test-id', SHEET_NAME, self.credentials)
                self.assertNotIn('DO_NOT_EXPOSE', str(error.exception))

    def test_auth_and_timeout_do_not_expose_secrets(self):
        for failure in (RefreshError('PRIVATE_KEY_SHOULD_NOT_APPEAR'), Timeout('PRIVATE_KEY_SHOULD_NOT_APPEAR')):
            with self.subTest(failure=failure):
                self.session.get.side_effect = failure
                with self.assertRaises(GoogleSheetsError) as error:
                    load_google_sales('test-id', SHEET_NAME, self.credentials)
                self.assertNotIn('PRIVATE_KEY', str(error.exception))
        self.auth.side_effect = ValueError('PRIVATE_KEY_SHOULD_NOT_APPEAR')
        with self.assertRaisesRegex(GoogleSheetsError, 'Kredensial') as error:
            load_google_sales('test-id', SHEET_NAME, self.credentials)
        self.assertNotIn('PRIVATE_KEY', str(error.exception))

    def test_forbidden_distinguishes_api_disabled_from_document_permissions(self):
        self.response.ok = False
        self.response.status_code = 403
        examples = [({'details': [{'reason': 'SERVICE_DISABLED'}]}, 'belum aktif'),
                    ({'message': 'The caller does not have permission'}, 'tidak memiliki izin'),
                    ({'errors': [{'reason': 'quotaExceeded'}]}, 'Kuota')]
        for payload, expected in examples:
            with self.subTest(expected=expected):
                self.response.json.return_value = {'error': payload}
                with self.assertRaisesRegex(GoogleSheetsError, expected):
                    load_google_sales('test-id', SHEET_NAME, self.credentials)

    def test_empty_and_malformed_responses_are_rejected(self):
        for payload in ({}, {'values': 'not rows'}, {'values': [['Unknown']]}, []):
            with self.subTest(payload=payload):
                self.response.json.return_value = payload
                with self.assertRaises(ValueError):
                    load_google_sales('test-id', SHEET_NAME, self.credentials)


if __name__ == '__main__':
    unittest.main()
