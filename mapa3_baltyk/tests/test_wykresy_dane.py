"""Testy sst.py i statystyki.py (bez internetu i bez scen). Uruchom z mapa3_baltyk:
python -m unittest discover -s tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sst import srednie_dzienne, bez_brakow
from statystyki import szczyty


class SstTests(unittest.TestCase):
    def test_srednia_dobowa_bez_brakow(self):
        czasy = ['2019-07-25T00:00', '2019-07-25T12:00', '2019-07-26T00:00', '2019-07-26T12:00']
        wynik = srednie_dzienne(czasy, [18.0, 20.0, None, 21.0])
        self.assertEqual(wynik, {'2019-07-25': 19.0, '2019-07-26': 21.0})

    def test_dzien_bez_danych_pominiety(self):
        self.assertEqual(srednie_dzienne(['2019-07-25T00:00'], [None]), {})

    def test_archiwum_puste_dni_pominiete(self):
        self.assertEqual(bez_brakow(['2019-07-25', '2019-07-26'], [18.1, None]), {'2019-07-25': 18.1})


class SzczytyTests(unittest.TestCase):
    def test_najwiekszy_zakwit_w_roku(self):
        wyniki = [{'data': '2020-07-14', 'zakwit_pct': 12.0, 'mci_mediana': 5.0},
                  {'data': '2020-08-13', 'zakwit_pct': 40.5, 'mci_mediana': 22.0},
                  {'data': '2021-07-14', 'zakwit_pct': 3.0, 'mci_mediana': 1.0}]
        s = szczyty(wyniki)
        self.assertEqual(s['2020']['data'], '2020-08-13')
        self.assertEqual(s['2021']['zakwit_pct'], 3.0)

    def test_rok_bez_wiarygodnej_sceny(self):
        wyniki = [{'data': '2023-07-29', 'zakwit_pct': None, 'mci_mediana': None},
                  {'data': '2024-08-07', 'zakwit_pct': None, 'mci_mediana': None},
                  {'data': '2024-08-27', 'zakwit_pct': 8.0, 'mci_mediana': 2.0}]
        s = szczyty(wyniki)
        self.assertIsNone(s['2023'])
        self.assertEqual(s['2024']['data'], '2024-08-27')


if __name__ == '__main__':
    unittest.main()
