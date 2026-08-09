"""Accessibilita': distanza dalla strada carrozzabile piu' vicina.

Eseguito da CLI, non importato altrove. Legge data/nord-ovest.osm.pbf e
data/derived/score.tif; scrive data/derived/access.tif (1 banda float32,
distanza in metri, stessa griglia AEQD a 180 m). Nessun dato personale: si
leggono solo geometrie con tag highway. Istruzione utente: "gestisci
accessibilita. Meteo mettilo nei to-do. Procedi"

Un punteggio del 94% su una cresta senza accessi non serve a nessuno. Questo
stadio rasterizza la rete stradale OSM sulla griglia del punteggio e calcola
una distance transform euclidea.

Sorgente: estratto Geofabrik nord-ovest (Piemonte, Valle d'Aosta, Liguria,
Lombardia). Overpass non regge una query di questa estensione: tutti e tre i
mirror provati rispondono 504.

Sono escluse le vie non percorribili in auto (sentieri, scale, piste
ciclabili) e le mulattiere (track): raggiungere un punto panoramico in serata
significa arrivarci con un mezzo normale e parcheggiare.
"""

import sys
import time

import numpy as np
import osmium
import rasterio
from pyproj import Transformer
from scipy.ndimage import distance_transform_edt

from config import CRS_WORK, DATA, DERIVED

PBF = DATA / "nord-ovest.osm.pbf"
POLY = DATA / "nord-ovest.poly"
SCORE = DERIVED / "score.tif"
OUT = DERIVED / "access.tif"

DRIVABLE = {
    "motorway", "motorway_link", "trunk", "trunk_link",
    "primary", "primary_link", "secondary", "secondary_link",
    "tertiary", "tertiary_link", "unclassified", "residential",
    "living_street", "service",
}
DENSIFY_M = 90.0  # passo di campionamento lungo i segmenti


def coverage_mask(poly_path, tr, nrow, ncol) -> np.ndarray:
    """Footprint dell'estratto Geofabrik (.poly) rasterizzato sulla griglia."""
    from rasterio.features import rasterize
    from shapely.geometry import Polygon
    from shapely.ops import transform as sh_transform
    from shapely.ops import unary_union

    rings: list[tuple[list[tuple[float, float]], bool]] = []
    current: list[tuple[float, float]] | None = None
    is_hole = False
    for line in poly_path.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if not t:
            continue
        if t == "END":
            if current is None:
                break
            if len(current) >= 4:
                rings.append((current, is_hole))
            current = None
            continue
        parts = t.split()
        if current is not None and len(parts) == 2:
            try:
                current.append((float(parts[0]), float(parts[1])))
                continue
            except ValueError:
                pass
        # Una riga non numerica apre un nuovo anello. Nel formato .poly il
        # prefisso ! indica una cavita' da sottrarre al footprint.
        current = []
        is_hole = t.startswith("!")

    fwd = Transformer.from_crs("EPSG:4326", CRS_WORK, always_xy=True)
    def project(ring):
        return sh_transform(lambda x, y: fwd.transform(x, y), Polygon(ring))

    outers = [project(ring) for ring, hole in rings if not hole]
    holes = [project(ring) for ring, hole in rings if hole]
    if not outers:
        raise ValueError(f"Footprint .poly non valido o vuoto: {poly_path}")
    footprint = unary_union(outers)
    if holes:
        footprint = footprint.difference(unary_union(holes))
    arr = rasterize(
        [(footprint, 1)], out_shape=(nrow, ncol), transform=tr, dtype="uint8"
    )
    return arr.astype(bool)


def read_roads(path):
    """Estremi dei segmenti stradali: (lon1, lat1, lon2, lat2)."""
    x1, y1, x2, y2 = [], [], [], []
    nways = 0
    # I nodi vanno letti (NODE|WAY) perche' la cache delle posizioni si
    # costruisce da li'; l'EntityFilter li esclude poi dall'iterazione.
    fp = (
        osmium.FileProcessor(str(path), osmium.osm.NODE | osmium.osm.WAY)
        .with_locations()
        .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
        .with_filter(osmium.filter.KeyFilter("highway"))
    )
    for obj in fp:
        if obj.tags.get("highway") not in DRIVABLE:
            continue
        lons, lats = [], []
        for n in obj.nodes:
            if not n.location.valid():
                continue
            lons.append(n.location.lon)
            lats.append(n.location.lat)
        if len(lons) < 2:
            continue
        nways += 1
        x1.extend(lons[:-1]); y1.extend(lats[:-1])
        x2.extend(lons[1:]); y2.extend(lats[1:])
    print(f"  vie carrozzabili: {nways:,}  segmenti: {len(x1):,}", flush=True)
    return (
        np.asarray(x1, "float64"), np.asarray(y1, "float64"),
        np.asarray(x2, "float64"), np.asarray(y2, "float64"),
    )


