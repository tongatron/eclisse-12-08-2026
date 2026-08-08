# Eclissi 12 agosto 2026 — dove guardarla in Piemonte

Mappa della visibilità reale dell'eclissi solare parziale del 12 agosto 2026,
tenendo conto degli ostacoli orografici. MVP su Piemonte e aree confinanti;
architettura pensata per estendersi a tutta Italia senza modifiche di codice.

**Live:** https://eclisse.tongatron.org

---

## 1. Il problema, in un numero

In Piemonte l'eclissi inizia alle **19:28 CEST** ma il massimo è alle **20:21**,
con il Sole a **2,6° di altezza** e azimut 288° (WNW, verso il tramonto). A
quell'altezza, la visibilità dipende quasi interamente dal profilo
dell'orizzonte nella direzione WNW:

| Orizzonte locale a 288° | Oscuramento max visibile |
|---|---|
| 0–2,5° | 93,8% |
| 3,0° | 91,7% |
| 5,0° | 65,3% |
| 8,0° | 26,9% |
| ≥12° | nulla |

La soglia è ~2,6°, e una cima di 3000 m a 50 km di distanza sottende ~3,0°
(con curvatura terrestre e rifrazione). Le Alpi occidentali, viste dalla
pianura, stanno esattamente sul filo: da Torino il Rocciamelone (3538 m, 50
km, azimut 287,5°) sottende 3,5° e taglia il massimo, facendo perdere alla
città **8 punti** di oscuramento rispetto a Vercelli, che è più lontana dalle
Alpi ma le vede più basse all'orizzonte.

Questo è il motivo per cui il progetto non è "colora di verde dove piove
poco": l'80%+ della variazione di visibilità in Piemonte è spiegata
dall'orografia, non dalla differenza di orario o di posizione del Sole (che
varia solo di ~1 grado in altezza su tutta l'AOI).

---

## 2. Architettura

```
pipeline/                    (Python, offline, eseguito una volta prima dell'evento)
  config.py                  parametri condivisi: date, bbox, CRS, risoluzioni
  01_download_dem.py    -->  data/dem_tiles/*.tif       (Copernicus GLO-90, WGS84)
  02_build_grid.py      -->  data/derived/dem_aeqd.tif  (mosaico, riproiettato)
  03_horizon.py         -->  data/derived/horizon.tif   (angolo orizzonte x 28 azimut)
                         -->  data/derived/obs.tif       (posizione/quota osservatore)
  04_score.py           -->  data/derived/score.tif     (punteggio finale, 4 bande)
  05_access.py          -->  data/derived/access.tif    (distanza da strada)
  06_export.py          -->  web/public/data/*.png,json,geojson
  validate.py                controllo di sanità, nessun output persistente

web/public/                  (sito statico, nessun backend)
  index.html                 MapLibre GL + logica di lettura pixel
  data/
    score.png                heatmap RGBA (visualizzazione)
    data.png                 raster RGBA "dati" (oscuramento/ora/orizzonte codificati nei canali)
    access.png               raster RGBA (distanza da strada, canale singolo replicato)
    meta.json                bounding box EPSG:3857 e legenda della codifica
    sites.geojson             top-20 punti panoramici raggiungibili
```

Non c'è database né backend: la pipeline gira una volta (o ogni volta che
cambiano i dati di input), produce file statici, e il sito li legge via
`fetch()`. Rigenerare tutto costa ~5 minuti di calcolo.

### Perché un raycast e non un viewshed a 360°

Il problema apparente ("dove si vede meglio l'eclissi") sembra richiedere un
viewshed completo (visibilità in ogni direzione). Ma il Sole occupa una fascia
di azimut stretta e nota in anticipo (277–299° di griglia, vedi §4), quindi
basta calcolare l'orizzonte in quella fascia: O(28 azimut × N celle) invece di
O(360 azimut × N celle), e senza dover fare line-of-sight fra coppie di punti.
Questo è ciò che rende il problema trattabile su un intero raster regionale in
pochi minuti invece di ore.

---

