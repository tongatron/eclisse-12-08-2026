# Eclisse 12 agosto 2026

[![Sito online](https://img.shields.io/badge/sito-online-4ade80?style=flat-square)](https://eclisse-12-08-2026.tongatron.org/)
[![Deploy GitHub Pages](https://img.shields.io/badge/deploy-GitHub%20Pages-222?style=flat-square&logo=githubpages&logoColor=white)](https://eclisse-12-08-2026.tongatron.org/)
[![Codice: MIT](https://img.shields.io/badge/codice-MIT-2563eb?style=flat-square)](LICENSE)
[![Contenuti: CC BY 4.0](https://img.shields.io/badge/contenuti-CC%20BY%204.0-6b21a8?style=flat-square)](LICENSE-CONTENT.md)

Mappa interattiva per capire **dove e quanto** sarà visibile dall'Italia
l'eclisse solare parziale del 12 agosto 2026. Il calcolo considera sia la
geometria dell'eclisse sia l'orizzonte reale: montagne, colline e tramonto.

**Guarda la mappa:** [eclisse-12-08-2026.tongatron.org](https://eclisse-12-08-2026.tongatron.org/)

![Anteprima della mappa dell'eclisse solare del 12 agosto 2026 in Italia](docs/images/anteprima-mappa-eclissi.png)

*Dettaglio su Torino: il pannello mostra copertura visibile, orari locali,
quota, coordinate e la simulazione dell'eclisse nel punto selezionato.*

![Dettaglio della mappa su Torino con pannello dei dati dell'eclisse](docs/images/dettaglio-torino-pannello-eclissi.png)

## In breve

- Il punto migliore sulla terraferma è la costa nord-occidentale della
  Sardegna, fino al **98,8%** di oscuramento visibile.
- In gran parte del Sud il Sole tramonta prima del massimo dell'eclisse.
- Al Nord, dove il Sole è ancora sopra l'orizzonte, anche una cresta lontana
  può cambiare sensibilmente ciò che si vede.

La mappa mostra il risultato nazionale a colpo d'occhio. Facendo clic su un
punto si ottengono oscuramento, orario, altezza del Sole e quota locale.

## Come funziona

Il sito è completamente statico: i raster sono calcolati offline a partire
dal DEM Copernicus e pubblicati con GitHub Pages. Non raccoglie dati personali
né richiede un backend.

Per calcoli, struttura dei dati, pipeline, validazione e limiti noti, consulta
[la documentazione tecnica](TECHNICAL.md).

## Pubblicazione e aggiornamenti

Il sito è pubblicato automaticamente da GitHub Pages a ogni push su `master`.
La cartella `web/public/` contiene l'app e tutti i dati necessari anche per le
interazioni sulla mappa.

Per aggiornare i dati:

1. esegui la pipeline descritta in [TECHNICAL.md](TECHNICAL.md);
2. aggiorna `ASSET_V` in `web/public/index.html` quando cambiano gli asset;
3. fai commit e push su `master`.

## Licenza

Il [codice](LICENSE) è rilasciato con licenza **MIT**. Testi,
visualizzazioni e immagini originali sono rilasciati con licenza [Creative
Commons Attribuzione 4.0 Internazionale (CC BY 4.0)](LICENSE-CONTENT.md).
I dati e i servizi di terze parti mantengono le rispettive licenze, riportate
nella [documentazione tecnica](TECHNICAL.md#dati-e-attribuzioni).

## Crediti

Un progetto di [Giovanni Bindi / tongatron.org](https://tongatron.org).
