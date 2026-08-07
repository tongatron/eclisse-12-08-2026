"""Parametri condivisi della pipeline. Eclissi solare parziale del 12 agosto 2026."""

import pathlib

# --- Evento ---
ECLIPSE_DATE = (2026, 8, 12)
# Finestra di calcolo in UTC. In CEST: 19:15 -> 21:00.
T_START_UTC = (2026, 8, 12, 17, 15, 0)
T_END_UTC = (2026, 8, 12, 19, 0, 0)
T_STEP_S = 20

# --- Dominio DEM ---
# Il buffer a ovest deve coprire ~250 km: e' da li' che arrivano le Alpi
# che tagliano il Sole quando e' a 2.6 gradi di altezza.
DEM_LAT_MIN, DEM_LAT_MAX = 43, 47  # tile N43..N47
DEM_LON_MIN, DEM_LON_MAX = 3, 9    # tile E003..E009

# --- Area di output (Piemonte + margine) ---
AOI_LAT_MIN, AOI_LAT_MAX = 44.0, 46.6
AOI_LON_MIN, AOI_LON_MAX = 6.5, 9.3

# --- Griglia di lavoro ---
# Azimutale equidistante centrata sull'AOI: distanze e azimut dal centro sono
# esatti, e la convergenza dei meridiani resta piccola sul Piemonte. EPSG:3035
# introdurrebbe 1-3 gradi di convergenza, non trascurabili quando il Sole e' a
# 2.6 gradi di altezza. La convergenza residua per cella e' comunque corretta
# esplicitamente in 04_score.py.
AEQD_LAT0, AEQD_LON0 = 45.3, 7.9
CRS_WORK = (
    f"+proj=aeqd +lat_0={AEQD_LAT0} +lon_0={AEQD_LON0} "
    "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
)
RES_M = 90.0

# --- Raycast ---
# Il Sole passa da az vero 278 (19:20 CEST) a 292 (tramonto). Il raycast lavora
# su azimut di GRIGLIA: allarghiamo di ~5 gradi per assorbire la convergenza.
AZ_MIN, AZ_MAX, AZ_STEP = 272.0, 299.0, 1.0
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
