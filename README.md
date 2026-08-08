# Eclissi 12 agosto 2026 — dove guardarla in Italia

Mappa della visibilità reale dell'eclissi solare parziale del 12 agosto 2026,
tenendo conto degli ostacoli orografici. Copre l'intero territorio italiano,
da Lampedusa al Brennero.

**Live:** https://eclisse-12-08-2026.tongatron.org

---

## 1. Il problema, in due numeri

### Il Sole tramonta durante l'eclissi

L'eclissi cade all'ora del tramonto, e il tramonto arriva prima a sud-est. Ne
esce un gradiente enorme lungo la penisola che non ha niente a che vedere con
le montagne: in mezza Italia il Sole sparisce sotto l'orizzonte **prima** di
arrivare al massimo dell'eclissi.

| Zona | Primo contatto | Massimo visibile | Oscuramento max |
|---|---|---|---|
| **Sardegna NO** (Stintino–Alghero) | 19:37 | 20:26 | **98,8%** |
| Piemonte NO | 19:28 | 20:22 | 93,6% |
| Alto Adige | 19:25 | 20:17 | 90,9% |
| Sardegna sud | 19:38 | 20:25 | 88,4% |
| Centro | 19:33 | 20:16 | 81,5% |
| Lampedusa | 19:42 | 20:04 | 30,3% |
| Calabria | 19:38 | 19:56 | 26,0% |
| Sicilia SE | 19:40 | 19:56 | 20,9% |
| Salento | 19:33 | 19:49 | **18,3%** |

Da Lampedusa in giù nella tabella il "massimo visibile" coincide col tramonto:
l'eclissi prosegue, ma sotto l'orizzonte.

**Il risultato che la versione regionale non poteva vedere.** Il punto
migliore d'Italia non è alpino: è la costa nord-occidentale della Sardegna,
con un massimo su terraferma del **98,78%** a 40,88 N / 8,22 E (zona Porto
Torres–Stintino), contro il 93,6% del Piemonte. La coda della fascia di
totalità termina al tramonto poco al largo, a ovest dell'isola: sul mare lì
l'oscuramento raggiunge il 100%.

Con un margine così, però, la geometria diventa spietata: in Sardegna il Sole
al momento migliore è a **0,1° di altezza**. Alghero e Sassari distano 35 km e
il raster dà 88,6% alla prima e 97,6% alla seconda, per mezzo grado di
differenza nell'orizzonte locale. È esattamente la ragione d'essere del
progetto — solo che qui l'ostacolo critico non è una montagna da 3000 m, è una
collina da 100.

### Dove il Sole è ancora alto, decide l'orografia

Al nord il Sole al massimo è a **2,6° di altezza**, azimut 288° (WNW). A
quell'altezza la visibilità dipende quasi interamente dal profilo
dell'orizzonte in quella direzione:

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

I due effetti si sommano e vanno tenuti distinti quando si legge la mappa: a
sud-est il rosso significa "già tramontato", sulle Alpi significa "dietro una
montagna". Il criterio di calcolo è lo stesso — il Sole conta solo finché è
sopra l'orizzonte *reale* — ma la causa è diversa.

Questo è anche il motivo per cui il progetto non è "colora di verde dove piove
poco": al nord la gran parte della variazione locale di visibilità è spiegata
dall'orografia, non dalla posizione del Sole.

---

## 2. Architettura

