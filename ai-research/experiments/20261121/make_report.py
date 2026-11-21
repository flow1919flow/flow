"""Render only completed, versioned research evidence; no data/model execution."""
from pathlib import Path
from html import escape
import json
from native_check import HERE,read,write,sha

LABELS={'base':'Basis · HY104-EMA22 → C28.03','ML1C':'Logistik · neue Schwellenregel',
    'ML8':'Gradient Boosting · flach','MR1':'Ridge · erwartetes Netto-R','ML9':'TabPFN v2'}

def money(x):return f'{x:,.0f}'.replace(',','’')+' $'

def main():
    cash=read(HERE/'Cash/results.json');assert cash['state']=='complete_native_gate_and_original_cash_comparison'
    assert read(HERE/'Controls/family-null.json')['state']=='complete'
    rows=[];summary=[]
    for arm,name in LABELS.items():
        n=cash['results']['normal'][arm];s=cash['results']['stress'][arm]
        delta=s['mean_end_cash_usd']-cash['results']['stress']['base']['mean_end_cash_usd']
        link='#' if arm=='base' else read(HERE/'MLflow'/f'{arm}.json')['url']
        omitted=0 if arm=='base' else read(HERE/'Training'/arm/'results.json')['metrics']['omitted']
        rows.append(f'<tr><td><a href="{escape(link)}">{escape(name)}</a></td><td>{omitted} / 230</td><td>{money(n["mean_end_cash_usd"])}</td><td>{money(n["median_end_cash_usd"])}</td><td>{money(s["mean_end_cash_usd"])}</td><td>{money(s["median_end_cash_usd"])}</td><td>{money(delta)}</td></tr>')
        summary.append(dict(arm=arm,name=name,normal_mean=n['mean_end_cash_usd'],normal_median=n['median_end_cash_usd'],
            stress_mean=s['mean_end_cash_usd'],stress_median=s['median_end_cash_usd'],stress_mean_delta_from_base=round(delta,2)))
    native=[]
    for arm in list(LABELS)[1:]:
        for p in sorted((HERE/'SQX'/arm).glob('*/verified.json')):
            j=read(p)
            files=sorted((p.parent/'result_sqx').glob('*.sqx'))
            assert len(files)>=3, 'Missing source and optimized native SQX reports'
            native.append(dict(arm=arm,segment=p.parent.name,proof_sha256=sha(p),
                seconds=j['seconds'],replicas_identical=j['replicas_identical'],
                candidates_identical=j['candidates_identical'],source_sha256=j['source_sha256'],
                trades_sha256=j['trades_sha256'],features_sha256=j['features_sha256'],
                decision_file_sha256=sha(p.parent/'ml-decisions.csv'),
                manifest_sha256=sha(p.parent/'manifest.txt'),
                native_log_sha256=sha(p.parent/'sqx.log'),
                sqx_reports=[dict(file=str(f.relative_to(HERE)),size_bytes=f.stat().st_size,sha256=sha(f)) for f in files]))
    assert len(native)==24
    write(HERE/'summary.json',dict(state='complete',comparison=summary,native_jobs=24,original_account_counterchecks=cash['original_account_counterchecks'],
        fresh_OOS=False,live_changed=False,cloud_spend_usd=0,preregister_commit=read(HERE/'preregister-github-receipt.json')['commit']))
    write(HERE/'native-acceptance-summary.json',dict(jobs=24,replicas=True,proofs=native))
    si=read(HERE/'SI/feasibility.json');null=read(HERE/'Controls/family-null.json')
    tp_normal=cash['results']['normal']['ML9'];tp_stress=cash['results']['stress']['ML9']
    base_normal=cash['results']['normal']['base'];base_stress=cash['results']['stress']['base']
    conclusion=(f'TabPFN verbessert hier den Tickstress-Fall: Ø {money(tp_stress["mean_end_cash_usd"])} statt '
        f'{money(base_stress["mean_end_cash_usd"])}, Median {money(tp_stress["median_end_cash_usd"])} statt '
        f'{money(base_stress["median_end_cash_usd"])}. Ohne Tickstress bleibt es etwas unter der Basis '
        f'(Ø {money(tp_normal["mean_end_cash_usd"])} statt {money(base_normal["mean_end_cash_usd"])}). '
        'Logistik, Boosting und Ridge liegen in beiden Kostenfällen unter der Basis. '
        'Kein bestätigter neuer Gesamtsieger; keine Änderung des laufenden Handels.')
    details=''.join(f'<li>{escape(LABELS[a])}: bedingter, über vier Arme korrigierter Rang {v:.3f}</li>' for a,v in null['max_statistic_adjusted_upper_tail_rank'].items())
    evidence=''.join(f'<li>{escape(LABELS[j["arm"]])} · {escape(j["segment"])}: '+
        ' · '.join(f'<code>{escape(f["file"])}</code>' for f in j['sqx_reports'] if 'Optimized' in f['file'])+'</li>' for j in native)
    text=f'''<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ES · Machine Learning · Ergebnisse</title>
<style>body{{margin:0;background:#f1f6fd;color:#183650;font:17px/1.6 system-ui,sans-serif}}main{{max-width:1260px;margin:45px auto;padding:0 25px}}section{{background:white;border:1px solid #dbe6f2;border-radius:18px;padding:28px;margin:22px 0}}h1{{font-size:36px;line-height:1.2}}h2{{font-size:23px}}a{{color:#176ab3}}table{{border-collapse:collapse;width:100%;font-size:16px}}th,td{{text-align:right;padding:14px 10px;border-bottom:1px solid #e3ebf4}}th{{color:#396687;font-size:14px}}td:first-child,th:first-child{{text-align:left}}tr:first-child td{{background:#eaf3ff;font-weight:650}}small{{color:#526d86}}.tag{{color:#34628c;background:#deecfc;padding:5px 12px;border-radius:18px}}</style>
<main><span class="tag">Forschungsvergleich · 21. November 2026</span><h1>Bringt Machine Learning mehr Endbargeld?</h1>
<p>ES · MFF Rapid EOD 50k · 1’000 USD Kaufbudget · 242 Sitzungen · 24.11.2025–30.10.2026</p>
<section><h2>Das Ergebnis</h2><p>{conclusion}</p><p><small>Die Modellkontrollen liefern keinen klaren Zusatzbeleg für verlässliche Prognoserangfolgen. Das bereits ausgewählte Jahr ersetzt keine frische Bestätigung.</small></p></section>
<section><h2>Gleicher Kontoverlauf, vier feste neue Modellarme</h2><p>Evaluation bleibt HY104-EMA22. Ab Funded läuft C28.03 mit oder ohne Modellentscheidung. Alle neuen Gates wurden tatsächlich in SQX neu gerechnet; danach folgte die unveränderte Kontoengine.</p>
<table><thead><tr><th>Funded-Variante</th><th>Ausgelassene Kandidaten</th><th>Normal Ø</th><th>Normal Median</th><th>Tickstress Ø</th><th>Tickstress Median</th><th>Stress-Ø zur Basis</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<p><small>Endbargeld enthält Restbudget und Auszahlungen nach Challengegebühren. Gewinn = Endbargeld − 1’000 USD. Ein Tick schlechter je Seite. Je Start 100 Sitzungen, 143 stark überlappende Startfenster; keine 143 unabhängigen Experimente. Kein monatliches Einkommen und keine Garantie.</small></p></section>
<section><h2>Einordnung nach Claudes Berichtsprüfung</h2><p>TabPFN ließ nur 14 der 230 bewerteten Kandidaten aus; die anderen neuen Arme 28–38. Es griff damit am wenigsten in die Basis ein. Seine Geldnähe zur Basis ist kein Nachweis guter Vorhersagen: Die AUC liegt bei 0,475 und die Rangkorrelation bei −0,026. Das kleine Stressplus bleibt ein gemischter Entwicklungsbefund.</p><p>Claude hat den öffentlichen Bericht, die Ergebnisdateien und die relevanten Merkmals-/Zielregeln gelesen. Er hat die Geldrechnung nicht unabhängig nachgerechnet. Die Zahl ausgelassener Kandidaten ist keine einfache Differenz der ausgeführten Trades; dafür wurden die Gates nativ neu gerechnet.</p></section>
<section><h2>Was tatsächlich geprüft wurde</h2><p>347 eindeutige Kandidaten, 230 spätere Vorhersagen je Modell. Gleiche fünf Merkmale und neun äußere Zeitblöcke. Schwelle aus fünf kreuzweisen Sitzungsblöcken im bereits bekannten Training. 24 native Gate-Jobs, identische Replikate, unveränderte Kandidaten und Merkmale. Die Basis wurde gegen den akzeptierten Quote- und Kontopfad exakt reproduziert.</p>
<p>Fünf physische native Prefix-Schnitte bestanden; zusätzlich Signalquote/Stop verglichen. Frühere Prefix-Zeilen sind Parität, die unmittelbare Zukunft ist nur an den fünf Schnittentscheidungen entfernt. Die absichtlich undichte Kontrollspalte testet den Validator, kein natives ML-Merkmal. Erweiterte Randfall-Schnitte und unabhängige frische Daten bleiben offen.</p>
<p>Der erste TabPFN-Versuch stoppte an einer absoluten Sammel-/Einzelabweichung von 0,00000131. Der erfolglose Versuch und der datierte Nachtrag sind erhalten. Handelsentscheidungen verwenden einzelne aktuelle Setups; Sammelabweichungen werden protokolliert. Keine still erhöhte Modellleistung durch neue Parameter.</p></section>
<section><h2>Zufallskontrollen und Grenzen</h2><p>ML1: 1’000 gematchte Zufallsauslassungen und 1’000 vollständige bedingte Permutationsläufe. Für vier neue Familien 199 gemeinsame Permutationen mit maximaler Rangkorrelation. Austauschbarkeit nur innerhalb Quartal/Kandidatenzahl angenommen. Dies sind Diagnosewerte des bereits untersuchten Jahres; keine frische Bestätigung.</p><ul>{details}</ul><p>Die Zufallsauslassungen auf Kandidatenebene ersetzen keinen vollständigen Zufalls-Kontoreplay. TabPFN-Nullwerte verwenden Sammelrechnung mit protokollierter numerischer Einzelabweichung; echte Gates verwenden Einzelvorhersagen.</p></section>
<section><h2>SI bleibt eine eigene Datenfrage</h2><p>{si['ES_stop_iceberg_messages']} ES-Meldungen; {si['setup_candidates_in_message_date_span']} Setups im Zeitraum der Meldungen. Nur {si['outer_test_candidates_with_prior15min_event']} spätere Setups hatten im festen 15-Minuten-Fenster eine vorher verfügbare Meldung desselben Kontrakts. Archivvollständigkeit belegt keine lückenlose Feed-Laufzeit. Kein neues SI-Modell trainiert und fehlende Abdeckung nicht als „kein Event“ kodiert.</p></section>
<section><h2>Nachweise</h2><p><a href="preregister.json">Vorabfestlegung</a> · <a href="summary.json">Ergebnisdatei</a> · <a href="native-acceptance-summary.json">24 SQX-Belege</a> · <a href="Cash/results.json">Kontovergleich</a> · <a href="Controls/family-null.json">Kontrollen</a> · <a href="http://127.0.0.1:5055/#/experiments/4">MLflow</a></p><details><summary>Native SQX-Dateien · lokal gespeicherte Originalberichte</summary><p>Die Dateipfade stehen im Nachweis. Der lokale Berichtsserver liefert nur seine erlaubten Formate; .sqx gegebenenfalls im Finder aus dem jeweiligen SQX/Arm/Segment/result_sqx-Ordner laden. Die Dateien enthalten Teilabschnitte je Kontrakt, keinen einzelnen Jahresbericht.</p><ul>{evidence}</ul></details><p><small>Built with PriorLabs-TabPFN · v2 · lokal und offline. Keine GPU-Miete oder Cloud-Modellaufrufe. Laufende NinjaTrader-Sims und produktives Leaderboard unverändert.</small></p></section></main></html>'''
    (HERE/'Ergebnisse.html').write_text(text)
    print(json.dumps(summary,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
