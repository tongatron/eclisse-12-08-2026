"""Angolo di orizzonte per azimut di griglia, via raycast vettoriale.

Importatori/chiamanti: eseguito da CLI; l'output horizon.tif e' letto da
04_score.py. Non espone API pubbliche oltre a horizon_for_azimuth().
Schema dati: legge data/derived/dem_aeqd.tif (float32, quote m); scrive
data/derived/horizon.tif, multi-banda int16, una banda per azimut di griglia
272->299 gradi, unita' 0.01 gradi, nodata -32768. Nessuna data, nessun dato
personale. Istruzione utente: "gestisci accessibilita. Meteo mettilo nei
to-do. Procedi"

Per ogni cella di output e ogni azimut, marcia lungo il raggio fino a 250 km e
tiene il massimo di

    tan(alpha) = (h_bersaglio - h_osservatore - d^2 / (2 R_eff)) / d

dove R_eff = 7/6 R_terra tiene conto insieme di curvatura terrestre e
rifrazione atmosferica standard. Si massimizza la tangente (monotona
nell'angolo) e si applica arctan una volta sola alla fine.

Piramide max-pool: nel campo lontano il DEM viene sottocampionato prendendo il
MASSIMO del blocco, non la media. Cosi' un passo grossolano non puo' mai
"saltare" una cresta e sottostimare l'ostruzione. E' leggermente conservativo,
il che e' corretto: un blocco da 1 km a 50 km sottende ~1.2 gradi di azimut,
confrontabile con il mezzo grado del disco solare.
"""

import argparse
import sys
import time

import numpy as np
import rasterio

from config import (
    AOI_LAT_MAX,
    AOI_LAT_MIN,
    AOI_LON_MAX,
    AOI_LON_MIN,
    AZ_MAX,
    AZ_MIN,
    AZ_STEP,
    CRS_WORK,
    DERIVED,
    R_EFF_M,
    RES_M,
)

DEM = DERIVED / "dem_aeqd.tif"
OUT = DERIVED / "horizon.tif"
OBS = DERIVED / "obs.tif"
SCALE = 100.0  # int16 in centesimi di grado

# (distanza_max_m, indice_livello_piramide)
#
# Il raggio si ferma a 150 km e non a 250 per un motivo fisico: con curvatura +
# rifrazione, per ostruire il Sole a 2.6 gradi (la quota al massimo
# dell'eclissi) servirebbe un rilievo entro 89 km; a 150 km il limite scende a
# ~1.2 gradi. Sotto 2.6 gradi il punteggio satura comunque, quindi il campo
# oltre 150 km non puo' cambiare il risultato.
PLAN = [(10_000.0, 0), (30_000.0, 1), (80_000.0, 2), (150_000.0, 3)]
POOL = [1, 4, 12, 24]  # fattori di max-pool rispetto ai 90 m


def aoi_window(tr, shape) -> tuple[int, int, int, int]:
    """Finestra riga/colonna che copre l'AOI geografica (Piemonte + margine)."""
    from pyproj import Transformer

    fwd = Transformer.from_crs("EPSG:4326", CRS_WORK, always_xy=True)
    lons = np.linspace(AOI_LON_MIN, AOI_LON_MAX, 50)
    lats = np.linspace(AOI_LAT_MIN, AOI_LAT_MAX, 50)
    lo, la = np.meshgrid(lons, lats)
    x, y = fwd.transform(lo.ravel(), la.ravel())
    c0 = max(0, int((x.min() - tr.c) / tr.a) - 1)
    c1 = min(shape[1], int((x.max() - tr.c) / tr.a) + 2)
    r0 = max(0, int((tr.f - y.max()) / -tr.e) - 1)
    r1 = min(shape[0], int((tr.f - y.min()) / -tr.e) + 2)
    return r0, r1, c0, c1


def build_pyramid(dem: np.ndarray) -> list[tuple[np.ndarray, float]]:
    """Livelli max-pooled: (array, risoluzione_m)."""
    levels = [(dem, RES_M)]
    for f in POOL[1:]:
        h, w = dem.shape
        hh, ww = h // f, w // f
        block = dem[: hh * f, : ww * f].reshape(hh, f, ww, f)
        levels.append((block.max(axis=(1, 3)).astype("float32"), RES_M * f))
    return levels


