"""Export per il web: heatmap nazionale d'insieme + tasselli dati a piena
risoluzione.

Eseguito da CLI, non importato altrove. Legge data/derived/{score,obs}.tif e
scrive web/public/data/{score.png,meta.json} e web/public/data/tiles/*.png.
Nessun dato personale. Istruzione utente: "Crea mappa per tutto il territorio
italiano, non solo per il piemonte"

Perche' due prodotti diversi e non un raster solo. Sull'Italia intera un unico
PNG alla risoluzione di analisi sarebbe 6706 x 8741 px: 70 MB di file e 234 MB
di ImageData una volta decodificato nel canvas del browser, per ognuna delle
immagini che il frontend legge. Quindi:

  score.png   vista d'insieme a 600 m, un'immagine sola, e' l'unico raster
              caricato all'avvio. A zoom nazionale il dettaglio fine non
              sarebbe comunque distinguibile.
  tiles/      i dati veri per l'interrogazione al click, a 250 m, spezzati in
              tasselli da 1024 px. Il browser ne scarica uno (piu' il gemello
              delle quote) solo quando l'utente clicca in quella zona.

I tasselli interamente vuoti - mare, o fuori dall'area calcolata - non vengono
scritti affatto: il frontend tratta il 404 come "nessun dato". Sono la
maggioranza, visto che il bounding box dell'Italia e' per lo piu' mare.

Tutto viene riproiettato in EPSG:3857 perche' e' la proiezione della mappa: un
image overlay di MapLibre mappa i quattro angoli linearmente, quindi in
qualsiasi altro CRS l'immagine risulterebbe deformata. Vista d'insieme e
tasselli condividono lo stesso bounding box 3857, calcolato una volta sola,
cosi' che le due griglie restino allineate.
"""

import json
import struct
import sys
import zlib

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.warp import Resampling, reproject, transform_bounds

from config import (
    AOI_LAT_MAX,
    AOI_LAT_MIN,
    AOI_LON_MAX,
    AOI_LON_MIN,
    DERIVED,
    WEB_PUBLIC,
    ensure_dirs,
)

SCORE = DERIVED / "score.tif"
OBS = DERIVED / "obs.tif"

# 600 m non e' un compromesso arbitrario: a questa risoluzione la vista
# d'insieme e' 2235 x 2913 px e sta dentro il limite di 4096 px per lato delle
# texture WebGL su molte GPU mobili. Un ImageSource di MapLibre e' una texture:
# a 400 m sarebbe 3353 x 4370 e su quei dispositivi non verrebbe disegnato.
RES_OVERVIEW = 600.0  # m di EPSG:3857 per la vista d'insieme
RES_TILE = 250.0      # m di EPSG:3857 per i tasselli dati
TILE_PX = 1024        # potenza di due, texture-friendly e ~1 MB per tassello


def png_write(path, rgba, quiet=False):
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
    if not quiet:
        print(f"  {path.name}: {w}x{h}, {len(png) / 1e6:.1f} MB")
    return len(png)


def bbox_3857(src_tr, src_crs, shape):
    """Bounding box 3857 della griglia di lavoro, ritagliato sull'AOI.

    La finestra di lavoro e' un rettangolo in AEQD, e un rettangolo in AEQD
    sborda dal riquadro lon/lat che doveva coprire: agli angoli arrivava fino
    a ~300 km a ovest del punto piu' occidentale d'Italia. Quelle celle non
    sono solo fuori tema, sono inaffidabili: stanno a ridosso del bordo del
    DEM (E003) e il loro buffer di 150 km verso ovest e' incompleto, quindi
    l'orizzonte risulta sottostimato. Erano anche l'origine dei valori al
    100%, che in Italia non esistono: li' ci si avvicina alla fascia di
    totalita' spagnola.

    Il ritaglio e' esatto senza costi: EPSG:3857 e' cilindrica, quindi un
    riquadro lon/lat e' un rettangolo allineato agli assi.
    """
    b = rasterio.transform.array_bounds(shape[0], shape[1], src_tr)
    full = transform_bounds(src_crs, "EPSG:3857", *b, densify_pts=64)
    fwd = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
    ax0, ay0 = fwd.transform(AOI_LON_MIN, AOI_LAT_MIN)
    ax1, ay1 = fwd.transform(AOI_LON_MAX, AOI_LAT_MAX)
    return (max(full[0], ax0), max(full[1], ay0), min(full[2], ax1), min(full[3], ay1))


