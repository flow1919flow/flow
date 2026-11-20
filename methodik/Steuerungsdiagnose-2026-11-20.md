# Computersteuerung nach dem App-Update

## Nachtrag: Zugriff wiederhergestellt

Nach einem weiteren App-Neustart am 20.11.2026 wurden die `cua_repl`-Werkzeuge wieder bereitgestellt und tatsächlich erfolgreich aufgerufen. RustDesk zeigte die vier Windows-NinjaTrader-Charts; anschließend wurde der bestehende echte Claude-Chat geöffnet und die sechs Gruppen offener Fragen abgesendet. Der Nutzer hatte „Any App“ bereits zuvor als eingeschaltet bestätigt. Es wurde keine Sicherheits- oder Plugin-Einstellung geändert. Welcher Teil des Neustarts die Bereitstellung wiederhergestellt hat, ist nicht nachgewiesen.

Der folgende Befund beschreibt den vorherigen Ausfall, nicht mehr den aktuellen Werkzeugzustand. Bei einem neuen Ausfall zuerst die tatsächlich verfügbare Werkzeugliste prüfen.

## Beobachteter Befund

Die vorher in dieser Sitzung verwendeten `cua_repl`-Werkzeuge wurden nach dem App-Update als nicht mehr verfügbar gemeldet. Deshalb ist weder die Claude-App noch RustDesk/Windows aus diesem Chat bedienbar. Dies ist kein belegter Claude-Loginfehler.

Am 20. November lesend geprüft:

- ChatGPT-Desktopversion `26.1117.31558`, gebündelte Codex-CLI `0.171.0-alpha.13`.
- Die CLI meldet das Feature `computer_use` als aktiviert.
- Lokale Konfiguration: `unified-computer-use@openai-bundled` und `computer-use@openai-bundled` sind beide `enabled=true`.
- Das Desktoplog nach dem Neustart meldet den verwalteten Computer-Service als verfügbar und führt beide Komponenten im gebündelten Marketplace auf.
- In den zwei geprüften üblichen Pfaden wurde keine sperrende `requirements.toml` gefunden. Das schließt eine anders ausgelieferte Workspace-Policy nicht aus.
- Ein älterer Chat enthält erfolgreiche RustDesk-/CUA-Aufrufe vor dem Update. Das ist kein neuer Funktionstest.
- Die aktuelle Werkzeugliste enthält trotzdem keine Computersteuerungswerkzeuge.
- Die gebündelte Definition des Servers `cua_repl` enthält `enabled: false`, obwohl die umgebenden Plugins als installiert/aktiviert gelistet werden. Die Ursache dieser Diskrepanz wurde nicht nachgewiesen. Das interne Manifest enthält keinen vollständigen Serverstart und wird nicht eigenmächtig umgeschrieben.

Damit ist die Ursache noch nicht bewiesen. Der Befund grenzt den Fehler auf Bereitstellung/Aktivierung der Bedienwerkzeuge oder deren Sitzungskontext ein; er beweist weder einen bestimmten Cachefehler noch eine generelle Produktstörung. Keine Zugriffseinstellung wurde bei dieser Diagnose geändert.

## Quellen und nächster Test

Die aktuelle [offizielle Anleitung](https://learn.chatgpt.com/docs/computer-use) nennt **Settings → Computer use → Control → Any App**. Eine Plugin-Seite ist nur eine alternative Oberfläche. Deshalb war die pauschale frühere Anweisung „Computer Use unter Plugins suchen“ für die Oberfläche des Nutzers nicht verlässlich. Auf macOS sind Bildschirmaufnahme und Bedienungshilfen zusätzlich erforderlich; ihr Fehlen wurde hier nicht nachgewiesen.

Sinnvolle Tests: vorhandenen Any-App-Status ansehen, falls der Eintrag verfügbar ist; einen neuen Chat mit einem eng begrenzten lesenden App-Auftrag prüfen; anschließend kontrollieren, ob die Computerwerkzeuge tatsächlich bereitgestellt werden. Ein neuer Chat ist ein Diagnosetest, keine garantierte Reparatur. Nicht wiederholt Mac, Windows oder Claude auf Verdacht neu starten. Persistiert der Fehler bei bereits aktiviertem Dienst, diese Fakten in eine Produkt-Fehlermeldung aufnehmen.

Der Nutzer hat anschließend ausdrücklich bestätigt: **„Any App“ ist eingeschaltet.** Eine fehlende Freigabe dieses Schalters erklärt den Ausfall damit nicht. Auch nach dieser Antwort enthält die aktuelle Werkzeugliste keine Computersteuerung. Der nächste sinnvolle Test ist ein neuer Chat mit einem rein lesenden Bildschirmauftrag. Falls dort dieselben Werkzeuge fehlen, den dokumentierten Versions-/Serverbefund an den Produktsupport geben. Die Ursache bleibt offen; keine Reparatur ist nachgewiesen.

Die genauen Rohlogs und Konfigurationen werden wegen möglicher privater Inhalte nicht im öffentlichen Repository veröffentlicht. Keine Zugangsdaten, Remote-IDs oder persönlichen Nachrichten sind Teil dieses Berichts.
