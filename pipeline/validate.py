"""Controllo di sanita' su punti noti: i numeri della pipeline reggono?

Eseguito da CLI, non importato da nessun altro modulo; non espone API e non
scrive file. Legge data/derived/{score.tif,horizon.tif,dem_aeqd.tif}.
Nessun dato personale. Istruzione utente: "gestisci accessibilita. Meteo
mettilo nei to-do. Procedi"

Due verifiche indipendenti:
  A. confronto analitico - angolo di elevazione di una cima nota calcolato a
     mano contro il valore letto dal raster horizon.tif;
  B. tabella su localita' reali, dove l'ordine atteso e' noto a priori
     (cime > colline > pianura > fondovalle alpino).
"""

import math
import sys

import numpy as np
import rasterio
from pyproj import Transformer

from config import AZ_MIN, AZ_STEP, CRS_WORK, DERIVED, R_EFF_M

SCORE = DERIVED / "score.tif"
HOR = DERIVED / "horizon.tif"
DEM = DERIVED / "dem_aeqd.tif"

# (nome, lat, lon, attesa)
SITES = [
    ("Monviso (cima)", 44.6673, 7.0910, "cima: orizzonte ~0"),
    ("Punta Gnifetti", 45.9269, 7.8769, "cima: orizzonte ~0"),
    ("Sestriere", 44.9578, 6.8778, "alto ma circondato"),
    ("La Morra (Langhe)", 44.6367, 7.9339, "collina, Alpi lontane"),
    ("Superga (TO)", 45.0806, 7.7683, "collina sopra Torino"),
    ("Torino centro", 45.0703, 7.6869, "pianura sotto le Alpi"),
    ("Vercelli", 45.3206, 8.4183, "pianura, Alpi a ~90 km"),
    ("Novara", 45.4469, 8.6222, "pianura, Alpi lontane"),
    ("Alessandria", 44.9133, 8.6156, "pianura orientale"),
    ("Mondovi", 44.3956, 7.8164, "pedemontana sud"),
    ("Cuneo", 44.3841, 7.5426, "pianura sotto le Marittime"),
    ("Biella", 45.5628, 8.0583, "pedemontana nord"),
    ("Bardonecchia", 45.0797, 6.6997, "fondovalle alpino chiuso: coperto"),
    ("Stresa (Maggiore)", 45.8850, 8.5300, "Mottarone a ovest: coperto"),
    # Da qui in giu': controllo del gradiente nazionale. Fuori dal nord non e'
    # piu' l'orografia a decidere ma l'ora del tramonto, quindi l'ordine
    # atteso segue la geografia e non l'altezza delle montagne. Le voci nuove
    # stanno in fondo apposta, cosi' IDX_TORINO resta valido.
    ("Bolzano", 46.4983, 11.3548, "nord-est, conca fra i monti"),
    ("Trieste", 45.6495, 13.7768, "nord-est estremo, mare a ovest"),
    ("Genova", 44.4056, 8.9463, "costa ligure, monti alle spalle"),
    ("Gran Sasso", 42.4500, 13.5667, "sul fianco sotto il Corno Grande: coperto"),
    ("Roma", 41.9028, 12.4964, "centro, Sole quasi al tramonto"),
    ("Cagliari", 39.2238, 9.1217, "citta' bassa, colli a WNW: coperto"),
    ("Napoli", 40.8518, 14.2681, "sud, tramonta prima del massimo"),
    ("Bari", 41.1171, 16.8719, "Adriatico, tramonto anticipato"),
    ("Lecce", 40.3515, 18.1750, "Salento: il minimo nazionale atteso"),
    ("Palermo", 38.1157, 13.3615, "Sicilia nord"),
    ("Etna (cima)", 37.7510, 14.9934, "quota massima del sud"),
    ("Lampedusa", 35.5000, 12.6000, "estremo sud, orizzonte tutto marino"),
]
IDX_TORINO = 5


def sample(path, pts_xy):
    with rasterio.open(path) as src:
        n = src.count
        return np.array(list(src.sample(pts_xy)), dtype="float64").reshape(-1, n)


def main() -> int:
    fwd = Transformer.from_crs("EPSG:4326", CRS_WORK, always_xy=True)
    pts = [fwd.transform(lon, lat) for _, lat, lon, _ in SITES]

    sc = sample(SCORE, pts)
    hz = sample(HOR, pts) / 100.0
    dem = sample(DEM, pts)[:, 0]

    # --- A. verifica analitica: Rocciamelone visto da Torino ---
    print("A. Verifica analitica indipendente")
    to_lat, to_lon = SITES[IDX_TORINO][1], SITES[IDX_TORINO][2]
    to_h = dem[IDX_TORINO]
    rm_lat, rm_lon, rm_h = 45.2036, 7.0772, 3538.0
    x1, y1 = fwd.transform(to_lon, to_lat)
    x2, y2 = fwd.transform(rm_lon, rm_lat)
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy)
    az = math.degrees(math.atan2(dx, dy)) % 360
    drop = d * d / (2 * R_EFF_M)
    ang = math.degrees(math.atan2(rm_h - to_h - drop, d))
    band = int(round((az - AZ_MIN) / AZ_STEP))
    letto = hz[IDX_TORINO, band]
    print(f"   Rocciamelone (3538 m) da Torino ({to_h:.0f} m)")
    print(f"   distanza {d / 1000:.1f} km, azimut di griglia {az:.1f} gradi (banda {band})")
    print(f"   angolo calcolato a mano : {ang:.2f} gradi")
    print(f"   angolo letto dal raster : {letto:.2f} gradi  (massimo su tutto il raggio)")
    ok = letto >= ang - 0.15
    print(f"   il raster deve essere >= del calcolo a mano -> {'OK' if ok else 'ANOMALIA'}")

    # --- B. tabella sui siti ---
    print("\nB. Siti noti")
    print(
        f"{'sito':20s} {'quota':>6s} {'oriz.':>7s} {'visib.':>7s} {'teor.':>7s} "
        f"{'perdita':>8s} {'ora max':>8s}  attesa"
    )
    for i in np.argsort(-sc[:, 0]):
        name, _, _, exp = SITES[i]
        vis, theo, tmin, horu = sc[i, 0] * 100, sc[i, 1] * 100, sc[i, 2], sc[i, 3]
        hh, mm = 19 + int(tmin) // 60, int(tmin) % 60
        ora = f"{hh:02d}:{mm:02d}" if tmin >= 0 else "--"
        print(
            f"{name:20s} {dem[i]:5.0f}m {horu:6.2f}g {vis:6.1f}% {theo:6.1f}% "
            f"{theo - vis:7.1f}p {ora:>8s}  {exp}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
