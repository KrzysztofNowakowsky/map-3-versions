"""Mapa 3: statystyki zakwitu dla scen porównawczych z lat 2017-2026 -> site/lata.json.

Wejście: daty z sceny_lata.csv (po 2 sceny ze szczytu sezonu z każdego roku) i pobrane pasma
w dane/sceny_lata/<RRRR-MM-DD>/ (pobierz_sceny.py albo paczka mapa3_sceny_lata.zip).
Liczymy tak samo jak przetworz.py (te same funkcje), żeby lata dało się porównać z sezonem na mapie.

Uruchom: python statystyki.py
"""
import csv
import json
from pathlib import Path

import numpy as np

from przetworz import (TU, SITE, wczytaj, maska_morza, wazne_piksele, mci, statystyki,
                       uzupelnij_luke, znajdz_dawce)

DANE = TU / 'dane' / 'sceny_lata'


def daty_z_csv(sciezka):
    with open(sciezka, newline='') as f:
        return [wiersz['data'] for wiersz in csv.DictReader(f)]


def szczyty(wyniki):
    """Dla każdego roku scena z największym % zakwitu (None = brak wiarygodnego wyniku)."""
    lata = {}
    for w in wyniki:
        rok = w['data'][:4]
        if w['zakwit_pct'] is None:
            lata.setdefault(rok, None)
            continue
        if lata.get(rok) is None or w['zakwit_pct'] > lata[rok]['zakwit_pct']:
            lata[rok] = {'data': w['data'], 'zakwit_pct': w['zakwit_pct'], 'mci_mediana': w['mci_mediana']}
    return dict(sorted(lata.items()))


def main():
    zatoka = json.loads((TU / 'zatoka.geojson').read_text(encoding='utf-8'))
    geom = zatoka['features'][0]['geometry']
    daty = daty_z_csv(TU / 'sceny_lata.csv')
    brak = [d for d in daty if not (DANE / d).is_dir()]
    if brak:
        print('brak pobranych scen (pomijam):', ', '.join(brak))
    daty = [d for d in daty if d not in brak]
    if not daty:
        raise SystemExit(f'Brak scen w {DANE} - rozpakuj mapa3_sceny_lata.zip albo uruchom pobierz_sceny.py')

    sceny = {d: wczytaj(DANE / d, geom) for d in daty}
    w_wielokacie = next(iter(sceny.values()))[2]
    # wspólna maska morza dla wszystkich scen porównawczych
    morze = maska_morza([pasma['SCL'] for pasma, _, _ in sceny.values()]) & w_wielokacie
    ile_morza = int(morze.sum())

    wyniki = []
    for data, (pasma, _, _) in sceny.items():
        dawca = znajdz_dawce(data, sceny, w_wielokacie)     # Zatoka Pucka z przelotu +-4 dni
        if dawca:
            pasma, _ = uzupelnij_luke(pasma, sceny[dawca][0])
        ok = wazne_piksele(pasma['SCL'], morze)
        b4, b5, b6 = (pasma[b].astype('float32') for b in ['B04', 'B05', 'B06'])
        wartosc = np.where(ok, mci(b4, b5, b6), np.nan)
        stat = {'data': data, **statystyki(wartosc, int(ok.sum()), ile_morza), 'uzupelnione_z': dawca}
        print(stat)
        wyniki.append(stat)

    SITE.mkdir(exist_ok=True)
    (SITE / 'lata.json').write_text(json.dumps(
        {'sceny': wyniki, 'szczyty': szczyty(wyniki)}, ensure_ascii=False, indent=1), encoding='utf-8')
    print('zapisano site/lata.json -', len(wyniki), 'scen')


if __name__ == '__main__':
    main()