## 3. Le tre correzioni che contano

A 2,6° di altezza solare, approssimazioni normalmente trascurabili smettono di
esserlo. Il progetto le tratta esplicitamente:

1. **Curvatura terrestre + rifrazione atmosferica.** L'abbassamento apparente
   di un punto a distanza `d` è `d² / (2 R_eff)`, con
   `R_eff = 7/6 · R_terra ≈ 7 431 833 m` (valore standard per la rifrazione in
   condizioni atmosferiche medie). Senza questa correzione, a 90 km di
   distanza l'errore sull'angolo di orizzonte è dell'ordine di 0,4°, più della
   metà della soglia critica di 2,6°.

2. **Convergenza dei meridiani.** Il raycast lavora in una proiezione
   azimutale equidistante (AEQD) centrata sull'AOI, dove gli **azimut di
   griglia** (rispetto al nord della proiezione) divergono dagli **azimut
   veri** (rispetto al nord geografico locale) man mano che ci si allontana
   dal meridiano centrale. Sull'AOI (~220×290 km) questa divergenza (gamma)
   arriva a ±1,06°. Viene ricalcolata per singola cella con una differenza
   finita (spostamento di 0,01° in latitudine, trasformato in AEQD) e sommata
   all'azimut vero prima di interrogare il raster dell'orizzonte.

3. **Variazione spaziale delle efemeridi.** Sull'AOI l'altezza del Sole
   all'istante del massimo varia di ~2,5°, un intervallo confrontabile con la
   soglia stessa: usare un solo calcolo di efemeridi per tutta l'area
   introdurrebbe un errore sistematico crescente ai bordi. Le efemeridi sono
   calcolate su una griglia rada 6×6 e interpolate bilinearmente per cella a
   ogni passo temporale.

Tutti e tre gli effetti sono verificati indipendentemente in `validate.py`
(vedi §8).

---

## 4. Pipeline, stadio per stadio

### `config.py` — parametri condivisi

| Parametro | Valore | Motivo |
|---|---|---|
| `T_START_UTC` … `T_END_UTC` | 17:15–19:00 UTC (19:15–21:00 CEST) | finestra che copre tutto l'evento con margine |
| `DEM_LAT/LON_MIN/MAX` | 43–47°N, 3–9°E | bbox di **download** del DEM: 250 km di buffer a ovest del Piemonte, perché è da lì che arrivano le Alpi che tagliano il Sole |
| `AOI_LAT/LON_MIN/MAX` | 44,0–46,6°N, 6,5–9,3°E | bbox di **output** (Piemonte + margine) |
| `CRS_WORK` | AEQD, `lat_0=45.3 lon_0=7.9` | proiezione azimutale equidistante centrata sull'AOI: distanze e azimut dal centro sono geometricamente esatti, a differenza di EPSG:3035 che introdurrebbe 1–3° di convergenza non corretta |
| `RES_M` | 90 m | risoluzione nativa del DEM Copernicus GLO-90 |
| `AZ_MIN/MAX/STEP` | 272–299°, passo 1° | il Sole (azimut vero) copre 278–292°; l'intervallo è allargato di ~5° per lato per assorbire la convergenza dei meridiani |
| `MAX_RANGE_M` (in `03_horizon.py`, `PLAN`) | 150 km | vedi calcolo sotto |
| `R_EFF_M` | 7/6 · R_terra | curvatura + rifrazione standard |

**Perché il raggio si ferma a 150 km e non a 250:** con curvatura e
rifrazione, un'ostruzione capace di bloccare un Sole a 2,6° di altezza deve
trovarsi entro 89 km; a 150 km il limite fisico scende comunque sotto 1,2°.
Sotto 2,6° il punteggio è già saturo (93,8%), quindi nulla oltre i 150 km può
cambiare il risultato — verificato in `pipeline/03_horizon.py` col commento
che riporta il calcolo.

### `01_download_dem.py`

