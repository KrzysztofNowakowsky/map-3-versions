# Mapa 1 - wersja "ręczna" (bez LLM) - test github komunikacja
# Landsat 8, 7.08.2013, powiat krakowski -> NDVI / NDBI / MNDWI -> strona WWW
#
# Podział pracy:
#   blok 1-3  Kuba     - importy, wczytanie listy kanałów
#   blok 4-5  Mikołaj      - podgląd kanału (show_band, show_band2)
#   blok 6-7  Andrzej      - przycięcie do granicy powiatu (clip_area)
#   blok 8-10 Krzysiek      - wskaźniki, zapis NDVI.tif, komendy GDAL

# %% Blok 1: importy
import os
import matplotlib.pyplot as plt
import numpy as np
import rasterio as rio
import rasterio.mask as rmask
import fiona as fio

# folder z kanałami LC08 (u mnie symlink do paczki NASA, ustaw swoją ścieżkę jeśli trzeba)
LC08_DIR = os.path.join('..', 'data', 'Landsat8', 'LC08')
VECTOR = os.path.join('..', 'data', 'Landsat8', 'vector', 'krakow_krakowskie.shp')