"""Punteggio: massimo oscuramento del Sole effettivamente VISIBILE.

Chiamato da CLI; legge data/derived/horizon.tif (03_horizon.py) e scrive
data/derived/score.tif. Nessun altro file calcola il punteggio.
Schema output: GeoTIFF 4 bande float32, CRS AEQD, pixel 180 m.
  1 obsc_vis   - max oscuramento visibile [0..1]
  2 obsc_theo  - max oscuramento teorico a orizzonte piatto [0..1]
  3 t_best     - minuti dopo le 19:00 CEST del momento migliore
  4 hor_used   - angolo di orizzonte all'azimut solare in quel momento [gradi]
Date in UTC, formato tuple (2026, 8, 12, 17, 25, 0) = 19:25 CEST.
Nessun dato personale. Istruzione utente: "gestisci accessibilita. Meteo
mettilo nei to-do. Procedi"

Tre correzioni che cambiano il risultato e vanno tenute insieme:

1. CONVERGENZA DEI MERIDIANI. Il raycast lavora su azimut di griglia, le
   efemeridi danno azimut veri. Su AEQD la differenza gamma arriva a qualche
   grado ai bordi dell'AOI: con il Sole a 2.6 gradi non e' trascurabile.
   grid_az = true_az + gamma, con gamma calcolata per cella.

2. VARIAZIONE SPAZIALE DELLE EFEMERIDI. Sull'AOI (220 x 290 km) l'altezza del
   Sole cambia di ~2.5 gradi, cioe' quanto la soglia stessa. Efemeridi su
   griglia rada 6x6 e interpolazione bilineare per cella.

3. RIFRAZIONE COERENTE. Il Sole usa l'altezza apparente (rifratta); il terreno
   usa R_eff = 7/6 R, che e' l'elevazione apparente del rilievo. Confronto
   apparente-contro-apparente, che e' quello che vede l'osservatore.
"""

import math
import sys
import time

import astronomy as A
import numpy as np
import rasterio
from pyproj import Transformer
from scipy.ndimage import map_coordinates

from config import AZ_MIN, AZ_STEP, CRS_WORK, DERIVED

HOR = DERIVED / "horizon.tif"
OUT = DERIVED / "score.tif"

T0_UTC = (2026, 8, 12, 17, 25, 0)  # 19:25 CEST
T1_UTC = (2026, 8, 12, 18, 55, 0)  # 20:55 CEST
STEP_S = 20
NODES = 6  # griglia efemeridi NODES x NODES

R_SUN_KM, R_MOON_KM, AU_KM = 695700.0, 1737.4, 149597870.7


def obscuration(sep_deg: float, rs_deg: float, rm_deg: float) -> float:
    """Frazione di AREA del disco solare coperta (non frazione di diametro)."""
    d, rs, rm = sep_deg, rs_deg, rm_deg
    if d >= rs + rm:
        return 0.0
    if d <= abs(rs - rm):
        return min(1.0, (rm / rs) ** 2)
    a1 = rs * rs * math.acos((d * d + rs * rs - rm * rm) / (2 * d * rs))
    a2 = rm * rm * math.acos((d * d + rm * rm - rs * rs) / (2 * d * rm))
    a3 = 0.5 * math.sqrt(max(0.0, (-d + rs + rm) * (d + rs - rm) * (d - rs + rm) * (d + rs + rm)))
    return (a1 + a2 - a3) / (math.pi * rs * rs)


def circumstances(t: A.Time, obs: A.Observer) -> tuple[float, float, float]:
    """(oscuramento, altezza apparente, azimut vero) del Sole."""
    sun = A.Equator(A.Body.Sun, t, obs, True, True)
    moon = A.Equator(A.Body.Moon, t, obs, True, True)
    hs = A.Horizon(t, obs, sun.ra, sun.dec, A.Refraction.Normal)
    hm = A.Horizon(t, obs, moon.ra, moon.dec, A.Refraction.Normal)
    a1, z1 = math.radians(hs.altitude), math.radians(hs.azimuth)
    a2, z2 = math.radians(hm.altitude), math.radians(hm.azimuth)
    c = math.sin(a1) * math.sin(a2) + math.cos(a1) * math.cos(a2) * math.cos(z1 - z2)
    sep = math.degrees(math.acos(max(-1.0, min(1.0, c))))
    rs = math.degrees(math.asin(R_SUN_KM / (sun.dist * AU_KM)))
    rm = math.degrees(math.asin(R_MOON_KM / (moon.dist * AU_KM)))
    return obscuration(sep, rs, rm), hs.altitude, hs.azimuth


