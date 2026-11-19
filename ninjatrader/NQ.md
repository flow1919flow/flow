# HY3 · NQ · TradeDay Fast Pass 50k · V8r4

| Instanz | Klasse | Konto | Phase |
| --- | --- | --- | --- |
| Eval | HY3TradeDayFastPassSim | SimTradeDayA | FundedPhase=false, EMA20 |
| Funded | HY3TradeDayFastPassSim | SimTradeDayB | FundedPhase=true, SMA5/10-Erweiterung |

Je 1 NQ, 5 Minuten, Tick Replay, CME US Index Futures ETH. Beide Varianten verwenden dieselben Basisbänder. Ab Funded kann der SMA10-Touch nach SMA5-Bruch früher einsteigen. Die Varianten müssen deshalb nicht dieselben Einstiege erzeugen. Einstieg frühestens 09:00 Chicago, zusätzlich ROC(5)-Ausstieg bei Richtungswechsel. Bollinger-Ziel um 0,75 Tick vorgezogen; Strategie-Stop am Gegenband plus 0,15 ATR, fest ab Einstieg. Mindestens fünf vollständige Aufwärmsitzungen.

V8r4 führt Gebühren von 2,88 USD je Ausführungsseite, EOD-Trailing und Kontostatus dauerhaft. Bei TradeDay zählt bereits das Erreichen der Verlustgrenze. Ein solcher Grenzausstieg bildet einen gescheiterten Kontoversuch ab. Es ist kein vorbeugender Stop-Risiko-Filter.

Der erste native Sim-Versuch vom 19. November endete für beide Instanzen mit jeweils −2.045,76 USD nach Modellgebühren. Am Prüfcheckpoint 19:38 Uhr Vaduz war der Status deshalb SIM-KONTO BEENDET: Charts und Signale laufen weiter, neue Orders sind gesperrt. Ein Reload erhält diesen Status. Der Benutzer hat anschließend einen neuen, gesondert zu protokollierenden Sim-Versuch angefordert. Die Windows-Umstellung erfolgte nach Freigabe des Computers als neue Epoche. Der fehlgeschlagene Versuch darf nicht aus den Ergebnissen entfernt oder rückwirkend als bestanden behandelt werden.

[Abnahme und konkrete Testgrenzen](../releases/2026-11-19-v8r4/README.md).

## Zweiter nativer Sim-Versuch

Am 19. November um 21:14 Uhr Vaduz initialisierten beide NQ-Instanzen die neue Testepoche mit jeweils 0 USD relativer Bilanz und −2.000 USD Verlustgrenze. Beim Abschlusscheck um 21:18 Uhr waren beide aktiviert, Sync=true, flat und zeigten grün LIVE. Die alten fehlgeschlagenen Journale und Seeds wurden auf Windows unter Run-1-Namen erhalten. Die ES-Journale blieben byteidentisch; ES wurde nicht neu geladen. Es wurden keine Testorders gesendet. Der Workspace mit vier Charts wurde um 21:15:22 Uhr gespeichert und die XML-Datei zurückgelesen.

[Nachweis des zweiten Sim-Versuchs](../releases/2026-11-19-v8r4/proofs/nq-run2-native-acceptance.json). Der native Cashstand wurde nicht zurückgesetzt; die Kontomodellbilanz beginnt relativ zur neuen Testepoche bei null. Vollständiger Prozessneustart, echter EOD-/Wochenendwechsel und neue vollständige Tick-Abgleiche bleiben offen.
