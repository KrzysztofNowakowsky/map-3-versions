"""Mapa 2 - wersja LLM: Landsat 8 -> wskaźniki -> GeoTIFF -> kafelki XYZ -> strona.

Odtwarzamy pakiet LABOLATORIUM z zajęć, krok po kroku.
Dane: wycinek sceny LC08 z 7.08.2013 (Collection 1) + granica aoi.geojson.

Podział pracy:
  Kuba     - szkielet, read_metadata, quality_mask + testy
  Mikołaj  - load_scene, normalized_difference, calculate_indices, stretch_rgb, index_rgba
  Krzysiek - write_geotiff, xyz_tiles, export_results, main + strona (map_template.html)
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / 'data' / 'LABOLATORIUM' / 'data'   # scene/ + aoi.geojson

# wskaźnik: (kanał a, kanał b) -> (a - b) / (a + b)
INDEX_BANDS = {'NDVI': (5, 4), 'NDBI': (6, 5), 'MNDWI': (3, 6)}
CMAPS = {'NDVI': 'RdYlGn', 'NDBI': 'PuOr_r', 'MNDWI': 'BrBG'}
NS = {'e': 'http://espa.cr.usgs.gov/v2'}   # przestrzeń nazw w XML z ESPA




def read_metadata(scene: Path) -> dict:
    """Czyta plik XML ESPA: nazwa produktu, data i dla każdego kanału skala, offset, fill, zakres."""
    files = list(Path(scene).glob('*.xml'))
    if len(files) != 1:
        raise ValueError(f'Oczekiwano jednego pliku XML w {scene}, jest {len(files)}.')
    root = ET.parse(files[0]).getroot()
    product = root.findtext('e:global_metadata/e:product_id', namespaces=NS)
    if not product or '_01_' not in product:
        raise ValueError('Obsługujemy tylko Landsat Collection 1 (z pixel_qa).')
    bands = {}
    for b in root.findall('e:bands/e:band', NS):
        valid = b.find('e:valid_range', NS)
        bands[b.attrib['name']] = {
            'file': b.findtext('e:file_name', namespaces=NS),
            'scale': float(b.get('scale_factor', 1)),
            'offset': float(b.get('add_offset', 0)),
            'fill': float(b.get('fill_value', -9999)),
            'valid_min': float(valid.get('min')) if valid is not None else None,
            'valid_max': float(valid.get('max')) if valid is not None else None,
        }
    date = root.findtext('e:global_metadata/e:acquisition_date', namespaces=NS)
    return {'product': product, 'date': date, 'bands': bands}


def quality_mask(qa: np.ndarray, saturation: np.ndarray) -> np.ndarray:
    """True = dobry piksel. Bity pixel_qa (Collection 1):
    0 fill, 2 woda (zostaje!), 3 cień chmury, 4 śnieg, 5 chmura,
    6-7 pewność chmury, 8-9 pewność cirrusa, 10 przesłonięcie terenu.
    radsat_qa: bit 0 fill, bity 2-6 = nasycenie kanałów B2-B6.
    """
    bad_bits = (1 << 0) | (1 << 3) | (1 << 4) | (1 << 5) | (1 << 10)
    bad = (qa & bad_bits) != 0
    bad |= ((qa >> 6) & 3) == 3   # wysoka pewność chmury
    bad |= ((qa >> 8) & 3) == 3   # wysoka pewność cirrusa
    sat_bits = 1 | sum(1 << b for b in range(2, 7))
    bad |= (saturation & sat_bits) != 0
    return ~bad


# %% Mikołaj: wczytanie sceny
def load_scene(data_dir: Path = DATA) -> dict:
    """Czyta kanały B2-B6 i maski QA, przycina do granicy aoi.geojson.
    Zwraca DN, reflektancję (NaN poza ważnymi pikselami), maski i profil rastra."""
    data_dir = Path(data_dir)
    meta = read_metadata(data_dir / 'scene')
    aoi = json.loads((data_dir / 'aoi.geojson').read_text(encoding='utf-8'))

    raw, profile = {}, None
    for key in [*(f'sr_band{i}' for i in range(2, 7)), 'pixel_qa', 'radsat_qa']:
        with rasterio.open(data_dir / 'scene' / meta['bands'][key]['file']) as src:
            if profile is None:
                profile = src.profile.copy()
            elif (src.crs != profile['crs'] or src.transform != profile['transform']
                  or src.width != profile['width'] or src.height != profile['height']):
                raise ValueError(f'Niezgodna siatka rastra: {key}')
            raw[key] = src.read(1)

    # granica: GeoJSON jest w EPSG:4326, raster w UTM -> przeliczamy geometrię
    geoms = [transform_geom('EPSG:4326', profile['crs'], f['geometry']) for f in aoi['features']]
    inside = geometry_mask(geoms, out_shape=raw['pixel_qa'].shape,
                           transform=profile['transform'], invert=True)
    if not inside.any():
        raise ValueError('Granica nie przecina sceny. Sprawdź CRS i zasięg.')

    # wspólna maska: w granicy + dobra jakość + nie fill + w zakresie valid_range
    quality = quality_mask(raw['pixel_qa'], raw['radsat_qa'])
    valid = inside & quality
    for i in range(2, 7):
        b, a = meta['bands'][f'sr_band{i}'], raw[f'sr_band{i}']
        valid &= a != b['fill']
        valid &= (a >= b['valid_min']) & (a <= b['valid_max'])
    if not valid.any():
        raise ValueError('Po maskowaniu nie pozostały ważne piksele.')

    # DN -> reflektancja ze skali/offsetu z XML (nie "magiczne 10000")
    reflectance = {}
    for i in range(2, 7):
        b = meta['bands'][f'sr_band{i}']
        a = raw[f'sr_band{i}'].astype('float32') * b['scale'] + b['offset']
        reflectance[i] = np.where(valid, a, np.nan)

    return {'metadata': meta, 'profile': profile, 'raw': raw, 'inside': inside,
            'valid': valid, 'quality': quality, 'reflectance': reflectance, 'aoi': aoi}


# %% Mikołaj: wskaźniki
def normalized_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """(a - b) / (a + b). Zera i wartości ujemne zostają, zerowy mianownik lub NaN -> NaN."""
    a, b = np.asarray(a, dtype='float32'), np.asarray(b, dtype='float32')
    out = np.full(np.broadcast_shapes(a.shape, b.shape), np.nan, dtype='float32')
    denominator = a + b
    ok = np.isfinite(a) & np.isfinite(b) & (np.abs(denominator) > 1e-6)
    np.divide(a - b, denominator, out=out, where=ok)
    return out


def calculate_indices(reflectance: dict) -> dict:
    """NDVI, NDBI, MNDWI według INDEX_BANDS."""
    return {name: normalized_difference(reflectance[a], reflectance[b])
            for name, (a, b) in INDEX_BANDS.items()}


# %% Mikołaj: warstwy do wyświetlenia
def stretch_rgb(reflectance: dict) -> np.ndarray:
    """RGB z kanałów 4/3/2, każdy rozciągnięty 2-98 percentyl (tylko do podglądu).
    Zwraca uint8 (wiersze, kolumny, 4) - czwarty kanał to alfa (0 poza maską)."""
    channels = []
    for band in (4, 3, 2):
        a = reflectance[band]
        lo, hi = np.nanpercentile(a, (2, 98))
        scaled = np.clip((a - lo) / max(hi - lo, 1e-6), 0, 1)
        channels.append((np.nan_to_num(scaled) * 255).astype('uint8'))
    alpha = (np.isfinite(reflectance[4]) * 255).astype('uint8')
    return np.dstack([*channels, alpha])


def index_rgba(array: np.ndarray, name: str) -> np.ndarray:
    """Koloruje wskaźnik (-1..1) paletą z CMAPS; NaN -> przezroczysty."""
    rgba = matplotlib.colormaps[CMAPS[name]](np.clip((array + 1) / 2, 0, 1), bytes=True)
    rgba[..., 3] = np.isfinite(array) * 255
    return rgba
    
def write_geotiff(path: Path, data: np.ndarray, profile: dict, rgba=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    p = profile.copy()
    if rgba:
        data = np.moveaxis(data, -1, 0)
        p.update(count=4, dtype='uint8', nodata=None, photometric='RGB')
    else:
        data = np.where(np.isfinite(data), data, -9999).astype('float32')[None]
        p.update(count=1, dtype='float32', nodata=-9999)
        p.pop('photometric', None)
    p.update(driver='GTiff', compress='deflate', tiled=True)
    with rasterio.open(path, 'w', **p) as dst:
        dst.write(data)
        if rgba:
            dst.colorinterp = (ColorInterp.red, ColorInterp.green, ColorInterp.blue, ColorInterp.alpha)
        else:
            dst.set_band_description(1, path.stem)
            dst.update_tags(meaning='normalized difference; no numeric clipping; NoData=-9999')



if __name__ == '__main__':
    meta = read_metadata(DATA / 'scene')
    print(meta['product'], meta['date'])
    print('kanały w XML:', len(meta['bands']), '| skala B5:', meta['bands']['sr_band5']['scale'])
    scene = load_scene()
    indices = calculate_indices(scene['reflectance'])
    print('ważne piksele:', int(scene['valid'].sum()), '(wzorzec: 1729266)')
    print('NDVI średnio:', round(float(np.nanmean(indices['NDVI'])), 3), '(wzorzec: 0.618)')