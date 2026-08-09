"""Genera l'indice locale dei comuni usato dalla ricerca del sito.

Input:
  - l'elenco ufficiale dei codici ISTAT (xlsx);
  - i confini comunali ISTAT generalizzati (zip/shapefile).

Output: web/public/data/comuni.json. Il browser non contatta servizi di
geocoding: nomi, provincia e coordinate sono tutti inclusi nel deploy statico.
Il solo centro geometrico e' sufficiente per portare la mappa nel comune; non
e' una promessa di rappresentare il capoluogo o un punto panoramico.

Esempio (dalla radice del repository):

    python pipeline/build_comuni_index.py \
      --codes-xlsx /percorso/Elenco-comuni-italiani.xlsx \
      --boundaries-zip /percorso/Limiti01012026_g.zip
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

from config import WEB_PUBLIC

ISTAT_CODES_URL = "https://www.istat.it/storage/codici-unita-amministrative/Elenco-comuni-italiani.xlsx"
ISTAT_BOUNDARIES_URL = "https://www.istat.it/storage/cartografia/confini_amministrativi/generalizzati/2026/Limiti01012026_g.zip"
REFERENCE_DATE = "2026-02-21"
BOUNDARIES_REFERENCE_DATE = "2026-01-01"
# L'elenco dei codici e' aggiornato al 21 febbraio, mentre i confini 2026
# pubblicati da ISTAT sono al 1 gennaio. La fusione e' fra territori contigui:
# la media dei loro centroidi resta all'interno del nuovo comune ed evita di
# escluderlo dalla ricerca fino alla prossima edizione dei confini.
RECENT_MERGES = {"024129": ("024027", "024071")}  # Castegnero + Nanto
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.itertext()) for node in root.findall(f"{NS}si")]


def cell_value(cell: ET.Element, shared: list[str]) -> str:
    value = cell.find(f"{NS}v")
    if value is None:
        return ""
    text = value.text or ""
    return shared[int(text)] if cell.get("t") == "s" else text


def column_index(reference: str) -> int:
    """Converte la parte alfabetica di A1 in indice zero-based."""
    value = 0
    for char in reference:
        if not char.isalpha():
            break
        value = value * 26 + ord(char.upper()) - ord("A") + 1
    return value - 1


def read_codes(path: Path) -> dict[str, tuple[str, str, str]]:
    """Restituisce codice -> (nome italiano, provincia, denominazione ufficiale)."""
    with zipfile.ZipFile(path) as archive:
        shared = read_shared_strings(archive)
        root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    out = {}
    rows = root.findall(f".//{NS}sheetData/{NS}row")
    for row in rows[1:]:
        values = [""] * 27
        for cell in row.findall(f"{NS}c"):
            values[column_index(cell.get("r", "A1"))] = cell_value(cell, shared)
        # Colonne del file ISTAT: E codice, F denominazione ufficiale,
        # G denominazione italiana, L provincia/UTS.
        if len(values) < 12:
            continue
        code, official, italian, province = values[4], values[5], values[6], values[11]
        if code and italian and province:
            out[code.zfill(6)] = (italian, province, official)
    return out


def read_dbf_codes(path: Path) -> list[str]:
    """Legge il solo campo PRO_COM_T senza dipendenze GIS esterne."""
    with path.open("rb") as fh:
        head = fh.read(32)
        count, header_len, record_len = struct.unpack("<xxxxIHH20x", head)
        fields = []
        while True:
            field = fh.read(32)
            if field[0] == 0x0D:
                break
            fields.append((field[:11].split(b"\0", 1)[0].decode("ascii"), field[16]))
        offset = 1
        positions = {}
        for name, length in fields:
            positions[name] = (offset, length)
            offset += length
        start, length = positions["PRO_COM_T"]
        records = []
        fh.seek(header_len)
        for _ in range(count):
            record = fh.read(record_len)
            records.append(record[start : start + length].decode("utf-8").strip().zfill(6))
    return records


def utm32_to_lonlat(easting: float, northing: float) -> tuple[float, float]:
    """Converte EPSG:32632 (il CRS ISTAT 2026) in longitudine, latitudine."""
    a = 6_378_137.0
    ecc_sq = 0.0066943799901413165
    k0 = 0.9996
    e1 = (1 - math.sqrt(1 - ecc_sq)) / (1 + math.sqrt(1 - ecc_sq))
    x, y = easting - 500_000.0, northing
    mu = y / (a * k0 * (1 - ecc_sq / 4 - 3 * ecc_sq**2 / 64 - 5 * ecc_sq**3 / 256))
    phi1 = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
    )
    ecc_prime_sq = ecc_sq / (1 - ecc_sq)
    n1 = a / math.sqrt(1 - ecc_sq * math.sin(phi1) ** 2)
    t1 = math.tan(phi1) ** 2
    c1 = ecc_prime_sq * math.cos(phi1) ** 2
    r1 = a * (1 - ecc_sq) / (1 - ecc_sq * math.sin(phi1) ** 2) ** 1.5
    d = x / (n1 * k0)
    lat = phi1 - (n1 * math.tan(phi1) / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * ecc_prime_sq) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * ecc_prime_sq - 3 * c1**2) * d**6 / 720
    )
    lon = (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * ecc_prime_sq + 24 * t1**2) * d**5 / 120
    ) / math.cos(phi1)
    return math.degrees(lon) + 9.0, math.degrees(lat)


def centroid_from_shape(content: bytes) -> tuple[float, float, float]:
    """Centroide piano firmato (E, N, area) di un record Polygon UTM32N."""
    shape_type = struct.unpack_from("<i", content, 0)[0]
    if shape_type == 0:
        return 0.0, 0.0, 0.0
    if shape_type not in (5, 15, 25):
        raise ValueError(f"Tipo geometria inatteso: {shape_type}")
    min_x, min_y, max_x, max_y = struct.unpack_from("<4d", content, 4)
    parts, points = struct.unpack_from("<2i", content, 36)
    part_offsets = struct.unpack_from(f"<{parts}i", content, 44)
    point_start = 44 + 4 * parts
    coords = [struct.unpack_from("<2d", content, point_start + 16 * i) for i in range(points)]

    twice_area = sum_x = sum_y = 0.0
    for index, first in enumerate(part_offsets):
        ring = coords[first : part_offsets[index + 1] if index + 1 < parts else points]
        if len(ring) < 3:
            continue
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            cross = x1 * y2 - x2 * y1
            twice_area += cross
            sum_x += (x1 + x2) * cross
            sum_y += (y1 + y2) * cross
    if abs(twice_area) < 1e-16:
        return (min_x + max_x) / 2, (min_y + max_y) / 2, 0.0
    return sum_x / (3 * twice_area), sum_y / (3 * twice_area), twice_area / 2


def read_centroids(zip_path: Path) -> dict[str, tuple[float, float]]:
    with zipfile.ZipFile(zip_path) as archive:
        dbf_name = next(name for name in archive.namelist() if name.endswith("Com01012026_g_WGS84.dbf"))
        shp_name = dbf_name[:-4] + ".shp"
        with tempfile.TemporaryDirectory(prefix="eclissi-istat-") as directory:
            dbf_path = Path(directory) / "comuni.dbf"
            shp_path = Path(directory) / "comuni.shp"
            dbf_path.write_bytes(archive.read(dbf_name))
            shp_path.write_bytes(archive.read(shp_name))
            codes = read_dbf_codes(dbf_path)
            geometries: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
            with shp_path.open("rb") as fh:
                fh.seek(100)
                for code in codes:
                    header = fh.read(8)
                    if not header:
                        break
                    _, words = struct.unpack(">2i", header)
                    geometries[code].append(centroid_from_shape(fh.read(words * 2)))
    out = {}
    for code, pieces in geometries.items():
        total = sum(abs(area) for _, _, area in pieces)
        if total:
            easting = sum(lon * abs(area) for lon, _, area in pieces) / total
            northing = sum(lat * abs(area) for _, lat, area in pieces) / total
            out[code] = (
                *utm32_to_lonlat(easting, northing),
            )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codes-xlsx", type=Path, required=True)
    parser.add_argument("--boundaries-zip", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=WEB_PUBLIC / "comuni.json")
    args = parser.parse_args()

    codes = read_codes(args.codes_xlsx)
    centroids = read_centroids(args.boundaries_zip)
    for target, sources in RECENT_MERGES.items():
        if target not in centroids and all(source in centroids for source in sources):
            centroids[target] = tuple(
                sum(centroids[source][axis] for source in sources) / len(sources)
                for axis in (0, 1)
            )
    missing = sorted(set(codes) - set(centroids))
    if missing:
        raise SystemExit(f"Mancano {len(missing)} centroidi ISTAT: {', '.join(missing[:5])}")

    comuni = []
    for code, (name, province, official) in sorted(codes.items(), key=lambda item: item[1][:2]):
        lon, lat = centroids[code]
        # L'alias conserva le denominazioni bilingui, ma non duplica il nome.
        alias = official if official and official != name else ""
        comuni.append([name, province, round(lat, 5), round(lon, 5), alias])

    payload = {
        "schema": 1,
        "source": {
            "name": "ISTAT — Codici e confini delle unità amministrative",
            "reference_date": REFERENCE_DATE,
            "boundaries_reference_date": BOUNDARIES_REFERENCE_DATE,
            "codes_url": ISTAT_CODES_URL,
            "boundaries_url": ISTAT_BOUNDARIES_URL,
        },
        "comuni": comuni,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Scritto {args.out}: {len(comuni)} comuni")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
