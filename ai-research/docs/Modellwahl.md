# Modellwahl: Klassifikation zuerst, Regression separat

**Der erste abgeschlossene Versuch ist ein L2-regulierter logistischer Klassifikator.** Er schätzt die Wahrscheinlichkeit eines positiven Nettoausgangs aus früheren Merkmalen und bekannten Trainingsausgängen. Das spätere Ergebnis eines neuen Kandidaten ist bei seiner Bewertung unbekannt. Ein zweiter Versuch mit Ridge auf Netto-R ist fest beschrieben und noch nicht ausgeführt. Weitere lineare Klassifikatoren sind zur Vorregistrierung vorgesehen und wurden nicht trainiert.

## sklearn-Bereiche erfüllen verschiedene Aufgaben

| Bereich | Aufgabe | Rolle hier |
|---|---|---|
| Classification | Klasse oder Klassenwahrscheinlichkeit schätzen | Erste Frage: Nettoausgang positiv ja/nein |
| Regression | Zahlenwert schätzen | Getrennter Vergleich: erwartetes Netto-R |
| Clustering | Fälle ohne Erfolgslabel gruppieren | Allenfalls Marktphasen beschreiben |
| Preprocessing | Eingaben aufbereiten | StandardScaler innerhalb jedes Trainingsfensters |
| Model Selection | Lernregeln auswählen und prüfen | Chronologische Auswertung; keine erste Parametersuche |
| Dimensionality Reduction | Eingaben verdichten | Bei fünf Merkmalen zunächst ausgelassen |

