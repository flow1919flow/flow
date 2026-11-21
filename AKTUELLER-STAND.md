# Nachtrag · SI1746 abgeschlossen und Modellwahl · 21. November 2026

Der Nutzer beauftragte explizit die vollständige Kursprüfung aller1746 RITHMIC-SI-Meldungen,Labels,Vergleichsfälle und den chronologischen TabPFN-Paarvergleich. Tatsächlich abgeschlossen:361 originalgebundene Quote-Parquetdateien (1.884.326.582Bytes),1635 gültige15min-Labels,111 mit dokumentiertem Ausschluss,1019 verbundene Episoden/936 gültige erste Ereignisse. Zwei feste TabPFN-v2-Arme mit je8Fits und644 gemeinsamen späteren Prognosen an71Tagen (23.07.–30.10.2026). Acht Designprüfungen,80 nach Markt/Zeit geschichtete physische Zukunftsabschneidungen,2968 native Preisdarstellungsprüfungen,Kontraktspezifikationen und unabhängige Metrik-/Fold-Abnahme bestanden.

**Kein belegter SI-Attribut-Vorteil.** Kurskontext:LogLoss0,801713/Treffer51,55%;zusätzliche6SI-Merkmale:0,801860/51,40%. Gepaarte Verbesserung−0,000147,95%-Fünftages-Blockintervall[−0,001925;+0,000966]. Trainingsprior52,48%Treffer. Der Test bewertet Attribute an Meldungszeitpunkten,keine garantierte SI-Abwesenheit. Nur45 vor den Labels gematchte Kontrollpaare,43 mit beidseitigen Labels;diese sind eine separate beschreibende Kontrolle,nicht die644Paartestfälle. Kein neues Gate,keine SQX-Auszahlungsrechnung und keine Änderung laufender Sims/Leaderboards. Das bereits untersuchte Mai–Oktober-Jahr ist Entwicklungsdaten,kein frischer OOS-Nachweis.

[Abschluss und Quellen](ai-research/experiments/20261121-si1746/README.md). Lokal:outputs/SI-TabPFN-Pool-20261121. MLflow04_ML_Forschung:9864ca90541745989eb4d4c4c0ab2340(Kurs),c804315311d541689f83ccc5e17aea82(+SI),beideFINISHED. Vorabplan vor Labels/Fits:Commit3ed9deeaf715391bebc22559e90f8d2ff7accac3. Ein erster Aufruf scheiterte vor dem Fit am fehlenden Arrow-Leser im Modell-Environment;geprüfter CSV-Transport mit exakter numerischer Parität und nullableInt64-Nanosekunden behob das ohne neue Fälle/Labels/Modelle. Fehlerbeleg bleibt erhalten.

Zusätzlich fragte der Nutzer nach DeepInfra-DREX/CLEF und präzisierte **nace-ai/drex-max-finance**. Die zunächst vorgeschlagenen DeepSeek/Qwen-Chatmodelle waren die falsche Familie und wurden nicht benutzt. Der tatsächliche Claude-Chat wurde erneut kontaktiert,zwei tatsächliche Antworten gelesen. Claude empfiehlt für fünf numerische Merkmale L2-Logit/TabPFNv2/flachesBoosting,für Netto-R Ridge;diese bisherigen Läufe liefern keinen robusten Vorteil. TabPFNRegressor bleibt ungetestet. Seine abschließende Empfehlung lautet,DREX/CLEF für diese Aufgabe zu streichen und prospektive Daten zu sammeln. Die geprüfte optionale API-Diagnose bleibt **vorbereitet,nicht ausgeführt**,0API-Aufrufe/0USD;kein Schlüssel wurde in das lokale Feld eingegeben. Keine API-Nutzung oder besseres Modell behaupten. [Vorbereitung und tatsächliche Claude-Einordnung](ai-research/experiments/20261121-decision-preparation/README.md). Die 10Offlineprüfungen sind keine echten Providerantworten. Alle Rohquotes,SI-Einzelzeilen/IDs,Kandidatenzeilen und Gewichte bleiben lokal.

---

# Nachtrag · SI und Merkmale · 21. November 2026

