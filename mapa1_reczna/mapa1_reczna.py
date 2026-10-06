# Mapa 1 - wersja "ręczna" (bez LLM) - test github komunikacja
# Landsat 8, 7.08.2013, powiat krakowski -> NDVI / NDBI / MNDWI -> strona WWW
#
# Na podstawie skryptu z zajęć
# Podział pracy:
#   blok 1-3  Kuba      - importy, wczytanie listy kanałów
#   blok 4-7  Mikołaj   - podgląd kanału (show_band, show_band2) + przycięcie do granicy powiatu (clip_area)
#   blok 8-10 Krzysiek  - wskaźniki, zapis NDVI.tif, komendy GDAL

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


# %% Blok 4: podgląd kanału
def show_band(band, color_map='gray'):
    """Wyświetla macierz rastra jako obraz z paskiem kolorów."""
    plt.figure(figsize=(8, 8))
    image_layer = plt.imshow(band)
    image_layer.set_cmap(color_map)
    plt.colorbar()
    plt.show()


def show_band2(band, color_map='gray', remove_negative=True, title=''):
    """Jak show_band, ale wartości <= 0 (brak danych, tło) zamienia na NaN,
    żeby nie zaburzały skali kolorów. Przyda się też do wskaźników (blok 8-10)."""
    matrix = band.astype(float)
    if remove_negative:
        matrix[matrix <= 0] = np.nan
    plt.figure(figsize=(8, 8))
    image_layer = plt.imshow(matrix)
    image_layer.set_cmap(color_map)
    plt.colorbar()
    plt.title(title)
    plt.show()



# %% Blok 5: test podglądu
# najpierw losowa macierz - sprawdzamy, czy funkcja w ogóle rysuje
test = np.random.randint(low=0, high=255, size=(200, 200))
show_band(test, color_map='winter')

# potem prawdziwy kanał 5 (bliska podczerwień) z całej sceny
print('kanał 5:', satellite_images[5])
with rio.open(satellite_images[5], 'r') as src:
    band_matrix = src.read(1)

show_band(band_matrix)
show_band2(band_matrix, title='Kanał 5 (bez wartości <= 0)')