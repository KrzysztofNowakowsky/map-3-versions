"""Mapa 3, krok 3: przetwarzanie pobranych scen Sentinel-2 LOKALNIE -> MCI, statystyki, kafelki, strona.

Wejście: dane/sceny_<rok>/<RRRR-MM-DD>/T34UCF_*_{B04,B05,B06,SCL,TCI}_20m.jp2 (z pobierz_sceny.py)
Wyjście: site/ (gotowa strona statyczna: index.html, kafelki, sceny.json) - nie commitujemy

Uruchom: python przetworz.py [--rok 2019]   (domyślnie 2026)
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import rasterio
from matplotlib.colors import LinearSegmentedColormap
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from PIL import Image
from rasterio.windows import from_bounds

TU = Path(__file__).resolve().parent
SITE = TU / 'site'
LABORATORIUM_SRC = TU.parent / 'data' / 'LABOLATORIUM' / 'src'   # kafelki XYZ + Leaflet z zajęć
sys.path.insert(0, str(LABORATORIUM_SRC))
from landsat_lab import xyz_tiles   # noqa: E402

PROG_ZAKWITU = 30          # MCI x10000 > 30 = zakwit (próg z pracy o Jeziorze Ełckim)
MIN_WAZNYCH_PCT = 30       # poniżej tego % czystej wody nie podajemy % zakwitu (zostają resztki chmur)
MIN_POKRYCIA_STRONY = 65   # na stronę tylko daty z >= 65% czystej wody (60-65% = rozproszone chmury, szum MCI, np. 28.09.2019)
MAX_DNI_UZUPELNIENIA = 4   # dziurę po przelocie 9:50 (Zatoka Pucka) bierzemy z przelotu +-4 dni
MAX_DNI_CHMURY = 3         # na MAPIE miejsca pod chmurami bierzemy z najbliższych czystych dni (+-3)
ALFA_UZUPELNIONE = 150     # piksele z innego dnia rysujemy przygaszone (255 = pełne)
ZOOM_MIN, ZOOM_MAX = 9, 11  # 11 ~ 40 m/piksel; zawirowania mają km, a strona mieści się na serwerze
SCL_WODA = [6]              # tylko czysta woda
SCL_CHMURY = [3, 8, 9, 10]  # cień chmur, chmury średnie i wysokie, cirrus (zawyża MCI - sprawdzone na 33 scenach)
SKALA_MCI = LinearSegmentedColormap.from_list(
    'mci', ['#08306b', '#2171b5', '#41b6c4', '#7fcd5b', '#f7e43a', '#f46d43', '#a50026'])
MCI_OD, MCI_DO = -10, 80   # zakres kolorów legendy


def mci(b4, b5, b6):
    """MCI = B5 - 0,4667*B4 - 0,5333*B6 na surowych DN (= reflektancja x10000).
    Współczynniki sumują się do 0, więc stały offset L2A (-1000 od 2022 r.) się znosi."""
    return b5 - 0.4667 * b4 - 0.5333 * b6


def poszerz(maska, piksele):
    """Rozszerza maskę o n pikseli (4-sąsiedztwo) - bufor od lądu i chmur."""
    out = maska.copy()
    for _ in range(piksele):
        m = out.copy()
        m[1:] |= out[:-1]
        m[:-1] |= out[1:]
        m[:, 1:] |= out[:, :-1]
        m[:, :-1] |= out[:, 1:]
        out = m
    return out


def plik(folder, pasmo):
    pliki = sorted(folder.glob(f'*_{pasmo}_20m.*'))
    if len(pliki) != 1:
        raise FileNotFoundError(f'W {folder} jest {len(pliki)} plików pasma {pasmo} (ma być 1) - '
                                'usuń folder tej daty i pobierz ją ponownie')
    return pliki[0]


def wczytaj(folder, zatoka_4326):
    """Czyta pasma przycięte do prostokąta zatoki. Zwraca słownik tablic + profil i maskę wielokąta."""
    with rasterio.open(plik(folder, 'SCL')) as src:
        geom = transform_geom('EPSG:4326', src.crs, zatoka_4326)
        xs = [p[0] for p in geom['coordinates'][0]]
        ys = [p[1] for p in geom['coordinates'][0]]
        okno = from_bounds(min(xs), min(ys), max(xs), max(ys), src.transform).round_offsets().round_lengths()
        profil = src.profile.copy()
        profil.update(driver='GTiff', width=okno.width, height=okno.height,
                      transform=src.window_transform(okno))
    pasma = {}
    for nazwa in ['B04', 'B05', 'B06', 'SCL']:
        with rasterio.open(plik(folder, nazwa)) as src:
            pasma[nazwa] = src.read(1, window=okno, boundless=True, fill_value=0)
    with rasterio.open(plik(folder, 'TCI')) as src:
        pasma['TCI'] = src.read([1, 2, 3], window=okno, boundless=True, fill_value=0)
    w_wielokacie = geometry_mask([geom], out_shape=pasma['SCL'].shape,
                                 transform=profil['transform'], invert=True)
    return pasma, profil, w_wielokacie


def uzupelnij_luke(pasma, dawca):
    """Przelot ok. 9:50 UTC nie sięga Zatoki Puckiej (SCL=0 = brak danych). Tam, gdzie scena nie ma
    danych, a dawca (najbliższy przelot 10:00) ma, wstawiamy piksele dawcy we WSZYSTKICH pasmach -
    łącznie z jego SCL, więc chmury z dnia dawcy są dalej maskowane. Zwraca (nowe pasma, ile pikseli)."""
    luka = (pasma['SCL'] == 0) & (dawca['SCL'] != 0)
    if not luka.any():
        return pasma, 0
    nowe = {k: v.copy() for k, v in pasma.items()}
    for nazwa in ['B04', 'B05', 'B06', 'SCL']:
        nowe[nazwa][luka] = dawca[nazwa][luka]
    nowe['TCI'][:, luka] = dawca['TCI'][:, luka]
    return nowe, int(luka.sum())


def znajdz_dawce(data, sceny, w_wielokacie):
    """Najbliższa data (max MAX_DNI_UZUPELNIENIA dni) z danymi tam, gdzie scena ich nie ma."""
    from datetime import date
    dzien = date.fromisoformat(data)
    luka = (sceny[data][0]['SCL'] == 0) & w_wielokacie
    if luka.mean() < 0.001:
        return None
    kandydaci = []
    for inna, (pasma, _, _) in sceny.items():
        roznica = abs((date.fromisoformat(inna) - dzien).days)
        if inna != data and roznica <= MAX_DNI_UZUPELNIENIA:
            pokrycie = (pasma['SCL'][luka] != 0).mean()
            if pokrycie > 0.9:
                kandydaci.append((roznica, -pokrycie, inna))
    return min(kandydaci)[2] if kandydaci else None


def uzupelnij_chmury(wartosc, dawcy):
    """Tylko do MAPY: tam, gdzie dzień nie ma czystej wody (NaN), wstawia MCI z dawców
    (lista tablic od najbliższego dnia). Statystyki liczymy wcześniej, z samego dnia.
    Zwraca (uzupełnione MCI, maska pikseli wziętych od dawców, ile pikseli dał każdy dawca)."""
    wynik = wartosc.copy()
    z_dawcow = np.zeros(wartosc.shape, bool)
    wklad = []
    for dawca in dawcy:
        brak = np.isnan(wynik) & np.isfinite(dawca)
        wynik[brak] = dawca[brak]
        z_dawcow |= brak
        wklad.append(int(brak.sum()))
    return wynik, z_dawcow, wklad


def maska_morza(lista_scl, min_udzial=0.2):
    """Stała maska morza: piksel, który był wodą (SCL=6) w >= 20% scen. Odcina ląd pod cirrusem."""
    woda = np.mean([scl == 6 for scl in lista_scl], axis=0)
    return woda >= min_udzial


def wazne_piksele(scl, morze):
    """Czysta woda morza: bez chmur i cirrusa, z buforem 60 m od lądu i 100 m od chmur."""
    return (morze & np.isin(scl, SCL_WODA)
            & ~poszerz(~morze, 3)
            & ~poszerz(np.isin(scl, SCL_CHMURY), 5))


def statystyki(wartosci_mci, ile_wazne, ile_morza):
    v = wartosci_mci[np.isfinite(wartosci_mci)]
    wazne_pct = round(100 * ile_wazne / ile_morza, 1)
    if v.size == 0 or wazne_pct < MIN_WAZNYCH_PCT:     # garstka pikseli nie mówi nic o zatoce
        return {'wazne_pct': wazne_pct, 'zakwit_pct': None, 'mci_mediana': None}
    return {'wazne_pct': wazne_pct,
            'zakwit_pct': round(100 * float((v > PROG_ZAKWITU).mean()), 1),
            'mci_mediana': round(float(np.median(v)), 1)}


def zapisz_rgba(sciezka, rgba, profil):
    p = profil.copy()
    p.update(count=4, dtype='uint8', nodata=None, compress='deflate')
    with rasterio.open(sciezka, 'w', **p) as dst:
        dst.write(np.moveaxis(rgba, -1, 0))


def zmniejsz_kafelki(folder):
    """PNG RGBA -> PNG z paletą (255 kolorów + 1 przezroczysty). Kilka razy mniejsze pliki."""
    for png in folder.rglob('*.png'):
        rgba = np.asarray(Image.open(png).convert('RGBA'))
        paleta = Image.fromarray(rgba[..., :3]).quantize(255, method=Image.Quantize.MEDIANCUT)
        indeksy = np.asarray(paleta).copy()
        indeksy[rgba[..., 3] == 0] = 255                  # indeks 255 = przezroczysty
        kolory = paleta.getpalette()                      # tylko użyte kolory -> dopełniamy do 256
        kolory = kolory[:765] + [0] * (765 - len(kolory[:765])) + [0, 0, 0]
        wynik = Image.fromarray(indeksy)
        wynik.putpalette(kolory)
        wynik.save(png, transparency=255)   # bez optimize - przenumerowałoby paletę


def koloruj_mci(wartosc, przygaszone=None):
    t = np.clip((wartosc - MCI_OD) / (MCI_DO - MCI_OD), 0, 1)
    rgba = SKALA_MCI(np.nan_to_num(t), bytes=True)
    rgba[..., 3] = np.isfinite(wartosc) * 255
    if przygaszone is not None:
        rgba[..., 3][przygaszone] = ALFA_UZUPELNIONE
    return rgba


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rok', type=int, default=2026, help='sezon do przetworzenia (domyślnie 2026)')
    args = parser.parse_args()
    DANE = TU / 'dane' / f'sceny_{args.rok}'
    zatoka = json.loads((TU / 'zatoka.geojson').read_text(encoding='utf-8'))
    geom = zatoka['features'][0]['geometry']
    foldery = sorted(p for p in DANE.iterdir() if p.is_dir())
    if not foldery:
        raise SystemExit(f'Brak scen w {DANE} - najpierw uruchom pobierz_sceny.py')
    print('scen:', len(foldery))

    sceny = {f.name: wczytaj(f, geom) for f in foldery}
    w_wielokacie = next(iter(sceny.values()))[2]
    morze = maska_morza([pasma['SCL'] for pasma, _, _ in sceny.values()]) & w_wielokacie
    ile_morza = int(morze.sum())

    tmp = TU / 'dane' / 'tmp'
    tmp.mkdir(parents=True, exist_ok=True)
    wyniki, wszystkie = [], []
    mci_dnia, tci_dnia = {}, {}
    # 1. przejście: MCI i statystyki z samego dnia (+ Zatoka Pucka z najbliższego przelotu)
    for data, (pasma, profil, _) in sceny.items():
        dawca = znajdz_dawce(data, sceny, w_wielokacie)
        if dawca:
            pasma, ile = uzupelnij_luke(pasma, sceny[dawca][0])
        ok = wazne_piksele(pasma['SCL'], morze)
        b4, b5, b6 = (pasma[b].astype('float32') for b in ['B04', 'B05', 'B06'])
        mci_dnia[data] = np.where(ok, mci(b4, b5, b6), np.nan).astype('float32')
        tci_dnia[data] = pasma['TCI']
        stat = {'data': data, **statystyki(mci_dnia[data], int(ok.sum()), ile_morza), 'uzupelnione_z': dawca}
        wszystkie.append(stat)
        if stat['wazne_pct'] < MIN_POKRYCIA_STRONY:
            print(data, 'pominięta na stronie - czystej wody tylko', stat['wazne_pct'], '%')
            continue
        wyniki.append(stat)

    # 2. przejście (tylko mapa): dziury po chmurach z najbliższych czystych dni, także tych spoza strony
    from datetime import date
    for stat in wyniki:
        data = stat['data']
        dzien = date.fromisoformat(data)
        blisko = sorted((abs((date.fromisoformat(d) - dzien).days), d) for d in mci_dnia if d != data)
        dawcy = [d for dni, d in blisko if dni <= MAX_DNI_CHMURY]
        wartosc, z_dawcow, wklad = uzupelnij_chmury(mci_dnia[data], [mci_dnia[d] for d in dawcy])
        stat['chmury_uzupelnione_pct'] = round(100 * int((z_dawcow & morze).sum()) / ile_morza, 1)
        stat['chmury_z'] = [d for d, ile in zip(dawcy, wklad) if ile > 0]
        print(data, stat)

        profil = sceny[data][1]
        zapisz_rgba(tmp / 'mci.tif', koloruj_mci(wartosc, przygaszone=z_dawcow), profil)
        xyz_tiles(tmp / 'mci.tif', SITE / 'kafelki' / 'mci' / data, ZOOM_MIN, ZOOM_MAX)
        zmniejsz_kafelki(SITE / 'kafelki' / 'mci' / data)
        tci = np.moveaxis(tci_dnia[data], 0, -1)
        alfa = (tci.max(axis=-1) > 0).astype('uint8') * 255
        zapisz_rgba(tmp / 'rgb.tif', np.dstack([tci, alfa]), profil)
        xyz_tiles(tmp / 'rgb.tif', SITE / 'kafelki' / 'rgb' / data, ZOOM_MIN, ZOOM_MAX)
        zmniejsz_kafelki(SITE / 'kafelki' / 'rgb' / data)

    # strona: źródła ze strona/ + Leaflet z zajęć + dane
    shutil.copytree(TU / 'strona', SITE, dirs_exist_ok=True)
    shutil.copytree(LABORATORIUM_SRC / 'vendor', SITE / 'vendor', dirs_exist_ok=True)
    shutil.copy(TU / 'zatoka.geojson', SITE / 'zatoka.geojson')
    legenda = ['#' + ''.join(f'{c:02x}' for c in SKALA_MCI(t, bytes=True)[:3]) for t in np.linspace(0, 1, 7)]
    (SITE / 'sceny.json').write_text(json.dumps({
        'rok': args.rok, 'sceny': wyniki, 'wszystkie_sceny': wszystkie, 'prog_zakwitu': PROG_ZAKWITU, 'zoom_min': ZOOM_MIN, 'zoom_max': ZOOM_MAX,
        'legenda': {'od': MCI_OD, 'do': MCI_DO, 'kolory': legenda}}, ensure_ascii=False, indent=1), encoding='utf-8')
    shutil.rmtree(tmp)
    print('na stronie', len(wyniki), 'z', len(wszystkie), 'dat ->', SITE)


if __name__ == '__main__':
    main()
