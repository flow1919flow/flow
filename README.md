# ES/NQ · aktueller Arbeitsstand und Übergabe

**Neuer Chat: zuerst [AKTUELLER-STAND.md](AKTUELLER-STAND.md) lesen.** Stand vom 20. November 2026; laufende Windows-Simulationen müssen vor jeder aktuellen Aussage neu angesehen werden.

- [Arbeitsweise mit RustDesk, NinjaTrader und Claude](methodik/Arbeitsweise-RustDesk-Claude.md)
- [Computersteuerung: Any App eingeschaltet, Werkzeuge fehlen](methodik/Steuerungsdiagnose-2026-11-20.md)
- [Aktueller gespeicherter MFF-/TradeDay-Datenstand](leaderboards/2026-11-20/README.md)
- [News-Kalender: Quellen, automatische Erneuerung und Abnahme](news-calendar/README.md)
- [ML-Forschung: erster tatsächlicher Versuch ohne Verbesserung](ai-research/README.md)
- [Vorbereitete Fragen an Claude](ai-research/docs/Offene-Fragen-an-Claude.md)

Der nachfolgende Versionsstand bleibt als historische Installationsdokumentation erhalten. Der neue Snapshot ersetzt weder eine aktuelle Bildschirmprüfung noch eine neue wirtschaftliche Validierung. Roh-Ticks und Zugangsschlüssel bleiben lokal.

---

# ES und NQ · NinjaTrader V8r4 · 19. November 2026

Aktueller auf Windows importierter, nativ kompilierter und auf vier lokalen Sim-Instanzen geprüfter Stand: **AccountReplay V8r4**.

- [Aktueller Stand, Installation und Grenzen der Prüfung](releases/2026-11-19-v8r4/README.md)
- [Importpaket](releases/2026-11-19-v8r4/AccountReplay-V8r4-ES-NQ-Sim-Import.zip)
- [ES-Strategien](ninjatrader/ES.md) · [NQ-Strategien](ninjatrader/NQ.md)
- [Installierte Quelldateien und SHA-256](releases/2026-11-19-v8r4/SHA256SUMS)
- [Native Sim-Abnahme](releases/2026-11-19-v8r4/proofs/native-acceptance.json)
- [MFF Leaderboard](leaderboards/MFF.md) · [TradeDay Leaderboard](leaderboards/TradeDay.md)

V8r4 ergänzt die persistente Kontoführung nach den gespeicherten Kontoreplay-Regeln: EOD-Trailing, Gebühren pro Ausführungsseite, dauerhaften Verluststatus und Prüfung gegen native Ausführungen. Die Signal-, Indikator-, Einstiegs-, Strategie-Stop- und Zielregeln wurden dabei nicht verändert. Ein vorbeugender Stop-Risiko-Filter wurde nicht ergänzt.

Die Leaderboards unten sind historische Snapshots vom 17. November. Dieser Commit berechnet oder bestätigt deren wirtschaftliche Ergebnisse nicht erneut. Die native Sim-Abnahme belegt Installation und die konkret genannten Prüfungen; sie ist keine vollständige Tick-für-Tick-Parität oder Einsatzfreigabe für Providerkonten.

## Archiv: Dokumentation vom 17. November

# ES und NQ · Strategiestand vom 17. November 2026

| Anbieter | Markt | NinjaTrader · lokale Simulation | Historischer Anbieter-Replay |
| --- | --- | --- | --- |
| MyFundedFutures | ES | HY104 mit EMA20 in der Eval, 104-C28.03 im Funded-Test, je 1 ES | Rapid EOD 50k mit HY104 und HY104-EMA22 als zwei Eval-Armen, jeweils mit 104-C28.03 ab Funded |
| TradeDay | NQ | HY3 auf zwei 50k-Sim-Konten, je 1 NQ und EMA20 beim ersten Fill-Vergleich | Fast Pass mit HY3, EMA20 in der Eval und SMA5/10 ab Sim Funded |

- [MFF Leaderboard](leaderboards/MFF.md)
- [TradeDay Leaderboard](leaderboards/TradeDay.md)
- [NinjaTrader-Regeln ES](ninjatrader/ES.md) und [NinjaTrader-Regeln NQ](ninjatrader/NQ.md)
- [Backtest und Kontoreplay](methodik/Backtest.md)
- [Quellenmanifest und SHA-256](belege/Quellenmanifest.json)
- [TradeDay-Skalierung mit bis zu fünf Konten](belege/TradeDay-Skalierung.json)

Die C#-Dateien entsprechen den lokalen Simulationsfassungen für die bezeichneten Testsitzungen. Der ES-Ansatz im NinjaTrader-Test nutzt EMA20. Die führende ES-Zeile im MFF Leaderboard verwendet EMA22 für den Rücklauf in der Eval. Die Mittellinie der Keltner-Bänder bleibt EMA20. NinjaTrader-Simulation und Portfolio-Replay haben unterschiedliche Aufgaben. Die NinjaTrader-Fassungen prüfen Signale und Ausführung im lokalen Simulator. Eval-Fortschritt, Gebühren und historische Auszahlungen werden im mehrtägigen Kontoreplay ausgewertet.

Der Keltner-Bandwechsel setzt die Handelsrichtung. Der Rücklauf zur Mitte löst den Einstieg aus. Der Stop liegt am Gegenband zuzüglich ATR-Puffer und bleibt fest. Das laufende Bollinger-Ziel ist um 0,75 Tick vorgezogen. Im ES-Funded-Test ergänzt das Hoch bzw. Tief der ersten Handelsstunde das Gewinnziel. In NQ ergänzt HY3 einen ROC-Ausstieg nach Richtungswechsel und ab Funded einen alternativen SMA10-Einstieg nach einem SMA5-Bruch.

## Ergebnis der Skalierung

Mit 1’000 USD TradeDay-Budget und einer modellierten Kaufgebühr von 99 USD je Fast Pass 50k ergaben zwei Konten mit je 1 NQ im Stress den höchsten TradeDay-Median der getesteten Größen. Drei Konten steigerten den Median des gemeinsamen Portfolios mit zwei MFF-Konten von 1’087 auf 1’380 USD je 30 Tage. Zugleich fiel die Zahl positiver Fenster von 133 auf 120 von 146 und die Schwelle der schwächsten 10 % von +121 auf −600 USD. Für ein Ergebnis mit geringerem Verlustrisiko ist 2 MFF + 2 TradeDay die bevorzugte der beiden Kombinationen.

Mit 4’000 USD TradeDay-Budget und Rabatt lag beim Stress-Median 4×100k mit je 2 NQ vorn, bei +2’372 USD je 30 Tage. Die schwächsten 10 % lagen bei ungefähr −1’327 USD je 30 Tage. 5×50k mit je 1 NQ hatte den höchsten Stress-Durchschnitt (+2’291 USD), einen Median von +1’856 USD und die Schwelle der schwächsten 10 % bei −693 USD. Bei 5×150k blieb der Stress-Median über alle vier Kontraktmengen negativ. Preise sind Szenarioannahmen.

