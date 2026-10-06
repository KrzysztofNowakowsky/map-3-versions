"""Testy maski jakości. Uruchom z folderu mapa2_llm: python -m unittest discover -s tests"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from landsat_v2 import quality_mask, read_metadata, DATA


class QualityMaskTests(unittest.TestCase):
    def test_water_is_valid(self):
        # 2 = bit 1 (czysty piksel), 4 = bit 2 (woda) - oba mają zostać
        qa = np.array([2, 4], dtype='uint16')
        self.assertTrue(quality_mask(qa, np.zeros_like(qa)).all())

    def test_clouds_shadow_snow_rejected(self):
        qa = np.array([1, 8, 16, 32, 3 << 6, 3 << 8, 1024], dtype='uint16')
        self.assertFalse(quality_mask(qa, np.zeros_like(qa)).any())

    def test_saturation_only_b2_b6(self):
        sat = np.array([0, 1 << 1, 1 << 4, 1 << 7], dtype='uint16')  # B1 i B7 nas nie obchodzą
        np.testing.assert_array_equal(quality_mask(np.full(4, 2, dtype='uint16'), sat), [1, 1, 0, 1])

    def test_metadata_date_and_scale(self):
        meta = read_metadata(DATA / 'scene')
        self.assertEqual(meta['date'], '2013-08-07')
        self.assertAlmostEqual(meta['bands']['sr_band5']['scale'], 0.0001)

    def test_low_cirrus_is_ok(self):
        qa = np.array([2 | (1 << 8)], dtype='uint16')
        self.assertTrue(quality_mask(qa, np.zeros_like(qa)).all())


if __name__ == '__main__':
    unittest.main()