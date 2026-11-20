# Kostenloser FRED-/Fed-Kalender · installierter Stand

Diese Quellen entsprechen dem geprüften Windows-Updater v2. Installation und tatsächlicher Start über die Aufgabenplanung wurden mit zwei aufeinanderfolgenden Generationen belegt; siehe [Abnahme](acceptance-summary.json). Ein zukünftiger Timerlauf oder echter Neustart wurde dadurch nicht physisch getestet.

`FreeCalendarRunner.ps1` holt Release-Tage von FRED und offizielle Fed-Kalender, prüft vollständige Kategorien und publiziert unveränderliche Daten/Quellenbelege vor dem atomisch ersetzten Manifest. Ein erfolgreicher vollständiger Abruf erneuert die Frische um 24 Stunden. Bei Fehlern bleibt die letzte gute Generation unverändert. Der installierte Task heißt **HY Free News Calendar**, läuft alle vier Stunden und beim Benutzer-Login. Er setzt keine Orders ab.

Der persönliche FRED-Schlüssel wird ausschließlich auf Windows für den angemeldeten Benutzer mit DPAPI verschlüsselt gespeichert. Er ist kein Bestandteil dieses Repositorys. Diese Veröffentlichung enthält weder Schlüssel noch Windows-Keystore, private Profile oder Aufgabenexport mit Zugangsdaten.

FRED liefert Tage, keine genauen Veröffentlichungsuhrzeiten. Für CPI/NFP gilt die eingefrorene geprüfte Zuordnung 08:30 America/New_York mit Sommerzeit. Außerordentliche Uhrzeitänderungen und frühere Terminrevisionen sind damit nicht vollständig bekannt. Der Fed-Parser und die nachgeschaltete ursprüngliche Kalenderprüfung akzeptieren nur das definierte Format und Profil. Bei unklaren Änderungen keine Frische erfinden oder verlängern.

Prüfumfang: 23 Komponentenassertionen mit echten Fed-Monatsseiten und synthetischem FRED-XML; anschließend echte Windows-FRED-Abnahme, 699 kompilierte Fälle des unveränderten Ninja-Kalenderlesers und 64 byteidentische archivierte SQX-Eingabevergleiche. Kein Nachweis einer vollständig historischen Point-in-time-Newsdatenbank und keine neue Strategieergebnisberechnung.

Die Quellen sind für die Prüfung/Übergabe veröffentlicht. Im laufenden Windows-Betrieb nichts neu installieren oder überschreiben, ohne den tatsächlichen Zustand, das konkrete Paket und den Nutzerauftrag abzugleichen. [Betriebs- und Übergabestand](../AKTUELLER-STAND.md).
