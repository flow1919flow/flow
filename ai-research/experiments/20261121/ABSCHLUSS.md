# Neue ML-Vergleiche abgeschlossen · 21. November 2026

**Built with PriorLabs-TabPFN.** Vier neue Modellarme wurden tatsächlich trainiert,
auf späteren Zeitblöcken bewertet und über 24 native SQX-Gate-Jobs sowie die
unveränderte Anbieterengine vollständig bis zum Endbargeld gerechnet.

| Funded-Modell | Normal Ø | Normal Median | Tickstress Ø | Tickstress Median |
|---|---:|---:|---:|---:|
| Basis · HY104-EMA22 → C28.03 | 8,424.89 USD | 9,899.36 USD | 6,860.65 USD | 7,142.94 USD |
| Logistik · neue Schwellenregel | 7,153.55 USD | 7,131.53 USD | 5,516.02 USD | 6,119.19 USD |
| Gradient Boosting · flach | 7,059.14 USD | 7,329.98 USD | 5,840.50 USD | 5,986.81 USD |
| Ridge · erwartetes Netto-R | 7,830.00 USD | 8,286.26 USD | 6,449.53 USD | 6,819.31 USD |
| TabPFN v2 | 8,325.73 USD | 9,723.52 USD | 6,959.86 USD | 7,794.06 USD |

Gemeinsame Basis: 1.000 USD Kaufbudget, MFF Rapid EOD 50k, Eval HY104-EMA22,
Funded C28.03, 242 Sitzungen vom 24.11.2025 bis 30.10.2026. 143 überlappende
Startfenster mit je 100 Sitzungen sind keine unabhängigen Experimente.
Endbargeld enthält unverbrauchtes Budget; Gewinn ist Endbargeld minus 1.000 USD.
Tickstress bedeutet einen Tick schlechter je Seite. Die akzeptierte Basis
wurde auf den Quote-/Kontopfaden exakt reproduziert.

347 eindeutige Kandidaten; neun äußere Zeitblöcke ergeben 230 spätere
Vorhersagen je Modell. Nur das Funded-Einstiegsgate ändert sich. Die ersten
Trainingssitzungen bleiben als Basis im Kontoverlauf. Keine Parametersuche:
L2-Logistik C=.1, flaches Gradient Boosting, Ridge alpha10 und TabPFN v2 mit
vier Ensemble-Schätzern und festem Seed. Schwellen kommen aus fünf
kreuzweisen Trainings-Sitzungsblöcken, nicht aus äußeren Testdaten.

ML1-Kontrollen: 1.000 gematchte Zufallsauslassungen und 1.000 vollständige
bedingte Pipeline-Permutationen. Vier neue Arme: dieselben 199 gemeinsamen
Sitzungspermutationen mit Maximum über die vier Rangkorrelationen. Das ist
eine bedingte Entwicklungsdiagnose, kein neuer OOS-Nachweis. Die Kontrollen
sind keine Verteilung aus 1.000 kompletten Zufalls-Kontoreplays.

Fünf physische SQX-Prefix-Schnitte und 181 frühere Paritätszeilen bestanden;
Signalquote und Stop wurden ebenfalls verglichen. Nur die fünf eigentlichen
Schnittentscheidungen haben ihre unmittelbare Zukunft vollständig entfernt.
Eine absichtlich undichte Kontrollspalte wurde vom Validator abgelehnt;
das ist kein Test eines absichtlich undichten nativen Modellfeatures.
Zusätzliche Randfall-/Zufallsschnitte und frische Forward-Prognosen bleiben offen.

Der erste TabPFN-Versuch stoppte an einer überstrengen numerischen
Sammel-/Einzelprüfung. Fehlerbeleg und vor dem neuen Fit veröffentlichter
Nachtrag bleiben erhalten. Tatsächliche Gates verwenden Einzelvorhersagen;
keine der neun Entscheidungen-Gruppen wechselte durch die gemessene
Sammelabweichung. Der Nullvergleich protokolliert seine Sammelrechen-Grenze.

SI: 229 archivierte ES-Meldungen, aber nur sieben spätere Setups mit einer
vorher verfügbaren Meldung im festen Fenster. Null verifiziert lückenlose
Feed-Sitzungen. Kein neues SI-Modell trainiert und Lücken nicht als null
Events behandelt. Frühere negative SI-Läufe bleiben erhalten.

Lokale MLflow-Oberfläche: http://127.0.0.1:5055/#/experiments/4 .
Native Engine: SQX144.2953 in einer isolierten Kopie. Kein Cloudaufruf,
keine DeepInfra-GPU, keine Datenkäufe und keine Änderung laufender Sims.
Claude prüfte den konkreten Versuchsplan und gab methodische Anregungen;
er hat die vollständigen neuen Kontoverläufe nicht unabhängig nachgerechnet.

[HTML-Ergebnisbericht](Ergebnisse.html), [Ergebnisse](summary.json),
[native Nachweise](native-acceptance-summary.json),
[Kontoreplay](Cash/results.json), [Kontrollen](Controls/family-null.json),
[SI-Abdeckung](SI/feasibility.json), [Vorabfestlegung](preregister.json).

Alle Ergebnisse betreffen das bereits vielfach ausgewählte Entwicklungsjahr.
Keine Aufnahme eines ML-Arms als bestätigt in ein produktives Leaderboard.
ML2–ML7 bleiben getrennte, noch nicht trainierte Registereinträge.