```
pipeline/                    (Python, offline, eseguito una volta prima dell'evento)
  config.py                  parametri condivisi: date, bbox, CRS, risoluzioni
  01_download_dem.py    -->  data/dem_tiles/*.tif       (Copernicus GLO-90, WGS84)
  02_build_grid.py      -->  data/derived/dem_aeqd.tif  (mosaico, riproiettato)
  03_horizon.py         -->  data/derived/horizon.tif   (angolo orizzonte x 26 azimut)
                         -->  data/derived/obs.tif       (posizione/quota osservatore)
  04_score.py           -->  data/derived/score.tif     (punteggio finale, 4 bande)
  05_access.py               distanza da strada — NON usato dalla mappa nazionale, vedi §4
  06_export.py          -->  web/public/data/{score.png,meta.json,tiles/*.png}
  validate.py                controllo di sanità, nessun output persistente

web/public/                  (sito statico, nessun backend)
  index.html                 MapLibre GL + logica di lettura pixel
  data/
    score.png                heatmap RGBA d'insieme a 600 m (l'unico raster caricato all'avvio)
    meta.json                bounding box EPSG:3857, legenda della codifica, griglia dei tasselli
    tiles/data_{r}_{c}.png   oscuramento/ora/orizzonte a 250 m, 1024 px per tassello
    tiles/elev_{r}_{c}.png   quote a 250 m, stessa griglia
```

Non c'è database né backend: la pipeline gira una volta (o ogni volta che
cambiano i dati di input), produce file statici, e il sito li legge via
`fetch()`.

### Perché due prodotti raster e non uno

Su scala nazionale un unico PNG alla risoluzione di analisi sarebbe
6706 × 8741 px: **70 MB** di file e **234 MB** di `ImageData` una volta
decodificato in un canvas, per ognuna delle immagini che il frontend
interroga. Insostenibile su telefono. Quindi:

- `score.png` è la sola immagine scaricata all'avvio, a 600 m: serve a
  *vedere* la mappa, e a zoom nazionale il dettaglio fine non sarebbe
  comunque distinguibile;
- i valori esatti che compaiono cliccando stanno in `tiles/`, a 250 m. Il
  browser scarica un tassello (più il gemello delle quote) solo per la zona
  cliccata, e lo tiene in cache.

I tasselli interamente vuoti non vengono scritti affatto: il frontend tratta
il 404 come "nessun dato". In pratica ne restano pochi, perché **anche il mare
ha dati validi**: sul mare il DEM vale 0 e l'orizzonte è libero, quindi
l'oscuramento lì è calcolato e sensato. Dopo il ritaglio sull'AOI la griglia è
7 × 6 tasselli e vengono scritti tutti.

I tasselli sono versionati in Git insieme al sito: sono 84 file per circa
47 MB. In questo modo un clone pulito e GitHub Pages contengono sempre anche i
dati interrogati al click, senza dipendere da un server separato.

### Perché un raycast e non un viewshed a 360°

Il problema apparente ("dove si vede meglio l'eclissi") sembra richiedere un
viewshed completo (visibilità in ogni direzione). Ma il Sole occupa una fascia
di azimut stretta e nota in anticipo (273–298° di griglia, vedi §4), quindi
basta calcolare l'orizzonte in quella fascia: O(26 azimut × N celle) invece di
O(360 azimut × N celle), e senza dover fare line-of-sight fra coppie di punti.
Questo è ciò che rende il problema trattabile su un raster nazionale da 45
milioni di celle in un'ora invece che in giorni.

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
   dal meridiano centrale. Sull'AOI nazionale questa divergenza (gamma)
   arriva a ±4,4°. Viene ricalcolata per singola cella con una differenza
   finita (spostamento di 0,01° in latitudine, trasformato in AEQD) e sommata
   all'azimut vero prima di interrogare il raster dell'orizzonte.

3. **Variazione spaziale delle efemeridi.** Sull'AOI nazionale (1000×1300 km)
   le circostanze cambiano moltissimo — l'oscuramento massimo visibile va dal
   94% in Piemonte al 18% in Salento — quindi un solo calcolo di efemeridi per
   tutta l'area sarebbe privo di senso. Sono calcolate su una griglia rada
   `NODES`×`NODES` e interpolate bilinearmente per cella a ogni passo
   temporale; `NODES` è passato da 6 a **16** proprio per questo, perché con 6
   nodi il passo sarebbe stato di 260 km.

Tutti e tre gli effetti sono verificati indipendentemente in `validate.py`
(vedi §8).

---

## 4. Pipeline, stadio per stadio

