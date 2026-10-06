"""Testy wskaźników. Uruchom z folderu mapa2_llm: python -m unittest discover -s tests"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from landsat_v2 import normalized_difference, calculate_indices


class IndicesTests(unittest.TestCase):
    def test_zero_denominator_gives_nan(self):
        out = normalized_difference(np.array([0.0, 0.2]), np.array([0.0, -0.2]))
        self.assertTrue(np.isnan(out).all())

    def test_values_and_negatives_kept(self):
        out = normalized_difference(np.array([0.3, 0.1, 0.0]), np.array([0.1, 0.3, 0.2]))
        np.testing.assert_allclose(out, [0.5, -0.5, -1.0], rtol=1e-6)

    def test_nan_input_gives_nan(self):
        out = normalized_difference(np.array([np.nan, 0.4]), np.array([0.2, 0.2]))
        self.assertTrue(np.isnan(out[0]))
        self.assertAlmostEqual(float(out[1]), 1 / 3, places=5)

    def test_calculate_indices_names(self):
        refl = {i: np.full((2, 2), 0.1 * i, dtype='float32') for i in range(2, 7)}
        self.assertEqual(set(calculate_indices(refl)), {'NDVI', 'NDBI', 'MNDWI'})


if __name__ == '__main__':
    unittest.main()