def densify(xa, ya, xb, yb, step):
    """Campiona ogni segmento a intervalli <= step. Vettoriale."""
    length = np.hypot(xb - xa, yb - ya)
    n = np.maximum(1, np.ceil(length / step)).astype(np.int64)
    total = int(n.sum())
    idx = np.repeat(np.arange(len(n)), n)
    start = np.concatenate(([0], np.cumsum(n)[:-1]))
    t = (np.arange(total) - np.repeat(start, n)) / np.repeat(n, n)
    return xa[idx] + t * (xb[idx] - xa[idx]), ya[idx] + t * (yb[idx] - ya[idx])


def main() -> int:
    if not PBF.exists():
        print(f"Manca {PBF}", file=sys.stderr)
        return 1
    if not POLY.exists():
        print(f"Manca {POLY}", file=sys.stderr)
        return 1
    if not SCORE.exists():
        print(f"Manca {SCORE}: eseguire prima 04_score.py", file=sys.stderr)
        return 1

    with rasterio.open(SCORE) as s:
        tr, crs, (nrow, ncol) = s.transform, s.crs, s.shape

    t0 = time.time()
    print("Lettura PBF...", flush=True)
    lon1, lat1, lon2, lat2 = read_roads(PBF)
    print(f"  in {time.time() - t0:.0f}s", flush=True)
    if not len(lon1):
        print("Nessuna strada carrozzabile trovata nell'estratto OSM", file=sys.stderr)
        return 1

    fwd = Transformer.from_crs("EPSG:4326", CRS_WORK, always_xy=True)
    xa, ya = fwd.transform(lon1, lat1)
    xb, yb = fwd.transform(lon2, lat2)

    # Scarta i segmenti interamente fuori dalla griglia, con un margine.
    x0, y0 = tr.c, tr.f
    x_max, y_min = x0 + ncol * tr.a, y0 + nrow * tr.e
    m = 5000.0
    keep = (
        (np.maximum(xa, xb) > x0 - m) & (np.minimum(xa, xb) < x_max + m)
        & (np.maximum(ya, yb) > y_min - m) & (np.minimum(ya, yb) < y0 + m)
    )
    xa, ya, xb, yb = xa[keep], ya[keep], xb[keep], yb[keep]
    print(f"  segmenti nella griglia: {keep.sum():,}", flush=True)

    px, py = densify(xa, ya, xb, yb, DENSIFY_M)
    print(f"  punti densificati: {len(px):,}", flush=True)

    cc = ((px - x0) / tr.a).astype(np.int64)
    rr = ((y0 - py) / -tr.e).astype(np.int64)
    ok = (rr >= 0) & (rr < nrow) & (cc >= 0) & (cc < ncol)
    road = np.zeros((nrow, ncol), dtype=bool)
    road[rr[ok], cc[ok]] = True
    print(f"  celle con strada: {road.sum():,} ({road.mean() * 100:.1f}% della griglia)", flush=True)

    dist = distance_transform_edt(~road, sampling=(abs(tr.e), tr.a)).astype("float32")

    # Fuori dal footprint dell'estratto (Francia, Svizzera) non ci sono strade
    # nel PBF: la distanza li' sarebbe finta, non grande. Va marcata NaN,
    # altrimenti quelle aree sembrerebbero solo "molto isolate".
    cov = coverage_mask(POLY, tr, nrow, ncol)
    print(f"  copertura dati stradali: {cov.mean() * 100:.1f}% della griglia", flush=True)
    dist[~cov] = np.nan

    profile = {
        "driver": "GTiff", "height": nrow, "width": ncol, "count": 1,
        "dtype": "float32", "crs": crs, "transform": tr,
        "compress": "deflate", "predictor": 3, "tiled": True, "nodata": float("nan"),
    }
    with rasterio.open(OUT, "w", **profile) as d:
        d.write(dist, 1)
        d.set_band_description(1, "dist_strada_m")

    d_ok = dist[np.isfinite(dist)]
    q = np.percentile(d_ok, [50, 75, 90, 99])
    print(f"\nScritto {OUT.name}")
    print(f"  distanza strada (dentro copertura): mediana {q[0]:.0f} m, p75 {q[1]:.0f}, p90 {q[2]:.0f}, p99 {q[3]:.0f}")
    print(f"  celle entro 500 m da una strada: {(d_ok <= 500).mean() * 100:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
