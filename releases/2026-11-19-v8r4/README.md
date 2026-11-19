# AccountReplay V8r4 · installierter Stand vom 19. November 2026

NinjaTrader bestätigte den erfolgreichen nativen Import. Die anschließend aus Windows zurückgeladenen vier Quelldateien stimmen bytegenau mit dem geprüften Kandidaten überein. Alle vier lokalen Instanzen waren aktiviert, synchronisiert und flat.

## Umfang

- Drei Strategieklassen und der gemeinsame HYAccountReplayV8-Kontocode.
- Persistente relative Kontobilanz, Gebühren, EOD-Hoch, Verlustgrenze, Auszahlungen und terminaler Kontostatus nach den gespeicherten Kontomodellen.
- Ausführungsabgleich, exklusives Kontojournal, Prüfsummen, atomare Speicherung und Schutz vor älteren zurückgespielten Kontoständen.
- Keine Änderung an Signal-, Indikator-, Einstieg-, Strategie-Stop- oder Zielregeln; kein neuer vorbeugender Risiko-Einstiegsfilter.
- Ausschließlich die vier fest zugeordneten lokalen Sim-Konten. Keine Provideraktivierung und keine Testorders.

## Nachweise

[Native Abnahme](proofs/native-acceptance.json), [installierte Quellhashes](proofs/native-install-source-match.json), [Kontomodelltests](proofs/account-tests.json), [Integrationstests](proofs/bridge-tests.json), [Speicherung in getrennten Prozessen](proofs/cross-process-tests.json), [Claudes Codeprüfung](proofs/claude-review.json).

Die tatsächliche C#-Kontoklasse bestand 165 Speicher-/Grenzprüfungen. 32 synthetische Szenarien lieferten 385 exakte Tagesvergleiche mit den gespeicherten Python-Kontomodellen. 71 Integrationstests benutzen ausdrücklich nachgebildete Vendor-Schnittstellen. Vier native Negativproben entfernten je einen echten Ausführungsfakt ausschließlich aus einer Journal-Kopie: diese wurde korrekt gesperrt und blieb nach Wiederöffnung gesperrt. Nach Deaktivieren/Aktivieren der vier Hauptinstanzen waren ihre produktiven Journale bytegleich; Gebühren wurden nicht erneut abgezogen.

R3 scheiterte beim nativen Compiler an einer nur für NQ vorhandenen Diagnosefunktion, die versehentlich auch in ES aufgerufen wurde. R4 entfernt genau diese zwei Aufrufe. Die ES-Testnachbildung wurde korrigiert, die Integrationstests erneut ausgeführt. Claude bestätigte das konkrete R4-Delta. Seine Prüfung war eine Codeprüfung ohne eigene C#-Ausführung.

## Was nicht als geprüft gilt

Der tatsächliche native EOD-Wechsel um 17:00 Eastern war am Prüfcheckpoint noch nicht erreicht. Ein kompletter Neustart des NinjaTrader-Prozesses wurde nicht durchgeführt; getrennte .NET-Prozesse und das native Neuladen der Strategien sind getrennte Nachweise. Der bevorstehende Wochenend-/Feiertagskalenderwechsel wurde auf Windows noch nicht beobachtet. Diese Abnahme ersetzt keinen neuen historischen Strategielauf, keine vollständige Roh-Tick-Parität und keinen OOS-Nachweis.

## Dateien und Installation

[Import-ZIP](AccountReplay-V8r4-ES-NQ-Sim-Import.zip) enthält die vier geprüften C#-Dateien. HYNewsCalendarV5 bleibt eine bestehende Abhängigkeit: [Quelle](../../ninjatrader/HYNewsCalendarV5.cs) und [Kalenderfassung](calendar/). Die News-Daten werden nicht durch diese ZIP automatisch aktualisiert.

Produktive Kontojournale, Migrationsseeds und rohe Marktdaten werden nicht veröffentlicht. Eine neue Installation ohne geprüftes Journal startet absichtlich kein frisches Konto. Ein autorisierter neuer Sim-Versuch bekommt eine neue Testepoche; der alte Lauf bleibt erhalten. Keine Journaldateien zur Wiederbelebung derselben gescheiterten Epoche löschen.

Die Dateien unter tests sind die verwendeten Testquellen und Fixtures. Die ursprünglichen Python-Prüfskripte referenzieren das lokale Forschungsprojekt und das damalige .NET-SDK; sie sind Belegquellen und kein fertig portiertes Installationsprogramm.

## Nachtrag: NQ-Sim-Versuch 2

Die beiden NQ-Instanzen wurden um 21:14 Uhr Vaduz mit einer ausdrücklich neuen Testepoche gestartet und blieben beim Check um 21:18 Uhr aktiviert und synchronisiert. Native neue Journale, monotone Prüfstände und übertragene Seeds wurden zurückgelesen und geprüft. Beide ES-Journale blieben bytegleich; ES wurde nicht deaktiviert oder neu geladen. Der gespeicherte Workspace enthält vier Charts. [Prüfbericht](proofs/nq-run2-native-acceptance.json). Die acht bisherigen gefüllten Orders blieben unverändert; keine Testorder wurde gesendet. Die bekannten noch offenen nativen Prüfungen bleiben offen.