Drei tatsächliche neue Claude-Rückmeldungen sind im [Review mit Messbefund](ai-research/experiments/20261121-geometry-si/Review-und-Plan.md) dokumentiert. Alle229ES-SI-Meldungen sind lokal in Parquet und MLflow geladen (78Tage,165Überlappungsgruppen), noch kein SI-Modell. Der zusätzlich registrierte native Ein-Merkmal-Test über347Kandidaten ist vollständig: sechs Beobachter- und fünf physische Prefix-Jobs bestanden; Rangkorrelation0,107, bedingter Nullrang0,082. Die feste5%-Hürde wurde nicht erreicht; kein neues Gate und keine geänderten Auszahlungszahlen. Die Gelddateien des vorherigen Vergleichs sind bytegleich erhalten. Priorität ist jetzt ein geprüfter, eingefrorener SI-Datensatz mit Kurslabels/Kontrollen, gegebenenfalls aus den vorhandenen1746RITHMIC-Meldungen über vier Märkte. Die vollständigen inneren MR1-Kalibrierprognosen wurden nicht gespeichert; keine Testdaten zur nachträglichen Kalibrierung verwenden. Laufende Sims unverändert.

---

# Nachtrag · 21. November 2026 · vier neue Modellarme abgeschlossen

Der neueste Forschungsstand steht im [vollständigen Abschluss](ai-research/experiments/20261121/ABSCHLUSS.md).
ML1-Zufallskontrollen, fünf native Prefix-Schnitte, L2-Schwellenkontrolle,
Boosting, Ridge und TabPFN sind inzwischen abgeschlossen, einschließlich
24 nativer Gate-Jobs und des ursprünglichen Kontoreplays. Frühere Aussagen
unten wie „noch nicht trainiert“ oder „Kontrollen fehlen“ beschreiben den
damaligen Stand. ML2–ML7 bleiben weiterhin offen. Laufende Sims und die
produktiven Leaderboards wurden durch diese Forschung nicht verändert.

| Funded-Modell | Normal Ø | Normal Median | Tickstress Ø | Tickstress Median |
|---|---:|---:|---:|---:|
| Basis · HY104-EMA22 → C28.03 | 8,424.89 USD | 9,899.36 USD | 6,860.65 USD | 7,142.94 USD |
| Logistik · neue Schwellenregel | 7,153.55 USD | 7,131.53 USD | 5,516.02 USD | 6,119.19 USD |
| Gradient Boosting · flach | 7,059.14 USD | 7,329.98 USD | 5,840.50 USD | 5,986.81 USD |
| Ridge · erwartetes Netto-R | 7,830.00 USD | 8,286.26 USD | 6,449.53 USD | 6,819.31 USD |
| TabPFN v2 | 8,325.73 USD | 9,723.52 USD | 6,959.86 USD | 7,794.06 USD |

Diese historischen Endbargelder sind keine garantierten Gewinne und keine
frische OOS-Bestätigung. Das letzte Windows-Betriebszeugnis unten bleibt
zeitlich begrenzt; heute wurde kein neuer Handelsbetrieb geprüft.

---

# Arbeitsstand und Übergabe · 20. November, Nachtrag 21. November 2026

Diese Datei ist der Einstieg für einen neuen Codex-Chat. Sie trennt beobachteten Betrieb, historische Forschung und offene Aufgaben. Zugangsdaten, Kontonummern, Remote-ID und lizenzierte Rohdaten werden nicht veröffentlicht.

## Zuerst lesen

1. Diesen Arbeitsstand und [die Arbeitsweise mit RustDesk und Claude](methodik/Arbeitsweise-RustDesk-Claude.md).
2. [ML-Forschung](ai-research/README.md), [tatsächliche Ergebnisse](ai-research/evidence/ml1-results.json) und [Modellregister](ai-research/model-register.json).
3. Den [installierten NinjaTrader-Stand V8r4](releases/2026-11-19-v8r4/README.md).
4. [Aktuellen Computersteuerungsbefund](methodik/Steuerungsdiagnose-2026-11-20.md).
5. [Gespeicherte aktuelle Leaderboard-Aggregate](leaderboards/2026-11-20/README.md), [Kalendercode und Abnahme](news-calendar/README.md) sowie [offene konkrete Fragen an Claude](ai-research/docs/Offene-Fragen-an-Claude.md).

