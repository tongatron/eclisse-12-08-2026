# Documentazione tecnica

Questa pagina descrive come viene prodotto il dato della mappa. Per una
presentazione sintetica del progetto, consulta il [README](README.md).

## Obiettivo del calcolo

Per ogni cella dell'area italiana il progetto determina il massimo
oscuramento dell'eclisse che è **effettivamente visibile**. Il Sole conta solo
quando è sopra l'orizzonte locale, non soltanto sopra quello astronomico.

Il risultato combina quindi:

1. effemeridi locali dell'eclisse;
2. altezza e azimut del Sole nel tempo;
3. profilo dell'orizzonte nella direzione del Sole;
4. curvatura terrestre e rifrazione atmosferica.

Questo distingue due fenomeni che sulla mappa possono sembrare uguali:

- nel Sud e nel versante orientale il limite è spesso il tramonto;
- nelle aree alpine e prealpine il limite è spesso il rilievo.

## Risultati di riferimento

| Zona | Massimo visibile | Osservazione |
|---|---:|---|
| Sardegna nord-occidentale | 98,8% | Sole bassissimo sull'orizzonte |
| Piemonte nord-occidentale | 93,6% | la visibilità dipende dalle Alpi |
| Alto Adige | 90,9% | orizzonte occidentale determinante |
| Centro Italia | 81,5% | massimo vicino al tramonto |
| Salento | 18,3% | Sole già al tramonto |

Il massimo su terraferma è nell'area Porto Torres–Stintino (circa 40,88 N,
8,22 E). Sul mare, poco a ovest, la fascia di totalità raggiunge il 100% al
tramonto.

## Architettura

```text
pipeline/                  calcolo offline in Python
  01_download_dem.py       scarica il DEM Copernicus
  02_build_grid.py         mosaico e riproiezione
  03_horizon.py            raycast dell'orizzonte
  04_score.py              geometria dell'eclisse e punteggio
  05_access.py             analisi stradale sperimentale
  06_export.py             export per il browser

web/public/                sito statico pubblicato da GitHub Pages
  index.html               interfaccia MapLibre e lettura dei pixel
  affidabilita.html        versione, validazione e limiti del dato
  data/score.png           heatmap nazionale a 600 m
  data/meta.json           griglia, bounding box e legenda
  data/tiles/              dati di dettaglio a 250 m
  data/comuni.json         indice locale dei 7.894 comuni per la ricerca
  data/validation.json     esito e campioni dell'ultima validazione
```

All'avvio il browser carica solo `score.png`. I valori mostrati al clic
provengono dai tasselli corrispondenti, caricati su richiesta e mantenuti in
cache. I 84 file in `data/tiles/` sono versionati insieme al sito, così il
deploy GitHub Pages è autosufficiente.

## Dati e proiezione

L'area di output copre 35,4–47,15° N e 6,55–18,60° E. I calcoli raster
avvengono in una proiezione azimutale equidistante centrata a 42,0° N,
12,5° E, a 90 m di risoluzione; l'export web usa 600 m per la heatmap e 250 m
per i tasselli interrogabili.

Il DEM è Copernicus GLO-90. Le celle senza dato nel mosaico sono trattate come
mare a quota zero: non costituiscono ostacoli e consentono di calcolare anche
la visibilità sul mare.

## Orizzonte e correzioni geometriche

Il raycast non analizza l'intero orizzonte: durante l'evento il Sole utile
occupa una fascia ristretta a ovest-nord-ovest. Vengono quindi campionati gli
azimut di griglia 273–298° con passo di 1°, fino a 150 km.

Le correzioni principali sono:

- **curvatura e rifrazione:** raggio terrestre efficace pari a 7/6 del raggio
  terrestre;
- **convergenza dei meridiani:** conversione dell'azimut vero in azimut della
  proiezione per ogni cella;
- **effemeridi spazialmente variabili:** calcolo su una griglia di 16×16 nodi
  e interpolazione bilineare nel tempo e nello spazio.

Il limite dei 150 km è fisicamente sufficiente: oltre quella distanza un
ostacolo non può modificare l'osservabilità del Sole alla quota critica
dell'evento.

