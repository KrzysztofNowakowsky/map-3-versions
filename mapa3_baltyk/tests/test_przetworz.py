"""Testy przetwarzania mapy 3. Uruchom z folderu mapa3_baltyk: python -m unittest discover -s tests"""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from przetworz import mci, poszerz, maska_morza, wazne_piksele, statystyki, zmniejsz_kafelki


class MciTests(unittest.TestCase):
    def test_wzor(self):
        self.assertAlmostEqual(float(mci(np.float32(100), np.float32(200), np.float32(150))), 200 - 0.4667 * 100 - 0.5333 * 150, places=2)

    def test_offset_l2a_sie_znosi(self):
        # od 2022 r. DN w L2A mają +1000 (BOA_ADD_OFFSET) - MCI ma wyjść tak samo
        b4, b5, b6 = np.float32(120), np.float32(260), np.float32(140)
        self.assertAlmostEqual(float(mci(b4, b5, b6)), float(mci(b4 + 1000, b5 + 1000, b6 + 1000)), places=2)


class MaskiTests(unittest.TestCase):
    def test_poszerz_o_jeden_piksel(self):
        m = np.zeros((5, 5), bool)
        m[2, 2] = True
        self.assertEqual(int(poszerz(m, 1).sum()), 5)   # środek + 4 sąsiadów

    def test_maska_morza_z_wielu_scen(self):
        woda, lad = np.full((2, 2), 6), np.full((2, 2), 4)
        self.assertTrue(maska_morza([woda, lad, lad]).all())        # 33% scen = woda -> morze
        self.assertFalse(maska_morza([woda, lad, lad, lad, lad, lad]).any())  # 17% -> nie

    def test_cirrus_zostaje_chmura_nie(self):
        scl = np.full((20, 20), 6)
        scl[0:2, 0:2] = 9                      # chmura w rogu
        scl[15:20, 15:20] = 10                 # cienki cirrus
        ok = wazne_piksele(scl, np.ones((20, 20), bool))
        self.assertTrue(ok[17, 17])            # cirrus = ważny
        self.assertFalse(ok[3, 3])             # 100 m bufora od chmury

    def test_statystyki_zakwitu(self):
        v = np.array([10, 20, 40, 50, np.nan])
        s = statystyki(v, ile_wazne=4, ile_morza=8)
        self.assertEqual(s['wazne_pct'], 50.0)
        self.assertEqual(s['zakwit_pct'], 50.0)

    def test_za_malo_pikseli_brak_wyniku(self):
        # regresja: 28.07 - skrawek sceny, kilka pikseli dawało "95% zakwitu"
        s = statystyki(np.array([50.0, 60.0]), ile_wazne=2, ile_morza=1000)
        self.assertIsNone(s['zakwit_pct'])


class KafelkiTests(unittest.TestCase):
    def test_przezroczystosc_po_zmniejszeniu(self):
        # regresja: przy paletowaniu przezroczyste tło zmieniało się w czarne
        with tempfile.TemporaryDirectory() as d:
            rgba = np.zeros((256, 256, 4), 'uint8')
            rgba[:100, :100] = [200, 50, 50, 255]
            Image.fromarray(rgba).save(Path(d) / 'k.png')
            zmniejsz_kafelki(Path(d))
            wynik = np.asarray(Image.open(Path(d) / 'k.png').convert('RGBA'))
            self.assertEqual(int(wynik[200, 200, 3]), 0)
            self.assertEqual(int(wynik[50, 50, 3]), 255)


if __name__ == '__main__':
    unittest.main()
