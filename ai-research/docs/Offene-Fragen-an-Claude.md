# Offene Fragen · nach Wiederherstellung gesendet

Zielchat: **Backtest von Scotts Setups – Nautilus**. Die vorbereiteten Fragen wurden nach Wiederherstellung der Bedienwerkzeuge am 20.11.2026 tatsächlich gesendet. Ergänzt wurden DeepInfra/modernere Modelle, die inzwischen installierte Kalendererneuerung und die Micro-Nachtests. Dieses Dokument enthält die fachliche Sendefassung, keine eigenständige Claude-Gegenprüfung. Die neue Antwort muss gesondert gelesen und belegt werden. Zugangsdaten, Roh-Ticks und private Bewerbungsunterlagen wurden nicht geteilt.

## 1. Erstes tatsächliches ML-Ergebnis

Wir haben auf der ES-Funded-Fassung C28.03 einen kleinen fest parametrisierten Klassifikator trainiert: StandardScaler, L2-Logit C=0,1, fünf kausale Merkmale. 242 Sitzungen, 347 Kandidaten, 80 Trainingssitzungen plus eine Abstandssitzung, danach expandierende Prüfblöcke zu 20 Sitzungen. 230 zeitlich spätere Vorhersagen, 35 verworfene Setups. Training allein setzt die 20%-Scorequantilschwelle. Neun Blöcke, letzter Block eine Restsitzung. Das Jahr wurde bereits intensiv zur Strategieauswahl verwendet.

AUC 0,50017, Brier 0,22871 gegenüber Grundrate 0,22985. Sechs native SQX-Beobachtersegmente reproduzieren Basis-Trades und Quotes; sechs anschließende vollständige native Gate-Läufe und der ursprüngliche Konto-Replay sind abgeschlossen. 1’000 USD Budget, 143 überlappende Fenster à 100 Sitzungen. Eval EMA22 bleibt unverändert. Normal: Basis Ø 8’424,89 / Median 9’899,36 USD; ML Ø 6’940,33 / Median 6’966,99. Stress: Basis Ø 6’860,65 / Median 7’142,94; ML Ø 5’889,35 / Median 5’964,30. Keine Verbesserung, kein Einsatz.

Bitte prüfe Zeitaufteilung, Definition des Labels, Trainingsquantil und vollständigen Konto-Neulauf kritisch. Welche wenigen Kontrollen sind vor weiteren Modellen zwingend? Was lernen wir aus einem nahezu zufälligen Ranking und schwächerem Endbargeld? Vollständige native Prefix-Prüfung, Zufallsauslassungen und Blockpermutationen fehlen noch. Eine Meinung zu diesen Zahlen ersetzt keine unabhängige Nachrechnung; bitte Prüfumfang ausdrücklich benennen.

## 2. Nächste Modellfamilien

Der Nutzer möchte die linearen Klassifikatoren geordnet untersuchen. Das Modellregister trennt L1-/Elastic-Net-Logit, RidgeClassifier, LinearSVC, SGD und Perceptron. Ridge-Regression auf erwartetes Netto-R ist ein separater noch nicht ausgeführter Versuch. Welche Reihenfolge ist angesichts nur 347 abhängiger Kandidaten sinnvoll? Wie vermeiden wir eine breite Auswahl auf demselben bekannten Jahr? Keine zusätzliche Suche ohne vorher gespeicherten Plan.

## 3. Forschung für das Gespräch mit Pavel Laskov

Die breite Idee Paper → regelgetreuer Strategiecode → gültiger Backtest → evidenzgebundene Aussage ist bereits eng besetzt. Bitte die verlinkten Primärquellen aus `Vorarbeiten-und-Abgrenzung.md` lesen: insbesondere QuantCode-Eval, RePro, SA-Bench, RECLAIM und PaperBenchX. Allgemein „LLMs machen Fehler“ oder „gestörte Daten schaden“ ist dem Nutzer zu flach.

Welche schmale, prüfbare Zusatzfrage bleibt gegenüber starken bestehenden Checks offen? Diskussionskandidat: unabhängige Prüfschichten für Regeln, kausale Zeit, Ausführung/Kontoregeln und Ergebnisbehauptungen unter festem Gesamtbudget; Metriken für unbelegte positive Aussagen, richtige Negativbefunde, falsche Zurückweisungen und Kosten. Das ist eine Hypothese zur Abgrenzung, kein belegter Neuheitsanspruch. Bitte gegebenenfalls ausdrücklich verwerfen.
