# Abschluss · 18 echte Modellarme · 21.November2026

Alle14 lokalen Arme und vier DeepInfra-Arme sind abgeschlossen und in MLflow als FINISHED verifiziert. Quelle sind159 echte HY104-EMA22-Setups;110 identische spätere Prüffälle,keine C28.03-Ersatzkohorte und keine isolierten15-Minuten-Kurslabels nach SI.

70 tatsächliche lokale Fits erzeugten1’540 Prognosen. DeepInfra lieferte440 Hauptprognosen und44 unverändert reproduzierte Wiederholungen;alle484 API-Antworten wurden unabhängig gegen den eingefrorenen Plan geprüft. Es wurden keine Antworten ersetzt,keine Prompts optimiert und keine Folgeaufrufe angehängt.

| Modell | Treffer Kurs → +SI | LogLoss Kurs → +SI | Brier Kurs → +SI |
|---|---:|---:|---:|
| Drex Max Finance | 51,8% →57,3% |0,745997 →0,747851|0,273285 →0,270965|
| Clef |40,0% →40,0%|0,800820 →0,831057|0,301162 →0,314454|
| Trainingshäufigkeit ohne Zusatzmerkmale |60,0%|0,677535|siehe lokale Ergebnisdatei|

Bei Drex steigt die Trefferquote,aber LogLoss verschlechtert sich geringfügig und Brier verbessert sich geringfügig. Die gepaarten LogLoss-Änderungen durch SI liegen für beide Modelle innerhalb eines Intervalls,das null einschließt: Drex−0,001854 [−0,038894;+0,027699],Clef−0,030237 [−0,071891;+0,009323];positive Werte hätten SI begünstigt. Das liefert keinen belastbaren zusätzlichen Prognosevorteil. Nur8 Prüffälle hatten einen archivierten15-Minuten-Treffer und26 einen60-Minuten-Treffer. Es ist kein Beweis,dass SI allgemein informationslos ist.

Die lokale vollständige Übersicht enthält alle sieben festen Modellfamilien je Kontextarm. RidgeClassifier,LinearSVC und Perceptron liefern rohe Entscheidungswerte;dafür wurden keine Wahrscheinlichkeiten und keine LogLoss-/Brier-Werte erfunden. Native Wahrscheinlichkeiten anderer Modelle wurden nicht als unabhängig kalibriert dargestellt.

Konservativ reserviert0,9507696USD;Schätzung anhand der gemeldeten1’223’916 Input-Tokens und zitierten Modellpreise0,21545904USD. Die tatsächliche Providerrechnung wurde nicht ausgelesen. Laufende Sims,Handelslogik und Auszahlungszahlen blieben unverändert;kein neues Gate oder Kontoreplay wurde berechnet.

Belege: Public/cloud-results.json,Public/cloud-independent-acceptance.json,Public/tracking-acceptance.json,Public/mlflow-receipt.json und die lokalen Modellnachweise. Der lokal angezeigte vollständige Bericht ist Stand.html. Die JSON-Dateien cloud-plan,API-readiness und feature-freeze sind erhaltene Vorab-/Zwischenstände;ihre damaligen Angaben zu noch nicht gestarteten Aufrufen beschreiben den dokumentierten Zeitpunkt.

---

# SI-Zusatzinformation für echte HY104-EMA22-Setups

Dieser Versuch beantwortet die korrigierte Nutzerfrage: Helfen bereits bekannte
SI-Meldungen bei der Vorhersage des tatsächlichen HY104-EMA22-Tradeausgangs?
Der frühere eigenständige Kursverlaufstest nach SI-Meldungen und die C28.03-Funded-
Kohorte beantworten andere Fragen und werden hier nicht als Ersatz verwendet.

## Tatsächlicher Datenstand

Die Quellen sind die bereits verifizierten strikten nativen EMA22-Läufe unter
`outputs/NQ-Woche-20261118/ema22-history-acceptance-20261119/ES/SQX/evaluation`.
EntryAverageCase5 ist EMA22; OpeningRange0; Zielversatz0,75Ticks. Das sind die
ausgeführten ursprünglichen Strategie-Trades, keine beliebigen nachträglich
erzeugten Signale. Keine neue SQX-Ausführung wurde behauptet.

Aus348 Trades des gemeinsamen Jahres bleiben159 nach der ersten verfügbaren
ES-Archivmeldung plus30Sekunden:28.05.–30.10.2026. Jeder spätere Trade gehört zur
Kohorte, unabhängig davon, ob an seinem Tag weitere Meldungen archiviert sind.
Die frühere Zahl112 beschreibt lediglich Trades an Tagen mit irgendeiner
archivierten ES-Meldung und ist ausdrücklich NICHT die gewählte Testpopulation.

Alle159 haben gültigen vergangenen TBBO-Kontext;95 exakte Kontraktdateien sind
gegen ihre Import-Prüfsummen kontrolliert.159 physische Zukunftsabschneidungen
lassen Preis- und SI-Merkmale unverändert;760 skalare Quote-Werte sind zusätzlich
mit den nativen Nautilus-Price/Quantity-Dekodierern verglichen. Die Merkmale wurden
eingefroren, bevor der Labelbauer die Exit-/PnL-Spalten auswertete.

