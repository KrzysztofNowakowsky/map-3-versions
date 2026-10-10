"""Mapa 3: temperatura nad Zatoką Gdańską z Open-Meteo -> site/sst.json (do wykresów).

Dwie serie, średnie dobowe, sezon VI-IX dla lat 2017-2026:
  morze     - temperatura powierzchni morza, Open-Meteo Marine API; dane od 2023 r.
              (era5_ocean ma tylko fale), dla wcześniejszych lat seria jest pusta
  powietrze - temperatura powietrza 2 m nad zatoką, archiwum Open-Meteo (ERA5, cell_selection=sea),
              wszystkie lata

Uruchom: python sst.py   (bez konta i klucza; potrzebny internet)
"""
import json
from pathlib import Path

import requests

TU = Path(__file__).resolve().parent
SITE = TU / 'site'
MORZE_API = 'https://marine-api.open-meteo.com/v1/marine'
ARCHIWUM_API = 'https://archive-api.open-meteo.com/v1/archive'
PUNKT = (54.55, 18.95)      # środek zatoki, otwarta woda (szer., dł.)
LATA = range(2017, 2027)


def sezon(rok):
    return {'start_date': f'{rok}-06-01', 'end_date': f'{rok}-09-30'}


def srednie_dzienne(czasy, wartosci):
    """'2019-07-25T13:00' -> dzień; średnia z godzin, które mają wartość (None pomijamy)."""
    suma, ile = {}, {}
    for czas, v in zip(czasy, wartosci):
        if v is None:
            continue
        dzien = czas[:10]
        suma[dzien] = suma.get(dzien, 0) + v
        ile[dzien] = ile.get(dzien, 0) + 1
    return {d: round(suma[d] / ile[d], 2) for d in sorted(suma)}


def bez_brakow(dni, wartosci):
    """Seria dzienna z archiwum -> słownik {dzień: wartość} bez pustych dni."""
    return {d: v for d, v in zip(dni, wartosci) if v is not None}


def temperatura_morza(rok):
    r = requests.get(MORZE_API, params={'latitude': PUNKT[0], 'longitude': PUNKT[1],
                                        'hourly': 'sea_surface_temperature', 'timezone': 'UTC',
                                        **sezon(rok)}, timeout=60)
    r.raise_for_status()
    godziny = r.json()['hourly']
    return srednie_dzienne(godziny['time'], godziny['sea_surface_temperature'])


def temperatura_powietrza(rok):
    r = requests.get(ARCHIWUM_API, params={'latitude': PUNKT[0], 'longitude': PUNKT[1],
                                           'daily': 'temperature_2m_mean', 'cell_selection': 'sea',
                                           'timezone': 'UTC', **sezon(rok)}, timeout=60)
    r.raise_for_status()
    dni = r.json()['daily']
    return bez_brakow(dni['time'], dni['temperature_2m_mean'])


def main():
    morze, powietrze = {}, {}
    for rok in LATA:
        m, p = temperatura_morza(rok), temperatura_powietrza(rok)
        print(rok, '| dni z temp. morza:', len(m), '| dni z temp. powietrza:', len(p))
        morze.update(m)
        powietrze.update(p)
    if not powietrze:
        raise SystemExit('Open-Meteo nie zwróciło temperatury powietrza - sprawdź internet i punkt')
    SITE.mkdir(exist_ok=True)
    (SITE / 'sst.json').write_text(json.dumps({
        'punkt': list(PUNKT), 'jednostka': '°C',
        'zrodlo_morze': 'temperatura morza: Open-Meteo Marine API (od 2023 r.)',
        'zrodlo_powietrze': 'temperatura powietrza 2 m: Open-Meteo, reanaliza ERA5',
        'morze': morze, 'powietrze': powietrze,
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    print('zapisano site/sst.json -', len(morze), 'dni morza,', len(powietrze), 'dni powietrza')


if __name__ == '__main__':
    main()