def main() -> int:
    with rasterio.open(HOR) as src:
        hor = src.read().astype("float32") / 100.0  # gradi
        tr, crs = src.transform, src.crs
    nb, nrow, ncol = hor.shape
    npix = nrow * ncol
    print(f"Orizzonte: {nb} bande, {nrow} x {ncol} = {npix / 1e6:.2f} M celle", flush=True)

    # --- coordinate di ogni cella ---
    rr, cc = np.meshgrid(np.arange(nrow), np.arange(ncol), indexing="ij")
    xs = tr.c + (cc + 0.5) * tr.a
    ys = tr.f + (rr + 0.5) * tr.e
    inv = Transformer.from_crs(CRS_WORK, "EPSG:4326", always_xy=True)
    lon, lat = inv.transform(xs.ravel(), ys.ravel())

    # --- 1. convergenza dei meridiani, per cella ---
    fwd = Transformer.from_crs("EPSG:4326", CRS_WORK, always_xy=True)
    x2, y2 = fwd.transform(lon, lat + 0.01)
    gamma = np.degrees(np.arctan2(x2 - xs.ravel(), y2 - ys.ravel())).astype("float32")
    print(f"Convergenza meridiani: da {gamma.min():.2f} a {gamma.max():.2f} gradi", flush=True)

    # --- 2. griglia rada per le efemeridi + coordinate bilineari precalcolate ---
    ny = nx = NODES
    node_r = np.linspace(0, nrow - 1, ny)
    node_c = np.linspace(0, ncol - 1, nx)
    node_x = tr.c + (node_c + 0.5) * tr.a
    node_y = tr.f + (node_r + 0.5) * tr.e
    ngx, ngy = np.meshgrid(node_x, node_y)
    with rasterio.open(DERIVED / "dem_aeqd.tif") as d:
        node_h = np.array(
            list(d.sample(list(zip(ngx.ravel(), ngy.ravel())))), dtype="float64"
        )[:, 0]
    nlon, nlat = inv.transform(ngx.ravel(), ngy.ravel())
    observers = [A.Observer(la, lo, max(0.0, h)) for la, lo, h in zip(nlat, nlon, node_h)]

    fy = (rr.ravel() / (nrow - 1) * (ny - 1)).astype("float32")
    fx = (cc.ravel() / (ncol - 1) * (nx - 1)).astype("float32")
    coords = np.vstack([fy, fx])

    # --- ciclo temporale ---
    t_start = A.Time.Make(*T0_UTC)
    nsteps = int((A.Time.Make(*T1_UTC).ut - t_start.ut) * 86400 / STEP_S) + 1
    print(f"Passi temporali: {nsteps} da 19:25 a 20:55 CEST", flush=True)

    best = np.zeros(npix, dtype="float32")
    best_theo = np.zeros(npix, dtype="float32")
    t_best = np.full(npix, -1.0, dtype="float32")
    hor_used = np.full(npix, np.nan, dtype="float32")
    hf = hor.reshape(nb, npix)
    pix = np.arange(npix)

    t_wall = time.time()
    for k in range(nsteps):
        t = t_start.AddDays(k * STEP_S / 86400.0)
        vals = [circumstances(t, o) for o in observers]
        Vo = np.array([v[0] for v in vals], dtype="float32").reshape(ny, nx)
        Va = np.array([v[1] for v in vals], dtype="float32").reshape(ny, nx)
        Vz = np.array([v[2] for v in vals], dtype="float32").reshape(ny, nx)
        if Vo.max() <= 0.0 or Va.max() <= 0.0:
            continue

        obsc = map_coordinates(Vo, coords, order=1, mode="nearest")
        alt = map_coordinates(Va, coords, order=1, mode="nearest")
        azt = map_coordinates(Vz, coords, order=1, mode="nearest")

        # --- 1. da azimut vero a azimut di griglia, poi interpolazione fra bande ---
        b = (azt + gamma - AZ_MIN) / AZ_STEP
        np.clip(b, 0, nb - 1.001, out=b)
        b0 = b.astype(np.int32)
        fb = b - b0
        h_az = hf[b0, pix] * (1.0 - fb) + hf[b0 + 1, pix] * fb

        visible = (alt > h_az) & (alt > 0.0)
        cand = np.where(visible, obsc, 0.0).astype("float32")
        improved = cand > best
        best = np.where(improved, cand, best)
        t_best = np.where(improved, (k * STEP_S) / 60.0 + 25.0, t_best)
        hor_used = np.where(improved, h_az, hor_used)
        best_theo = np.maximum(best_theo, np.where(alt > 0.0, obsc, 0.0).astype("float32"))

    print(f"Ciclo completato in {time.time() - t_wall:.1f}s", flush=True)

    profile = {
        "driver": "GTiff",
        "height": nrow,
        "width": ncol,
        "count": 4,
        "dtype": "float32",
        "crs": crs,
        "transform": tr,
        "compress": "deflate",
        "predictor": 3,
        "tiled": True,
    }
    names = ["obsc_vis", "obsc_theo", "t_best_min_after_1900", "hor_used_deg"]
    data = [best, best_theo, t_best, hor_used]
    with rasterio.open(OUT, "w", **profile) as d:
        for i, (n, arr) in enumerate(zip(names, data), start=1):
            d.write(arr.reshape(nrow, ncol), i)
            d.set_band_description(i, n)

    v = best * 100
    print(f"\nScritto {OUT.name}")
    print(f"  oscuramento visibile: mediana {np.median(v):.1f}%  max {v.max():.1f}%")
    print(f"  celle >= 90%: {(v >= 90).mean() * 100:.1f}%   < 50%: {(v < 50).mean() * 100:.1f}%")
    print(f"  perdita media dovuta al terreno: {(best_theo - best).mean() * 100:.1f} punti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
