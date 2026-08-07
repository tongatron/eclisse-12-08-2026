"""Scarica i tile Copernicus DEM GLO-90 dal bucket pubblico AWS Open Data.

I tile oceanici non esistono (404): vengono saltati e trattati come mare.
"""

import concurrent.futures as cf
import sys
import urllib.error
import urllib.request

from config import DEM_LAT_MAX, DEM_LAT_MIN, DEM_LON_MAX, DEM_LON_MIN, DEM_TILES, ensure_dirs

BASE = "https://copernicus-dem-90m.s3.eu-central-1.amazonaws.com"


def tile_name(lat: int, lon: int) -> str:
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"Copernicus_DSM_COG_30_{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00_DEM"


def fetch(lat: int, lon: int) -> tuple[str, str]:
    name = tile_name(lat, lon)
    dest = DEM_TILES / f"{name}.tif"
    if dest.exists() and dest.stat().st_size > 0:
        return name, "cached"
    url = f"{BASE}/{name}/{name}.tif"
    try:
        with urllib.request.urlopen(url, timeout=120) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return name, "assente (mare)"
        return name, f"HTTP {e.code}"
    except Exception as e:  # rete instabile: segnalato, non fatale
        return name, f"errore {type(e).__name__}"
    dest.write_bytes(data)
    return name, f"{len(data) / 1e6:.1f} MB"


def main() -> int:
    ensure_dirs()
    jobs = [
        (lat, lon)
        for lat in range(DEM_LAT_MIN, DEM_LAT_MAX + 1)
        for lon in range(DEM_LON_MIN, DEM_LON_MAX + 1)
    ]
    print(f"Tile da recuperare: {len(jobs)}", flush=True)
    ok = failed = 0
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for name, status in ex.map(lambda a: fetch(*a), jobs):
            short = name.replace("Copernicus_DSM_COG_30_", "").replace("_DEM", "")
            print(f"  {short:14s} {status}", flush=True)
            if status.startswith(("errore", "HTTP")):
                failed += 1
            else:
                ok += 1
    print(f"\nCompletati {ok}/{len(jobs)}, falliti {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
