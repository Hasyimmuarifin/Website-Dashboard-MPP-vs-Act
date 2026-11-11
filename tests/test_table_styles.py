import unittest

import pandas as pd

from table_styles import gap_cell_style, style_gap_cells


def background(value, scale=10):
    return gap_cell_style(value, scale).split(';')[0].split(': ')[1]


class GapColorTests(unittest.TestCase):
    def test_zero_stays_white_and_larger_signed_gaps_are_darker(self):
        self.assertEqual(background(0), '#FFFFFF')
        for sign in (-1, 1):
            light = tuple(int(background(sign)[i:i+2], 16) for i in (1, 3, 5))
            dark = tuple(int(background(sign * 10)[i:i+2], 16) for i in (1, 3, 5))
            self.assertTrue(all(dark[i] < light[i] for i in range(3)))
            if sign < 0:
                self.assertGreater(dark[0], dark[1])
            else:
                self.assertGreater(dark[1], dark[0])

    def test_styling_preserves_numbers_percentages_and_csv(self):
        data = pd.DataFrame({'Gap': [-10, 0, 10], 'Pemenuhan (%)': [50.0, 100.0, 150.0]})
        before = data.copy(deep=True)
        styled = style_gap_cells(data)
        styled.to_html()  # Exercise real Styler computation/serialization.
        pd.testing.assert_frame_equal(styled.data, before)
        self.assertEqual(styled.data.to_csv(index=False), before.to_csv(index=False))

    def test_missing_and_all_zero_gaps_do_not_raise(self):
        self.assertEqual(background(float('nan')), '#FFFFFF')
        style_gap_cells(pd.DataFrame({'Gap': [0, 0]})).to_html()
