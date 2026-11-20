# SI als mögliche zusätzliche Information · Entwurf

Status: auf Nutzerwunsch vorbereitet, an Claude als Nachtrag in die Warteschlange gestellt. Kein neuer Datensatz, kein Modelltraining und kein neuer Strategielauf ausgeführt. Nicht als vorab eingefrorenen fertigen Versuch ausgeben.

## Bereits vorhanden

`outputs/SI-Gradient-Boosting-10min-v1/letzter_lauf.json` belegt den von Flo am 09.11. gestarteten abgeschlossenen Versuch. Er verglich unter anderem nichtlineare Gradient-Boosting-Modelle, Ridge und lineare MAE mit Grundraten. Entscheidung nach zehn Minuten Beobachtung plus zwei Sekunden; Hauptziel war die weitere Fünf-Minuten-Midpointbewegung. Im Hauptziel 737 spätere Ereignisprognosen auf vier Märkten, kein belastbarer Vorteil gegenüber Trainingsmedian nachgewiesen. Das war keine Fill-/Anbieter-Auszahlungsprüfung. Die ursprüngliche Voll-Rohdatenabnahme ist in diesem Ordner nicht vollständig belegt.

Damit ist „bisher kein Nutzen nachgewiesen“ angemessen; „SI kann grundsätzlich keine Information enthalten“ ist nicht bewiesen. Ein erstmals komplexerer Algorithmus allein ist keine neue Abgrenzung, weil nichtlineare Modelle bereits getestet wurden.

## Zwei getrennte Fragen

1. **Zusätzliche Information für die vorhandene Strategie:** Modell ohne SI gegen dasselbe Modell mit sehr wenigen festgelegten SI-Merkmalen auf identischen tatsächlich abgedeckten Sitzungen. Zunächst Vorhersagen auf zeitlich späteren Setups, anschließend kompletter nativer SQX-Neulauf und unverändertes Konto-/Auszahlungsmodell, falls ein Kandidat weiter geprüft werden soll.
2. **Neue Zusammenhänge außerhalb dieser Setups:** explorative Analyse von SI-Ereignis, vorab messbarem Regime und folgender Marktreaktion. Daraus abgeleitete Handelsregeln wären eigene Hypothesen und müssten auf späteren Daten geprüft werden. Eine interessante Untergruppe im bekannten Material ist kein neuer Edge-Nachweis.

Mögliche Merkmale zur Diskussion: gerichtete SI-Aktivität vor der Entscheidung, Abstand zur zuletzt gemeldeten SI-Zone und eine bereits beobachtete Preis-/Volumenreaktion. Die genaue Fensterlänge, Normalisierung und höchstens zwei bis drei Zusatzmerkmale sind vor dem Lauf festzulegen, nicht nach dem besten Ergebnis auszuwählen.

## Vor jeder Verknüpfung klären

Konkreter Bestandsbefund: `outputs/SI-Nautilus-Ereignistest-v1/source_reader.py` setzt `ts_init=max(sent, edited)` und kennzeichnet `discord_sent_proxy` beziehungsweise `discord_edited_proxy`. Das bildet die Archivmeldung als zeitliche Näherung ab, keinen nachgewiesenen originalen Bookmap-Ereignis- oder eigenen Bot-Empfangszeitpunkt. Diese Grenze muss im neuen Modellvergleich erhalten bleiben; aus einem erfolglosen verspäteten Meldungsmodell folgt nichts Allgemeines über native SI-Ereignisse.

- Welche Ereignisse mit welcher Quelle, Abdeckung, Revision und tatsächlichen Empfangs-/Verfügbarkeitszeit vorliegen. Ein später veröffentlichter Hinweis darf nicht zum früheren Ereigniszeitpunkt nutzbar werden.
- Abdeckungslücke und echtes Ausbleiben eines Events unterscheiden; keine Nullfüllung für Monate ohne Feed. Der gemeinsame Jahreskalender der Mini-/Micro-Vergleiche beweist keine ganzjährige SI-Abdeckung.
- Änderungen derselben Meldung, nahe Ereignisse und gleichzeitige Marktbewegungen zusammenfassen; nicht als zusätzliche unabhängige Stichproben zählen.
- Modell-, Zeit- und Kostenvergleich vorher begrenzen. Kontrollen ohne SI sowie passende Kontrollzeiten/zufällige Zuordnungen und Tag-/Wochenblöcke berücksichtigen.
- Aus früheren negativen SI-Tests lernen, statt denselben bekannten Zeitraum durch immer mehr Modelle und Untergruppen erneut zu durchsuchen. Noch nicht beobachtete spätere Daten bleiben die entscheidende Bestätigung.
