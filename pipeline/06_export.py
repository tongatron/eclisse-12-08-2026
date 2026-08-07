"""Export per il web: heatmap, raster dati codificato, top-20 siti.

Eseguito da CLI, non importato altrove. Legge data/derived/{score,access,obs}.tif
e scrive web/public/data/{score.png,data.png,access.png,meta.json,sites.geojson}.
sites.geojson: Point WGS84 con proprieta' rango, oscuramento_pct, ora_massimo
("20:21"), orizzonte_deg, quota_m, dist_strada_m.
Nessun dato personale. Istruzione utente: "gestisci accessibilita. Meteo
mettilo nei to-do. Procedi"

Tutto viene riproiettato in EPSG:3857 perche' e' la proiezione della mappa:
un image overlay di MapLibre mappa i quattro angoli linearmente, quindi in
qualsiasi altro CRS l'immagine risulterebbe deformata.
"""

import json
import struct
import sys
import zlib

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.warp import Resampling, calculate_default_transform, reproject

from config import DERIVED, WEB_PUBLIC, ensure_dirs

SCORE = DERIVED / "score.tif"
ACCESS = DERIVED / "access.tif"
OBS = DERIVED / "obs.tif"
RES_3857 = 200.0

MIN_OBSC = 0.92
MAX_DIST_ROAD = 300.0
MIN_SEP_M = 12_000.0
N_SITES = 20


def png_write(path, rgba):
    h, w, _ = rgba.shape
    raw = b"".join(b"\x00" + rgba[i].tobytes() for i in range(h))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    print(f"  {path.name}: {w}x{h}, {len(png) / 1e6:.1f} MB")


def to_3857(arr, src_tr, src_crs, shape):
    b = rasterio.transform.array_bounds(shape[0], shape[1], src_tr)
    dst_tr, w, h = calculate_default_transform(
        src_crs, "EPSG:3857", shape[1], shape[0], *b, resolution=RES_3857
    )
    out = np.full((h, w), np.nan, dtype="float32")
    reproject(
        source=arr, destination=out, src_transform=src_tr, src_crs=src_crs,
        dst_transform=dst_tr, dst_crs="EPSG:3857", resampling=Resampling.bilinear,
        src_nodata=np.nan, dst_nodata=np.nan,
    )
    return out, dst_tr


def ramp(v):
    """0->rosso, 50->arancio, 75->giallo, 88->verde chiaro, 94->verde."""
    stops = [(0, (140, 22, 22)), (50, (200, 90, 30)), (75, (225, 190, 60)),
             (88, (120, 190, 70)), (94, (30, 200, 120))]
    xs = [s[0] for s in stops]
    return np.stack(
        [np.interp(v, xs, [s[1][i] for s in stops]) for i in range(3)], axis=-1
    ).astype("uint8")


def main() -> int:
    ensure_dirs()
    with rasterio.open(SCORE) as s:
        obsc, tbest, horu = s.read(1), s.read(3), s.read(4)
        tr, crs, shape = s.transform, s.crs, s.shape
    with rasterio.open(ACCESS) as a:
        dist = a.read(1)
    with rasterio.open(OBS) as o:
        h_obs, x_obs, y_obs = o.read(1), o.read(2), o.read(3)

    o3, dst_tr = to_3857(obsc, tr, crs, shape)
    t3, _ = to_3857(tbest, tr, crs, shape)
    h3, _ = to_3857(horu, tr, crs, shape)
    d3, _ = to_3857(dist, tr, crs, shape)
    H, W = o3.shape
    print(f"Griglia web {H} x {W} @ {RES_3857:.0f} m (EPSG:3857)", flush=True)

    pct = np.clip(np.nan_to_num(o3, nan=0.0) * 100, 0, 100)
    valid = np.isfinite(o3)

    rgb = ramp(pct)
    alpha = np.where(valid, 190, 0)
    alpha = np.where(valid & (pct < 25), 120, alpha).astype("uint8")
    png_write(WEB_PUBLIC / "score.png", np.dstack([rgb, alpha]))

    R = np.round(pct * 2.55).astype("uint8")
    G = np.clip(np.nan_to_num(t3, nan=0.0), 0, 255).astype("uint8")
    B = np.clip(np.nan_to_num(h3, nan=0.0) * 4, 0, 255).astype("uint8")
    A = np.where(valid, 255, 0).astype("uint8")
    png_write(WEB_PUBLIC / "data.png", np.dstack([R, G, B, A]))

    D = np.clip(np.nan_to_num(d3, nan=99999) / 20.0, 0, 255).astype("uint8")
    png_write(
        WEB_PUBLIC / "access.png",
        np.dstack([D, D, D, np.where(np.isfinite(d3), 255, 0).astype("uint8")]),
    )

    west, south, east, north = rasterio.transform.array_bounds(H, W, dst_tr)
    inv = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    lw, ls = inv.transform(west, south)
    le, ln = inv.transform(east, north)
    meta = {
        "bounds_3857": [west, south, east, north],
        "corners_lonlat": [[lw, ln], [le, ln], [le, ls], [lw, ls]],
        "res_m": RES_3857,
        "evento": "eclissi solare parziale 12 agosto 2026",
        "codifica": "R=oscuramento%*2.55, G=minuti dopo 19:00 CEST, B=orizzonte*4 gradi",
    }
    (WEB_PUBLIC / "meta.json").write_text(json.dumps(meta, indent=1))

    ok = (obsc >= MIN_OBSC) & np.isfinite(dist) & (dist <= MAX_DIST_ROAD)
    print(f"Celle candidate: {ok.sum():,}")
    rank = np.where(ok, obsc * 1000 - dist / 1000.0 + h_obs / 100000.0, -1e9)
    order = np.argsort(rank, axis=None)[::-1]
    inv_aeqd = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    picked, feats = [], []
    for flat in order:
        if len(feats) >= N_SITES:
            break
        r, c = np.unravel_index(flat, obsc.shape)
        if not ok[r, c]:
            break
        x, y = float(x_obs[r, c]), float(y_obs[r, c])
        if any((x - px) ** 2 + (y - py) ** 2 < MIN_SEP_M**2 for px, py in picked):
            continue
        picked.append((x, y))
        lon, lat = inv_aeqd.transform(x, y)
        tm = float(tbest[r, c])
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]},
            "properties": {
                "rango": len(feats) + 1,
                "oscuramento_pct": round(float(obsc[r, c]) * 100, 1),
                "ora_massimo": f"{19 + int(tm) // 60:02d}:{int(tm) % 60:02d}",
                "orizzonte_deg": round(float(horu[r, c]), 2),
                "quota_m": round(float(h_obs[r, c])),
                "dist_strada_m": round(float(dist[r, c])),
            },
        })
    (WEB_PUBLIC / "sites.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": feats}, indent=1)
    )
    print(f"\nScritti {len(feats)} siti")
    for f in feats[:8]:
        p, g = f["properties"], f["geometry"]["coordinates"]
        print(f"  {p['rango']:2d}. {g[1]:.4f},{g[0]:.4f}  {p['oscuramento_pct']}%  "
              f"oriz {p['orizzonte_deg']}g  {p['quota_m']}m  strada {p['dist_strada_m']}m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