### `config.py` — parametri condivisi

| Parametro | Valore | Motivo |
|---|---|---|
| `T_START_UTC` … `T_END_UTC` | 17:15–19:00 UTC (19:15–21:00 CEST) | finestra che copre tutto l'evento con margine |
| `DEM_LAT/LON_MIN/MAX` | 35–47°N, 3–18°E | bbox di **download** del DEM (208 tile, 163 esistenti): i raggi puntano a ovest, quindi il buffer che conta è quello a ovest — E003 copre con margine i 150 km a ovest dell'osservatore più occidentale (6,6°E) |
| `AOI_LAT/LON_MIN/MAX` | 35,4–47,15°N, 6,55–18,60°E | bbox di **output**: l'Italia intera con un margine |
| `CRS_WORK` | AEQD, `lat_0=42.0 lon_0=12.5` | azimutale equidistante centrata sull'AOI: distanze e azimut dal centro sono geometricamente esatti. Il centro è in mezzo alla penisola e non più in Piemonte: da 45,3/7,9 la convergenza dei meridiani arrivava a −7,8° in Salento, da 42,0/12,5 resta entro ±4,4°. Su 1300 km di raggio la deformazione trasversale resta sotto lo 0,5% |
| `RES_M` | 90 m | risoluzione nativa del DEM Copernicus GLO-90 |
| `AZ_MIN/MAX/STEP` | 273–298°, passo 1° | misurato, non stimato: sull'Italia intera il Sole eclissato è sopra l'orizzonte con azimut **vero** fra 278,7° e 293,3°; sommata la convergenza (±4,4°) servono 274,3–297,5°, arrotondati con margine |
| `MAX_RANGE_M` (in `03_horizon.py`, `PLAN`) | 150 km | vedi calcolo sotto |
| `R_EFF_M` | 7/6 · R_terra | curvatura + rifrazione standard |

**Perché il raggio si ferma a 150 km e non a 250:** con curvatura e
rifrazione, un'ostruzione capace di bloccare un Sole a 2,6° di altezza deve
trovarsi entro 89 km; a 150 km il limite fisico scende comunque sotto 1,2°.
Sotto 2,6° il punteggio è già saturo (93,8%), quindi nulla oltre i 150 km può
cambiare il risultato — verificato in `pipeline/03_horizon.py` col commento
che riporta il calcolo.

### `01_download_dem.py`

Scarica 208 tile Copernicus DEM GLO-90 (30 m nativi, qui usati alla risoluzione
di pubblicazione 90 m) dal bucket pubblico AWS Open Data
(`copernicus-dem-90m.s3.eu-central-1.amazonaws.com`), in parallelo (8
thread). I tile marittimi assenti (404) sono normali e trattati come mare.
Licenza: Copernicus DEM è distribuito con licenza gratuita ESA (nessuna
attribuzione obbligatoria per uso non commerciale, ma buona pratica citarla).

### `02_build_grid.py`

Mosaica i 163 tile esistenti (`rasterio.merge`) e riproietta in AEQD a 90 m
(`rasterio.warp.reproject`, resampling bilineare). Nodata trattato come
mare (0 m): non ostruisce l'orizzonte, comportamento corretto per l'uso.
Griglia risultante 16498 × 16247 celle (365 MB, quote da −30 a 4788 m); ~30 s,
picco di memoria 2,4 GB.

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
del DEM serve solo da bersaglio dei raggi. Sul dominio nazionale riduce
l'output da 268M a 44,75M celle per banda (7346 × 6092 a 180 m).

**Blocchi da 300k celle.** Il raycast processa gli osservatori a blocchi
invece che tutti insieme. Il calcolo è identico; cambia solo la dimensione dei
temporanei. Su 45M celle, `xs`/`ys`/`cc`/`rr`/`ht` sarebbero sei array da
centinaia di MB ciascuno, che escono dalla cache a ogni passo del raggio.
Misurato sullo stesso azimut, a parità di risultato:

