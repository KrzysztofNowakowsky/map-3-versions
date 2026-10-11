"""Mapa 3: zapas danych na żywo -> site/live_zapas.json.

Strona pobiera temperaturę wody (IMGW-PIB) i morza (Open-Meteo) prosto z przeglądarki.
Gdy na uczelni firewall zablokuje te API, live.js pokaże ostatni zapisany stan z tego pliku.
Uruchom tuż przed publikacją strony: python live_zapas.py   (bez konta i klucza)
"""
import json
from datetime import datetime

import requests

from przetworz import SITE

IMGW = 'https://danepubliczne.imgw.pl/api/data/hydro/'
MORZE = ('https://marine-api.open-meteo.com/v1/marine?latitude=54.55&longitude=18.75'
         '&current=sea_surface_temperature&daily=sea_surface_temperature_max&forecast_days=7'
         '&timezone=Europe%2FWarsaw')
STACJE = ['153180120', '154180120', '154180090', '154180140', '154180100']  # Hel, Gdynia, Puck, Gdańsk, Władysławowo


def main():
    hydro = requests.get(IMGW, timeout=60).json()
    morze = requests.get(MORZE, timeout=60).json()
    zapas = {
        'pobrano': datetime.now().isoformat(timespec='minutes'),
        'hydro': [s for s in hydro if s['id_stacji'] in STACJE],
        'morze': morze,
    }
    SITE.mkdir(exist_ok=True)
    (SITE / 'live_zapas.json').write_text(json.dumps(zapas, ensure_ascii=False, indent=1), encoding='utf-8')
    print('zapisano site/live_zapas.json -', len(zapas['hydro']), 'stacji, morze:',
          morze['current']['sea_surface_temperature'], '°C')


if __name__ == '__main__':
    main()
