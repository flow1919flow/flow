# Merkmale und SI · tatsächliche Claude-Prüfung · 21. November 2026

Claude hat im bestehenden Chat „Backtest von Scotts Setups – Nautilus“ den
Abschluss am öffentlichen Commit `170a331f42bb7370ddf125c1b34fcd8dad7860a1`
gelesen: Ergebnis-, Kontroll-, Trainings- und SI-Dateien sowie die relevanten
Java-Regeln für Merkmale, Stops und Ziele. Er hat die neuen Geldverläufe
**nicht unabhängig nachgerechnet**. Beide tatsächlich gelesenen Antworten
betrafen Bericht und Versuchsplanung; die zweite präzisierte die Kalibrierung.

## Ergebnisbericht: kleine Änderung, kein belegter Prognosevorteil

TabPFN ließ 14 von 230 später bewerteten Kandidaten aus. Bei der neuen
Logistik waren es28, beim Boosting38, bei Ridge33. Diese Zahlen stehen jetzt
neben der Geldtabelle. Die geringe Veränderung der Basis darf nicht mit
guter Trennleistung verwechselt werden: TabPFN-AUC0,475, Rangkorrelation−0,026,
bedingter über vier Arme korrigierter Nullrang0,99. Das Stressplus von99USD
im Mittel ist ein gemischter Entwicklungsbefund. Die Geldzahlen selbst
wurden für diese Darstellung nicht neu berechnet oder verändert.

## Zwei begründete Merkmalsfamilien

| Reihenfolge | Information | Kausale Definition |
|---|---|---|
| A zuerst | Weg zum nächsten aktiven Ziel in R | Bekannte Ask/Bid-Entscheidungsquote zum laufenden Bollinger-Ziel bzw. gültigen Opening-Range-Niveau, geteilt durch geplanten ursprünglichen Stopabstand. Kein zukünftiger Fill und kein späteres Ziel. |
| A | Lage in der Eröffnungsspanne | Gerichtete Position innerhalb der ersten60Minuten, erst nach deren Ablauf; vorher fehlend und als nicht bereit markiert. |
| B später, eigener Versuch | Alter des Setups | Zeit zwischen tatsächlich armierendem Keltner-Kontakt und Einstiegsauslöser. Übernommene Vorsitzung gesondert kennzeichnen. |
| B | Stärke des vorangegangenen Impulses | Größte bis zur Entscheidung beobachtete Ausdehnung jenseits des Kontaktbandes, normiert mit abgeschlossenem ATR. |

Das alte BB/KC-Breitenverhältnis enthält schon viel gewöhnliche
Ziel-/Stopgeometrie. Neu ist insbesondere die tatsächlich aktive
Eröffnungsspanne; bloß ähnliche Indikatoren umzubenennen fügt keine
neue Information hinzu. Deshalb zuerst ein einziger gerichteter
Geometrie-Messversuch ohne Modellfit. Die Beobachterquelle und Statistik
wurden vor der Messung veröffentlicht. Sechs native Abschnitte müssen
dieselben Trades, Kandidaten, bisherigen Merkmale und Signalquotes liefern.
Fünf physische Prefix-Schnitte prüfen die neuen Merkmale; zwei vorhandene
Schnitte liegen vor Minute60 (ca.Minute10,34 und6,07). Das ist eine begrenzte
Stichprobe, kein universeller Kausalitätsbeweis. Eine absichtlich undichte
native OR-Variante als Positivkontrolle ist zusätzlich noch offen.

Primär: positive Rangkorrelation von Zielweg/Stopweg mit Stressnetto,
1.000 bedingte Permutationen ganzer Sitzungsvektoren. Das bereits für viele
Entscheidungen verwendete Jahr bleibt Entwicklungsdaten. Ein positiver
Befund rechtfertigt einen registrierten Folgetest, keine Live-Freigabe.
Ein Nullbefund widerlegt auch nicht jede mögliche nichtmonotone Wechselwirkung.