| Blocco | Tempo/azimut |
|---|---|
| tutte le celle insieme | 523 s |
| 2M celle | 221 s |
| 300k celle | **152 s** |

Stessa ragione dietro due altre scelte: le coordinate osservatore sono
`float32` e non `float64` (a ~1,5·10⁶ m un float32 risolve 0,12 m, irrilevante
su celle da 90 m, e risparmia 360 MB per array), e la selezione
dell'osservatore confronta `s*s` sottogriglie sfalsate — che sono viste a
passo costante — invece di usare `reshape`+`transpose`+`argmax`, che
materializzava due copie da 716 MB.

**Scrittura banda per banda.** Ogni banda si calcola e si scrive subito.
Tenerle tutte in memoria sarebbe costato 2,4 GB su una macchina da 8,6 GB. Il
profilo GTiff usa `interleave=band` (si scrive una banda intera alla volta:
con l'interleave per pixel ogni scrittura toccherebbe e ricomprimerebbe tutti
i tile del file) e **`BIGTIFF=YES`**, obbligatorio perché 26 bande × 44,75M
celle superano il limite di 4 GB degli offset del TIFF classico — GDAL non se
ne accorge alla creazione, fallisce a metà scrittura con `Maximum TIFF file
size exceeded`.

**Output:**
- `horizon.tif` — 26 bande int16 (una per azimut di griglia, passo 1°), unità
  centesimi di grado, nodata `-32768`. Tag `scale_centideg`, `az_min`,
  `az_max`, `az_step`.
- `obs.tif` — 3 bande float32: quota dell'osservatore selezionato (m),
  coordinate X/Y AEQD esatte del punto (necessarie perché l'osservatore non
  coincide col centro del pixel di output, essendo la cella più alta del
  blocco).

Tempo di calcolo: ~150 s/azimut sull'AOI nazionale, **~70 minuti totali**.
È di gran lunga lo stadio più lento della pipeline.

### `04_score.py` — dalla geometria all'osservabilità

Per ogni cella e ogni passo temporale (20 s, da 19:25 a 20:55 CEST):

1. Efemeridi Sole/Luna interpolate bilinearmente dalla griglia rada 16×16
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

**Due accorgimenti per la scala nazionale.** Le efemeridi sui nodi si
calcolano **una volta sola** per tutti i passi temporali, prima del ciclo
principale: dipendono solo dai nodi, non dalla porzione di griglia in
lavorazione. E la griglia si processa a **strisce di righe** (`STRIPE_ROWS`),
perché `src.read()` su tutte le bande costerebbe 4,8 GB di float32; a strisce
ne restano ~250 MB per volta. Ogni cella è indipendente dalle altre, quindi il
risultato è identico a quello del ciclo su tutta la griglia.

Tempo di calcolo: ~20 minuti per l'intero ciclo (271 passi × 44,75M celle,
vettorizzato con NumPy — nessun loop Python su singole celle).

### `05_access.py` — non fa parte della mappa nazionale

**Questo stadio non viene eseguito** nella pipeline nazionale, e il suo output
non è più letto da `06_export.py`. Serviva a scegliere i 20 punti panoramici
migliori scartando quelli irraggiungibili; su scala nazionale una classifica
assoluta finirebbe tutta in Piemonte e Valle d'Aosta, dove l'oscuramento è
massimo, e sarebbe inutile per chi guarda da Sicilia o Salento. La mappa è
quindi puramente esplorativa: cerca un comune, o clicca un punto.

Il codice resta nel repo, funzionante, perché è il punto di partenza naturale
se si vuole reintrodurre una classifica per regione (servirebbe
`italy-latest.osm.pbf`, ~2 GB, al posto dell'estratto nord-ovest). Quanto
segue descrive com'è fatto.

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
qualunque altro CRS produrrebbe una distorsione visibile) e scrive PNG **senza
dipendenze esterne** (encoder PNG scritto a mano con `struct` + `zlib`, RGBA,
deflate compressione 6) per evitare Pillow come dipendenza pesante.

