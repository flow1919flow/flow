# Überprüfbare Modelle und Agenten für Finanzforschung

Dieser Forschungsbereich trennt zwei Aufgaben: Ein kleiner Klassifikator bewertet bestehende ES-Setups; eine mögliche spätere Agentenstudie untersucht die Kette Paper → regelgetreuer Code → gültiger Backtest → evidenzgebundene Aussage. Die breite Agentenidee hat deutliche Vorarbeiten. Die [Literaturabgrenzung](docs/Vorarbeiten-und-Abgrenzung.md) begründet keinen Neuheitsanspruch.

**Stand 20.11.2026: Der erste historische Klassifikations- und Kontovergleich ist abgeschlossen. Das ML-Gate verbessert den wirtschaftlichen Pfad nicht.** Der native SQX-Beobachter, die Baseline-Prüfung und vollständige native Gate-Läufe über sechs Segmente wurden ausgeführt. Baseline-Quotes blieben im Beobachtervergleich unverändert. Die verwendeten technischen Zeitprüfungen begrenzen den Nachweis auf ihre dokumentierten Fälle.

## Erstes Modell: kleine feste Lernregel

347 eindeutige Kandidaten liegen in einem Kalender von 242 Sitzungen vom 24.11.2025 bis 30.10.2026; 204 Sitzungen enthalten Kandidaten. Kandidaten und Sitzungen sind abhängig. Das Jahr wurde bereits für die Strategieauswahl verwendet und ist kein frischer OOS-Bestand.

`StandardScaler → L2-Logit`, festes `C=0.1`, verwendet fünf zum Entscheidungszeitpunkt verfügbare Merkmale. Training beginnt mit 80 Sitzungen, gefolgt von einer Sitzung Abstand und 20 Sitzungen Vorhersage; danach expandiert es. Noch nicht bekannte Trainingsoutcomes werden ausgeschlossen. Neun Blöcke erzeugen **230 zeitlich spätere Vorhersagen und 35 Auslassungen**. Der letzte Block umfasst eine Restsitzung. Die Ablehnungsschwelle ist das ausschließlich im Training bestimmte 20%-Quantil; Gleichstände werden angenommen. Diese Schwelle und C sind vorab gewählte Heuristiken, keine optimierten Einstellungen.

| Prognosemetrik | L2-Logit | Trainingsgrundrate |
|---|---:|---:|
| AUC | 0,5001667 | — |
| Brier-Score | 0,2287076 | 0,2298530 |
| Log-loss | 0,6498616 | 0,6524803 |

Die geringe Differenz der Wahrscheinlichkeitsverluste belegt keine verlässliche Rangfolge, Kalibrierung oder Geldwirkung. Der Score schätzt aus historischen Merkmalen und Ausgängen eine Erfolgswahrscheinlichkeit; ein künftiger Ausgang ist bei der Entscheidung unbekannt. [Definitionen und Modellregister](docs/Modellwahl.md).

## Vollständiger Kontoreplay: beide Hauptgrößen sinken

Jede Politik wurde vollständig nativ simuliert; historische Trades wurden nicht bloß nachträglich gelöscht. Der unveränderte MFF-Rapid-EOD-50k-Replay vergleicht **143 überlappende Startfenster mit je 100 Sitzungen**, aus demselben Kalender und mit 1.000 Dollar Gesamtbudget. Gebühren, Ersatzkäufe, Auszahlungen und Restbudget gehören zum Endcash. Evaluation bleibt in beiden Armen EMA22; nur Funded C28.03 erhält im ML-Arm das Entry-Gate. Vor dem ersten Prognoseblock bleibt dessen Verhalten unverändert.

| Kosten | Politik | Mittleres Endcash, USD | Medianes Endcash, USD |
|---|---|---:|---:|
| Normal | C28.03 | 8.424,89 | 9.899,36 |
| Normal | C28.03 mit Logit-Gate | 6.940,33 | 6.966,99 |
| Stress | C28.03 | 6.860,65 | 7.142,94 |
| Stress | C28.03 mit Logit-Gate | 5.889,35 | 5.964,30 |

Diese aggregierten historischen Ergebnisse sind Entwicklungsdiagnostik, einschließlich der bereits ausgewählten Baseline. 143 überlappende Fenster sind keine 143 unabhängigen Replikationen. Zufallsauslassungen, vollständige Blockpermutationen und frische vorab gespeicherte Prognosen sind noch offen. Das Modell wird nicht in eine Bestenliste befördert.

## Nächste Entscheidungen bleiben getrennte Versuche

Weitere lineare Klassifikatoren müssen vor Training mit festen Einstellungen registriert werden; sie wurden noch nicht trainiert. Ein eigener zweiter Versuch sieht Ridge auf Netto-R mit festem `alpha=10.0` und `solver="svd"` vor. Er ist noch nicht ausgeführt und ersetzt die Klassifikationsfrage nicht nachträglich.

Die mögliche Agentenstudie verlangt zuerst eine konkrete Abgrenzung zu bestehenden Finanz- und Reproduktionsbenchmarks. Allgemeine Eingabestörungen oder „LLMs machen Fehler“ bilden hier keine eigenständige Paperidee. [Forschungsfragen und Gesprächseinstieg](docs/Laskov-und-Forschungsfragen.md).

## Öffentlich teilbarer Bestand

Dieser Bereich enthält selbst erstellten Code, Protokolle, geprüfte Aggregate und Primärquellenlinks. Private Marktdaten und vollständige geschützte Paper bleiben außerhalb des Repositorys. Der Prototyp ist ein Offline-Forschungsbeispiel; Live-Handel und produktive Handelsinstallation wurden nicht verändert. Eine frühere Claude-Rückmeldung existiert, die neuen Fragen wurden nach Wiederherstellung der Steuerung an den echten Claude-Chat gesendet. Seine neue Prüfung läuft; eine abgeschlossene Gegenrechnung wird damit noch nicht behauptet.

Die Skripte setzen die dokumentierte lokale Projektstruktur und eine lizenzierte SQX-Installation voraus; ein frischer Git-Clone allein kann die Läufe nicht ausführen. Das [lokale Eingabemanifest](evidence/local-input-inventory.json) enthält relative Pfade, Größen und Hashes, keine Tickinhalte. Das [Ergebnismanifest](evidence/ml1-results.json) bindet Training, native Segmente und Kontovergleich an ihre Quellen. Die tatsächlich ausgeführte Trainingsfassung liegt separat unter [train_ml1-executed.py](evidence/train_ml1-executed.py); `train_ml1.py` ergänzt danach ausschließlich die Ausgabe einer leeren Entscheidungsdatei für ein Segment ohne Kandidaten. Kein Modell wurde dafür neu angepasst.

Für einen neuen Chat: [vollständiger Arbeitsstand](../AKTUELLER-STAND.md), [Bedienablauf mit RustDesk/Claude](../methodik/Arbeitsweise-RustDesk-Claude.md), [an Claude gesendete Fragen](docs/Offene-Fragen-an-Claude.md).