Scarica 35 tile Copernicus DEM GLO-90 (30 m nativi, qui usati alla risoluzione
di pubblicazione 90 m) dal bucket pubblico AWS Open Data
(`copernicus-dem-90m.s3.eu-central-1.amazonaws.com`), in parallelo (8
thread). I tile marittimi assenti (404) sono normali e trattati come mare.
Licenza: Copernicus DEM è distribuito con licenza gratuita ESA (nessuna
attribuzione obbligatoria per uso non commerciale, ma buona pratica citarla).

### `02_build_grid.py`

Mosaica i 35 tile (`rasterio.merge`) e riproietta in AEQD a 90 m
(`rasterio.warp.reproject`, resampling bilineare). Nodata trattato come
mare (0 m): non ostruisce l'orizzonte, comportamento corretto per l'uso.

### `03_horizon.py` — il cuore geometrico

Per ogni cella di output e ogni azimut di griglia, marcia lungo il raggio e
tiene il massimo di:

```
tan(alpha) = (h_bersaglio - h_osservatore - d² / (2 R_eff)) / d
```

Si massimizza la **tangente** (monotona nell'angolo, evita `arctan` ripetuti)
e si applica `arctan` una sola volta alla fine.

**Piramide max-pool.** Il DEM viene sottocampionato in blocchi via
**massimo**, non media, per 4 livelli (1×, 4×, 12×, 24× → 90 m, 360 m, 1080 m,
2160 m). Il raycast usa il livello più fine vicino e il più grossolano
lontano (piano in `PLAN`). Usare il massimo invece della media è una scelta
deliberata e conservativa: con la media, un passo grossolano potrebbe
"saltare" una cresta stretta e sottostimare l'ostruzione; con il massimo, un
blocco da 1 km a 50 km sottende ~1,2° di azimut — confrontabile col mezzo
grado del disco solare — quindi non manca mai una cresta rilevante.

**Selezione dell'osservatore.** L'output è sottocampionato di uno `stride`
(default 2, cioè 180 m) rispetto al DEM nativo. Per ogni blocco stride×stride
si sceglie come osservatore la **cella più alta**, non una cella d'angolo
arbitraria. È stato un bug reale in una versione precedente: con una cella
d'angolo, un punto vicino a una vetta poteva cadere sul fianco anziché in
cresta, risultando "ostruito dalla propria sommità" — la cima del Monviso
misurava 0% di visibilità finché non è stata corretta questa selezione. È
anche semanticamente corretto: la cella più alta del blocco è dove un
osservatore reale si metterebbe.

**Finestra AOI.** Solo la sotto-regione geografica dell'AOI viene scritta in
output (righe/colonne calcolate proiettando gli angoli AOI in AEQD); il resto
del DEM serve solo da bersaglio dei raggi. Riduce l'output da ~40M a ~2M
celle per banda.

**Output:**
- `horizon.tif` — 28 bande int16 (una per azimut di griglia, passo 1°), unità
  centesimi di grado, nodata `-32768`. Tag `scale_centideg`, `az_min`,
  `az_max`, `az_step`.
- `obs.tif` — 3 bande float32: quota dell'osservatore selezionato (m),
  coordinate X/Y AEQD esatte del punto (necessarie perché l'osservatore non
  coincide col centro del pixel di output, essendo la cella più alta del
  blocco).

Tempo di calcolo: ~5–8 s/azimut sull'AOI, ~2,5 minuti totali.

### `04_score.py` — dalla geometria all'osservabilità

Per ogni cella e ogni passo temporale (20 s, da 19:25 a 20:55 CEST):

1. Efemeridi Sole/Luna interpolate bilinearmente dalla griglia rada 6×6
   (`astronomy-engine`, altezza e azimut **apparenti**, cioè già rifratti da
   `A.Refraction.Normal` — coerente con l'uso di `R_eff` per il terreno: il
   confronto è apparente-contro-apparente, quello che vede davvero
   l'osservatore).
2. Oscuramento come **frazione di area** del disco solare coperta dalla Luna
   (intersezione di due cerchi via la formula dell'area della lente),
   *non* frazione di diametro — le due differiscono sensibilmente vicino
   alla totalità.
3. Azimut vero → azimut di griglia (+ gamma, la convergenza per cella),
   interpolazione lineare fra le due bande di `horizon.tif` più vicine.
4. Visibilità: `altezza_apparente > angolo_orizzonte AND altezza_apparente > 0`.
5. Punteggio = massimo di (2) su tutti i passi temporali che soddisfano (4).

**Output** `score.tif`, 4 bande float32, stessa griglia di `horizon.tif`:

| Banda | Nome | Contenuto |
|---|---|---|
| 1 | `obsc_vis` | oscuramento massimo **visibile** [0–1] — il punteggio principale |
| 2 | `obsc_theo` | oscuramento massimo teorico a orizzonte piatto [0–1] — per calcolare quanto "costa" il terreno |
| 3 | `t_best_min_after_1900` | minuti dopo le 19:00 CEST dell'istante migliore |
| 4 | `hor_used_deg` | angolo di orizzonte usato in quell'istante |

Tempo di calcolo: ~35–40 s per l'intero ciclo (271 passi × 2M celle,
vettorizzato con NumPy — nessun loop Python su singole celle).

### `05_access.py` — un buon panorama serve a poco se non ci arrivi

Legge un estratto **Geofabrik** (`nord-ovest-latest.osm.pbf`, Piemonte + Valle
d'Aosta + Liguria + Lombardia, licenza OSM **ODbL**) con `pyosmium`
(`osmium.FileProcessor`), filtra le vie con `highway` in un set di classi
"carrozzabili" (motorway…residential, `living_street`, `service`; **esclude**
sentieri e `track`), densifica ogni segmento a passi di 90 m, rasterizza sulla
griglia e calcola una **distance transform euclidea** (`scipy.ndimage.
distance_transform_edt`).

**Perché Geofabrik e non Overpass:** una query Overpass su un'area di questa
estensione (220×290 km, migliaia di km di rete stradale) va sistematicamente
in timeout (504) — verificato su `overpass-api.de`, `overpass.kumi.systems` e
`overpass.private.coffee`. L'estratto regionale precompilato è l'unica
strategia che regge a questa scala.

**Maschera di copertura.** L'AOI sconfina in Francia e Svizzera, che
l'estratto nord-ovest non copre: senza maschera, quelle celle mostrerebbero
una "grande distanza da strada" che in realtà è solo mancanza di dati, non
isolamento reale. Il footprint esatto dell'estratto (`nord-ovest.poly`,
formato Osmosis) viene rasterizzato e le celle fuori copertura sono marcate
`NaN`.

**Output** `access.tif`, 1 banda float32, distanza in metri, `NaN` fuori
copertura.

### `06_export.py` — impacchettare per il web

Riproietta tutto in **EPSG:3857** (obbligatorio: un `ImageSource` di MapLibre
GL mappa i quattro angoli dell'immagine linearmente sulla mappa, quindi
qualunque altro CRS produrrebbe una distorsione visibile) a 200 m di
risoluzione, e scrive PNG **senza dipendenze esterne** (encoder PNG scritto a
mano con `struct` + `zlib`, RGBA, deflate compressione 6) per evitare Pillow
come dipendenza pesante.

**Codifica di `data.png`** (il raster "dati", non la heatmap visiva):

| Canale | Contenuto | Decodifica |
|---|---|---|
| R | oscuramento % | `R / 2.55` |
| G | minuti dopo le 19:00 CEST dell'istante migliore | `G` diretto (0–255, satura oltre 255 min = 23:15, mai raggiunto) |
| B | angolo di orizzonte usato, gradi | `B / 4` (range utile 0–63,75°) |
| A | 255 se valido, 0 fuori area calcolata | — |

`access.png` replica la distanza (m/20, clampata a 255 → 5100 m) sui tre
canali RGB per compatibilità visiva, alpha a 0 fuori copertura.

`score.png` è la heatmap **visiva**: rampa di colore rosso→arancio→giallo→
verde con stop a 0/50/75/88/94% (vedi `ramp()`, duplicata in JS in
`index.html` per la legenda — se si cambia una rampa va cambiata anche
l'altra).

`meta.json` contiene i bound EPSG:3857 e gli angoli in lon/lat (per
`ImageSource.coordinates` di MapLibre, che vuole WGS84).

`sites.geojson`: top-20 punti panoramici. Selezione: celle con
`obsc_vis ≥ 92%` **e** `dist_strada ≤ 300 m`, ordinate per un punteggio
composito (oscuramento primario, distanza da strada e quota come
spareggio), con **separazione minima di 12 km** fra siti scelti (evita che i
20 risultati siano tutti sulla stessa cresta).

---

## 5. Frontend (`web/public/index.html`)

Pagina singola, nessun bundler, MapLibre GL da CDN. Nessun backend: tutta la
logica di lettura pixel gira nel browser.

- **Overlay raster**: `score.png` e `access.png` come `ImageSource` di
  MapLibre, opacità regolabile da slider.
- **Ispezione al click**: `data.png` e `access.png` vengono caricati anche
  come `ImageData` via `<canvas>` (non solo mostrati come layer), così un
  click sulla mappa può leggere direttamente i valori del pixel sotto il
  cursore (proiezione manuale lon/lat → EPSG:3857 → indice pixel, replicando
  la trasformazione di Web Mercator lato client per evitare una chiamata di
  rete).
- **Race condition nota e risolta**: `map.addSource()` va chiamato solo dopo
  l'evento `load` dello style; l'app aspetta `mapReady` insieme al
  caricamento dei dati con `Promise.all`.
- **Resize**: il canvas MapLibre viene ridimensionato esplicitamente
  (`map.resize()`) su `ResizeObserver` del contenitore, perché la creazione
  della mappa può avvenire prima che il layout CSS sia definitivo.
- **Ricerca comune**: campo di testo in cima al pannello, geocoding
  client-side via API `search` di **Nominatim/OpenStreetMap**
  (`nominatim.openstreetmap.org`), con `viewbox` limitato ai bound del DEM
  (`3,47,9,43`, `bounded=1`) e `countrycodes=it` per scartare risultati fuori
  area. Input con debounce di 400 ms e `AbortController` per annullare le
  richieste stale mentre l'utente digita. Alla selezione di un risultato:
  `map.flyTo()` sul punto e chiamata a `inspect()` come per un click sulla
  mappa. Nessuna chiave API richiesta; rispetta la usage policy di Nominatim
  per volumi bassi (uso personale, non un servizio ad alto traffico).

---

## 6. Librerie e versioni (pipeline)

```
astronomy-engine==2.1.19   efemeridi Sole/Luna ad alta precisione
numpy==2.5.1               calcolo vettoriale
scipy==1.18.0               distance_transform_edt, map_coordinates
rasterio==1.5.0             I/O raster, riproiezione (include GDAL 3.12.1 in wheel)
pyproj==3.7.2               trasformazioni di coordinate
shapely==2.1.2               geometrie per la maschera di copertura OSM
osmium==4.3.1                lettura .osm.pbf (pyosmium)
```

Nessuna installazione di sistema richiesta (niente GDAL/GRASS a livello OS):
`rasterio` porta GDAL nella propria wheel. Python 3.12.

Frontend: `maplibre-gl@4.7.1` da CDN unpkg, nessuna altra dipendenza.

---

## 7. Esecuzione

```bash
python3 -m venv .venv
./.venv/bin/pip install rasterio numpy scipy astronomy-engine pyproj shapely osmium
```

```bash
curl -sL -o data/nord-ovest.osm.pbf https://download.geofabrik.de/europe/italy/nord-ovest-latest.osm.pbf
curl -sL -o data/nord-ovest.poly    https://download.geofabrik.de/europe/italy/nord-ovest.poly
```

```bash
cd pipeline
for s in 01_download_dem 02_build_grid 03_horizon 04_score 05_access 06_export validate; do
  ../.venv/bin/python $s.py
done
```

Tempi indicativi: DEM 154 MB / 35 tile, `03_horizon` ~2,5 min, `04_score`
~40 s, `05_access` ~1–2 min (dominato dal parsing del PBF), `06_export` ~10 s.

Sito in locale:

```bash
cd web/public && python3 -m http.server 8931
```

`03_horizon.py` accetta `--stride N` (default 2, output a 180 m) e `--bench`
(cronometra un solo azimut senza scrivere file — utile per stimare i tempi
prima di un run completo su un dominio più grande).

---

## 8. Validazione

`validate.py` esegue due controlli indipendenti, entrambi da rilanciare dopo
ogni modifica alla geometria del raycast:

**A. Confronto analitico.** L'angolo di elevazione del Rocciamelone (3538 m)
visto da Torino centro viene ricalcolato a mano con la stessa formula di
`03_horizon.py` (distanza e azimut via trasformazione di coordinate diretta,
non tramite il raster) e confrontato col valore letto dal raster:
**3,56° calcolato vs 3,52° letto** (il raster, che prende il massimo su tutto
il raggio e non un singolo bersaglio, deve essere ≥ del valore puntuale — lo
è).

**B. Tabella su 14 località note**, dove l'ordine atteso è deducibile a priori
dalla geografia (cime aperte > colline > pianura > pianura sotto le Alpi >
fondovalle alpino). Risultato: Mondovì/Langhe/pianura orientale 93–94,5%,
Superga 93,5%, **Torino 86,2%** (penalizzata dal Rocciamelone), Biella 25,6%
(Prealpi biellesi vicine e alte), Sestriere 24,0% (circondato da vette più
alte), Bardonecchia e Monviso 0% (fondovalle/versante in ombra).

**Un'anomalia investigata e non corretta perché corretta:** la cima del
Monviso, prima del fix sulla selezione dell'osservatore (§4, `03_horizon.py`),
risultava 0%. Indagando pixel per pixel: a 360 m a ovest della cresta
(oltre lo spartiacque) il punteggio è 94,4%; sul versante est, prima della
cresta, è 0%. È il comportamento fisicamente corretto — un gradiente ripido
attorno a uno spartiacque, non un artefatto — ed è rimasto identico anche
dopo il fix, che ha spostato l'osservatore sulla cella più alta del blocco
(risultato: sulla vetta vera, che è visibile, non più sul fianco).

---

## 9. Limiti noti

- **Griglia di output a 180 m** su DEM nativo a 90 m: vicino a creste molto
  strette (< 180 m) il pixel di output può non catturare esattamente lo
  spartiacque. L'osservatore è scelto come cella più alta del blocco 2×2, ma
  per un singolo punto d'interesse conviene sempre verificare i pixel
  adiacenti o rilanciare con `--stride 1` (90 m, ~4× il tempo di calcolo).
- **DEM di superficie (DSM), non di terreno (DTM):** Copernicus GLO-90 include
  vegetazione ed edifici mediati sulla cella. Ostacoli sotto ~100–200 m di
  altezza (alberi isolati, edifici, tralicci) non sono rappresentati in modo
  affidabile a questa risoluzione.
- **Accessibilità stradale disponibile solo dentro il footprint** dell'estratto
  Geofabrik nord-ovest (~66% della griglia AOI): fuori è `NaN`, cioè "non
  calcolato", non "molto lontano" — la UI lo mostra come "fuori copertura".
- **Mulattiere e sentieri (`track`) esclusi** dalla rete carrozzabile:
  raggiungere un punto panoramico in serata presuppone un mezzo normale.
- **Nessun modello di traffico o parcheggio**: "vicino a una strada" non
  implica che ci sia dove fermarsi.
- **Nessun fattore meteo** (vedi §10): un punto con visibilità geometrica del
  94% può essere completamente coperto da nuvole quella sera.
- Il punteggio composito di `sites.geojson` privilegia oscuramento e vicinanza
  a strada in parti uguali circa; non è stato tarato con un test utente.

---

## 10. Da fare

- **Meteo** (esplicitamente differito dall'utente in questa iterazione).
  Copertura nuvolosa oraria (bassa/media/alta) da **Open-Meteo**
  (`api.open-meteo.com`, nessuna API key richiesta) per il 12/08/2026,
  20:00–20:45 CEST, come livello aggiuntivo e fattore di ranking. Le
  previsioni a 5 giorni sono già utilizzabili al momento della stesura di
  questo documento (7 agosto 2026). È il fattore singolo più impattante
  rimasto fuori: può azzerare un orizzonte geometricamente perfetto.
  Implementazione suggerita: chiamata client-side (CORS aperto su
  Open-Meteo), overlay separato, nessuna modifica alla pipeline Python.
- **Grafico del profilo d'orizzonte** nel popup di dettaglio: disegnare la
  curva `horizon(azimut)` sovrapposta alla traiettoria del Sole (con i dischi
  Sole/Luna all'istante migliore) per il punto cliccato. I dati ci sono già
  in `horizon.tif`/`data.png`; serve solo un piccolo canvas SVG lato client
  che legga le 28 bande — oggi il raster dati esportato ne porta solo il
  valore all'istante migliore, non l'intero profilo, quindi servirebbe
  esportare anche `horizon.tif` (o un suo sottocampionamento) verso il web.
- **DEM ad alta risoluzione** (5 m, Geoportale Piemonte) applicato *solo* ai
  siti finalisti della classifica, per raffinare gli ultimi metri attorno alle
  creste dov'è più facile che la griglia a 180 m sbagli di qualche punto
  percentuale.
- **Estensione a tutta Italia**: cambiare `DEM_LAT/LON_MIN/MAX` e
  `AOI_LAT/LON_MIN/MAX` in `config.py`; nessun'altra modifica di codice è
  necessaria. Il costo cresce linearmente con l'area (l'Italia intera è
  ~5× l'AOI attuale ⇒ stima ~15–20 min di calcolo totale). L'estratto OSM
  andrebbe sostituito con l'estratto Italia completo di Geofabrik.
- **Mobile**: il layout a due colonne (pannello fisso + mappa) non è ancora
  responsive sotto ~600px di larghezza.
- Validare la classifica dei 20 siti con un secondo criterio indipendente
  (es. presenza di parcheggio OSM entro 200 m) prima di pubblicizzarla.

---

## 11. Fonti dati e licenze

| Dato | Fonte | Licenza |
|---|---|---|
| DEM | Copernicus DEM GLO-90, ESA / AWS Open Data | gratuita, attribuzione consigliata |
| Rete stradale | OpenStreetMap, estratto Geofabrik nord-ovest | ODbL — attribuzione richiesta (presente nel footer della mappa) |
| Efemeridi | `astronomy-engine` (Don Cross, MIT) | MIT |
| Tile di base | OpenStreetMap standard tile server | uso per sviluppo; per produzione ad alto traffico servirebbe un provider dedicato (es. MapTiler, Stadia) per rispettare la tile usage policy di OSM |
| Geocoding (ricerca comune) | Nominatim, OpenStreetMap | uso per sviluppo/basso volume; per produzione ad alto traffico servirebbe un'istanza propria o un provider a pagamento, per rispettare la usage policy di Nominatim |
| Meteo (previsto) | Open-Meteo | CC BY 4.0, nessuna API key |

---

## 12. Deploy

Sito statico servito da un container `nginx:alpine` (bind-mount di
`web/public/`) sul server personale dell'autore, esposto pubblicamente via
Cloudflare Tunnel su `eclisse.tongatron.org`. Il repository Git **non**
contiene credenziali di accesso al server: la documentazione di deploy con
IP/SSH/password è mantenuta in un file locale separato, deliberatamente
escluso dal controllo di versione (vedi `.gitignore`).

Per ripubblicare dopo una modifica al sito o ai dati:

```bash
rsync -az --delete web/public/ hp-ubuntu:/srv/apps/eclisse/public/
ssh hp-ubuntu 'docker restart eclisse-site'
```
