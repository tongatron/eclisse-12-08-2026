# Pipeline di elaborazione

Questa cartella contiene il calcolo offline che produce i raster pubblicati dal sito. Per ogni cella dell'area italiana determina il massimo oscuramento dell'eclisse solare parziale del 12 agosto 2026 **effettivamente visibile**: il Sole deve essere sopra l'orizzonte astronomico e quello modellato dal terreno.

Per il metodo, le assunzioni fisiche e i limiti del dato, consulta anche la [documentazione tecnica](../TECHNICAL.md).

## Prerequisiti

È richiesto Python 3.11 o successivo, spazio disco per i tile del DEM e una connessione Internet per il primo stadio. Dalla radice del repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install numpy rasterio pyproj astronomy-engine scipy osmium shapely
```

`rasterio` include dipendenze geospaziali native; se l'installazione da wheel non fosse disponibile sulla piattaforma in uso, installare prima GDAL con il gestore di pacchetti del sistema.

I dati intermedi sono scritti in `data/`, cartella ignorata da Git. I risultati web sono in `web/public/data/` e vanno versionati insieme al sito.

## Esecuzione completa

Tutti i comandi vanno eseguiti dalla radice del repository.

```bash
python pipeline/01_download_dem.py
python pipeline/02_build_grid.py
python pipeline/03_horizon.py
python pipeline/04_score.py
python pipeline/06_export.py
python pipeline/validate.py
```

Lo stadio `05_access.py` è opzionale e sperimentale: non alimenta la mappa pubblica.

| Stadio | Scopo | Input principale | Output principale |
|---|---|---|---|
| `01_download_dem.py` | Scarica il DEM Copernicus GLO-90 | bucket Copernicus | `data/dem_tiles/*.tif` |
| `02_build_grid.py` | Mosaica e riproietta il DEM | tile DEM | `data/derived/dem_aeqd.tif` |
| `03_horizon.py` | Calcola il profilo dell'orizzonte | DEM riproiettato | `horizon.tif`, `obs.tif` |
| `04_score.py` | Combina effemeridi e orizzonte locale | orizzonte e DEM | `score.tif` |
| `05_access.py` *(opzionale)* | Stima la distanza dalla strada percorribile più vicina | `score.tif`, estratto OSM | `access.tif` |
| `06_export.py` | Prepara immagini e tasselli per il browser | `score.tif`, `obs.tif` | `web/public/data/` |
| `validate.py` | Esegue controlli di coerenza | raster derivati | solo output a console |

## Dettaglio degli stadi

### 1. Scaricare il DEM

`01_download_dem.py` recupera in parallelo i tile Copernicus DEM GLO-90 per la finestra geografica definita in `config.py`. I tile già presenti e non vuoti vengono riutilizzati; un `404` per un tile oceanico è previsto e viene trattato come mare, non come errore. Se il comando termina con errori di rete, rieseguirlo: scaricherà solo ciò che manca.

### 2. Costruire la griglia di lavoro

`02_build_grid.py` unisce i tile disponibili, assegna quota zero alle celle senza dato (mare) e riproietta il risultato nella proiezione azimutale equidistante nazionale, a 90 m. Il file prodotto, `dem_aeqd.tif`, è la base per gli stadi successivi.

### 3. Calcolare l'orizzonte

`03_horizon.py` effettua un raycast per gli azimut di griglia 273–298°, direzioni in cui il Sole è utile durante l'evento. Considera curvatura terrestre e rifrazione con raggio terrestre efficace pari a 7/6 di quello reale. Per limitare memoria e tempo usa una piramide del DEM con max-pooling, mantenendo nel lontano campo la cima più alta.

L'esecuzione normale usa `--stride 2`, quindi produce celle a 180 m. Per una misura rapida delle prestazioni senza scrivere file:

```bash
python pipeline/03_horizon.py --bench
```

I file prodotti sono `data/derived/horizon.tif` (26 bande `int16`, una per azimut, in centesimi di grado) e `data/derived/obs.tif` (quota dell'osservatore per ogni cella).

### 4. Attribuire il punteggio di visibilità

`04_score.py` campiona l'evento ogni 20 secondi, dalle 19:25 alle 20:55 CEST. Le circostanze dell'eclisse sono calcolate su una griglia 16×16 e interpolate per l'intera area. Per ciascuna cella il Sole è visibile soltanto quando la sua altezza apparente supera sia zero sia l'orizzonte interpolato nella sua direzione.

Il GeoTIFF `data/derived/score.tif` contiene quattro bande `float32`:

1. `obsc_vis`: massimo oscuramento effettivamente visibile, fra 0 e 1;
2. `obsc_theo`: massimo oscuramento teorico con orizzonte piatto;
3. `t_best_min_after_1900`: minuti dopo le 19:00 CEST dell'istante migliore;
4. `hor_used_deg`: angolo dell'orizzonte usato nell'istante migliore.

### 5. Analizzare l'accessibilità (opzionale)

`05_access.py` non è necessario per pubblicare la mappa. Richiede `data/nord-ovest.osm.pbf` e il corrispondente `data/nord-ovest.poly`, ottenuti da Geofabrik. Rasterizza solo le strade percorribili con un veicolo e calcola la distanza euclidea dalla strada più vicina. Fuori dalla copertura dell'estratto OSM il valore è `NaN`, non una distanza grande.

```bash
python pipeline/05_access.py
```

### 6. Esportare gli asset web

`06_export.py` converte i raster nella proiezione Web Mercator usata da MapLibre e genera:

- `web/public/data/score.png`: heatmap nazionale a 600 m, caricata all'avvio;
- `web/public/data/tiles/`: tasselli a 250 m per valori e quota al clic;
- `web/public/data/meta.json`: bounding box, risoluzione e schema di codifica.

L'export elimina e ricrea i PNG presenti in `web/public/data/tiles/`. Prima di eseguirlo, assicurarsi di non avere modifiche manuali da conservare in quella cartella.

## Validazione e pubblicazione

Dopo ogni rigenerazione eseguire:

```bash
python pipeline/validate.py
```

Il comando non scrive file: confronta il raster dell'orizzonte con un calcolo analitico indipendente e stampa una tabella di località di controllo.

Prima del commit, verificare gli asset generati e incrementare `ASSET_V` in `web/public/index.html`. Il parametro di versione evita che browser e service worker combinino HTML nuovo con raster precedenti in cache. Infine versionare gli asset in `web/public/data/` e pubblicare su `master`; GitHub Pages serve quella cartella come sito statico.

## Configurazione

`config.py` è l'unico punto da modificare per variare data dell'evento, finestra temporale, area geografica, proiezione, risoluzione e azimut analizzati. Cambiare questi parametri richiede di rieseguire la pipeline dall'inizio, a partire dal download del DEM se il nuovo dominio non è già coperto dai tile locali.