## Pipeline

La pipeline richiede Python 3.11+ e dipendenze geospaziali quali `rasterio`,
`numpy`, `pyproj`, `astronomy-engine`, `numba` e `osmnx` (quest'ultima solo
per l'analisi stradale sperimentale).

Esecuzione tipica:

```bash
python pipeline/01_download_dem.py
python pipeline/02_build_grid.py
python pipeline/03_horizon.py
python pipeline/04_score.py
python pipeline/06_export.py
python pipeline/validate.py
```

`05_access.py` non contribuisce alla mappa nazionale pubblicata. Serve a
classifiche sperimentali legate alla raggiungibilità stradale.

La pipeline produce grandi raster intermedi sotto `data/`; questi non sono
versionati. L'export finale in `web/public/` invece è parte del sito e viene
pubblicato da GitHub Pages.

## Validazione

`pipeline/validate.py` esegue controlli su:

- coerenza geometrica degli azimut e della convergenza dei meridiani;
- effetto della curvatura/rifrazione;
- coordinate e orari dell'eclisse;
- intervallo e coerenza delle bande raster esportate.

Al termine scrive `web/public/data/validation.json`, che alimenta la pagina
pubblica [Affidabilità del dato](web/public/affidabilita.html). Il report
registra data dei dati analizzati, data della verifica, parametri della griglia,
esito del confronto analitico Torino–Rocciamelone e i campioni territoriali.
Il comando termina con errore se il controllo analitico non supera la tolleranza.
Va eseguito dopo ogni rigenerazione dei dati e versionato insieme agli asset.

## Frontend e cache

`web/public/index.html` usa MapLibre GL per la mappa, un indice locale ISTAT
per la ricerca dei comuni e tile di base OpenStreetMap. La ricerca non invia il
testo digitato a servizi di geocoding esterni. `data/comuni.json` contiene
nome, provincia, eventuale denominazione bilingue e centro geometrico del
comune; è generato da `pipeline/build_comuni_index.py` a partire dai codici e
dai confini ISTAT.

Le risorse dati sono richieste con un parametro `?v=ASSET_V`: quando si
rigenerano raster, tasselli o indice dei comuni, incrementare quella costante
evita che il browser riusi dati non coerenti dalla cache.

Il service worker in `web/public/sw.js` consente l'uso offline delle risorse
già visitate.

## Pubblicazione

`.github/workflows/deploy-pages.yml` pubblica `web/public/` su GitHub Pages a
ogni push su `master`. Il dominio personalizzato
`eclisse-12-08-2026.tongatron.org` punta a GitHub Pages tramite un CNAME DNS
only verso `tongatron.github.io`.

## Limiti noti e sviluppi possibili

- La mappa non include il meteo: una buona visibilità geometrica non implica
  cielo sereno.
- Il DEM a 90 m e l'export a 250 m non descrivono ostacoli molto locali.
- Un valore alto di copertura visibile non certifica un punto di osservazione:
  restano da verificare accesso, proprietà, sicurezza e orizzonte reale.
- Mappe di base e geocoding pubblici sono adatti a traffico moderato; per un
  uso intenso serve un provider dedicato.
- Possibili evoluzioni: overlay meteo, profilo dell'orizzonte nel popup,
  classifiche regionali raggiungibili e DEM ad alta risoluzione in punti
  selezionati.

## Dati e attribuzioni

| Risorsa | Fonte | Licenza / note |
|---|---|---|
| Modello digitale del terreno | Copernicus DEM GLO-90, ESA / AWS Open Data | gratuito; attribuzione consigliata |
| Rete stradale | OpenStreetMap / Geofabrik | ODbL; non usata dalla mappa nazionale |
| Effemeridi | astronomy-engine, Don Cross | MIT |
| Tile di base | OpenStreetMap | rispettare la tile usage policy |
| Indice dei comuni | ISTAT, codici e confini delle unità amministrative | incorporato nel sito; codici aggiornati al 21 febbraio 2026, confini al 1 gennaio 2026 |

I marchi, le mappe di base, i dati e i servizi di terze parti restano soggetti
alle rispettive licenze e condizioni.
