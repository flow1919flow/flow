# ES · zwei lokale Sim-Strategien · V8r4

| Instanz | Klasse | Konto | Signalregeln |
| --- | --- | --- | --- |
| Rapid EOD Eval | HY104RapidEvalSim | SimHY104RapidEval | HY104, Rücklauf EMA20 |
| Rapid EOD Funded | HY104C2803FundedSim | Sim104C28Funded | 104-C28.03, zusätzlich 60-Minuten-Eröffnungsspannenziel |

Je 1 ES, 5 Minuten, Tick Replay, CME US Index Futures ETH. Der eigene Kerzenaufbau verwendet Trade-Zeitstempel. Mindestens fünf vollständige Aufwärmsitzungen sind erforderlich. Das laufende Bollinger-Ziel ist um 0,75 Tick vorgezogen; der Strategie-Stop bleibt fest.

AccountReplay V8r4 führt das Konto separat von den Signalen. ES kostet im gespeicherten Modell 2,87 USD je Ausführungsseite. EOD-Hoch und Verlustgrenze werden nach dem tatsächlichen Sitzungsschluss fortgeschrieben und gespeichert. Das Überschreiten der Grenze beendet diese Testepoche dauerhaft. Ein Reload beginnt kein neues Konto. Ein neuer Sim-Versuch braucht einen ausdrücklich protokollierten neuen Start.

Die beiden ES-Journale enthielten am nativen Prüfcheckpoint 19. November, 19:38 Uhr Vaduz jeweils +1.869,26 USD netto. Beide waren flat und handelsbereit. Der tatsächliche EOD-Wechsel stand noch aus. [Belege und Einschränkungen](../releases/2026-11-19-v8r4/README.md).

Die führende historische MFF-Leaderboard-Variante mit EMA22 in der Eval ist ein eigener Ansatz; die hier installierte ES-Eval verwendet EMA20.
