"""Testy przetwarzania mapy 3. Uruchom z folderu mapa3_baltyk: python -m unittest discover -s tests"""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from przetworz import mci, poszerz, maska_morza, wazne_piksele, statystyki, zmniejsz_kafelki, uzupelnij_luke, uzupelnij_chmury, koloruj_mci


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

    def test_chmura_i_cirrus_odrzucone_z_buforem(self):
        scl = np.full((20, 20), 6)
        scl[0:2, 0:2] = 9                      # chmura w rogu
        scl[15:20, 15:20] = 10                 # cirrus - zawyża MCI, więc też odrzucamy
        ok = wazne_piksele(scl, np.ones((20, 20), bool))
        self.assertFalse(ok[17, 17])           # cirrus
        self.assertFalse(ok[3, 3])             # 100 m bufora od chmury
        self.assertTrue(ok[9, 9])              # czysta woda daleko od chmur

    def test_statystyki_zakwitu(self):
        v = np.array([10, 20, 40, 50, np.nan])
        s = statystyki(v, ile_wazne=4, ile_morza=10)
        self.assertEqual(s['wazne_pct'], 40.0)
        self.assertEqual(s['zakwit_pct'], 50.0)

    def test_za_malo_pikseli_brak_wyniku(self):
        # regresja: 28.07 - skrawek sceny, kilka pikseli dawało "95% zakwitu"
        s = statystyki(np.array([50.0, 60.0]), ile_wazne=2, ile_morza=1000)
        self.assertIsNone(s['zakwit_pct'])


class UzupelnianieTests(unittest.TestCase):
    def test_luka_wypelniona_z_dawcy_z_jego_maska(self):
        def scena(scl, dn):
            return {'B04': np.full((2, 2), dn), 'B05': np.full((2, 2), dn), 'B06': np.full((2, 2), dn),
                    'SCL': np.array(scl), 'TCI': np.full((3, 2, 2), dn, 'uint8')}
        cel = scena([[0, 6], [0, 6]], 10)        # lewa kolumna: brak danych (przelot 9:50)
        dawca = scena([[6, 6], [9, 6]], 50)      # u dawcy: woda i jedna chmura
        nowe, ile = uzupelnij_luke(cel, dawca)
        self.assertEqual(ile, 2)
        self.assertEqual(nowe['B05'][0, 0], 50)  # wzięte od dawcy
        self.assertEqual(nowe['B05'][0, 1], 10)  # własne dane zostają
        self.assertEqual(nowe['SCL'][1, 0], 9)   # chmura dawcy dalej jest chmurą
        self.assertEqual(cel['B05'][0, 0], 10)   # oryginał nieruszony


class ChmuryTests(unittest.TestCase):
    def test_najblizszy_dawca_ma_pierwszenstwo(self):
        nan = np.nan
        dzien = np.array([[10.0, nan, nan]])            # 2 piksele pod chmurą
        blizszy = np.array([[99.0, 40.0, nan]])          # zna środkowy
        dalszy = np.array([[99.0, 70.0, 50.0]])          # zna oba
        wynik, z_dawcow, wklad = uzupelnij_chmury(dzien, [blizszy, dalszy])
        np.testing.assert_array_equal(wynik, [[10.0, 40.0, 50.0]])  # własna wartość nietknięta
        self.assertEqual(wklad, [1, 1])
        self.assertEqual(z_dawcow.tolist(), [[False, True, True]])
        self.assertTrue(np.isnan(dzien[0, 1]))                      # oryginał bez zmian

    def test_uzupelnione_przygaszone_na_mapie(self):
        rgba = koloruj_mci(np.array([[20.0, 20.0]]), przygaszone=np.array([[False, True]]))
        self.assertEqual(int(rgba[0, 0, 3]), 255)
        self.assertLess(int(rgba[0, 1, 3]), 255)


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