## Ziel und Bewertungsmaßstab

Ziel ist das Endbargeld aus einem festen Challenge-Kaufbudget von 1’000 USD nach Gebühren, Kontoverlusten, Ersatzkäufen und Auszahlungen. Nicht verbrauchtes Startbudget gehört zum Endbargeld; Gewinn ist Endbargeld minus Startbudget. Vergleiche müssen denselben Zeitraum, Gebühren, Providerregeln, Positionsgrößen und Ausführungsstress verwenden. Eine Bestehensquote, Trefferquote oder AUC allein beantwortet die wirtschaftliche Frage nicht.

Der aktuelle gemeinsame Jahresvergleich umfasst **24.11.2025–30.10.2026, 242 Sitzungen**, einschließlich separat nachgewiesenem Warmlauf. Ältere Auswertungen verwendeten 245 Sitzungen ab 19.11.2025. Der Budgetvergleich verwendet 143 überlappende Startfenster mit je 100 Sitzungen. Diese Fenster sind keine unabhängigen Experimente. Das Jahr wurde schon für viele Strategien ausgewählt; es ist kein frischer Out-of-Sample-Nachweis.

## NinjaTrader und Windows

Installiert und zuletzt geprüft wurde AccountReplay V8r4. Vier lokale Sim-Instanzen sind vorgesehen:

Der zuletzt gespeicherte Windows-Workspace heißt **`rapid eod - eval und funded sim`**. Trotz des historischen Namens enthält er vier Charts, ES und NQ. Gesicherter Speichernachweis: 19.11.2026 21:15:22 Europe/Vaduz; siehe die [native NQ-Run2-Abnahme](releases/2026-11-19-v8r4/proofs/nq-run2-native-acceptance.json). Ein späterer Speichervorgang wird hier nicht behauptet.

| Anbieterprofil | Markt | Phase | Strategie |
|---|---|---|---|
| MFF Rapid EOD 50k | ES | Eval-Simulation | HY104, EMA20 im dokumentierten installierten Stand |
| MFF Rapid EOD 50k | ES | Funded-Simulation | 104-C28.03, zusätzliches Eröffnungsspannenziel |
| TradeDay Fast Pass 50k | NQ | Eval-Simulation | HY3, EMA20 |
| TradeDay Fast Pass 50k | NQ | Funded-Simulation | HY3, SMA5/10-Fassung |

**Letzte vollständige Control-Center-Sichtprüfung: 20.11.2026, 21:48:09 Europe/Vaduz:** alle vier Enabled, Sync True und flat. Nach Wiederherstellung der Computersteuerung wurden um 23:46 Europe/Vaduz die vier Charts erneut tatsächlich gesehen; alle vier Karten standen außerhalb der regulären Sitzung. Das ersetzt keine erneute Prüfung der Enabled-/Sync-/Positionsspalten im Control Center. Ein neuer Chat muss den tatsächlichen aktuellen Zustand neu prüfen.

Der Forschungs-/Kontoreplay für die führende ES-Mischung verwendet EMA22 in der Eval. Das ist von der dokumentierten EMA20-Sim-Instanz zu unterscheiden. Nicht eigenmächtig eine Variante im Betrieb ersetzen. Zunächst Quellen, Instanzparameter und Nutzerauftrag abgleichen.

Der installierte Kontocode enthält EOD-Trailing, Gebühren und persistente Zustände über Neustarts. Eine Sim-Abschaltung an der Anbietergrenze bildet ein gescheitertes Konto ab; sie ist keine vorbeugende Rettungsgarantie. Neue Sim-Käufe/Resets erfolgen nicht automatisch.

## News-Kalender

Der kostenlose FRED-/Fed-Updater v2 wurde auf Windows installiert. Die Aufgabe **HY Free News Calendar** erneuert alle vier Stunden und beim Anmelden des Windows-Benutzers. Der Benutzer muss angemeldet bleiben. Der Schlüssel ist nur dort benutzergebunden DPAPI-verschlüsselt gespeichert.