## Andere Zielgröße und Gate-Regel: vorbereitet, noch nicht getestet

Gewinnwahrscheinlichkeit allein berücksichtigt die wechselnden Gewinn-
und Verlusthöhen nicht. Für diesen Anwendungsfall ist erwartetes Stress-Netto-R
ein sinnvoller getrennter Versuch. Das macht Classification nicht allgemein
falsch. Auch eine Nullschwelle garantiert bei Schätzfehlern keine Schadensfreiheit.

Claudes präzisierte Kalibrierung für später:

1. Ziel `y = Stressnetto / geplantes Stoprisiko`; Definition des Risikos
   bleibt innerhalb des Vergleichs identisch. Keine nachträgliche Stutzung.
2. Modell mit festen Parametern: Ridge wie MR1; optional TabPFN-v2-Regressor
   erst nach separater Gewichts-/Versionsbindung.
3. Innerhalb des äußeren Trainings kreuzweise Prognosen `z` erzeugen.
4. `a = mean(y)`, `b = clip(cov(z,y)/var(z),0,1)`; bei konstanter Prognose
   `b=0` vorab definieren. Kalibrierter Wert `a + b*(z-mean(z))`.
5. Nur bei erwartetem Wert unter null auslassen. Die bisherige
   20%-Trainingsquantilschwelle wird damit als eigenständige Regel untersucht.
   Ist `a<=0`, bleibt das Gate nach diesem Vorschlag inaktiv; eine generelle
   Nicht-Handeln-Entscheidung wäre ein eigener Versuch.

Alle Größen der Kalibrierung kommen aus bereits bekannten Trainingsdaten,
nicht aus dem späteren Prüfblock. Die neue Regel braucht denselben nativen
Gate-Neulauf und vollständigen Kontoreplay; sie ist bisher kein Ergebnis.

## SI: die229 ES-Meldungen sind wirklich geladen

`SI/es-events-229.parquet` und CSV enthalten alle229 verifizierten
ES-Meldungen:187ICEBERG,42STOP,78Chicago-Kalendertage,165 verbundene
Überlappungsgruppen bei Fenstern `[Entscheidung−5min,Entscheidung+15min]`.
Alle Zeilen bleiben erhalten; Gruppen sind keine165 unabhängigen Beweise.
Keiner der229Datensätze hat einen späten Edit. Verfügbarkeit bleibt ein
Discord-Versandproxy, keine nachgewiesene Bookmap-Erkennung oder echte
Empfangszeit. Der Datensatz und sein identischer Parquet-Roundtrip sind in
MLflow dokumentiert; Importstatus ist ausdrücklich kein Modelltraining.

Für alle229Ereignisse umfassen die vorhandenen exakten Kontraktdateien
laut Metadaten den Kontext und Prognosehorizont. Noch fehlen die Prüfung
gültiger/lückenfreier Quotes und die entsprechend gebildeten Zielwerte.
Es werden keine Rohdaten gekauft. Sieben Überschneidungen mit HY104 im
festen15Minutenfenster begrenzen nur die Setup-Ablation, nicht die Zahl
separat geladener SI-Ereignisse.

Claude empfiehlt bei dieser Fallzahl kein eigenständiges ES-Modell als
belastbaren Prognosetest. Der bereits vorhandene RITHMIC-Bestand umfasst
1.746Meldungen: ES229,NQ907,GC208,CL402. Ein gepoolter späterer Test kann
mehr Fälle nutzen, braucht aber Markt-/Volatilitätsnormalisierung,
Quoteabdeckung und zeitlich getrennte Prüfungen über alle Märkte hinweg.
Ein Poolvorteil ist kein Nachweis eines Vorteils speziell auf ES.

