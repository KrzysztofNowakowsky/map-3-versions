"""Mapa 3, krok 1: wybór scen Sentinel-2 nad Zatoką Gdańską (GEE służy TYLKO do wyszukania dat).

Zapisuje:
  sceny_<rok>.csv - wszystkie daty VI-IX wybranego roku z min. 50% morza w zatoce widocznego (bez chmur)
  sceny_lata.csv  - po 2 najlepsze daty ze szczytu sezonu (VII-VIII) dla pozostałych lat 2017-2026

Uruchom: python szukaj_scen.py --projekt <id projektu GEE> [--rok 2019]
"""
import argparse
import csv
import json
from pathlib import Path

import ee

TU = Path(__file__).resolve().parent
KAFEL = '34UCF'          # cała zatoka mieści się w jednym kaflu S2
MIN_WODY = 0.50          # min. udział morza w zatoce widoczny jako woda (SCL 6) lub cienki cirrus (SCL 10)


def udzial_wody(obraz, zatoka, morze):
    """Jaka część MORZA w wielokącie jest widoczna (woda lub cienki cirrus, bez chmur)."""
    scl = obraz.select('SCL').unmask(0)                 # brak danych liczy się jako niewidoczne
    widac = scl.eq(6).Or(scl.eq(10)).And(morze)         # cirrus nad lądem się nie liczy
    suma = ee.Image.cat(widac.rename('w'), morze.rename('m')).reduceRegion(
        ee.Reducer.sum(), zatoka, 200, maxPixels=1e9)
    udzial = ee.Number(suma.get('w')).divide(ee.Number(suma.get('m')))
    return obraz.set({'data': obraz.date().format('YYYY-MM-dd'), 'woda': udzial})


def lista_dat(zatoka, od, do):
    # stała mapa wód JRC (woda w >50% obserwacji 1984-2021) - tylko do wyboru scen
    morze = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence').gt(50).unmask(0)
    kolekcja = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                .filter(ee.Filter.eq('MGRS_TILE', KAFEL))
                .filterDate(od, do)
                .map(lambda img: udzial_wody(img, zatoka, morze)))
    wiersze = kolekcja.reduceColumns(ee.Reducer.toList(2), ['data', 'woda']).get('list').getInfo()
    najlepsze = {}
    for data, woda in wiersze:          # ta sama data może mieć 2 sceny - bierzemy lepszą
        najlepsze[data] = max(najlepsze.get(data, 0), woda or 0)
    return sorted(najlepsze.items())


def zapisz(sciezka, wiersze):
    with open(sciezka, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['data', 'udzial_wody'])
        for data, woda in wiersze:
            w.writerow([data, round(woda, 3)])
    print('zapisano', sciezka.name, '-', len(wiersze), 'dat')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projekt', required=True, help='id projektu Google Earth Engine')
    parser.add_argument('--rok', type=int, default=2026, help='sezon pokazywany na mapie (domyślnie 2026)')
    args = parser.parse_args()
    ee.Initialize(project=args.projekt)
    geom = json.loads((TU / 'zatoka.geojson').read_text(encoding='utf-8'))['features'][0]['geometry']
    zatoka = ee.Geometry(geom)

    sezon = [(d, w) for d, w in lista_dat(zatoka, f'{args.rok}-06-01', f'{args.rok}-10-01') if w >= MIN_WODY]
    zapisz(TU / f'sceny_{args.rok}.csv', sezon)

    lata = []
    for rok in [r for r in range(2017, 2027) if r != args.rok]:
        daty = [(d, w) for d, w in lista_dat(zatoka, f'{rok}-07-01', f'{rok}-09-01') if w >= MIN_WODY]
        lata += sorted(sorted(daty, key=lambda x: -x[1])[:2])
    zapisz(TU / 'sceny_lata.csv', lata)


if __name__ == '__main__':
    main()