Erster erfolgreicher Abruf: 20.11.2026 20:37:48 UTC. Der anschließend tatsächlich über die Aufgabenplanung gestartete Abruf erzeugte eine zweite geprüfte Generation um 20:42:44 UTC. Deren Abdeckung reicht bis 31.12.2026; die Frische gilt trotzdem nur 24 Stunden, bis 21.11.2026 20:42:44 UTC. Spätere Generationen müssen am tatsächlichen Windows-Manifest geprüft werden. Ein künftiger Timerlauf oder echter Neustart wurde damit nicht physisch getestet.

Quellen: FRED Release 50/NFP und 10/CPI sowie offizielle Fed-Kalender. FRED liefert Datentage, keine Ereignisuhrzeiten; CPI/NFP werden nach geprüfter Definition auf 08:30 America/New_York mit DST abgebildet. Außerordentliche Zeitänderungen und historische Terminrevisionen sind damit nicht vollständig abgedeckt. BLS-HTTP403 war bekannt; keine Schutzumgehung.

Eingefrorene Sperrprofile: MFF-Eval ohne News-Sperre; MFF-Funded und TradeDay beide Phasen benannte T1-Ereignisse, zwei Minuten davor/danach mit zehn Sekunden Dispatch-Vorlauf. ES-Funded enthält zusätzlich die vorsichtige FOMC-Pressekonferenz-Sperre. Widersprüchlicher breiterer MFF-Wortlaut bleibt offen. Keine pauschale Ganztagssperre ergänzen.

Ein Trading-Economics-Kalenderangebot wurde mit Freigabe angefragt; Preisantwort steht aus. Kein Abo wurde gebucht.

**Neuer offener Reviewpunkt:** Der Updater verlangt den laufenden und folgenden Fed-Monat. Eine noch unveröffentlichte Folgemonatsseite könnte die Erneuerung blockieren. Die Quelltextabhängigkeit wurde bestätigt; Monatswechseltest und sichere Korrektur sind noch offen. Die aktuelle Windows-Fassung wurde nicht verändert. Details im [Claude-Review](ai-research/docs/Claude-Review-20261121.md).

## Micros

Nullreserve- und feste 11–15-MNQ-Versuche sind abgeschlossen. 3’146 Kaufketten wurden auf Bargeldidentität geprüft. Kein robuster neuer Gesamtsieger:

- 1 NQ: Ø normal 4’480,03 USD, Stress 4’022,05 USD; Stress-Median 4’204 USD.
- 10 MNQ: Stress-Ø 4’053,86 USD, derselbe Stress-Median; normal schlechter.
- 15 MNQ: Stress-Ø 4’126,27 USD, Stress-Median 4’105 USD; normal Ø 3’944,15 USD.

Dies sind vollständige Kontoreplays auf bereits verifizierten SQX-Signalen und Mengen-Fillpfaden, keine neu gestarteten nativen Strategievarianten. Die Nullreserve entfernt nur die 100-USD-Reservierung; die risikobasierte Stückzahl verlangt weiterhin, dass geschätzter Stop und Kosten in den Restpuffer passen. Feste Mini-Größe hat diese Eintrittsbedingung nicht.

## Erster Machine-Learning-Versuch

**ML1 ist tatsächlich trainiert und vollständig bis zum Kontovergleich gerechnet.** Modell: StandardScaler und L2-logistische Regression, festes C=0,1, fünf kausale Merkmale. Classification schätzt den positiven Nettoausgang; Ridge-Regression für erwartete Ergebnisgröße ist ein separater Folgeversuch.

347 eindeutige ES-Setupkandidaten aus Funded C28.03, keine NQ-Kandidaten und keine Vervielfachung durch Micro-/Mini-Kopien oder Kaufketten. Neun chronologische Prüfblöcke, zunächst 80 Trainingssitzungen, eine Sitzung Abstand, dann 20 Prüfungssitzungen. Überlappende noch unbekannte Outcomes werden entfernt. 230 spätere Kandidaten erhielten Prognosen, 35 wurden verworfen. Die vorherige Trainingsphase handelt als unveränderte Basis weiter.

