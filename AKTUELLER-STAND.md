# Arbeitsstand und Übergabe · 20. November 2026

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

**Letzte tatsächliche Sichtprüfung: 20.11.2026, 21:48:09 Europe/Vaduz:** alle vier Enabled, Sync True und flat. Seit Verlust der Computerwerkzeuge gab es keine neue Bildschirmprüfung. Ein neuer Chat darf daraus keinen aktuellen Betriebszustand behaupten.

Der Forschungs-/Kontoreplay für die führende ES-Mischung verwendet EMA22 in der Eval. Das ist von der dokumentierten EMA20-Sim-Instanz zu unterscheiden. Nicht eigenmächtig eine Variante im Betrieb ersetzen. Zunächst Quellen, Instanzparameter und Nutzerauftrag abgleichen.

Der installierte Kontocode enthält EOD-Trailing, Gebühren und persistente Zustände über Neustarts. Eine Sim-Abschaltung an der Anbietergrenze bildet ein gescheitertes Konto ab; sie ist keine vorbeugende Rettungsgarantie. Neue Sim-Käufe/Resets erfolgen nicht automatisch.

## News-Kalender

Der kostenlose FRED-/Fed-Updater v2 wurde auf Windows installiert. Die Aufgabe **HY Free News Calendar** erneuert alle vier Stunden und beim Anmelden des Windows-Benutzers. Der Benutzer muss angemeldet bleiben. Der Schlüssel ist nur dort benutzergebunden DPAPI-verschlüsselt gespeichert.

Erster erfolgreicher Abruf: 20.11.2026 20:37:48 UTC. Der anschließend tatsächlich über die Aufgabenplanung gestartete Abruf erzeugte eine zweite geprüfte Generation um 20:42:44 UTC. Deren Abdeckung reicht bis 31.12.2026; die Frische gilt trotzdem nur 24 Stunden, bis 21.11.2026 20:42:44 UTC. Spätere Generationen müssen am tatsächlichen Windows-Manifest geprüft werden. Ein künftiger Timerlauf oder echter Neustart wurde damit nicht physisch getestet.

Quellen: FRED Release 50/NFP und 10/CPI sowie offizielle Fed-Kalender. FRED liefert Datentage, keine Ereignisuhrzeiten; CPI/NFP werden nach geprüfter Definition auf 08:30 America/New_York mit DST abgebildet. Außerordentliche Zeitänderungen und historische Terminrevisionen sind damit nicht vollständig abgedeckt. BLS-HTTP403 war bekannt; keine Schutzumgehung.

Eingefrorene Sperrprofile: MFF-Eval ohne News-Sperre; MFF-Funded und TradeDay beide Phasen benannte T1-Ereignisse, zwei Minuten davor/danach mit zehn Sekunden Dispatch-Vorlauf. ES-Funded enthält zusätzlich die vorsichtige FOMC-Pressekonferenz-Sperre. Widersprüchlicher breiterer MFF-Wortlaut bleibt offen. Keine pauschale Ganztagssperre ergänzen.

Ein Trading-Economics-Kalenderangebot wurde mit Freigabe angefragt; Preisantwort steht aus. Kein Abo wurde gebucht.

## Micros

Nullreserve- und feste 11–15-MNQ-Versuche sind abgeschlossen. 3’146 Kaufketten wurden auf Bargeldidentität geprüft. Kein robuster neuer Gesamtsieger:

- 1 NQ: Ø normal 4’480,03 USD, Stress 4’022,05 USD; Stress-Median 4’204 USD.
- 10 MNQ: Stress-Ø 4’053,86 USD, derselbe Stress-Median; normal schlechter.
- 15 MNQ: Stress-Ø 4’126,27 USD, Stress-Median 4’105 USD; normal Ø 3’944,15 USD.

Dies sind vollständige Kontoreplays auf bereits verifizierten SQX-Signalen und Mengen-Fillpfaden, keine neu gestarteten nativen Strategievarianten. Die Nullreserve entfernt nur die 100-USD-Reservierung; die risikobasierte Stückzahl verlangt weiterhin, dass geschätzter Stop und Kosten in den Restpuffer passen. Feste Mini-Größe hat diese Eintrittsbedingung nicht.

## Erster Machine-Learning-Versuch

**ML1 ist tatsächlich trainiert und vollständig bis zum Kontovergleich gerechnet.** Modell: StandardScaler und L2-logistische Regression, festes C=0,1, fünf kausale Merkmale. Classification schätzt den positiven Nettoausgang; Ridge-Regression für erwartete Ergebnisgröße ist ein separater Folgeversuch.

347 eindeutige Setupkandidaten, keine Vervielfachung durch Micro-/Mini-Kopien oder Kaufketten. Neun chronologische Prüfblöcke, zunächst 80 Trainingssitzungen, eine Sitzung Abstand, dann 20 Prüfungssitzungen. Überlappende noch unbekannte Outcomes werden entfernt. 230 spätere Kandidaten erhielten Prognosen, 35 wurden verworfen. Die vorherige Trainingsphase handelt als unveränderte Basis weiter.