Sinnvoller nächster SI-Vergleich: auf **denselben** Ereignisepisoden
Kurs-/Volumenkontext allein gegen denselben Kontext plus vorher bekannte
SI-Attribute (Typ, berichtete Größe/Faktor, Zonenabstand/-breite). Primärer
Horizont15Minuten,5Minuten nur feste Nebenanalyse. Keine zufällige
Zeilenaufteilung, keine „kein Event“-Klasse aus Feedlücken und keine
nachträgliche Auswahl der besten Richtung oder Haltedauer. Der Vergleich
misst den Zusatznutzen der Attribute an beobachteten Meldungszeitpunkten;
die Nützlichkeit des Ereigniszeitpunkts selbst braucht weitere Kontrollen.

Keine Änderung laufender NinjaTrader-Simulationen, keine Orders,
keine kostenpflichtigen Modellaufrufe und keine neue Leaderboard-Freigabe.

## Primärquellen zur Methodik

- [PriorLabs TabPFN: fachliche Merkmale und Leistungsgrenzen](https://github.com/PriorLabs/TabPFN)
- [scikit-learn: zeitliche Trennung](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
- [scikit-learn: Gruppen dürfen nicht zwischen Training und Prüfung aufgeteilt werden](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupKFold.html)

Die unregelmäßig auftretenden Ereignisse werden nach Kalenderblöcken und
Gruppen aufgeteilt; ein Standard-Zeilensplit ersetzt diese Konstruktion nicht.

## Tatsächlich gemessen: erster Geometrietest

Der vorab veröffentlichte einzelne Messversuch ist abgeschlossen:347Kandidaten,
Rangkorrelation0.107217, bedingter einseitiger Nullrang
0.081918 aus1.000Sitzungspermutationen. Die5%-Hürde
wurde nicht erreicht. Die Richtung entspricht der Hypothese und ist mit dem
Nullbefund vereinbar. Kein Geometrie-Gate, keine neue Modellanpassung und
keine neue Auszahlungsbehauptung.

Alle6nativen Beobachterabschnitte haben3identische Replikate und dieselben
ursprünglichen Trades/Kandidaten/Merkmale/Signalquotes geliefert. Alle5
physisch gekürzten Prefix-Läufe bestanden (181Paritätszeilen, darunter
2Entscheidungen vorMinute60). Die ursprünglichen Kassen-Ergebnisdateien
sind bytegleich erhalten. Der ganze Prüfbereich bleibt begrenzt; die
zusätzliche native absichtlich undichte OR-Positivkontrolle ist noch offen.

## Abschließende tatsächliche Rückmeldung nach dem Messbefund

Claude hat auch die fertigen Zahlen0,107/0,082 eingeordnet und ausdrücklich
keine nachträgliche Lockerung der Hürde oder Teilgruppensuche empfohlen.
Priorität jetzt: gepoolteSI-Daten bis zum geprüften und eingefrorenen
Zustand aufbereiten, noch ohne Modell. Dafür fehlen je Episode gültige
frische Einstiegs-/Ausstiegsquotes, Kosten- und Sitzungsgrenzen, vor den
Labels festgelegte Kontrollzeiten und eine eingefrorene Forward-Fallzahl.
Die alten Monate sind bereits vielfach ausgewertet. Eine spätere Analyse
bleibt vorläufig, bis neue Daten sie bestätigen.

Eine wichtige Umsetzungsgrenze: Die von Claude vorgeschlagene reine
Nachauswertung des Null-Gates aus gespeicherten kreuzweisenMR1-Prognosen
ist mit dem vorhandenen Bestand nicht vollständig möglich. Gespeichert
sind äußere Prüfprognosen und Fold-Zähler, keine vollständigen inneren
Kalibrierprognosen. Sie werden nicht aus späteren Testausgängen ersetzt.
Ein erneuter Fit nur zur Rekonstruktion bräuchte eine getrennte
registrierte Auswertung; in diesem Schritt wurde er nicht gemacht.