Die fünf Merkmale sind Stoprisiko aus der Entscheidungsquote, Bollinger-/Keltner-Breitenverhältnis, gerichtete abgeschlossene EMA-Steigung/ATR, abgeschlossenes relatives Volumen und Chicago-Handelsminute. Kein späterer Fill, Exit, MFE oder Auszahlungsergebnis ist Eingabe.

Native SQX-Beobachtung: sechs Kontraktabschnitte mit identischen Basis-Trades, Kandidaten und Quotes sowie identischen Replikaten. Danach sechs echte neue native SQX-Läufe mit dem Einstiegsgate. Anschließend ursprünglicher Quote-Equity-Leser und unveränderte Anbieter-Kontoengine; die Basis wurde auf allen gemeinsamen Kennzahlen exakt reproduziert. Native Engine **144.2953**; 145 kann Berichte anzeigen, wurde hier nicht als Rechenkern ausgegeben.

| Endbargeld aus 1’000 USD | Basis Ø | ML1 Ø | Basis Median | ML1 Median |
|---|---:|---:|---:|---:|
| Normal | 8’424,89 | 6’940,33 | 9’899,36 | 6’966,99 |
| Ein Tick schlechter je Seite | 6’860,65 | 5’889,35 | 7’142,94 | 5’964,30 |

AUC 0,50017; keine erkennbare Trennleistung. Das erste Modell verbessert die Strategie nicht. Keine Übernahme in NinjaTrader oder das Leaderboard. Nachtrag21.11.: Zufallskontrollen und fünf native Prefix-Schnitte sowie die neue Claude-Planprüfung sind erledigt; erweiterte Randfallprüfungen und frische Forward-Daten bleiben offen. Nicht als fertige ML-Einsatzfreigabe darstellen.

Lokal zeigt MLflow den Lauf unter `http://127.0.0.1:5055/#/experiments/4/runs/ebaea0eb92bf4c1993ecc7c953655145`. Startdatei: `outputs/Research-Tools-20261119/MLflow-starten.command`, nur 127.0.0.1. Der Server muss nach einem App-Neustart gegebenenfalls neu gestartet werden. Eine im Browser angezeigte Dokumentationsseite von scikit-learn ist keine Trainingsoberfläche.

## Forschung und Professorentermin

Der Nutzer hat nächste Woche einen Termin bei Prof. Pavel Laskov. Die vorliegende Stelle betrifft Sicherheit und Zuverlässigkeit von KI-Agenten in Finanzdienstleistungen. Vorhanden ist die Stellenbeschreibung, keine persönliche Bewerbung/CV zur Veröffentlichung.

Die breite Idee „ein KI-Agent setzt Paper korrekt um und erkennt eigene Fehler“ ist bereits deutlich untersucht. QuantCode-Eval, RePro, SA-Bench, RECLAIM und PaperBenchX sind enge Vorarbeiten. Deshalb keinen Neuheits- oder Publikationsanspruch behaupten. Details und Abgrenzung stehen in [den Forschungsunterlagen](ai-research/docs/Vorarbeiten-und-Abgrenzung.md). Der Nutzer möchte kein generisches Paper über kaputte/manipulierte Eingaben; gefragt ist eine belastbare, eng abgegrenzte Studie zur Zuverlässigkeit von Research-Agenten. Das ist von ML1 getrennt.

## Offene Aufgaben in Reihenfolge

1. Computersteuerung wurde nach erneutem App-Neustart tatsächlich wiederhergestellt; RustDesk und der echte Claude-Chat sind wieder erreichbar. Keine Einstellungsänderung oder bestimmte Fehlerursache nachgewiesen.
2. Die gesammelten Fragen und der SI-Nachtrag wurden im echten Claude-Chat gesendet; die fertige Antwort wurde am 21.11. gelesen und [getrennt protokolliert](ai-research/docs/Claude-Review-20261121.md). Code-/Berichtsreview, keine unabhängige neue ML-Kontorechnung. Interne Codex-Rechercheagenten sind nicht Claude.
3. Zuerst Kontrollen für ML1 und native Feature-Prefix-Prüfung vorbereiten. Danach eine feste flache Boosting-Gegenprobe und den getrennten MR1-Regressionsversuch, jeweils gleiche Daten-/Kontobasis. TabPFN nur nach konkreter Versions-/Lizenzprüfung. Keine breite Suche als Bestätigung ausgeben. SI-Zusatzinformation und explorative Regimefragen sind als [getrennter Entwurf](ai-research/docs/SI-Naechster-Schritt.md) gespeichert, noch nicht trainiert.
4. Vor einem Paperprojekt die engere Forschungsfrage und Abgrenzung mit Laskov besprechen. Ein sauberer Nullbefund ist kein Fehler und kein Profitversprechen.

