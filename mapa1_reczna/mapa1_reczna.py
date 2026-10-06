# Mapa 1 - wersja "ręczna" (bez LLM) - test github komunikacja
# Landsat 8, 7.08.2013, powiat krakowski -> NDVI / NDBI / MNDWI -> strona WWW
#
# Na podstawie skryptu z zajęć
# Podział pracy:
#   blok 1-3  Kuba     - importy, wczytanie listy kanałów
#   blok 4-5  Mikołaj      - podgląd kanału (show_band, show_band2)
#   blok 6-7  Andrzej      - przycięcie do granicy powiatu (clip_area)
#   blok 8-10 Krzysiek      - wskaźniki, zapis NDVI.tif, komendy GDAL

# Blok 1: importy
import os
import matplotlib.pyplot as plt
import numpy as np
import rasterio as rio
import rasterio.mask as rmask
import fiona as fio

# folder z kanałami LC08 (u mnie symlink do paczki NASA, ustaw swoją ścieżkę jeśli trzeba)
LC08_DIR = os.path.join('..', 'data', 'Landsat8', 'LC08')
VECTOR = os.path.join('..', 'data', 'Landsat8', 'vector', 'krakow_krakowskie.shp')




#  Blok 2: lista kanałów
def read_landsat_images(folder_name):
    """Zwraca słownik {nr kanału: ścieżka do pliku} dla kanałów 1-7."""
    file_list = os.listdir(folder_name)
    channel_list = []
    for f in file_list:
        if f.startswith('LC') and f.endswith('.tif') and 'band' in f:
            # os.path.join zamiast folder + f -> działa z ukośnikiem na końcu i bez
            channel_list.append(os.path.join(folder_name, f))
    channel_list.sort()
    if len(channel_list) != 7:
        print('Uwaga: znaleziono', len(channel_list), 'kanałów zamiast 7')
    channel_numbers = np.arange(1, 8)
    return dict(zip(channel_numbers, channel_list))



# Blok 3: sprawdzenie
satellite_images = read_landsat_images(LC08_DIR)
for band in satellite_images:
    print(band, os.path.basename(satellite_images[band]))

print('rozmiar kanału 1:', rio.open(satellite_images[1]).shape)