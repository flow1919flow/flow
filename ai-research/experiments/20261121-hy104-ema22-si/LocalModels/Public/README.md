# HY104 EMA22: sechs lineare Klassifikatoren und TabPFN v2

Alle sieben festen Modelle wurden tatsächlich gerechnet: je Kurskontext allein und derselbe Kontext plus SI, fünf unveränderte chronologische Blöcke. Das sind **70 Fits und 1’540 gespeicherte Prognosen**, jeweils **110 identische spätere Trades an 67 Tagen** pro Modellarm. Die 13 Daten-/Methodikprüfungen und die unabhängige Nachrechnung der gespeicherten Prognosen bestanden.

Die Quelle ist der korrekte native HY104-EMA22-Bestand: 348 Trades im 242-Sitzungen-Jahr, davon 159 nach Beginn des ES-SI-Archivs. Eingaben sind acht ausschließlich vor dem Entscheidungszeitpunkt berechnete Kurs-/Seitenmerkmale sowie optional vier SI-Merkmale. Ziel ist der tatsächliche native Strategieausgang nach Vereinheitlichung der Rundlaufgebühr auf 5,74 USD und weiteren 25 USD Kostenstress; positiv genau bei Nettoergebnis > 0. Die alte 347er-C28.03-Gruppe und eigenständige 15-Minuten-SI-Labels wurden nicht verwendet.

Zunächst mindestens 48 Trainingstrades, eine ganze Geschäftstagslücke, danach Blöcke mit 20 Geschäftstagen und wachsendem Training. Vor Testbeginn noch unbekannte Ausgänge werden entfernt. Medianersatz, explizite Fehlwertindikatoren und Standardisierung werden ausschließlich am Training bestimmt. SI ohne Archivtreffer bleibt ein Fall unbekannter Abdeckung. Es wurde keine tatsächliche SI-Abwesenheit unterstellt.

| Modell | Treffer Kurs | Treffer +SI | AUC innerhalb Blöcken Kurs | AUC innerhalb Blöcken +SI | LogLoss Kurs | LogLoss +SI |
|---|---:|---:|---:|---:|---:|---:|
| L1-Logistik | 60,00 % | 60,00 % | 0,5000 | 0,5000 | 0,682294 | 0,682225 |
| Elastic-Net-Logistik | 60,00 % | 60,00 % | 0,4675 | 0,4675 | 0,678295 | 0,678586 |
| RidgeClassifier | 54,55 % | 52,73 % | 0,4869 | 0,4979 | — | — |
| LinearSVC | 54,55 % | 53,64 % | 0,4855 | 0,5007 | — | — |
| SGDClassifier, log_loss | 50,91 % | 46,36 % | 0,5152 | 0,5270 | 5,698640 | 5,422460 |
| Perceptron | 43,64 % | 47,27 % | 0,4813 | 0,4952 | — | — |
| TabPFN v2, lokal CPU | 60,00 % | 59,09 % | 0,4993 | 0,5021 | 0,678102 | 0,681509 |

Die AUC innerhalb der Blöcke gewichtet die erkennbaren Positiv-Negativ-Paare je Block. Der letzte Block mit einem Testtrade hat keine definierte AUC und bleibt bei Trefferquote und Wahrscheinlichkeitsverlusten enthalten. Die ebenfalls gespeicherte Gesamt-AUC ist bei unkalibrierten Entscheidungswerten über verschiedene Fits nur beschreibend, weil sich deren Skalen zwischen Fits ändern können. RidgeClassifier, LinearSVC und Perceptron liefern rohe Entscheidungswerte; dafür wurden keine Wahrscheinlichkeiten, LogLoss- oder Brier-Werte erfunden.

Der allein aus dem jeweiligen Training berechnete Klassenprior erzielt 60,00 % Treffer und LogLoss 0,677535. Für TabPFN beträgt der Brier-Wert 0,242342 ohne SI und 0,244020 mit SI. Die festen Einstellungen wurden vor dem ersten Fit registriert; es gab keine Parameter-, Merkmal- oder Schwellenoptimierung und keine Testkalibrierung. TabPFN verwendete den SHA-gebundenen offiziellen v2-Checkpoint mit vier Schätzern auf CPU, jeder Testfall wurde einzeln vorhergesagt. Die extremen SGD-Wahrscheinlichkeiten und ihre hohen Verluste wurden unverändert dokumentiert.

Die Änderungen liefern hier keinen belastbaren zusätzlichen Nutzen durch SI. **Nur acht Testfälle haben einen archivierten SI-Treffer in den vorigen 15 Minuten, 26 in den vorigen 60 Minuten.** Diese geringe Überlappung und die unbekannte Feedabdeckung begrenzen die Aussagekraft; ein gemischter oder negativer Befund beweist keine Informationslosigkeit von SI. Das vielfach untersuchte historische Jahr bleibt Entwicklungsdaten. Es entstand weder ein neues Handelsgate noch ein Konto-/Auszahlungsreplay oder eine Änderung laufender Sims.

Maschinenlesbare Belege: [Vorabregistrierung](preregister.json), [Prüffälle](fixtures.json), [zusammengefasste Ergebnisse](results-combined.json), [Modellpaare als CSV](model-pairs-summary.csv), [Einzelmetriken sklearn](results-sklearn.json), [Einzelmetriken TabPFN](results-tabpfn.json), [unabhängige Abnahme](independent-acceptance.json). Rohdaten, Fall-IDs, Prognosezeilen, Koeffizienten und Vorverarbeitungszustände bleiben lokal unter `Private/`.