def to_3857(arr, src_tr, src_crs, box, res, resampling=Resampling.bilinear):
    """Riproietta su una griglia 3857 ancorata a `box`, alla risoluzione `res`."""
    west, south, east, north = box
    w = int(np.ceil((east - west) / res))
    h = int(np.ceil((north - south) / res))
    dst_tr = rasterio.Affine(res, 0.0, west, 0.0, -res, north)
    out = np.full((h, w), np.nan, dtype="float32")
    reproject(
        source=arr, destination=out, src_transform=src_tr, src_crs=src_crs,
        dst_transform=dst_tr, dst_crs="EPSG:3857", resampling=resampling,
        src_nodata=np.nan, dst_nodata=np.nan,
    )
    return out


def ramp(v):
    """0->rosso, 50->arancio, 75->giallo, 88->verde chiaro, 94->verde."""
    stops = [(0, (140, 22, 22)), (50, (200, 90, 30)), (75, (225, 190, 60)),
             (88, (120, 190, 70)), (94, (30, 200, 120))]
    xs = [s[0] for s in stops]
    return np.stack(
        [np.interp(v, xs, [s[1][i] for s in stops]) for i in range(3)], axis=-1
    ).astype("uint8")


def encode_data(o3, t3, h3):
    """RGBA dei tasselli dati: oscuramento, istante migliore, orizzonte."""
    pct = np.clip(np.nan_to_num(o3, nan=0.0) * 100, 0, 100)
    return np.dstack([
        np.round(pct * 2.55).astype("uint8"),
        np.clip(np.nan_to_num(t3, nan=0.0), 0, 255).astype("uint8"),
        np.clip(np.nan_to_num(h3, nan=0.0) * 4, 0, 255).astype("uint8"),
        np.where(np.isfinite(o3), 255, 0).astype("uint8"),
    ])


