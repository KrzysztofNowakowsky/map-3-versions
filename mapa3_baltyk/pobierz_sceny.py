"""Mapa 3, krok 2: pobranie scen Sentinel-2 L2A z Copernicus Data Space (oficjalne źródło ESA).

Dla każdej daty z sceny_<rok>.csv i sceny_lata.csv pobiera z kafla 34UCF tylko potrzebne pliki 20 m:
B04, B05, B06 (do MCI), SCL (maska) i TCI (prawdziwe kolory) - ok. 125 MB na datę zamiast 1 GB.

Konto: https://dataspace.copernicus.eu (darmowe). Login i hasło podajesz przy uruchomieniu
(albo w zmiennych CDSE_USER / CDSE_PASSWORD) - nigdy nie wpisuj ich do kodu ani do gita.

Uruchom:  python pobierz_sceny.py [--rok 2019]  (pobiera brakujące; domyślnie rok 2026)
          python pobierz_sceny.py --sprawdz  (tylko szuka produktów, bez logowania i pobierania)
"""
import argparse
import csv
import getpass
import os
from pathlib import Path

import requests

TU = Path(__file__).resolve().parent
KATALOG = 'https://catalogue.dataspace.copernicus.eu/odata/v1'
POBIERANIE = 'https://download.dataspace.copernicus.eu/odata/v1'
TOKEN = 'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token'
KAFEL = 'T34UCF'
PASMA = ['B04', 'B05', 'B06', 'SCL', 'TCI']


def wczytaj_daty(nazwa):
    with open(TU / nazwa, newline='') as f:
        return [wiersz['data'] for wiersz in csv.DictReader(f)]


def znajdz_produkt(data):
    """Produkt L2A z kafla 34UCF z danego dnia. Bywa kilka (dwa przeloty albo skrawek kafla na
    krawędzi pasa) - bierzemy NAJWIĘKSZY, bo pokrywa najwięcej kafla (mały = głównie brak danych)."""
    filtr = (f"Collection/Name eq 'SENTINEL-2' and contains(Name,'MSIL2A') and contains(Name,'_{KAFEL}_') "
             f"and ContentDate/Start ge {data}T00:00:00.000Z and ContentDate/Start le {data}T23:59:59.999Z")
    r = requests.get(f'{KATALOG}/Products', params={'$filter': filtr, '$top': 20}, timeout=60)
    r.raise_for_status()
    produkty = r.json()['value']
    if not produkty:
        return None
    return max(produkty, key=lambda p: p['ContentLength'])


def pliki_20m(produkt):
    """Ścieżki (węzły OData) do plików 20 m wewnątrz produktu .SAFE."""
    baza = f"{KATALOG}/Products({produkt['Id']})/Nodes({produkt['Name']})/Nodes(GRANULE)"
    granula = requests.get(f'{baza}/Nodes', timeout=60).json()['result'][0]['Name']
    folder = f'{baza}/Nodes({granula})/Nodes(IMG_DATA)/Nodes(R20m)'
    nazwy = [n['Name'] for n in requests.get(f'{folder}/Nodes', timeout=60).json()['result']]
    wynik = {}
    for pasmo in PASMA:
        nazwa = next(n for n in nazwy if n.endswith(f'_{pasmo}_20m.jp2'))
        wynik[pasmo] = (nazwa, f'{folder}/Nodes({nazwa})/$value'.replace(KATALOG, POBIERANIE))
    return wynik


def zaloguj(uzytkownik, haslo):
    r = requests.post(TOKEN, data={'client_id': 'cdse-public', 'grant_type': 'password',
                                   'username': uzytkownik, 'password': haslo}, timeout=60)
    if r.status_code != 200:
        raise SystemExit(f'Logowanie do Copernicus nie powiodło się: {r.json().get("error_description", r.text)}')
    return r.json()['access_token']


def pobierz_plik(url, cel, token):
    """Pobiera z autoryzacją; przekierowania obsługujemy ręcznie, bo requests gubi nagłówek przy zmianie hosta."""
    naglowki = {'Authorization': f'Bearer {token}'}
    for _ in range(5):
        r = requests.get(url, headers=naglowki, stream=True, allow_redirects=False, timeout=300)
        if r.status_code in (301, 302, 303, 307, 308):
            url = r.headers['Location']
            continue
        r.raise_for_status()
        tymczasowy = cel.with_suffix('.czesc')
        with open(tymczasowy, 'wb') as f:
            for kawalek in r.iter_content(1 << 20):
                f.write(kawalek)
        tymczasowy.rename(cel)          # plik pojawia się dopiero po pełnym pobraniu
        return
    raise RuntimeError(f'Za dużo przekierowań: {url}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sprawdz', action='store_true', help='tylko znajdź produkty, nic nie pobieraj')
    parser.add_argument('--rok', type=int, default=2026, help='sezon pokazywany na mapie (domyślnie 2026)')
    args = parser.parse_args()

    zadania = [(f'sceny_{args.rok}', d) for d in wczytaj_daty(f'sceny_{args.rok}.csv')]
    zadania += [('sceny_lata', d) for d in wczytaj_daty('sceny_lata.csv')]
    print('dat do pobrania:', len(zadania))

    if not args.sprawdz:
        uzytkownik = os.environ.get('CDSE_USER') or input('Login Copernicus (e-mail): ')
        haslo = os.environ.get('CDSE_PASSWORD') or getpass.getpass('Hasło Copernicus: ')

    for i, (zestaw, data) in enumerate(zadania, 1):
        folder = TU / 'dane' / zestaw / data
        produkt = znajdz_produkt(data)
        if produkt is None:
            print(f'[{i}/{len(zadania)}] {data}: brak produktu L2A w katalogu - pomijam')
            continue
        pliki = pliki_20m(produkt)
        if args.sprawdz:
            print(f'[{i}/{len(zadania)}] {data}: {produkt["Name"]} -> {", ".join(n for n, _ in pliki.values())}')
            continue
        brakujace = {p: v for p, v in pliki.items() if not (folder / v[0]).exists()}
        if not brakujace:
            print(f'[{i}/{len(zadania)}] {data}: już pobrane')
            continue
        folder.mkdir(parents=True, exist_ok=True)
        token = zaloguj(uzytkownik, haslo)   # token ważny ~10 min, więc nowy dla każdej daty
        for pasmo, (nazwa, url) in brakujace.items():
            pobierz_plik(url, folder / nazwa, token)
        print(f'[{i}/{len(zadania)}] {data}: pobrano {len(brakujace)} plików')


if __name__ == '__main__':
    main()
