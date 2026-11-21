"""Aggregate-only report and scientific comparison plot from completed predictions."""
from common import *
import os
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'work/tools/tabpfn/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import html

def main():
 r=json.loads((PUB/'results.json').read_text());cov=json.loads((PUB/'coverage.json').read_text());runs=json.loads((PUB/'mlflow-receipt.json').read_text())
 a=r['metrics']['price_context'];b=r['metrics']['price_plus_SI'];p=r['metrics']['train_prior'];diff=r['paired_logloss_improvement_SI'];lo=diff['ci95_low'];hi=diff['ci95_high']
 if lo>0:conclusion='SI verbessert die Prognose in diesem Entwicklungsvergleich; unabhängig bestätigen.'
 elif hi<0:conclusion='Die zusätzlichen SI-Merkmale verschlechtern hier die Prognose.'
 else:conclusion='Kein belastbarer zusätzlicher Prognosevorteil durch SI in diesem Vergleich.'
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
 fig,axes=plt.subplots(1,2,figsize=(11,4),gridspec_kw={'width_ratios':[1.25,1]})
 names=['Nur bisherige\nKlassenhäufigkeit','Kurskontext\n8 Merkmale','Kurskontext + SI\n14 Merkmale'];vals=[p['log_loss'],a['log_loss'],b['log_loss']]
 axes[0].bar(names,vals,color=['#a2adbc','#3678bf','#0a9e9a']);axes[0].set_ylabel('Log Loss · niedriger ist besser');axes[0].set_title(f'{r["chronological_test_episodes"]} spätere Episoden · gleiche Prüffälle')
 for i,v in enumerate(vals):axes[0].text(i,v+.012,f'{v:.4f}',ha='center')
 axes[0].set_ylim(0,max(vals)*1.2)
 axes[1].errorbar([diff['mean']],[0],xerr=[[diff['mean']-lo],[hi-diff['mean']]],fmt='o',capsize=6,color='#155b86')
 axes[1].axvline(0,color='#8893a3',linestyle='--');axes[1].set_yticks([]);axes[1].set_xlabel('Log-Loss-Verbesserung durch SI\npositiv = besser');axes[1].set_title('Gepaart · 95%-Blockbootstrap-Intervall')
 axes[1].text(.02,.1,f'Δ {diff["mean"]:+.4f}\n95% [{lo:+.4f}; {hi:+.4f}]',transform=axes[1].transAxes)
 fig.suptitle('SI1746 · TabPFN v2 · chronologische Entwicklungsprüfung',fontweight='bold');fig.tight_layout();fig.savefig(PUB/'comparison.png',dpi=160);plt.close(fig)
 marketrows=''.join(f'<tr><td>{x["market"]}</td><td>{x["n"]}</td><td>{x["log_loss"]:.4f}</td><td>{next(y["log_loss"] for y in r["by_market"] if y["market"]==x["market"] and y["arm"]=="price_plus_SI"):.4f}</td></tr>' for x in r['by_market'] if x['arm']=='price_context')
 coverage=''.join(f'<tr><td>{x["market"]}</td><td>{x["all_events"]}</td><td>{x["labels_ok"]}</td><td>{x["eligible_heads"]}</td></tr>' for x in cov['by_market'])
 murl='http://127.0.0.1:5055/#/experiments/4';links=' · '.join(f'<a href="{murl}/runs/{rid}">{name}</a>' for name,rid in runs['runs'].items())
 txt=f'''# SI1746 · TabPFN v2 · 21. November 2026

{conclusion}

Alle1746 archivierten RITHMIC-Meldungen aus ES229/NQ907/GC208/CL402 wurden geprüft.
Exakte Kontrakte:361 Quote-Parquetdateien,1.884.326.582Bytes per SHA256 gegen die
Importprotokolle geprüft; native Nautilus-Dekodierung von2968 skalaren Werten.
1635 Meldungen haben gültige 15min-Labels,111 bleiben mit Ausschlussgrund erhalten.
Die1019 überlappungsfreien Episoden ergeben936 gültige erste Meldungen.
43 der45 vor den Labels eingefrorenen Kontrollpaare haben beidseitig gültige Labels.

Tatsächlich abgeschlossen: zwei TabPFNv2-Arme, jeweils8 chronologische Fits;
{r['chronological_test_episodes']} spätere Prüfepisoden an{r['test_days_with_predictions']} Tagen,
{r['first_test_day']} bis{r['last_test_day']}. Erste40 Handelstage Training,
eine ganze Tageslücke, danach10-Tagesblöcke. Früher geprüfte Daten dürfen in späteren
Fits als inzwischen bekannte Vergangenheit eingehen. Kein Zufallssplit.

| Gleiche Prüffälle | Log Loss ↓ | Brier ↓ | Trefferquote | Balancierte Trefferquote |
|---|---:|---:|---:|---:|
| Trainingshäufigkeiten | {p['log_loss']:.6f} | {p['brier']:.6f} | {p['accuracy']:.2%} | {p['balanced_accuracy']:.2%} |
| Nur Kurskontext | {a['log_loss']:.6f} | {a['brier']:.6f} | {a['accuracy']:.2%} | {a['balanced_accuracy']:.2%} |
| Kurskontext + SI | {b['log_loss']:.6f} | {b['brier']:.6f} | {b['accuracy']:.2%} | {b['balanced_accuracy']:.2%} |

Primär: LogLoss(Kurs)−LogLoss(Kurs+SI)={diff['mean']:+.6f};95%-Intervall
[{lo:+.6f};{hi:+.6f}],1999 bewegliche Fünftages-Blockbootstrap-Züge.
Die Unsicherheit gilt bedingt auf diese Fits/Entwicklungsdaten; keine universelle
Signifikanz oder unberührte Bestätigung. Makro-Gleichgewicht der Märkte zusätzlich
in results.json; NQ dominiert die gepoolte Anzahl.

Ziel:LONG/SHORT/FLAT nach15Minuten, anhand ausführbarer Bid/Ask-Seiten und des
eingefrorenen Forschungsgebührenmodells. Ausgabe sind hypothetische Quote-Markouts,
keine Orders, HY-Entries, Prop-Kontoverläufe oder Auszahlungen. Die Flach-Klasse
bedeutet,dass weder Long noch Short nach Spread/Gebühren positiv ist; Trefferquote
allein ist wegen ungleicher Klassen nicht die primäre Kennzahl.

Kursmerkmale: Markt,Chicago-Minute,Bewegung60s/300s relativ zur vergangenen RV,
RV in Ticks,Spread,Top-Size-Imbalance,Quotealter. SI zusätzlich:Typ,Bot-Pfeil,
Menge,Faktor,Zonenbreite und gerichteter Zonenabstand. Keine Zukunftsextrema,
Original-Erkennungszeit,echte aggressive Kauf-/Verkaufsseite oder Feed-Vollständigkeit
behauptet. Entscheidungszeit=Discord-Verfügbarkeit+30s. Archivbracketing und enge
Kaliper liefern wenige Kontrollen; Kontrollen sind keine bewiesenen Nicht-SI-Zeiten.
Der primäre Modellvergleich prüft die sechs zusätzlichen Meldungsattribute an
SI-Zeitpunkten. Er isoliert nicht den Nutzen der bloßen Existenz einer Meldung
gegenüber garantiert meldungsfreien Marktphasen. Beide Arme wissen durch die
Fallauswahl indirekt,dass es ein archivierter Meldungszeitpunkt ist.

80 nach Markt/Zeit geschichtete physische Zukunftsabschneidungen,8 Designprüfungen,
exakte Float64-Parität der CSV-Transportmerkmale mit Parquet sowie native
Kontraktspezifikationen geprüft. Der erste Aufruf stoppte vor dem Fit wegen fehlendem
Arrow-Leser im TabPFN-Environment; unveränderte Fälle/Klassen/Modelle über geprüften
CSV-Transport. Optional fehlende Nanosekundenwerte werden als nullable Int64
gespeichert. Erster Fehler und Korrekturbeleg bleiben erhalten.

Versuchsplan vor Labels/Fits auf GitHub:Commit3ed9deeaf715391bebc22559e90f8d2ff7accac3.
Alle privaten Ereigniszeilen/Kursquotes/IDs bleiben lokal. Quellen/Parameter,
aggregierte Belege und Ergebnisse sind öffentlich dokumentiert; Dateien in Private
nicht hochladen. Ausführen aus dem ursprünglichen outputs/SI-TabPFN-Pool-20261121/
Unterprojekt (Source/common.py leitet den Workspace dort relativ ab).

MLflow: {murl}
Kurslauf:{runs['runs']['price_context']}
SI-Lauf:{runs['runs']['price_plus_SI']}

Built with PriorLabs-TabPFN. Offizielles lokales v2-Modell,CPU,4Estimatoren,
Seed20261121,kein Fine-Tuning großer Gewichte/keine Cloudaufrufe/keine Käufe.
Bestehende Strategien,Sims,Leaderboards und deren Geldzahlen unverändert.
'''
 (PUB/'README.md').write_text(txt)
 page=f'''<!doctype html><html lang="de"><meta charset="utf-8"><title>SI1746 · TabPFN Ergebnis</title><style>
 body{{margin:0;background:#f1f6fc;color:#163450;font:17px/1.55 system-ui}}main{{max-width:1100px;margin:auto;padding:32px}}section{{background:white;border:1px solid #dbe7f3;border-radius:18px;padding:24px;margin:20px 0}}h1{{font-size:32px}}h2{{font-size:23px}}a{{color:#1166ab}}table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #e5edf6}}.lead{{font-size:22px}}.muted{{color:#61758c}}img{{width:100%}}code{{font-size:13px}}</style><main>
 <p>Forschung · 21. November2026 · Built with PriorLabs-TabPFN</p><h1>Bringen SI-Merkmale zusätzliche Vorhersagekraft?</h1>
 <section><p class="lead">{conclusion}</p><p>{r['chronological_test_episodes']} spätere Episoden · {r['test_days_with_predictions']} Handelstage · {r['first_test_day']} bis {r['last_test_day']} · zwei tatsächlich abgeschlossene TabPFN-v2-Läufe mit jeweils acht Fits.</p><p>{links} · <a href="{murl}">MLflow Experiment04</a></p></section>
 <section><img src="Public/comparison.png" alt="Log Loss und gepaartes Unsicherheitsintervall"><p>Log Loss bewertet die Wahrscheinlichkeiten: kleiner ist besser. Ein besserer Punktwert allein ist kein Beweis; das Intervall muss mitbeachtet werden.</p><table><tr><th>Gleiche Fälle</th><th>Log Loss ↓</th><th>Brier ↓</th><th>Trefferquote</th></tr>
 <tr><td>Bisherige Trainingshäufigkeiten</td><td>{p['log_loss']:.4f}</td><td>{p['brier']:.4f}</td><td>{p['accuracy']:.1%}</td></tr>
 <tr><td>Kurskontext · 8 Merkmale</td><td>{a['log_loss']:.4f}</td><td>{a['brier']:.4f}</td><td>{a['accuracy']:.1%}</td></tr>
 <tr><td>Kurskontext + SI · 14 Merkmale</td><td>{b['log_loss']:.4f}</td><td>{b['brier']:.4f}</td><td>{b['accuracy']:.1%}</td></tr></table></section>
 <section><h2>Alle 1’746 Meldungen bleiben nachprüfbar</h2><table><tr><th>Markt</th><th>Meldungen</th><th>Gültige Labels</th><th>Gültige erste Episoden</th></tr>{coverage}</table><p>111 Meldungen ohne vollständiges gültiges Label. Überlappende Meldungen werden nicht als unabhängige Beispiele vervielfacht. Von45 vorher gematchten Kontrollpaaren sind43 beidseitig auswertbar. Zu wenige für weitreichende kausale Behauptungen.</p></section>
 <section><h2>Zusätzlich je Markt · beschreibend</h2><table><tr><th>Markt</th><th>Prüffälle</th><th>Kurs LogLoss</th><th>+SI LogLoss</th></tr>{marketrows}</table></section>
 <section><h2>Was wurde vorhergesagt?</h2><p>Long,Short oder keine profitable Richtung nach15Minuten. Einstieg/Ausstieg auf den passenden Bid/Ask-Seiten,nach eingefrorenen Gebühren. Kein HY-Setup und kein Kontopayout wird daraus automatisch abgeleitet.</p><p>Erste40 Tage zum Lernen,eine Tageslücke,danach spätere10-Tagesblöcke;in beiden Armen identische Fälle und Parameter. Alle Meldungen sind nur zum Discord-Sendezeitpunkt bekannt,plus30Sekunden. Der tatsächliche Bookmap-Erkennungszeitpunkt ist unbekannt.</p><p class="muted">Mai–Oktober2026 wurde bereits mehrfach untersucht:Entwicklungsprüfung,kein frischer OOS-Nachweis. TBBO zeigt Quotes an Trades,keinen vollständigen BBO-Strom. Enge Quotealter-/Pfadregeln reduzieren die Fallzahl. Fehlende archivierte Meldungen beweisen keine SI-Abwesenheit. Quote-Markouts sind keine simulierten Orders oder Auszahlungen.</p></section>
 <section><h2>Belege</h2><p><a href="Public/results.json">Vollständige Kennzahlen</a> · <a href="Public/coverage.json">Abdeckung aller Meldungen</a> · <a href="Public/preregister.json">Vorabplan</a> · <a href="Public/stratified-temporal-audit.json">Zeitliche Prüfung</a> · <a href="Public/native-decode-proof.json">Native Dekodierung</a> · <a href="Public/design-tests.json">Designprüfungen</a> · <a href="Public/README.md">Methodik</a></p><p>Laufende NinjaTrader-Sims und produktive Leaderboards unverändert. Keine kostenpflichtigen Daten oder Cloud-Aufrufe.</p></section></main></html>'''
 (HERE/'Stand.html').write_text(page);print(conclusion)
if __name__=='__main__':main()