def encode_elev(e3):
    """RGBA delle quote: quota_m = R*256 + G."""
    eh = np.clip(np.nan_to_num(e3, nan=0), 0, 65535).astype("uint32")
    return np.dstack([
        (eh // 256).astype("uint8"),
        (eh % 256).astype("uint8"),
        np.zeros(eh.shape, dtype="uint8"),
        np.where(np.isfinite(e3), 255, 0).astype("uint8"),
    ])


def write_tiles(tile_dir, name, rgba):
    """Spezza un RGBA in tasselli TILE_PX; salta quelli interamente vuoti."""
    h, w, _ = rgba.shape
    cols = int(np.ceil(w / TILE_PX))
    rows = int(np.ceil(h / TILE_PX))
    written = skipped = total_bytes = 0
    for r in range(rows):
        for c in range(cols):
            block = rgba[r * TILE_PX : (r + 1) * TILE_PX, c * TILE_PX : (c + 1) * TILE_PX]
            if not block[..., 3].any():
                skipped += 1
                continue
            # I tasselli di bordo sarebbero piu' piccoli del previsto: si
            # riempiono fino a TILE_PX cosi' il frontend indicizza con una
            # formula sola, senza conoscere la dimensione di ognuno.
            if block.shape[0] < TILE_PX or block.shape[1] < TILE_PX:
                pad = np.zeros((TILE_PX, TILE_PX, 4), dtype="uint8")
                pad[: block.shape[0], : block.shape[1]] = block
                block = pad
            total_bytes += png_write(tile_dir / f"{name}_{r}_{c}.png", block, quiet=True)
            written += 1
    print(f"  {name}: {written} tasselli scritti, {skipped} vuoti saltati, "
          f"{total_bytes / 1e6:.1f} MB")
    return rows, cols


def main() -> int:
    ensure_dirs()
    tile_dir = WEB_PUBLIC / "tiles"
    tile_dir.mkdir(parents=True, exist_ok=True)
    for old in tile_dir.glob("*.png"):
        old.unlink()

    with rasterio.open(SCORE) as s:
        obsc, tbest, horu = s.read(1), s.read(3), s.read(4)
        tr, crs, shape = s.transform, s.crs, s.shape
    with rasterio.open(OBS) as o:
        h_obs = o.read(1)

    box = bbox_3857(tr, crs, shape)
    west, south, east, north = box
    print(f"Bounding box 3857: {(east - west) / 1000:.0f} x "
          f"{(north - south) / 1000:.0f} km", flush=True)

    # --- vista d'insieme ---
    o_ov = to_3857(obsc, tr, crs, box, RES_OVERVIEW)
    pct = np.clip(np.nan_to_num(o_ov, nan=0.0) * 100, 0, 100)
    valid = np.isfinite(o_ov)
    print(f"Vista d'insieme {o_ov.shape} @ {RES_OVERVIEW:.0f} m", flush=True)
    alpha = np.where(valid, 190, 0)
    alpha = np.where(valid & (pct < 25), 120, alpha).astype("uint8")
    png_write(WEB_PUBLIC / "score.png", np.dstack([ramp(pct), alpha]))

    # --- tasselli dati ---
    # Nearest e non bilinear, al contrario della vista d'insieme. Qui ogni
    # pixel e' un valore che l'utente legge come numero, e l'oscuramento
    # visibile non e' un campo continuo: dipende da una soglia (il Sole sta
    # sopra l'orizzonte o non ci sta). Mediando una cella bloccata con le
    # vicine libere esce un numero che non corrisponde a nessun calcolo -
    # Roma centro passava da 30.4% (orizzonte 3.01 gradi, valore vero a 180 m)
    # a 60.0% (orizzonte 0.75), cioe' la media fra "coperto" e "scoperto".
    # Nearest prende il valore della cella a 180 m piu' vicina: e' meno
    # levigato ma e' un risultato realmente calcolato. Conserva anche il
    # sentinella t_best = -1 dei punti mai visibili, che il bilineare
    # spalmava sui vicini producendo percentuali piccole ma non nulle.
    near = Resampling.nearest
    o3 = to_3857(obsc, tr, crs, box, RES_TILE, near)
    t3 = to_3857(tbest, tr, crs, box, RES_TILE, near)
    h3 = to_3857(horu, tr, crs, box, RES_TILE, near)
    e3 = to_3857(h_obs, tr, crs, box, RES_TILE, near)
    print(f"Griglia tasselli {o3.shape} @ {RES_TILE:.0f} m", flush=True)

    rows, cols = write_tiles(tile_dir, "data", encode_data(o3, t3, h3))
    write_tiles(tile_dir, "elev", encode_elev(e3))

    # I bound dichiarati sono quelli dell'IMMAGINE, non quelli richiesti: la
    # larghezza in pixel e' arrotondata per eccesso, quindi score.png si spinge
    # fino a qualche centinaio di metri oltre `box`. Dichiarare `box` come
    # angoli dell'ImageSource sfaserebbe l'overlay di quel tanto.
    oh, ow = o_ov.shape
    ov_east = west + ow * RES_OVERVIEW
    ov_south = north - oh * RES_OVERVIEW

    inv = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    lw, ls = inv.transform(west, ov_south)
    le, ln = inv.transform(ov_east, north)
    meta = {
        "bounds_3857": [west, ov_south, ov_east, north],
        "corners_lonlat": [[lw, ln], [le, ln], [le, ls], [lw, ls]],
        "res_m": RES_OVERVIEW,
        "evento": "eclissi solare parziale 12 agosto 2026",
        "codifica": "R=oscuramento%*2.55, G=minuti dopo 19:00 CEST, B=orizzonte*4 gradi",
        "codifica_elev": "elev: quota_m = R*256+G",
        "tiles": {
            "west_3857": west,
            "north_3857": north,
            "res_m": RES_TILE,
            "px": TILE_PX,
            "rows": rows,
            "cols": cols,
            "data": "data/tiles/data_{r}_{c}.png",
            "elev": "data/tiles/elev_{r}_{c}.png",
            "nota": "i tasselli assenti sono mare o fuori area: 404 = nessun dato",
        },
    }
    (WEB_PUBLIC / "meta.json").write_text(json.dumps(meta, indent=1))

    v = pct[valid]
    print(f"\noscuramento visibile (vista d'insieme): mediana {np.median(v):.1f}%  "
          f"max {v.max():.1f}%")
    print(f"  celle >= 90%: {(v >= 90).mean() * 100:.1f}%   < 50%: {(v < 50).mean() * 100:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