Der Nutzer bestätigt, dass **Settings → Computer use → Control → Any App eingeschaltet** ist. Nach dem weiteren App-Neustart funktionieren die Werkzeuge wieder. NinjaTrader/Windows wurden dafür nicht neu gestartet oder verändert. Ein neuer Chat soll den Werkzeugzugang zunächst prüfen, bevor er auf alte Fehlerzustände reagiert.

## Lokale Artefakte wiederfinden

Projekt relativ zu `HY_WORKSPACE`: `Documents/Codex/2026-11-07/de`. In einer lokalen Sitzung ist das Arbeitsverzeichnis bereits der Projektstamm. Betrieb und Forschung haben getrennte Quellen:

| Zweck | Relativer Pfad |
|---|---|
| Neustart-Checkpoint | `outputs/AI-Forschung-20261120/RESUME.txt` |
| ML1, native SQX-Läufe, Entscheidungen, Kontoergebnisse | `outputs/AI-Forschung-20261120/` |
| Ursprüngliche Micro-/Mini-Vergleiche | `outputs/Micro-RiskSize-20261120/` |
| Neue Micro-Nachtests | `outputs/Micro-ZeroReserve-20261120/` |
| Kalendercode | `work/tools/news_calendar/` |
| Kalender-Windows-Abnahme | `outputs/HY-NewsCalendar-Auto-20261120/FreeFeed/` |
| Native installierte NT-Abnahme | `outputs/HY18b-NinjaTrader/AccountReplay-V8-20261119/` |
| Lokale Leaderboard-App | `outputs/HY-Forschung/` — eigene AGENTS.md beachten |
| Aktive Boardrevision | `history-micro-20261120-7460a2f26d22` |
| Neue Literaturprüfung | `research_notes/KI Agenten für Finanzforschung/` |

Die älteren öffentlichen Leaderboard-Dateien sind als Snapshots vom 17. November gekennzeichnet. Der neue Ordner `leaderboards/2026-11-20/` enthält die Aggregate der tatsächlich aktiven Revision einschließlich ihrer Herkunft und die getrennten Micro-Nachtests. Die Dateien direkt unter `app/static/` können alte 245-Sitzungs-Werte enthalten: Für aktuelle Exporte unbedingt `board-revision.json` lesen, dessen `base` auflösen und die einzelnen Datei-Hashes prüfen. ML1 verändert die Leaderboard-Zahlen nicht. Eine Hashbindung belegt den Dateistand, keine neue wirtschaftliche Validierung.

## Starttext für einen neuen Chat

> Arbeite im vorhandenen lokalen Projekt weiter. Lies im GitHub-Repo `flow1919flow/flow` zuerst `AKTUELLER-STAND.md`, die Arbeitsweise und den Steuerungsbefund. Lies lokal `outputs/AI-Forschung-20261120/RESUME.txt` und prüfe neuere Artefakte. Computerzugriff funktionierte nach dem letzten Neustart wieder; prüfe ihn und RustDesk/NinjaTrader zunächst nur lesend. Keine Testorders, keine Konto-Resets, keine Handelslogikänderung. Die gesammelten Fragen wurden an den bestehenden echten Claude-Chat gesendet; lies dessen neue Antwort, bevor du erneut sendest. ML1 ist ein abgeschlossener negativer Entwicklungsbefund; vier neue Klassifikations-/Regressionsarme sind abgeschlossen; der Abschluss vom21.11. ist maßgeblich, ML2–ML7 bleiben offen. Prüfe den aktuellen Stand, bevor du frühere Angaben übernimmst.
