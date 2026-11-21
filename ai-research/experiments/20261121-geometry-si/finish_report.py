"""Render completed geometry and SI ingestion evidence and log local MLflow."""
from pathlib import Path
from html import escape
import json,os,math
os.environ['MLFLOW_DISABLE_AGENT_HINT']='1'
from mlflow.tracking import MlflowClient

HERE=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())

def main():
    g=read(HERE/'Geometry/results.json');assert g['state']=='native_geometry_measurement_complete'
    assert math.isfinite(g['spearman_rho']) and math.isfinite(g['conditional_upper_tail_rank'])
    j=read(HERE/'SI/ingest-result.json');si=read(HERE/'SI/mlflow-ingest.json')
    client=MlflowClient('http://127.0.0.1:5055');exp=client.get_experiment_by_name('04_ML_Forschung');assert exp
    path=HERE/'Geometry/mlflow.json'
    if path.exists():rid=read(path)['run_id']
    else:rid=client.create_run(exp.experiment_id,tags={'mlflow.runName':'GEOM01 · Zielweg/Stopweg · Messung',
        'kind':'single_feature_native_measurement_no_model','fresh_OOS':'false','live_changes':'false',
        'supervised_model_trained':'false'}).info.run_id
    for key,value in g.items():
        if isinstance(value,(int,float)) and not isinstance(value,bool):client.log_metric(rid,key,value)
    for f in ['Geometry/results.json','geometry-preregister.json','geometry-github-receipt.json','Review-und-Plan.md']:
        client.log_artifact(rid,str(HERE/f),'evidence')
    client.set_terminated(rid,'FINISHED')
    geom_url=f'http://127.0.0.1:5055/#/experiments/{exp.experiment_id}/runs/{rid}'
    path.write_text(json.dumps(dict(run_id=rid,url=geom_url,state='complete_measurement_not_model'),indent=2)+'\n')
    positive=g['spearman_rho']>0 and g['conditional_upper_tail_rank']<.05
    decision=('Die gerichtete Geometrie-Hypothese liefert hier einen explorativen Hinweis. '
        'Das kann einen registrierten Modell-Folgetest begründen; es ist noch keine Geldverbesserung.' if positive else
        'Die gerichtete Geometrie-Hypothese hat in diesem Test keinen klaren Zusatzbeleg geliefert. '
        'Daraus folgt keine pauschale Widerlegung aller möglichen Wechselwirkungen; neue Modelle wurden nicht nachgeschoben.')
    text=f'''<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TabPFN · neue Merkmale und SI</title>
<style>body{{margin:0;background:#f2f6fc;color:#183650;font:17px/1.65 system-ui,sans-serif}}main{{max-width:1120px;margin:36px auto;padding:0 25px}}section{{background:white;border:1px solid #dbe6f2;border-radius:18px;padding:27px;margin:20px 0}}h1{{font-size:35px;line-height:1.2}}h2{{font-size:23px}}a{{color:#176ab3}}.cards{{display:flex;gap:20px;flex-wrap:wrap}}.metric{{background:#eaf3ff;border-radius:12px;padding:14px 20px;flex:1;min-width:150px}}.metric strong{{display:block;font-size:30px}}small{{color:#567086}}table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;padding:12px;border-bottom:1px solid #e1eaf5}}code{{font-size:14px;overflow-wrap:anywhere}}</style>
<main><h1>Neue Merkmale und die229 SI-Meldungen</h1><p>Mit Claude besprochen ·21.November2026 · keine Änderung laufender Sims</p>
<section><h2>Was sich aus dem bisherigen TabPFN-Test ableiten lässt</h2><p>TabPFN blieb nahe an der Basis und ließ nur14 von230 bewerteten Kandidaten aus. Der kleine Stressvorteil ist kein belegter Prognosevorteil. Der aktualisierte <a href="../AI-Forschung-20261121/Ergebnisse.html">Ergebnisbericht</a> zeigt jetzt die Auslassungen für jeden Arm. Claude hat Bericht und Regeln gelesen, die Kontorechnung nicht neu nachgerechnet.</p></section>
<section><h2>Zuerst prüfen: Platz bis zum tatsächlich aktiven Ziel</h2><p>Neues Merkmal: Abstand der bekannten Einstiegsquote zum nächsten aktiven Bollinger-/Eröffnungsspannenziel, geteilt durch den geplanten Stopabstand. Beispiel:8Punkte bis zum Ziel und10Punkte bis zum Stop ergeben0,8R. Die Eröffnungsspanne ist vor Ablauf der ersten60Minuten unbekannt.</p>
<div class="cards"><div class="metric"><strong>{g['candidates']}</strong>Kandidaten, unveränderte Trades</div><div class="metric"><strong>{g['spearman_rho']:.3f}</strong>Rangkorrelation mit Stressnetto</div><div class="metric"><strong>{g['conditional_upper_tail_rank']:.3f}</strong>bedingter Nullrang</div></div>
<p>{decision}</p><p><small>6native Beobachterabschnitte, identische3Replikate je Abschnitt,5physische Prefix-Schnitte, darunter2 vorMinute60. 1.000 bedingte Sitzungspermutationen auf dem bereits ausgewählten Jahr. Keine universelle Kausalitätsgarantie; zusätzliche native Positivkontrolle noch offen. Keine Modell-/Auszahlungsverbesserung damit behauptet.</small></p><p><a href="{geom_url}">Tatsächliche Messung in MLflow</a> · <a href="Geometry/results.json">Ergebnisdatei</a> · <a href="geometry-preregister.json">Vorabfestlegung</a></p></section>
<section><h2>SI ist jetzt als eigener Datensatz geladen</h2><div class="cards"><div class="metric"><strong>229</strong>ES-Meldungen vollständig eingelesen</div><div class="metric"><strong>187 /42</strong>Icebergs /Stops</div><div class="metric"><strong>78</strong>Chicago-Kalendertage</div><div class="metric"><strong>165</strong>zeitliche Überlappungsgruppen</div></div>
<p>Die sieben zuvor genannten Fälle waren nur die enge Überschneidung mit HY104-Setups. Im eigenen SI-Datensatz stehen alle229Meldungen. Für alle sind passende Kontraktdateien mit ausreichenden Zeitgrenzen vorhanden. Gültigkeit und Lücken der einzelnen Quotes sowie die künftigen Kursreaktions-Labels müssen noch geprüft werden.</p><p><strong>Geladen bedeutet noch nicht trainiert.</strong> Der Import in MLflow ist fertig; es gibt noch keine neue SI-Vorhersageleistung. Discord-Zeit ist ein Verfügbarkeitsproxy, keine belegte Bookmap-Empfangszeit. Aus fehlenden Meldungen wurde keine „kein Event“-Klasse erzeugt.</p><p><a href="{si['url']}">229SI-Meldungen in MLflow ansehen</a> · <a href="SI/ingest-result.json">Importnachweis</a></p></section>
<section><h2>Danach sinnvoll weiter</h2><table><tr><th>Frage</th><th>Abgegrenzter Folgetest</th></tr><tr><td>Andere Merkmale?</td><td>Zuerst aktive Zielgeometrie; später Alter und Stärke des Wegs ins Setup. Keine beliebige Suche über viele Indikatoren.</td></tr><tr><td>Andere Vorhersage?</td><td>Erwartetes Stress-Netto-R statt nur Gewinnhäufigkeit; kalibrierte Nullschwelle als eigener Versuch statt bisherigem Trainingsquantil. Noch nicht getestet.</td></tr><tr><td>SI-Zusatznutzen?</td><td>Auf denselben Episoden Kurskontext allein gegen Kurskontext plus SI-Attribute. Größerer vorhandener Pool1746Meldungen aus ES/NQ/GC/CL; kein ES-Erfolgsbeleg durch Poolbildung.</td></tr></table><p><a href="https://github.com/flow1919flow/flow/blob/main/ai-research/experiments/20261121-geometry-si/Review-und-Plan.md">Vollständige Review-Notizen</a> · <a href="https://github.com/PriorLabs/TabPFN">PriorLabs: fachliche Merkmale</a></p></section></main></html>'''
    (HERE/'Stand.html').write_text(text)
    print(json.dumps(dict(geometry=geom_url,SI=si['url'],positive_exploratory_measurement=positive)))

if __name__=='__main__':main()
