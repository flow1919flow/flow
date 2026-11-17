# HY3 · TradeDay Fast Pass 50k · NinjaTrader-Simulation

Der Teststand ist für die Chicago-Sitzung am 17. November 2026 gebaut. Strategie und Konten sind ausschließlich lokal. Die Phase wird je Instanz eingestellt. Für den paarweisen Vergleich laufen beide in derselben Phase.

| Einstellung | Chart A | Chart B |
| --- | --- | --- |
| Konto | `SimTradeDayA` | `SimTradeDayB` |
| Startsaldo | 50’000 USD | 50’000 USD |
| Chart | NQ DEC26 · 5 Min. · CME US Index Futures ETH · Tick Replay | identisch |
| Strategie | `HY3TradeDayFastPassSim` | identisch |
| Für den ersten Vergleich | Funded aus, Sim-Automatik an | identisch |
| Für den zweiten Vergleich | Funded an, Sim-Automatik an | identisch |

Mindestens fünf vollständige Sitzungen müssen im Chart geladen sein. Die Konten dürfen keinem Echo-Profil angehören. Beide müssen vor der Aktivierung in NQ flat sein. Eine zweite Instanz auf demselben Konto sendet keine Orders. Wechsel der Phase bei deaktivierten, flachen Instanzen. Ein- und Ausstieg je ein NQ.

HY3 berechnet EMA20, Keltner mit ATR10 und Bollinger 20 mit 1,75 σ auf fünf Minuten. Beide Phasen handeln frühestens ab 09:00 Uhr Chicago. Nach einem Wechsel des berührten äußeren Keltnerbands wartet die Eval auf den Rücklauf zur EMA20. Funded akzeptiert zusätzlich den früheren SMA10-Touch, wenn SMA5, SMA10 und abgeschlossene EMA20 in Handelsrichtung im Abstand von mindestens einem Tick liegen und der Preis zuerst SMA5 um einen Tick durchbricht. Das Fenster dafür beträgt 30 Minuten ab dem zweiten Bandkontakt. Das SQX-Bollingerziel ist um 0,75 Tick vorgezogen. Der feste Stop liegt am Gegenband plus 0,15 ATR nach außen. ROC(5) kann nach einem Vorzeichenwechsel gegen die offene Position aussteigen. Normale Orders werden nach zwei Sekunden auf einem neuen gültigen Quote-Ereignis an den lokalen Simulator übergeben. Die Testsitzung hat keinen geplanten NQ-Tier-1-Termin nach dem BLS-/Fed-Kalender. Die Fassung geht spätestens ab 15:09 Uhr Chicago in die Glattstellung.

Für den Vergleich im NinjaScript Output nach `HY3 FILL` suchen. Pro Phase, Signalzeit und Aktion die beiden Konten nebeneinanderstellen. Die Zeile enthält Preis, Uhrzeit, Menge, zuletzt sichtbaren Kurs auf der Gegenseite und die Übergabezeit. Ein Signal ohne Fill, einen abweichenden Preis und einen späteren Fill separat zählen. Ob eine Abweichung aus dem Feed, der Orderübergabe oder dem Sim-Fill stammt, lässt sich so nachvollziehen. NinjaTrader und das historische TBBO-Replay verwenden unterschiedliche Fill-Modelle.

Die Ein-Tages-Prüfung enthält einen lokalen $2’000 Verlustschutz ab Testbeginn, keine mehrtägige Kontoführung oder Auszahlungssimulation. Quelle der Regeln ist der bereits ausgeführte SQX-Quellstand `HY3TradeDayFastPass.java`. Die ZIP enthält den NinjaScript-Quellcode und die Importmetadaten.