Die Labels stammen vom tatsächlichen nativen Strategieausstieg: native4,68USD
Gebühren auf5,74USD normalisieren,also1,06USD abziehen; zusätzlich25USD für einen
schlechteren ES-Tick je Seite. Positiv ist danach Netto>0. Es gibt95 positive und
64 nichtpositive Fälle. Das sind kostenangepasste ursprüngliche Tradeausgänge,
keine neuen Fill-/Gate-/Prop-Kontoreplays und keine festen15-Minuten-Kurslabels.

## Gemeinsamer Vergleich

Acht vergangene Preis-/Setupmerkmale: Seite,Chicago-RTH-Minute,gerichtete60s-
und300s-Bewegung relativ zur vergangenen300s-RV,log1pRV in Ticks,Spread,gerichtete
Top-Size-Imbalance und Quotealter. Sie sind generischer TBBO-Kontext an der
nativen Entscheidung, nicht übernommene C28.03-Indikatorwerte.

SI ergänzt ausschließlich den letzten STOP-Pfeil und ICEBERG-Pfeil innerhalb
15Minuten relativ zur Trade-Seite sowie die Anzahl archivierter Nachrichten der
letzten60Minuten,gekürzt auf5. Nur229 eigene ES-RITHMIC-Meldungen,derselbe exakte
Kontrakt,Verfügbarkeit=max(Sende-,Editzeit),mindestens30Sekunden vor Entscheidung.
Andere Märkte werden nicht zu ES-Setups. Die Bot-Pfeile werden nicht als bewiesene
aggressive Kauf-/Verkaufsrichtung interpretiert.

Kein Treffer bedeutet null/NaN plus ausdrücklich unbekannte Archivabdeckung,
nicht bewiesene SI-Abwesenheit. Status+1 bedeutet archivierten Treffer;−1 bedeutet
keinen archivierten Treffer bei weiterhin unbekannter Feed-Abdeckung. Im gesamten
Zeitraum haben nur8 Setups einen Treffer innerhalb15Minuten und27 innerhalb60.

Die ersten mindestens48 Fälle dienen dem Training;eine ganze Chicago-Tageslücke
folgt. Fünf spätere20-Geschäftsdatumsblöcke ergeben110 Prüffälle an67 Tagen vom
10.07.–30.10.2026. Darunter nur8 mit15-Minuten- und26 mit60-Minuten-SI-Kontext:
**geringe Aussagekraft,SI-Teilgruppen ausschließlich beschreibend.**

Vier Cloud-Arme: Drex Max Finance und Clef,jeweils Preis-/Setupkontext allein
gegen denselben Kontext plus kausale SI-Merkmale. Identische Fälle,Labels,Falten
und32 frühere abgeschlossene Trainingsbeispiele;ein aktuelles Setup pro Aufruf.
Sechs signifikante Stellen,keine Datums-,Kontrakt-,Preisniveau-,ID- oder Zukunfts-
Angaben an die API. Kein Training großer Gewichte und keine Prompt-/Parametersuche.

Primär wird die gepaarte Verbesserung von LogLoss und Brier durch SI je Modell
gemessen; AUC/Rang und Teilgruppen sind zusätzliche Diagnosen. Die feste Unsicherheit
verwendet1999 bewegliche Fünftages-Blockbootstrap-Züge. Das mehrfach untersuchte
Entwicklungsjahr ist keine frische OOS-Bestätigung und kein Kausalitätsnachweis.

## Ausführung und Belege

`Public/dataset-manifest.json` bindet die gemeinsame CSV-,NPY- und Faltenfassung
für die Cloud- und lokalen Modelle. `Public/cloud-plan.json` bindet den Cloud-Code
und alle Aufrufkörper. `Public/cloud-offline-tests.json` dokumentiert13 bestandene
Offlineprüfungen einschließlich explizit synthetischer HTTP-/Auswertungsfälle.
Diese Fixtures sind keine realen Modellvorhersagen.

Geplant sind440 Hauptaufrufe und44 vorher anhand der Metadaten gewählte identische
Wiederholungen. Die konservative gesamte Reservierung beträgt0,9507696USD bei
höchstens4500 serialisierten Bytes plus2048 Wrapper-Tokens und0,30USD/M je Modell.
Keine automatische Wiederholung nach API-/Schemafehlern;keine Weiterleitung
authentifizierter Requests. Die wirkliche Rechnung ist dadurch nicht nachgewiesen;
Preis-Schätzungen sind getrennt von Providerabrechnungen zu lesen.

Root kontrolliert den verdeckten lokalen Schlüsselzugang,die konkrete Freigabe
und den Start. Der API-Runner wird standardmäßig nur vorbereitet und nicht
automatisch ausgeführt. Zugangsschlüssel werden nicht in Dateien oder Logs
gespeichert. `Private` enthält vertrauliche Eingabe-/Antwortzeilen und bleibt lokal.
Laufende NinjaTrader-Simulationen und produktive Leaderboards werden nicht geändert.