def horizon_for_azimuth(
    az_deg: float,
    levels: list[tuple[np.ndarray, float]],
    x_obs: np.ndarray,
    y_obs: np.ndarray,
    h_obs: np.ndarray,
    x0: float,
    y0: float,
) -> np.ndarray:
    """Restituisce tan(angolo di orizzonte) per ogni osservatore."""
    a = np.radians(az_deg)
    ux, uy = np.sin(a), np.cos(a)  # azimut orario da nord di griglia
    best = np.full(x_obs.shape, -9.0, dtype="float32")

    d_prev = 0.0
    for d_max, lev in PLAN:
        arr, res = levels[lev]
        nrow, ncol = arr.shape
        step = res  # un passo per cella del livello: non salta nulla
        d = d_prev + step
        while d <= d_max:
            xs = x_obs + d * ux
            ys = y_obs + d * uy
            cc = ((xs - x0) / res).astype(np.int32)
            rr = ((y0 - ys) / res).astype(np.int32)
            np.clip(cc, 0, ncol - 1, out=cc)
            np.clip(rr, 0, nrow - 1, out=rr)
            ht = arr[rr, cc]
            # abbassamento per curvatura + rifrazione
            drop = (d * d) / (2.0 * R_EFF_M)
            ratio = (ht - h_obs - drop) / d
            np.maximum(best, ratio, out=best)
            d += step
        d_prev = d_max
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stride", type=int, default=2, help="sottocampionamento output (2 = 180 m)")
    ap.add_argument("--bench", action="store_true", help="cronometra un solo azimut e esce")
    args = ap.parse_args()

    with rasterio.open(DEM) as src:
        dem = src.read(1).astype("float32")
        tr = src.transform
        crs = src.crs
    x0, y0 = tr.c, tr.f
    print(f"DEM {dem.shape} @ {RES_M:.0f} m", flush=True)

    t = time.time()
    levels = build_pyramid(dem)
    print(f"Piramide max-pool: {[l[0].shape for l in levels]} in {time.time() - t:.1f}s", flush=True)

    # L'output copre solo l'AOI: il resto del dominio serve unicamente come
    # bersaglio dei raggi. Alle celle fuori AOI mancherebbe parte del buffer a
    # ovest, quindi il loro orizzonte sarebbe sottostimato.
    r0, r1, c0, c1 = aoi_window(tr, dem.shape)
    print(f"Finestra AOI: righe {r0}:{r1}, colonne {c0}:{c1}", flush=True)

    s = args.stride
    # Osservatore = cella PIU' ALTA del blocco s x s, non un angolo arbitrario.
    # Con stride 2 si scartano 3 celle DEM su 4: prendendone una qualsiasi si
    # finisce sistematicamente sul fianco delle cime invece che in cresta, e
    # una vetta panoramica risulta ostruita dalla propria sommita'. La cella
    # piu' alta e' anche il punto dove un osservatore si metterebbe davvero.
    nro, nco = (r1 - r0) // s, (c1 - c0) // s
    win = dem[r0 : r0 + nro * s, c0 : c0 + nco * s]
    flat = win.reshape(nro, s, nco, s).transpose(0, 2, 1, 3).reshape(nro, nco, s * s)
    k = flat.argmax(axis=2)
    h_obs = np.take_along_axis(flat, k[..., None], axis=2)[..., 0].astype("float32").ravel()
    abs_r = r0 + np.arange(nro)[:, None] * s + (k // s)
    abs_c = c0 + np.arange(nco)[None, :] * s + (k % s)
    x_obs = (x0 + (abs_c + 0.5) * RES_M).astype("float64").ravel()
    y_obs = (y0 - (abs_r + 0.5) * RES_M).astype("float64").ravel()
    out_shape = (nro, nco)
    print(f"Output {out_shape} = {h_obs.size / 1e6:.2f} M celle @ {RES_M * s:.0f} m", flush=True)

    azimuths = np.arange(AZ_MIN, AZ_MAX + 1e-9, AZ_STEP)
    if args.bench:
        azimuths = azimuths[:1]

    bands = np.empty((len(azimuths), *out_shape), dtype="int16")
    for i, az in enumerate(azimuths):
        t = time.time()
        tanv = horizon_for_azimuth(az, levels, x_obs, y_obs, h_obs, x0, y0)
        ang = np.degrees(np.arctan(tanv)).reshape(out_shape)
        bands[i] = np.round(ang * SCALE).astype("int16")
        print(
            f"  az {az:6.1f}  {time.time() - t:5.1f}s  "
            f"mediana {np.median(ang):5.2f}  max {ang.max():5.2f} gradi",
            flush=True,
        )

    if args.bench:
        print("\n(bench) nessun file scritto")
        return 0

    profile = {
        "driver": "GTiff",
        "height": out_shape[0],
        "width": out_shape[1],
        "count": len(azimuths),
        "dtype": "int16",
        "crs": crs,
        "transform": rasterio.Affine(
            RES_M * s, 0, x0 + c0 * RES_M, 0, -RES_M * s, y0 - r0 * RES_M
        ),
        "compress": "deflate",
        "predictor": 2,
        "tiled": True,
        "nodata": -32768,
    }
    with rasterio.open(OUT, "w", **profile) as d:
        for i, az in enumerate(azimuths):
            d.write(bands[i], i + 1)
            d.set_band_description(i + 1, f"grid_az_{az:.0f}")
        d.update_tags(scale_centideg=SCALE, az_min=AZ_MIN, az_max=AZ_MAX, az_step=AZ_STEP)
    print(f"\nScritto {OUT.name}: {OUT.stat().st_size / 1e6:.0f} MB, {len(azimuths)} bande")

    # Posizione e quota dell'osservatore scelto in ogni pixel: serve
    # all'export per dare le coordinate esatte del punto panoramico.
    obs_profile = {**profile, "count": 3, "dtype": "float32", "nodata": None}
    with rasterio.open(OBS, "w", **obs_profile) as d:
        for i, (n, arr) in enumerate(
            zip(("h_obs_m", "x_aeqd_m", "y_aeqd_m"), (h_obs, x_obs, y_obs)), start=1
        ):
            d.write(arr.reshape(out_shape).astype("float32"), i)
            d.set_band_description(i, n)
    print(f"Scritto {OBS.name}: quota osservatore {h_obs.min():.0f}-{h_obs.max():.0f} m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
