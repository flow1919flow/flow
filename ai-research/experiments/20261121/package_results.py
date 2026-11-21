"""Prepare a reviewed allowlist of completed public research evidence."""
from pathlib import Path
import json, hashlib
from native_check import HERE, DE, read, write, sha

REPO=DE/'outputs/AI-Forschung-20261120/repo'
BASE='ai-research/experiments/20261121'
ARMS=['ML1C','ML8','MR1','ML9']

def main():
    summary=read(HERE/'summary.json'); assert summary['state']=='complete'
    assert read(HERE/'Controls/parallel-execution.json')['state']=='complete'
    assert read(HERE/'run-status.json')['state']=='complete'
    public=HERE/'Public'; public.mkdir(exist_ok=True)
    allow=['README.md','preregister.json','preregister-v1.json','preregister-v11.json',
        'preregister-github-receipt.json','preregister-github-receipt-v1.json','preregister-github-receipt-v11.json',
        'implementation-amendment.json','tabpfn-numerical-amendment.json','tabpfn-batch-diagnosis.json',
        'tabpfn-weight-proof.json','tabpfn-environment.lock.txt','tabpfn-synthetic-smoke.json',
        'train-ML9-batch-audit-failed.log','Training/ML9/batch-audit-failed-progress.json',
        'MLflow/ML9-batch-failed-original.json','cash-attempt1-missing-dependency.log',
        'research.py','research-v11-executed.py','native_check.py','accept_prefix.py','replay.py','track.py',
        'run.py','finish.py','parallel_null.py','make_report.py','package_results.py','si_feasibility.py',
        'operational-resume.json','native-source-proof.json','prefix-progress.json','prefix-additional-acceptance.json',
        'cash-environment-correction.json','cash-environment.lock.txt',
        'summary.json','native-acceptance-summary.json','Ergebnisse.html',
        'input-dataset-manifest.json',
        'Controls/results.json','Controls/execution-provenance.json','Controls/family-null.json',
        'Controls/parallel-execution.json','Cash/design-before-results.json','Cash/results.json',
        'Controls/family-sequential-partial.json',
        'SI/feasibility.json','Source/HYML1ESResearch.java']
    allow += [f'Training/{a}/results.json' for a in ARMS]
    exports={}; manifest=[]
    for relative in allow:
        p=HERE/relative; text=p.read_text()
        # Export path normalization is explicit and hash-bound, not a claim
        # that the normalized public bytes equal the executed local source.
        normalized=text.replace(str(DE),'${HY_WORKSPACE}').replace(str(Path.home()),'${HOME}')
        path=f'{BASE}/{relative}'; exports[path]=normalized
        manifest.append(dict(path=path,local_source_sha256=sha(p),
            public_sha256=hashlib.sha256(normalized.encode()).hexdigest(),
            local_home_path_normalized=(text!=normalized)))
    for path,text in exports.items():
        target=public/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
    write(public/BASE/'public-export-manifest.json',dict(state='allowlisted_export',files=manifest,
        excluded=['raw quotes/ticks/carriers','per-candidate feature rows','model checkpoint weights',
            'private messages and credentials','Windows account identifiers','raw licensed papers'],
        normalization='Only workspace/home path strings replaced; source and exported hashes recorded separately.'))
    table=['| Funded-Modell | Normal Ø | Normal Median | Tickstress Ø | Tickstress Median |',
           '|---|---:|---:|---:|---:|']
    for row in summary['comparison']:
        values=[row[k] for k in ['normal_mean','normal_median','stress_mean','stress_median']]
        table.append('| '+row['name']+' | '+' | '.join(f'{x:,.2f} USD' for x in values)+' |')
    overview='\n'.join(table)
    note=f'''# Neue ML-Vergleiche abgeschlossen · 21. November 2026

**Built with PriorLabs-TabPFN.** Vier neue Modellarme wurden tatsächlich trainiert,
auf späteren Zeitblöcken bewertet und über 24 native SQX-Gate-Jobs sowie die
unveränderte Anbieterengine vollständig bis zum Endbargeld gerechnet.

{overview}

Gemeinsame Basis: 1.000 USD Kaufbudget, MFF Rapid EOD 50k, Eval HY104-EMA22,
Funded C28.03, 242 Sitzungen vom 24.11.2025 bis 30.10.2026. 143 überlappende
Startfenster mit je 100 Sitzungen sind keine unabhängigen Experimente.
Endbargeld enthält unverbrauchtes Budget; Gewinn ist Endbargeld minus 1.000 USD.
Tickstress bedeutet einen Tick schlechter je Seite. Die akzeptierte Basis
wurde auf den Quote-/Kontopfaden exakt reproduziert.

347 eindeutige Kandidaten; neun äußere Zeitblöcke ergeben 230 spätere
Vorhersagen je Modell. Nur das Funded-Einstiegsgate ändert sich. Die ersten
Trainingssitzungen bleiben als Basis im Kontoverlauf. Keine Parametersuche:
L2-Logistik C=.1, flaches Gradient Boosting, Ridge alpha10 und TabPFN v2 mit
vier Ensemble-Schätzern und festem Seed. Schwellen kommen aus fünf
kreuzweisen Trainings-Sitzungsblöcken, nicht aus äußeren Testdaten.

ML1-Kontrollen: 1.000 gematchte Zufallsauslassungen und 1.000 vollständige
bedingte Pipeline-Permutationen. Vier neue Arme: dieselben 199 gemeinsamen
Sitzungspermutationen mit Maximum über die vier Rangkorrelationen. Das ist
eine bedingte Entwicklungsdiagnose, kein neuer OOS-Nachweis. Die Kontrollen
sind keine Verteilung aus 1.000 kompletten Zufalls-Kontoreplays.

Fünf physische SQX-Prefix-Schnitte und 181 frühere Paritätszeilen bestanden;
Signalquote und Stop wurden ebenfalls verglichen. Nur die fünf eigentlichen
Schnittentscheidungen haben ihre unmittelbare Zukunft vollständig entfernt.
Eine absichtlich undichte Kontrollspalte wurde vom Validator abgelehnt;
das ist kein Test eines absichtlich undichten nativen Modellfeatures.
Zusätzliche Randfall-/Zufallsschnitte und frische Forward-Prognosen bleiben offen.

Der erste TabPFN-Versuch stoppte an einer überstrengen numerischen
Sammel-/Einzelprüfung. Fehlerbeleg und vor dem neuen Fit veröffentlichter
Nachtrag bleiben erhalten. Tatsächliche Gates verwenden Einzelvorhersagen;
keine der neun Entscheidungen-Gruppen wechselte durch die gemessene
Sammelabweichung. Der Nullvergleich protokolliert seine Sammelrechen-Grenze.

SI: 229 archivierte ES-Meldungen, aber nur sieben spätere Setups mit einer
vorher verfügbaren Meldung im festen Fenster. Null verifiziert lückenlose
Feed-Sitzungen. Kein neues SI-Modell trainiert und Lücken nicht als null
Events behandelt. Frühere negative SI-Läufe bleiben erhalten.

Lokale MLflow-Oberfläche: http://127.0.0.1:5055/#/experiments/4 .
Native Engine: SQX144.2953 in einer isolierten Kopie. Kein Cloudaufruf,
keine DeepInfra-GPU, keine Datenkäufe und keine Änderung laufender Sims.
Claude prüfte den konkreten Versuchsplan und gab methodische Anregungen;
er hat die vollständigen neuen Kontoverläufe nicht unabhängig nachgerechnet.

[HTML-Ergebnisbericht](Ergebnisse.html), [Ergebnisse](summary.json),
[native Nachweise](native-acceptance-summary.json),
[Kontoreplay](Cash/results.json), [Kontrollen](Controls/family-null.json),
[SI-Abdeckung](SI/feasibility.json), [Vorabfestlegung](preregister.json).

Alle Ergebnisse betreffen das bereits vielfach ausgewählte Entwicklungsjahr.
Keine Aufnahme eines ML-Arms als bestätigt in ein produktives Leaderboard.
ML2–ML7 bleiben getrennte, noch nicht trainierte Registereinträge.
'''
    (public/BASE/'ABSCHLUSS.md').write_text(note)
    register=read(REPO/'ai-research/model-register.json')
    existing={m['id']:m for m in register['models']}
    for arm in ARMS:
        row=next(v for v in summary['comparison'] if v['arm']==arm)
        model=existing.get(arm,{'id':arm});model.update(name=row['name'],
            status='trained_native_gate_and_cash_complete_selected_year_not_adopted',
            result=f'experiments/20261121/Training/{arm}/results.json',
            normal_mean_end_cash_usd=row['normal_mean'],stress_mean_end_cash_usd=row['stress_mean'],
            fresh_OOS=False)
        if arm not in existing:register['models'].append(model)
    register['next_priority']=['No automatic adoption from selected year',
        'Freeze any further policy before future outcomes',
        'Expanded physical-prefix boundary audits',
        'Verified SI feed availability before any SI training']
    register['modern_tabular_comparison']='TabPFN v2 completed locally; exact licence/weight/package hashes retained. No cloud calls.'
    path=public/'ai-research/model-register.json';write(path,register)
    # Preserve earlier detailed studies, but make completion status unambiguous.
    for relative in ['AKTUELLER-STAND.md','ai-research/README.md']:
        old=(REPO/relative).read_text()
        if relative=='AKTUELLER-STAND.md':
            old=old.replace('Zusätzliche Zufallsauslassungs-/Permutationstests, eine vollständige native Zukunfts-Prefix-Prüfung, neue Claude-Gegenprüfung und frische Forward-Daten fehlen.',
                'Nachtrag21.11.: Zufallskontrollen und fünf native Prefix-Schnitte sowie die neue Claude-Planprüfung sind erledigt; erweiterte Randfallprüfungen und frische Forward-Daten bleiben offen.')
            old=old.replace('weitere Klassifikatoren und Ridge stehen im Register, sind nicht bereits getestet.',
                'vier neue Klassifikations-/Regressionsarme sind abgeschlossen; der Abschluss vom21.11. ist maßgeblich, ML2–ML7 bleiben offen.')
        else:
            old=old.replace('Zufallsauslassungen, vollständige Blockpermutationen und frische vorab gespeicherte Prognosen sind noch offen.',
                'Nachtrag21.11.: Die bedingten Zufallskontrollen sind abgeschlossen; frische vorab gespeicherte Prognosen bleiben offen.')
            old=old.replace('Er ist noch nicht ausgeführt und ersetzt die Klassifikationsfrage nicht nachträglich.',
                'Er ist seit21.11. als getrennter Versuch abgeschlossen und ersetzt die Klassifikationsfrage nicht nachträglich.')
        rel_link='ai-research/experiments/20261121/ABSCHLUSS.md' if relative=='AKTUELLER-STAND.md' else 'experiments/20261121/ABSCHLUSS.md'
        prefix=f'''# Nachtrag · 21. November 2026 · vier neue Modellarme abgeschlossen

Der neueste Forschungsstand steht im [vollständigen Abschluss]({rel_link}).
ML1-Zufallskontrollen, fünf native Prefix-Schnitte, L2-Schwellenkontrolle,
Boosting, Ridge und TabPFN sind inzwischen abgeschlossen, einschließlich
24 nativer Gate-Jobs und des ursprünglichen Kontoreplays. Frühere Aussagen
unten wie „noch nicht trainiert“ oder „Kontrollen fehlen“ beschreiben den
damaligen Stand. ML2–ML7 bleiben weiterhin offen. Laufende Sims und die
produktiven Leaderboards wurden durch diese Forschung nicht verändert.

{overview}

Diese historischen Endbargelder sind keine garantierten Gewinne und keine
frische OOS-Bestätigung. Das letzte Windows-Betriebszeugnis unten bleibt
zeitlich begrenzt; heute wurde kein neuer Handelsbetrieb geprüft.

---

'''
        target=public/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(prefix+old)
    files=[str(p.relative_to(public)) for p in public.rglob('*') if p.is_file()]
    write(HERE/'publication-ready.json',dict(state='ready_for_reviewed_github_publish',files=files,
        count=len(files),base_path=BASE))
    print('Prepared',len(files),'allowlisted public files')

if __name__=='__main__':main()