Die Begriffskategorien folgen [sklearn](https://scikit-learn.org/stable/); die Auswahl ist projektspezifisch. LogisticRegression ist trotz ihres Namens ein Klassifikator. Gewinnwahrscheinlichkeit und erwartete Gewinnhöhe sind verschiedene Ziele: Unterschiedliche Gewinn- und Verlustbeträge können bei hoher Trefferquote einen negativen Erwartungswert erzeugen. Beide Größen unterscheiden sich zusätzlich vom vollständigen, pfadabhängigen Konto-Endcash.

## Fünf Eingaben und ein nachträgliches Label

Eine Zeile bezeichnet einen eindeutigen Kandidaten unmittelbar vor der Entscheidung. `y = (netto_nach_festen_labelkosten > 0)` entsteht anschließend aus seinem unabhängig simulierten Outcome. Labelkosten umfassen die eingefrorene Mini-Provision und einen nachteiligen Tick je Seite. Das Label misst weder Kontoschutz noch erwartetes Endcash.

| Merkmal | Zulässiger Stand |
|---|---|
| Geplantes Stoprisiko in USD | Entscheidungsquote bis Originalstopp plus bekannte Kostenreserve |
| Bollinger-/Keltner-Breitenverhältnis | Nativer Zustand unmittelbar vor Entscheidung |
| Richtungsbezogene EMA-Steigung/ATR | Letzte zwei abgeschlossene EMA-Werte und abgeschlossener ATR |
| Relatives Volumen | Letzte abgeschlossene Kerze relativ zu vorherigen 20 abgeschlossenen Kerzen |
| Chicago-Sitzungsminute | DST-fähige Zone `America/Chicago`, Ursprung 08:30 |

Späterer Fill, Exit, Outcome und vollständiges Volumen der laufenden Kerze sind ausgeschlossen. Die lineare Sitzungsminute unterstellt einen monotonen Zusammenhang; die Richtungssignierung einen gemeinsamen Long-/Short-Effekt. Es gab keine Suche über Merkmalskombinationen.

## Eingefrorene Lernregel und beobachteter Befund

Die Lernregel lautet `StandardScaler → LogisticRegression`, L2, `C=0.1`, `solver="lbfgs"`, `max_iter=2000`, keine Klassengewichtung. Das Laufmanifest hält sklearn 1.9.1 und die äquivalente installierte API fest. C=0,1 ist eine vorab gewählte Schrumpfungsregel, kein gemessenes Optimum; bei expandierendem Training bleibt ihre relative Wirkung nicht konstant. [Logit-Zielfunktion](https://scikit-learn.org/stable/modules/linear_model.html).

Chronologische Sitzungsfenster beginnen mit 80 Training, einer Sitzung Abstand und 20 Vorhersage; danach expandiert das Training. Transformationen und 20%-Trainingsquantil lernen ausschließlich im Training, noch unbekannte Trainingsoutcomes werden entfernt. Ein Score unter dem Quantil führt zum Auslassen; Gleichstände werden angenommen. Die Heuristik garantiert keine 20% Testauslassungen. Zusätzliche Kalibrierung wurde nicht vorgenommen.

Neun Blöcke aus dem bereits ausgewählten Jahr ergeben 230 spätere Vorhersagen und 35 Auslassungen bei insgesamt 347 Kandidaten. **AUC 0,5001667; Brier 0,2287076 gegenüber Dummy 0,2298530; Log-loss 0,6498616 gegenüber 0,6524803.** Dummy liefert die Trainingsgrundrate, keinen sinnvollen Rangfilter. Brier und Log-loss isolieren Kalibrierung nicht. [Dummy](https://scikit-learn.org/stable/modules/generated/sklearn.dummy.DummyClassifier.html), [Kalibrierung](https://scikit-learn.org/stable/modules/calibration.html).

Der vollständige native Gate-Lauf und Kontoreplay sind abgeschlossen: Mittleres und medianes Endcash liegen unter der Baseline, normal wie unter Stress. Details stehen im [README](../README.md). Der zeitliche Split macht das häufig untersuchte Jahr nicht nachträglich zu frischem OOS. Weder Prognosevorteil noch Kalibrierung oder wirtschaftliche Verbesserung sind bestätigt.

## Registrierter zweiter Versuch: Ridge auf Netto-R

Der getrennte MR1-Plan verwendet dieselben fünf Merkmale, Trainingsfenster und Datenregeln. `R = Nettoergebnis / vorab_geplantes_Dollarrisiko`; Nenner und Kostenkonvention werden vor Training geprüft und eingefroren. Späterer Fill oder tatsächlicher Verlust dürfen den Nenner nicht definieren.

Fest vorgesehen ist `StandardScaler → Ridge(alpha=10.0, fit_intercept=True, solver="svd", positive=False)`, ohne Zieltransformation, Gewichtung, Interaktionen oder Suche. Alpha 10 ist eine unbewiesene feste Wahl, keine mathematische Entsprechung zu Logit-C=0,1. Der Gate-Score lautet geplantes Dollarrisiko × vorhergesagtes R; seine 20%-Trainingsquantilschwelle wird ausschließlich im jeweiligen Training bestimmt, Gleichstände werden angenommen. Ein Gate auf rohem R wäre eine andere Fragestellung.

`DummyRegressor(strategy="mean")` dient als R-Referenz; R-MSE und der vollständige neue SQX-/Kontopfad werden getrennt ausgewertet. Ein später historisch ausgewählter Gewinner braucht anschließend frische Bestätigung. [Ridge](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html), [DummyRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.dummy.DummyRegressor.html).

## Weitere Modelle sind noch keine Ergebnisse

Weitere lineare Klassifikatoren erhalten vor einem Vergleich exakte Lernregel, Scoredefinition, Schwelle und Reihenfolge; dieser Registereintrag ist noch offen. SVM, kNN, Bäume, Netze oder Reinforcement Learning wurden hier nicht trainiert. Die Untersuchung eines Forschungsagenten ist nochmals ein eigenes Experiment; ein negativer Logit-Test misst keine Agentenzuverlässigkeit. [Vorarbeiten](Vorarbeiten-und-Abgrenzung.md).

Kennungskorrektur nach dem Review: Ridge heißt im Register MR1; die frühere Textbezeichnung ML2 war widersprüchlich. Kein ausgeführter Versuch wurde umbenannt.
