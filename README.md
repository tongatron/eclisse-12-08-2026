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

## Funzionalità

- **Mappa nazionale interattiva** con la copertura massima realmente visibile,
  calcolata considerando orografia, curvatura terrestre e rifrazione.
- **Analisi puntuale** con percentuale di oscuramento, orari locali, quota,
  coordinate e collegamento condivisibile.
- **Simulazione nel tempo** dell'eclisse nel punto selezionato, con distinzione
  fra Sole visibile, tramonto e orizzonte ostruito dai rilievi.
- **Ricerca di tutti i comuni italiani**, locale e istantanea: l'indice ISTAT
  include province e denominazioni bilingui, senza inviare ciò che si digita a
  servizi di geocoding esterni.
- **Geolocalizzazione su richiesta**, condivisibile solo se l'utente lo sceglie.
- **Esperienza mobile e PWA**, con pannello richiudibile per lasciare la mappa
  a tutto schermo.
- **Embed per articoli**, con mappa interattiva, risultato al clic e
  simulazione compatta dell’eclisse, adattata alla larghezza di una colonna
  editoriale.
- **Affidabilità verificabile**, con data dei dati, report della validazione,
  campioni territoriali e limiti d'uso pubblicati nella
  [pagina dedicata](https://eclisse-12-08-2026.tongatron.org/affidabilita.html).

## Come funziona

Il sito è completamente statico: i raster sono calcolati offline a partire
dal DEM Copernicus e pubblicati con GitHub Pages. Non raccoglie dati personali
né richiede un backend. La ricerca dei comuni usa un indice ISTAT incluso nel
sito: ciò che si digita non viene inviato a servizi di geocoding esterni.

Per calcoli, struttura dei dati, validazione e limiti noti, consulta la
[documentazione tecnica](TECHNICAL.md). Per installare, eseguire o rigenerare
gli asset, consulta la [guida della pipeline](pipeline/README.md).

## Incorporare la mappa in un articolo

La versione incorporabile è disponibile a questo URL:

`https://eclisse-12-08-2026.tongatron.org/?embed=1`

In WordPress, incolla il seguente codice in un blocco **HTML personalizzato**:

```html
<iframe src="https://eclisse-12-08-2026.tongatron.org/?embed=1"
  width="100%" height="540" frameborder="0" loading="lazy"
  title="Mappa della visibilità dell'eclisse solare"
  allow="geolocation"></iframe>
```

L’embed privilegia la mappa: facendo clic su un punto, il lettore vede il
valore calcolato e la simulazione dell’eclisse. Il pannello della simulazione
può essere chiuso e, se coprirebbe il risultato selezionato, viene spostato
automaticamente dall’altro lato della mappa. Il pulsante **Apri la mappa**
porta alla versione completa, con ricerca dei comuni e dettagli aggiuntivi.

Per verificare l’integrazione in una colonna editoriale, apri la
[pagina di test](https://eclisse-12-08-2026.tongatron.org/embed-test.html).

## Pubblicazione e aggiornamenti

Il sito è pubblicato automaticamente da GitHub Pages a ogni push su `master`.
La cartella `web/public/` contiene l'app e tutti i dati necessari anche per le
interazioni sulla mappa.

Per aggiornare i dati:

1. esegui la [pipeline di elaborazione](pipeline/README.md);
2. aggiorna l'indice dei comuni se ISTAT ha pubblicato una nuova versione;
3. aggiorna `ASSET_V` in `web/public/index.html` quando cambiano gli asset;
4. fai commit e push su `master`.

## Licenza

Il [codice](LICENSE) è rilasciato con licenza **MIT**. Testi,
visualizzazioni e immagini originali sono rilasciati con licenza [Creative
Commons Attribuzione 4.0 Internazionale (CC BY 4.0)](LICENSE-CONTENT.md).
I dati e i servizi di terze parti mantengono le rispettive licenze, riportate
nella [documentazione tecnica](TECHNICAL.md#dati-e-attribuzioni).

## Crediti

Un progetto di [Giovanni Bindi / tongatron.org](https://tongatron.org).
