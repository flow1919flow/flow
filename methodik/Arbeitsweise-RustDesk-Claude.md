# Arbeitsweise: Mac, RustDesk, Windows und Claude

## Rollen

- Auf dem Mac liegen Code, Marktdaten, SQX-Forschung, MLflow und Dokumentation.
- RustDesk zeigt den Windows-PC mit NinjaTrader. RustDesk ist die Fernbedienung; Rust als Programmiersprache ist hier nicht gemeint.
- NinjaTrader führt vier getrennte lokale ES-/NQ-Simulationen aus. Der Provider-Kontoreplay bleibt eine getrennte historische Auswertung.
- Der bestehende echte Claude-Chat heißt **„Backtest von Scotts Setups – Nautilus“**. Er ist für Gegenprüfung vorgesehen. Eine Codex-Unteraufgabe ist keine Claude-Antwort.

## Eine Windows-Prüfung

1. Zuerst verfügbare Computerwerkzeuge und erlaubte Apps prüfen. Nach Kontext-/App-Neustart ihre Dokumentation laden und aktuelle App-/Fensteransicht anfordern.
2. RustDesk öffnen/auswählen, richtige Fernsitzung und Monitorbelegung anhand der sichtbaren Ansicht prüfen. Nicht von früheren Koordinaten oder dem zuletzt gewählten Monitor ausgehen.
3. Frische Ansicht des NinjaTrader-Control-Centers: Verbindung, vier richtige Strategie-/Kontozuordnungen, Enabled, Sync, Positionen, Orders und Fehlermeldungen lesen.
4. Charts prüfen: Sitzung und Countdown, Historien-/Warmlaufstatus, News-Gültigkeit, Indikatorlabels, aktuelle Sequenz und zugehörige Chartmarkierungen. Ein eingezeichnetes Signal ist nicht automatisch ein Fill.
5. Bei Abweichungen zunächst Executions/Log und gespeicherte Diagnosebelege lesen. Code-, Feed-, Sitzungs-, Zeitzonen- und Kontomodellunterschiede getrennt untersuchen. Ein sichtbarer finaler Bandkontakt beweist keinen intrabar Kontakt zum früheren Tick.
6. Ergebnis mit Beobachtungszeit dokumentieren. Ohne aktuelle Ansicht keine Aussage „läuft jetzt“ machen.

Keine Testorder senden. Kein Konto resetten, keine Position schließen, keine Strategie deaktivieren/neu aktivieren oder Handelslogik ersetzen, wenn der konkrete Auftrag das nicht autorisiert. Einen abgeschalteten Sim-Kontolauf nicht eigenmächtig als neuen Kauf fortsetzen.

Dateitransfer verwendet die separate RustDesk-Ansicht. Ein erforderliches Passwort gibt der Nutzer direkt dort ein. Nur konkrete freigegebene Dateien übertragen; keinen Ordner mit Zugangsschlüsseln kopieren. Neue ausführbare Pakete zuerst offline prüfen, versionieren und mit SHA-256 binden; anschließend die vom Bedienwerkzeug erforderliche Bestätigung unmittelbar vor Installation einholen. Import, native Kompilierung, Instanzparameter und Sichtprüfung getrennt belegen. Im flachen Zustand arbeiten, sofern der Auftrag Änderungen erlaubt.

## Gegenprüfung mit Claude

1. Den bestehenden Chat über seinen Titel finden und den Kontext lesen, bevor gesendet wird. Nicht versehentlich in einem anderen Claude-Chat schreiben.
2. Konkrete Frage, Regeln, Quellen, Codeversion und Prüfziel senden. Zugangsdaten und Roh-Ticks nicht teilen. Bei sensiblen neuen Daten die konkrete Freigabe beachten.
3. Bei Blindprüfung erwartete Ergebnisse zurückhalten; anschließend tatsächlich gelieferte Ergebnisse vergleichen. Eine Meinung zu berichteten Zahlen ist keine unabhängige Nachrechnung der vollständigen Matrix.
4. Antwort vollständig lesen, Änderungen/Einwände dokumentieren und Grenzen der Prüfung nennen. Keine neue Zustimmung aus einer älteren Antwort ableiten.

Die Fragen zu Modellwahl/DeepInfra, ML-Methodik, Kalendercode, Micro-Fairness und Research-Agent-Vorarbeiten wurden nach Wiederherstellung der Werkzeuge am 20.11.2026 im bestehenden echten Claude-Chat gesendet. Die Antwort wird als neue Prüfung getrennt vom älteren Review geführt. Die ältere tatsächliche L2-Logit-Empfehlung liegt lokal in `outputs/Micro-RiskSize-20261120/Claude-Abschluss-Einordnung.txt`.

## Betriebsregeln

Die Handelsstrategie und das Kontomodell sind unterschiedliche Ebenen. Neues ML oder neue Anzeige darf nicht still in die vier Simulationen gelangen. Native SQX-Berichte, Ausführungsmodell und mehrstufiger Anbieter-Replay bleiben getrennte Belege. Gleiches Datum, Warm-up, Gebühren, News-Profil und Fillmodell sind Voraussetzung eines gepaarten Vergleichs.

Bei fehlender Computersteuerung keine Umgehung über andere UI-Automation oder ungesicherte Fernschnittstellen bauen. Auf Dateiseite darf unabhängig gearbeitet werden; dadurch entsteht aber kein neuer Sichtbeleg des Windows-PCs.
