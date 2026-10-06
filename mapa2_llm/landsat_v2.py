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

import numpy as np

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / 'data' / 'LABOLATORIUM' / 'data'   # scene/ + aoi.geojson

# wskaźnik: (kanał a, kanał b) -> (a - b) / (a + b)
INDEX_BANDS = {'NDVI': (5, 4), 'NDBI': (6, 5), 'MNDWI': (3, 6)}
CMAPS = {'NDVI': 'RdYlGn', 'NDBI': 'PuOr_r', 'MNDWI': 'BrBG'}
NS = {'e': 'http://espa.cr.usgs.gov/v2'}   # przestrzeń nazw w XML z ESPA