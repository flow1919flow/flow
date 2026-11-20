# Vorarbeiten begrenzen die Agentenidee deutlich

Stand: 20.11.2026. Diese gezielte Primärquellenprüfung untersucht Nähe zur Kette Paper → regelgetreuer Code → gültiger Backtest → evidenzgebundene Aussage. Sie ist keine vollständige systematische Literaturübersicht und kein Neuheitsnachweis. Die beschriebenen Benchmarks wurden hier nicht reproduziert.

## Finanzielle Paper-Reproduktion ist direkt vorbesetzt

**QuantCode-Eval** ist der engste Treffer: 30 Finanzpaper, Referenzimplementierungen und 572 ausführbare Eigenschaftsprüfer. Die Prüfungen umfassen zeitliche Integrität und paperspezifische Semantik. Der aktuelle Release enthält auch Traces und Ergebnisartefakte. Ein weiterer allgemeiner Paper-zu-Tradingcode-Benchmark würde deshalb einen erheblichen Teil bestehender Arbeit wiederholen. [Autoren-Volltext](https://www.researchgate.net/publication/405091723_QuantCode-Eval_Benchmarking_Quantitative_Strategy_Code_Reproduction_from_Finance_Papers), [Release](https://huggingface.co/datasets/quantcodeeval/task_data/blob/main/README.md).

**RD-Agent(Q)** verwendet Referenzvergleiche zur Implementierungsprüfung; ein pauschaler eigener Leakage-Prüfer wird hier nicht behauptet. **AlphaAgent** prüft Hypothesen-/Formelkonsistenz durch LLM-Urteile. **Quant-Arena** begrenzt Kandidatenversuche und sperrt den Abschlusstest, untersucht jedoch offene Strategieentwicklung. Diese Verfahren liefern relevante Vergleichsmaßstäbe für unterschiedliche Teilaufgaben. [RD-Agent(Q)](https://arxiv.org/html/2505.15155v1), [AlphaAgent](https://arxiv.org/html/2502.16789v1), [Quant-Arena](https://arxiv.org/html/2610.30113v1).

## Allgemeine Wissenschaftsagenten prüfen bereits Evidenz

| Arbeit | Bereits vorhandene Kontrolle | Grenze der hier zitierten Evidenz |
|---|---|---|
| [RePro](https://arxiv.org/html/2508.16671#S3) | Atomare Paperkriterien, Verifikation, Codekorrektur | Code-Dev-Score 62,6 statt 49,6 ist keine Vollreproduktionsquote |
| [SA-Bench](https://arxiv.org/html/2608.24252#S3) | 1.491 geprüfte Implementierungsaussagen aus 30 Papern | Statische Semantikbewertung ohne Codeausführung; bester mittlerer Score 0,301 |
| [RECLAIM](https://arxiv.org/html/2609.28850#S4) | Vorab fixierte Ziele, unabhängiges Provenienz-/Protokollaudit | Gespeicherte Artefakte statt erneuter Reproduktion |
| [PaperBenchX](https://arxiv.org/html/2610.39744#S3) | Expertenverträge und saubere erneute Ausführung; nur regenerierte Evidenz zählt | 93 Aufgaben in zwölf gelisteten Bereichen ohne Finanzforschung |

Bei RECLAIM stehen 128 positive Selbstaussagen und 73 auditbestätigte Zellen gegenüber. **128−73 ist keine Zahl der Falschbehauptungen**, weil Bestätigungen und Abweichungen nicht nur in eine Richtung verlaufen. Bei PaperBenchX erreicht die beste Konfiguration 13/93 Vollreproduktionen oberhalb R > 0,9; Teilscore und Vollreproduktion sind verschiedene Maße. Diese Zahlen gelten für die jeweiligen Protokolle und begründen keine allgemeine LLM-Ausfallquote.

## Drei Erfolgsebenen dürfen nicht verschmelzen

**Paper-Treue** fragt, ob Regeln und Methode implementiert sind. **Backtestgültigkeit** fragt zusätzlich nach damaliger Informationsverfügbarkeit, Ausführung, Kosten und Auswahlgeschichte. **Evidenzreichweite** fragt, welche Aussage die tatsächlich erzeugten Artefakte tragen. Ein semantisch korrektes negatives Resultat ist ein anderes Ergebnis als profitable Zahlen mit falscher Methode.

Ein endliches bestandenes Prüfset beweist keine universelle Korrektheit. Auch „nicht hinreichend dokumentiert“ bedeutet nicht „im Forschungsfeld nicht vorhanden“. Besonders ein vermeintlich neuer freier Berichtsaudit benötigt weitere gezielte Prüfung gegenüber vorhandenen Finanzarbeiten.

## Eigener Vorschlag bleibt eine zu prüfende Erweiterung

Eine engere Interventionsstudie könnte prüfen, ob ausführbare Finanzbedingungen über Informationszeit, Ausführung, Auswahl und Aussageumfang einen Zusatznutzen gegenüber Paper-Checklisten und allgemeinem Evidenzaudit bringen. Modell und Budget müssten vergleichbar sein; unabhängige Referenzurteile und saubere Wiederholung würden alle Varianten bewerten. Unveränderte Paper und gewöhnliche Daten genügen, einschließlich korrekt implementierter Strategien ohne überzeugende wirtschaftliche Überlegenheit.

Primär wären ungedeckte positive Aussagen, korrekte negative/unklare Berichte, Implementierungstreue, Ausführungsgültigkeit, Fehlzurückweisungen und Aufwand zu messen. Ein Kontrollnutzen darf nicht lediglich mehr Rechenversuche abbilden. Neuheit, Aufgabenrechte, Stichprobenumfang und Publizierbarkeit bleiben offen. Der bestehende [Logit-Versuch](../README.md) ist ein separates Modellprojekt und kein Agentensicherheitsexperiment. Der nächste Schritt ist das [fachliche Abgrenzungsgespräch](Laskov-und-Forschungsfragen.md).
