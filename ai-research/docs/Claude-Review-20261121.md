# Tatsächliche Claude-Gegenprüfung · 21. November

Der bestehende Chat **Backtest von Scotts Setups – Nautilus** wurde nach Wiederherstellung der Computersteuerung tatsächlich bedient. Die sechs offenen Fragegruppen und der SI-Nachtrag wurden übermittelt; die abgeschlossene neue Antwort wurde vollständig gelesen. Diese Datei fasst sie mit eigener fachlicher Einordnung zusammen.

Claude gibt an, am Commit `8b59a857154b3b53e164c3e937751faa834e5b93` die ausgeführte Trainingsfassung, Ergebnisdateien, Replay, Kalendercode, Micro-Nachtests und Forschungsdokumente gelesen zu haben. Externe Seiten las er über zusammenfassende Abrufe, nicht als vollständige Paper. **Die neuen ML- und Kontozahlen hat er nicht unabhängig nachgerechnet.**

## Modellentscheidung

ML1 bleibt eine sinnvolle einfache Referenz mit negativem Entwicklungsbefund. Claude empfiehlt zuerst gematchte Zufallsauslassungen, Sitzungsblock-Permutationen und eine native Prefix-Prüfung. Danach höchstens eine feste nichtlineare Gegenprobe und die getrennt registrierte Ridge-Frage zur Gewinnhöhe.

Sein Vorschlag lautet `HistGradientBoostingClassifier(max_depth=1, learning_rate=0.05, max_iter=100, min_samples_leaf=20, l2_regularization=1.0, early_stopping=False)`. Noch nicht trainiert oder endgültig vorregistriert. Tiefe 1 prüft additive nichtlineare Einzeleffekte, keine SI-/Regime-Wechselwirkungen. Die benötigen einen eigenen begrenzten Plan. Andere lineare Registereinträge bleiben als nicht trainiert erhalten.

Zusätzlich nötig: AUC nach Prüfblock, konsistente Modellkennungen und eine vor dem tatsächlichen Lauf unveränderlich gespeicherte Registrierung. Die AUC-Unsicherheit aus unabhängigen Beispielen ist nur eine Näherung; Zeitabhängigkeit und neun unterschiedliche Blockmodelle bleiben zu berücksichtigen.

## Zwei Empfehlungen werden eingegrenzt

**TabPFN-Lizenz:** Claude bezog sich auf nichtkommerzielle TabPFN-2.6-Gewichte. Das offizielle Repository unterscheidet Versionen: Code Apache 2.0, neuere Gewichte nichtkommerziell, Version 2 mit gesonderter Prior-Labs-Lizenz einschließlich Attribution. Daraus folgt kein pauschales Verbot aller Versionen. Vor einer Nutzung die konkrete Version prüfen. [Offizielle Lizenzübersicht](https://github.com/PriorLabs/TabPFN#license).

**Zufallskontrollen durch Löschen alter Trades:** Ein exakter Abgleich des beobachteten ML1-Gates beweist nicht, dass beliebige Auslassungsmuster durch Löschen alter Fills richtig simuliert werden. Übersprungene Positionen können spätere Signale freigeben. Erforderlich ist ein validierter kausaler Kandidaten-/Positionsablauf oder ein vollständiger nativer Neulauf. Die Löschabkürzung wird ohne diesen Nachweis nicht übernommen.

DeepInfra bietet neben Inferenz/Deployment auch GPU-Miete für eigenes Training. Für den kleinen Tabellenvergleich wird zunächst lokal gerechnet. [Offizielle GPU-Dokumentation](https://docs.deepinfra.com/gpu-instances/overview). Keine GPU wurde angelegt und kein kostenpflichtiger Modellaufruf ausgeführt.

## SI

Claude unterstützt zwei getrennte Fragen: Zusatznutzen für bestehende Setups und explorative Zusammenhänge außerhalb davon. Beide Vergleichsarme brauchen dieselben tatsächlich abgedeckten Tage und damals verfügbare Meldungen. Seine Schätzung von 140–155 ES-Setups mit SI-Abdeckung ist **nicht nachgezählt** und kein akzeptierter Datenbestand.

Die vorgeschlagenen 15-/60-Minuten-Fenster und 30 Sekunden Abstand sind heuristische Vorschläge, keine optimierten Regeln. Bei zu wenigen SI-haltigen Testfällen nur beschreibend berichten. Der [SI-Entwurf](SI-Naechster-Schritt.md) dokumentiert frühere negative Boosting-Läufe und die Discord-Zeitstempelgrenze. Kein neuer SI-Lauf wurde gestartet.

## Kalender: tatsächlicher neuer Prüfbedarf

Claude bestätigt im gelesenen Code Schutz vor verschwindenden Zukunftsterminen, Manifest zuletzt, Hostbegrenzung, Schlüsseltrennung und richtige Fenstergrenzen. Offen sind insbesondere:

- **Monatswechsel:** Der Updater verlangt immer laufenden und folgenden Fed-Monat. Das ist im eigenen Quelltext bestätigt. Ist die nächste Seite noch unveröffentlicht, scheitert die Erneuerung; nach Ablauf der letzten guten Generation können die drei newsabhängigen Sims blockieren. Wann eine künftige Seite erscheint, ist unbekannt. Monatswechsel-/Fehlerfalltest und sichere Abdeckungsregel sind noch offen. Windows-Code und Kalender wurden dafür nicht verändert.
- FRED ist die einzige maschinelle Quelle für neue CPI-/NFP-Tage; unabhängiger Jahresanker fehlt.
- Im öffentlichen Quellordner fehlte zunächst `package-hashes.json`; die unveränderte Datei wird samt Hashabgleich ergänzt. Das ist keine neue Installation.
- Echter Login-/Neustart nach Fehler und Aufräumen alter Generationen sind nicht vollständig physisch getestet. Der Task führt einen Scriptblock aus Text aus; keine globale Ausführungsrichtlinie wurde geändert.

Die Abnahme vom 20.11. wird nicht zurückdatiert erweitert. Dieser Review verlängert keine Kalenderfrische und ändert keine Sim- oder Handelslogik.

## Micro- und Forschungseinordnung

Kleine uneinheitliche Micro-Kontraste ergeben keinen robusten Gesamtsieger. Claudes pauschale Formulierung „die Stückzahl hat keinen Effekt“ wird nicht als bewiesene Nullwirkung übernommen. Die Vergleiche bleiben auf ihre benannten Annahmen beschränkt.

Claude nennt weitere enge Vorarbeiten zu zeitlicher Nichtinterferenz, Placeboverbesserungen und gestuften Audits. Diese Quellen benötigen vor neuen Zahlen-/Neuheitsbehauptungen eigenständige Prüfung. Er würde die Forschungsfrage stärker auf Ausführungs-/Kontosemantik, Fehlzurückweisungen und Prüfkosten eingrenzen. Das ist kein Neuheitsnachweis oder unabhängiger Reproduktionslauf.