Produce due cose a risoluzioni diverse — il perché è in §2:

| Prodotto | Risoluzione | Quando viene scaricato |
|---|---|---|
| `score.png` | 600 m | all'avvio, sempre |
| `tiles/data_{r}_{c}.png` | 250 m, 1024 px | al primo click in quella zona |
| `tiles/elev_{r}_{c}.png` | 250 m, 1024 px | idem |

I 600 m della vista d'insieme non sono un compromesso estetico: un
`ImageSource` di MapLibre **è una texture WebGL**, e molte GPU mobili si
fermano a 4096 px per lato. A 600 m l'immagine è 2235 × 2913 e passa; a 400 m
sarebbe 3353 × 4370 e su quei dispositivi la mappa resterebbe semplicemente
vuota.

Il bounding box EPSG:3857 è calcolato **una volta sola** (`bbox_3857()`) e le
due griglie ci vengono ancorate sopra con transform espliciti, così restano
allineate: se ognuna calcolasse i propri bound, gli arrotondamenti le
sfaserebbero di qualche pixel.

**Codifica dei tasselli `data`** (i valori veri, non la heatmap visiva):

| Canale | Contenuto | Decodifica |
|---|---|---|
| R | oscuramento % | `R / 2.55` |
| G | minuti dopo le 19:00 CEST dell'istante migliore | `G` diretto (0–255, satura oltre 255 min = 23:15, mai raggiunto) |
| B | angolo di orizzonte usato, gradi | `B / 4` (range utile 0–63,75°) |
| A | 255 se valido, 0 fuori area calcolata | — |

**Codifica dei tasselli `elev`**: `quota_m = R * 256 + G`, alpha come sopra.
Servono due immagini perché quattro canali non bastano a tenere insieme
oscuramento, orario, orizzonte, quota a 16 bit e maschera di validità.

I tasselli di bordo vengono riempiti fino a 1024 px, così il frontend
indicizza con una formula sola senza conoscere la dimensione di ognuno. Quelli
interamente vuoti non vengono scritti: il 404 **è** il valore "nessun dato".

