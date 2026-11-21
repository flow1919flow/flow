# DeepInfra decision-head diagnostic · prepared, not executed

**No real model request has been sent.** User is currently reconsidering model
suitability. Do not start until root explicitly resolves that question and the
separate authorization file is valid. The localhost form is only an ephemeral
key handoff; submitting it does not call DeepInfra.

The selected pair is `nace-ai/drex-max-finance` and `Cloudflare/clef`. These are
decision-head inference models, not ordinary chat-completion models. The documented
endpoint is `POST https://api.deepinfra.com/v1/decisions`, with `state` and typed
`questions`; `noul` returns the probability of yes. The endpoint is not documented
as a supervised weight-training/fine-tuning service. Conditioning on earlier
examples is an experiment, not guaranteed learning or financial calibration.

Primary sources checked21November2026:

- [Decision endpoint and Clef integration](https://docs.deepinfra.com/integrations/clef)
- [Drex Max Finance model](https://deepinfra.com/nace-ai/drex-max-finance)
- [Drex Max Finance API](https://deepinfra.com/nace-ai/drex-max-finance/api)
- [Clef API](https://deepinfra.com/Cloudflare/clef/api)
- [Inference privacy](https://docs.deepinfra.com/account/data-privacy)

The Finance card reports performance on financial documents, news and other
finance decision tasks; that does not demonstrate prediction of trade outcomes.
Vendor-described probability calibration also does not establish calibration
for these setups. No strong model recommendation follows from those benchmarks.

## Frozen diagnostic

- Existing ES C28.03 cohort:347 candidates,242 sessions,24November2025–30October2026.
- Exactly the same230 later IDs and nine expanding outer splits as the existing
  Logit/TabPFN comparison;80 initial training sessions,one gap,20-session test blocks.
- Five causal numeric features only. No dates,contracts,absolute market prices,
  private IDs,raw quotes,current/future outcomes or account data are sent.
- The most recent32 eligible earlier training examples per fixed block,selected
  only by chronology,with known binary labels. Current setup is one record per
  request. Input numbers are rounded once to six significant digits; originals
  remain unchanged in local source data.
- Target: standalone candidate positive net after the same original research
  commissions and an additional adverse ES tick on entry and exit.
- Two main arms,230 requests each. Separate fixed mechanism checks:32 zero-shot
  cases per model and23 identical-payload repeated requests per model. Both audit
  samples cover all nine blocks and are chosen using metadata only,not outcomes.
-570 maximum calls,never a broad parameter/prompt/threshold search. No retries
  after errors;401/403/404/429,network/schema errors or excessive token usage stop
  immediately with a retained ledger. Redirects are disabled on authenticated calls.

AUC/rank discrimination is primary. Raw Brier and LogLoss use clipping1e−7;
the separately reported fixed .01–.99 sensitivity cannot replace them. Comparators
are full-training and exact32-example class priors,stored Logit and stored TabPFN
on the same IDs. Per-block coverage/metrics and paired five-session block bootstrap
intervals are recorded,1999 draws,seed20261121. The two primary model comparisons
use97.5% individual intervals as a conservative two-comparison family diagnostic.
This selected development year is not fresh OOS; conditional intervals and a
pretrained model's rankings are not a claim of account payouts.

## Cost and privacy

Reservation uses4000 maximum serialized bytes for full/repeat requests,2000 for
zero-shot,plus2048 wrapper tokens,at0.30USD per million input tokens for each model.
Output is documented free. Worst conservative client reservation:

`506 × 6048 × 0.30/1e6 + 64 × 4048 × 0.30/1e6 = 0.995808 USD`.

Finance's current quoted promotional input price is0.12USD/M;Clef is0.24USD/M.
The Finance undiscounted upper estimate uses0.24USD/M. Reported-usage estimates
are not the actual invoice,and this reservation is not a provider-side billing
cap. A response beyond the token allowance stops before the next call.

DeepInfra states these inference inputs/outputs are not stored or used to train
models;metadata is logged. That is the vendor policy,not an independent privacy
audit. Five numeric research features and earlier labels still leave the computer.
No model invocation is authorized solely by a key being available.

## Local execution and key handling

Use `work/tools/mlflow/.venv/bin/python` from the project root.

1. `decision_probe.py prepare` builds/verifies the source cohort and freezes
   `plan.json` plus private request bodies. It has no network action.
2. `test_offline.py` checks source provenance,request causality,shape,byte/cost
   bounds,redirect refusal,error stopping and complete evaluation with explicitly
   synthetic HTTP fixtures. It never calls real models.
3. `key_form.py` binds an ephemeral port only on127.0.0.1. Its receipt supplies
   the current URL. The password input has autocomplete off;key is never written
   to disk or logs. POST/receive stores it only in memory. Root must explicitly
   POST/start with a local control token after a valid authorization file exists.
4. `authorization.json` must contain `approved:true`,`model_ids`,exact
   `plan_sha256`,`max_usd`<=1,and
   `numeric_features_and_past_labels_to_deepinfra_approved:true`. Root writes this
   only after the user-facing suitability/authorization decision is resolved.
5. The server then passes the key to one subprocess through its environment,
   clears its own reference,and the runner executes only that frozen plan.
6. `decision_probe.py evaluate` evaluates the real response ledger. No native SQX
   rerun or financial/account result is claimed by this script.

`Private` contains input features,labels,case IDs,control token and eventual API
responses. Keep it local. Do not publish it or a key to GitHub. Source code and
aggregate plan/test/provenance documents may be reviewed publicly after privacy
screening. The running SI experiment and all NinjaTrader Sims are untouched.

## Final suitability hold

The actual Claude answer138 recommends not spending on these decision heads for the five-numeric-feature prediction task. Root accepted a hold on paid calls. The code and10 passing offline tests are preserved;there is no authorization file,no real response ledger,and no API expenditure. See readiness.json for final hashes. The local password form is left running for root to inspect/close safely;it never auto-starts model calls.
