"""Mosaica i tile GLO-90 e riproietta nella griglia di lavoro AEQD a 90 m.

Chiamato da CLI; il suo output dem_aeqd.tif alimenta 03_horizon.py.
Nessun altro file in pipeline/ esegue mosaicatura o riproiezione.
Legge data/dem_tiles/*.tif (float32, quote in m, nodata -32767).
Scrive data/derived/dem_aeqd.tif (float32, CRS AEQD lat_0=45.3 lon_0=7.9,
pixel 90 m, mare = 0 m). Nessuna data, nessun dato personale.
Istruzione utente: "gestisci accessibilita. Meteo mettilo nei to-do. Procedi"
"""

import sys

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.warp import Resampling, calculate_default_transform, reproject

from config import CRS_WORK, DEM_TILES, DERIVED, RES_M, ensure_dirs

NODATA = -32767.0
OUT = DERIVED / "dem_aeqd.tif"


def main() -> int:
    ensure_dirs()
    tiles = sorted(DEM_TILES.glob("*.tif"))
    if not tiles:
        print("Nessun tile: eseguire prima 01_download_dem.py", file=sys.stderr)
        return 1
    print(f"Mosaicatura di {len(tiles)} tile...", flush=True)

    srcs = [rasterio.open(t) for t in tiles]
    mosaic, src_transform = merge(srcs, nodata=NODATA)
    src_crs = srcs[0].crs
    for s in srcs:
        s.close()
    mosaic = mosaic[0]
    print(f"  mosaico {mosaic.shape} in {src_crs}", flush=True)

    # Il mare (tile assenti o nodata) vale 0 m: non ostruisce l'orizzonte.
    mosaic = np.where(mosaic == NODATA, 0.0, mosaic).astype("float32")

    h, w = mosaic.shape
    left = src_transform.c
    top = src_transform.f
    right = left + w * src_transform.a
    bottom = top + h * src_transform.e

    dst_transform, dst_w, dst_h = calculate_default_transform(
        src_crs, CRS_WORK, w, h, left, bottom, right, top, resolution=RES_M
    )
    print(f"  griglia di lavoro {dst_h} x {dst_w} @ {RES_M:.0f} m", flush=True)

    dst = np.zeros((dst_h, dst_w), dtype="float32")
    reproject(
        source=mosaic,
        destination=dst,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs=CRS_WORK,
        resampling=Resampling.bilinear,
        src_nodata=None,
        dst_nodata=None,
        num_threads=4,
    )

    profile = {
        "driver": "GTiff",
        "height": dst_h,
        "width": dst_w,
        "count": 1,
        "dtype": "float32",
        "crs": CRS_WORK,
        "transform": dst_transform,
        "compress": "deflate",
        "predictor": 2,
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
    }
    with rasterio.open(OUT, "w", **profile) as d:
        d.write(dst, 1)

    print(
        f"\nScritto {OUT.name}: quote da {dst.min():.0f} a {dst.max():.0f} m, "
        f"{OUT.stat().st_size / 1e6:.0f} MB"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