Die fünf Merkmale sind Stoprisiko aus der Entscheidungsquote, Bollinger-/Keltner-Breitenverhältnis, gerichtete abgeschlossene EMA-Steigung/ATR, abgeschlossenes relatives Volumen und Chicago-Handelsminute. Kein späterer Fill, Exit, MFE oder Auszahlungsergebnis ist Eingabe.

Native SQX-Beobachtung: sechs Kontraktabschnitte mit identischen Basis-Trades, Kandidaten und Quotes sowie identischen Replikaten. Danach sechs echte neue native SQX-Läufe mit dem Einstiegsgate. Anschließend ursprünglicher Quote-Equity-Leser und unveränderte Anbieter-Kontoengine; die Basis wurde auf allen gemeinsamen Kennzahlen exakt reproduziert. Native Engine **144.2953**; 145 kann Berichte anzeigen, wurde hier nicht als Rechenkern ausgegeben.

| Endbargeld aus 1’000 USD | Basis Ø | ML1 Ø | Basis Median | ML1 Median |
|---|---:|---:|---:|---:|
| Normal | 8’424,89 | 6’940,33 | 9’899,36 | 6’966,99 |
| Ein Tick schlechter je Seite | 6’860,65 | 5’889,35 | 7’142,94 | 5’964,30 |

AUC 0,50017; keine erkennbare Trennleistung. Das erste Modell verbessert die Strategie nicht. Keine Übernahme in NinjaTrader oder das Leaderboard. Zusätzliche Zufallsauslassungs-/Permutationstests, eine vollständige native Zukunfts-Prefix-Prüfung, neue Claude-Gegenprüfung und frische Forward-Daten fehlen. Nicht als fertige ML-Einsatzfreigabe darstellen.

Lokal zeigt MLflow den Lauf unter `http://127.0.0.1:5055/#/experiments/4/runs/ebaea0eb92bf4c1993ecc7c953655145`. Startdatei: `outputs/Research-Tools-20261119/MLflow-starten.command`, nur 127.0.0.1. Der Server muss nach einem App-Neustart gegebenenfalls neu gestartet werden. Eine im Browser angezeigte Dokumentationsseite von scikit-learn ist keine Trainingsoberfläche.

## Forschung und Professorentermin

Der Nutzer hat nächste Woche einen Termin bei Prof. Pavel Laskov. Die vorliegende Stelle betrifft Sicherheit und Zuverlässigkeit von KI-Agenten in Finanzdienstleistungen. Vorhanden ist die Stellenbeschreibung, keine persönliche Bewerbung/CV zur Veröffentlichung.

Die breite Idee „ein KI-Agent setzt Paper korrekt um und erkennt eigene Fehler“ ist bereits deutlich untersucht. QuantCode-Eval, RePro, SA-Bench, RECLAIM und PaperBenchX sind enge Vorarbeiten. Deshalb keinen Neuheits- oder Publikationsanspruch behaupten. Details und Abgrenzung stehen in [den Forschungsunterlagen](ai-research/docs/Vorarbeiten-und-Abgrenzung.md). Der Nutzer möchte kein generisches Paper über kaputte/manipulierte Eingaben; gefragt ist eine belastbare, eng abgegrenzte Studie zur Zuverlässigkeit von Research-Agenten. Das ist von ML1 getrennt.

## Offene Aufgaben in Reihenfolge

1. Computersteuerung wieder verfügbar machen und erst dann Windows/Claude tatsächlich ansehen. Bis dahin keinen aktuellen Sim-Zustand behaupten.
2. Gesammelte Fragen an den echten Claude-Chat senden und seine tatsächliche Antwort lesen. Interne Codex-Rechercheagenten sind nicht Claude.
3. Modellfamilien nach dem Register einzeln vergleichen, mit identischer Daten- und Kontobasis; keine breite nachträgliche Merkmals-/Schwellensuche als Bestätigung ausgeben.
4. Vor einem Paperprojekt die engere Forschungsfrage und Abgrenzung mit Laskov besprechen. Ein sauberer Nullbefund ist kein Fehler und kein Profitversprechen.

Der Nutzer bestätigt inzwischen, dass **Settings → Computer use → Control → Any App eingeschaltet** ist. Die Werkzeuge fehlen trotzdem in diesem Chat. Kein weiterer Neustart von NinjaTrader oder Windows ist daraus abzuleiten. Ein neuer Chat soll zunächst nur prüfen, ob ihm Computerwerkzeuge bereitgestellt werden.

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

> Arbeite im vorhandenen lokalen Projekt weiter. Lies im GitHub-Repo `flow1919flow/flow` zuerst `AKTUELLER-STAND.md`, die Arbeitsweise und den Steuerungsbefund. Lies lokal `outputs/AI-Forschung-20261120/RESUME.txt` und prüfe neuere Artefakte. Stelle zuerst den vorgesehenen Computerzugriff wieder her und prüfe RustDesk/NinjaTrader nur lesend. Keine Testorders, keine Konto-Resets, keine Handelslogikänderung. Sende dann die gesammelten Fragen an den bestehenden echten Claude-Chat. ML1 ist ein abgeschlossener negativer Entwicklungsbefund; weitere Klassifikatoren und Ridge stehen im Register, sind nicht bereits getestet. Prüfe den aktuellen Stand, bevor du frühere Angaben übernimmst.
