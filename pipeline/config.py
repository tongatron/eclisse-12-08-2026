"""Parametri condivisi della pipeline. Eclissi solare parziale del 12 agosto 2026."""

import pathlib

# --- Evento ---
ECLIPSE_DATE = (2026, 8, 12)
# Finestra di calcolo in UTC. In CEST: 19:15 -> 21:00.
T_START_UTC = (2026, 8, 12, 17, 15, 0)
T_END_UTC = (2026, 8, 12, 19, 0, 0)
T_STEP_S = 20

# --- Dominio DEM ---
# I raggi puntano a ovest (azimut vero 279-293), quindi il buffer che conta e'
# quello a ovest: da li' arrivano le Alpi che tagliano il Sole quando e' a
# pochi gradi di altezza. 150 km a lat 45 sono ~1.9 gradi di longitudine,
# quindi E003 copre con margine l'osservatore piu' occidentale (6.6).
# A est basta E018: Otranto, il punto piu' orientale, sta a 18.5.
DEM_LAT_MIN, DEM_LAT_MAX = 35, 47  # tile N35..N47, da Lampedusa al Brennero
DEM_LON_MIN, DEM_LON_MAX = 3, 18   # tile E003..E018

# --- Area di output (Italia + margine) ---
AOI_LAT_MIN, AOI_LAT_MAX = 35.4, 47.15
AOI_LON_MIN, AOI_LON_MAX = 6.55, 18.60

# --- Griglia di lavoro ---
# Azimutale equidistante centrata sull'AOI: distanze e azimut dal centro sono
# esatti. Su un dominio nazionale (1300 km di raggio) la deformazione
# trasversale resta sotto lo 0.5%, irrilevante per raggi da 150 km.
# Il centro sta in mezzo alla penisola e non piu' in Piemonte: da 45.3/7.9 la
# convergenza dei meridiani arrivava a -7.8 gradi in Salento, da 42.0/12.5
# resta entro +-4.4. La convergenza residua per cella e' comunque corretta
# esplicitamente in 04_score.py.
AEQD_LAT0, AEQD_LON0 = 42.0, 12.5
CRS_WORK = (
    f"+proj=aeqd +lat_0={AEQD_LAT0} +lon_0={AEQD_LON0} "
    "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
)
RES_M = 90.0

# --- Raycast ---
# Sull'intera Italia il Sole eclissato e' sopra l'orizzonte con azimut VERO fra
# 278.7 (primo contatto in Piemonte) e 293.3 (tramonto in Alto Adige). Il
# raycast lavora su azimut di GRIGLIA: sommata la convergenza (+-4.4 gradi col
# centro AEQD nazionale) servono 274.3-297.5, arrotondati con margine.
AZ_MIN, AZ_MAX, AZ_STEP = 273.0, 298.0, 1.0
MAX_RANGE_M = 250_000.0
R_EARTH_M = 6_371_000.0
R_EFF_M = R_EARTH_M * 7.0 / 6.0  # curvatura + rifrazione standard

# Passo del raycast: fine vicino, grossolano lontano.
# (limite_m, passo_m)
RAY_STEPS = [
    (2_000.0, 45.0),
    (10_000.0, 90.0),
    (30_000.0, 250.0),
    (80_000.0, 600.0),
    (250_000.0, 1_500.0),
]

# --- Percorsi ---
ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DEM_TILES = DATA / "dem_tiles"
DERIVED = DATA / "derived"
WEB_PUBLIC = ROOT / "web" / "public" / "data"


def ensure_dirs() -> None:
    for p in (DATA, DEM_TILES, DERIVED, WEB_PUBLIC):
        p.mkdir(parents=True, exist_ok=True)