`score.png` è la heatmap **visiva**: rampa di colore rosso→arancio→giallo→
verde con stop a 0/50/75/88/94% (vedi `ramp()`, duplicata in JS in
`index.html` per la legenda — se si cambia una rampa va cambiata anche
l'altra).

`meta.json` contiene i bound EPSG:3857, gli angoli in lon/lat (per
`ImageSource.coordinates` di MapLibre, che vuole WGS84) e il blocco `tiles`
con origine, risoluzione, dimensione e numero di righe/colonne della griglia
dei tasselli.

---

## 5. Frontend (`web/public/index.html`)

Pagina singola, nessun bundler, MapLibre GL da CDN. Nessun backend: tutta la
logica di lettura pixel gira nel browser.

- **Overlay raster**: `score.png` come `ImageSource` di MapLibre, opacità
  regolabile da slider. È l'unico raster caricato all'avvio.
- **Ispezione al click, a tasselli**: al click si calcola quale tassello copre
  il punto (proiezione manuale lon/lat → EPSG:3857 → indice di tassello e
  pixel, replicando Web Mercator lato client per evitare una chiamata di
  rete), si scaricano `data` ed `elev` di quel solo tassello e si leggono come
  `ImageData` via `<canvas>`. Dettagli che contano:
  - la **cache contiene la Promise**, non l'immagine: due click ravvicinati
    sullo stesso tassello condividono un download invece di lanciarne due;
  - un contatore di sequenza scarta la risposta di un click ormai superato,
    così un tassello lento non sovrascrive un click più recente;
  - il 404 di un tassello mancante è atteso (mare, fuori area) e viene
    tradotto in "nessun dato", non in un errore;
  - il click fuori area ora lo dice esplicitamente. Prima non succedeva
    nulla e sembrava che il sito fosse rotto — su una mappa che è in larga
    parte mare, capita di continuo.
- **Pannello a scomparsa (mobile)**: sotto i 768 px il pannello occupa
  `46dvh` in cima e la mappa il resto; una maniglia sulla cucitura fra i due
  lo chiude, e la mappa va a tutto schermo. A pannello chiuso la maniglia
  risale in cima allo schermo. Note di implementazione: `dvh` e non `vh`
  (su iOS la barra degli indirizzi che si ritrae cambia `vh` e lascerebbe la
  mappa tagliata); `overflow:hidden` su `html,body` (col documento
  scrollabile il trascinamento sulla mappa muoveva la pagina); `map.resize()`
  a ogni cambio di stato, altrimenti il canvas resta della misura vecchia;
  in orizzontale su telefono il pannello parte già chiuso, perché lascerebbe
  una striscia di mappa inutilizzabile.
- **Race condition nota e risolta**: `map.addSource()` va chiamato solo dopo
  l'evento `load` dello style; l'app aspetta `mapReady` insieme al
  caricamento dei dati con `Promise.all`.
- **Resize**: il canvas MapLibre viene ridimensionato esplicitamente
  (`map.resize()`) su `ResizeObserver` del contenitore, perché la creazione
  della mappa può avvenire prima che il layout CSS sia definitivo.
- **Ricerca comune**: campo di testo in cima al pannello, geocoding
  client-side via API `search` di **Nominatim/OpenStreetMap**
  (`nominatim.openstreetmap.org`), con `viewbox` limitato ai bound dell'AOI
  (`6.55,47.15,18.6,35.4`, `bounded=1`) e `countrycodes=it` per scartare
  risultati fuori area. Input con debounce di 400 ms e `AbortController` per annullare le
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
cd pipeline
for s in 01_download_dem 02_build_grid 03_horizon 04_score 06_export validate; do
  ../.venv/bin/python -u $s.py
done
```

`05_access` non è nell'elenco: vedi §4: non fa parte della mappa nazionale.
Solo se lo si vuole reintrodurre servono gli estratti OSM:

```bash
curl -sL -o data/nord-ovest.osm.pbf https://download.geofabrik.de/europe/italy/nord-ovest-latest.osm.pbf
curl -sL -o data/nord-ovest.poly    https://download.geofabrik.de/europe/italy/nord-ovest.poly
```

Tempi indicativi sul dominio nazionale (Apple M3, 8,6 GB di RAM): DEM 528 MB /
208 tile richiesti, 163 esistenti (i mancanti sono mare); `02_build_grid`
~30 s; `03_horizon` **~70 min**; `04_score` ~20 min; `06_export` ~2 min.
Rigenerare tutto da zero è quindi una cosa da un'ora e mezza, non da cinque
minuti come nella versione regionale.

Su una macchina con poca RAM conviene non fare altro nel frattempo:
`03_horizon` e `04_score` sono stati scritti apposta per stare sotto i ~4 GB
(vedi §4), ma il margine non è enorme.

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
- **Nessuna informazione di accessibilità**: la classifica dei punti
  panoramici è stata rimossa passando a scala nazionale (vedi §4). La mappa
  dice dove si vede, non se ci si arriva in auto o se c'è dove parcheggiare.
- **La vista d'insieme è a 600 m, i valori cliccabili a 250 m**, mentre
  l'analisi gira a 180 m. Il colore che si vede sulla mappa è quindi più
  grossolano del numero che compare cliccando: su creste strette i due
  possono discordare, e il numero è quello giusto.
- **Al sud il rosso ha un significato diverso**: non "montagna davanti" ma
  "Sole già tramontato". Il valore è corretto, ma cercare un punto panoramico
  migliore in Salento non serve a niente — non è un problema di orizzonte
  locale, e nessuna cima lo risolve.
- **In Sardegna il margine è di frazioni di grado.** Col Sole a 0,1° di
  altezza, la differenza fra 98% e 88% è mezzo grado di orizzonte, cioè una
  collina di 100 m a 10 km. A quelle altezze contano cose che il modello non
  ha: rifrazione anomala sul mare, foschia costiera, la quota esatta da cui
  si guarda. I valori sardi vanno letti come "ottimi ma fragili", non come
  una promessa.
- **Striature radiali sul mare.** A est di Corsica e Sardegna si vedono raggi
  sfrangiati: sono l'ombra reale di quei rilievi (una cella di mare guarda a
  WNW e vede le montagne còrse), resa a scalini dal passo di 1° in azimut e
  dai blocchi max-pool da 2160 m del campo lontano. È un artefatto di
  rendering su celle marine, non tocca i valori sulla terraferma.
- **Nessun fattore meteo** (vedi §10): un punto con visibilità geometrica del
  94% può essere completamente coperto da nuvole quella sera.

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
  in `horizon.tif`; serve solo un piccolo canvas SVG lato client che legga le
  26 bande — oggi i tasselli dati portano solo il valore all'istante migliore,
  non l'intero profilo, quindi servirebbe esportare anche `horizon.tif` (o un
  suo sottocampionamento) verso il web.
- **Classifica dei punti panoramici per regione.** Rimossa in questa
  iterazione perché una top-20 nazionale finirebbe tutta in Piemonte e Valle
  d'Aosta. Reintrodurla per macro-area renderebbe la mappa utile anche a chi
  guarda da sud; serve `italy-latest.osm.pbf` (~2 GB) e riattivare
  `05_access.py`, il cui codice è già lì.
- **Heatmap a tasselli anche per la visualizzazione**, non solo per i dati:
  oggi lo zoom sulle Alpi mostra un colore a 600 m sopra un dato a 250 m.
  Tasselli XYZ generati a 180 m eliminerebbero lo scarto, al costo di
  migliaia di file e ~200–300 MB nel deploy statico.
- **DEM ad alta risoluzione** (5 m, dove disponibile dai geoportali
  regionali) applicato *solo* a punti d'interesse specifici, per raffinare gli
  ultimi metri attorno alle creste dov'è più facile che la griglia a 180 m
  sbagli di qualche punto percentuale.

---

## 11. Fonti dati e licenze

| Dato | Fonte | Licenza |
|---|---|---|
| DEM | Copernicus DEM GLO-90, ESA / AWS Open Data | gratuita, attribuzione consigliata |
| Rete stradale | OpenStreetMap, estratto Geofabrik nord-ovest — **non usata dalla mappa nazionale**, vedi §4 | ODbL — attribuzione richiesta (presente nel footer della mappa) |
| Efemeridi | `astronomy-engine` (Don Cross, MIT) | MIT |
| Tile di base | OpenStreetMap standard tile server | uso per sviluppo; per produzione ad alto traffico servirebbe un provider dedicato (es. MapTiler, Stadia) per rispettare la tile usage policy di OSM |
| Geocoding (ricerca comune) | Nominatim, OpenStreetMap | uso per sviluppo/basso volume; per produzione ad alto traffico servirebbe un'istanza propria o un provider a pagamento, per rispettare la usage policy di Nominatim |
| Meteo (previsto) | Open-Meteo | CC BY 4.0, nessuna API key |

---

## 12. Deploy

Il sito è pubblicato da GitHub Pages tramite il workflow
`.github/workflows/deploy-pages.yml`. A ogni push su `master`, GitHub carica
direttamente `web/public/`, inclusi i tasselli dei dati. Non serve alcun
server applicativo o procedura manuale di deploy.

Il dominio `eclisse-12-08-2026.tongatron.org` è configurato come dominio
personalizzato di GitHub Pages. Per pubblicare una modifica basta eseguire il
normale flusso Git: commit e push su `master`.

**Quando cambiano gli asset dei dati, alzare `ASSET_V` in `index.html`.** I
file vengono richiesti con `?v=ASSET_V`, così browser e CDN non riutilizzano
una heatmap o tasselli della versione precedente.
