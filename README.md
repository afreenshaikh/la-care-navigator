# LA Care Navigator

A dependency-free local Python + browser hackathon prototype. Requires Python 3.10+ and a modern browser. It is not a medical device, clinical triage system, insurance broker, or production patient-data service.

## Run

From `/workspace/la-care`:

```sh
python3 app.py --port 8000
```

Open http://localhost:8000. To choose another port, change `--port`.

```sh
python3 -m unittest -v
```

## Demo

1. In Care navigator, load the fictional example and submit. Baseline asks only missing ZIP/insurance; it misses other navigation preferences.
2. Open Improvement lab. Propose the next patch. Inspect development/holdout scores and safety checks.
3. Approve the patch. Return to the navigator and submit again; the new policy asks for the missing preference.
4. Repeat three times. Policy v4 asks missing language, travel, and service preferences. The proposer explicitly stops after its three supported patches.

## What the RSI is and is not

This is bounded application-level improvement: a rule-based proposer consumes development-test failures and patches a persistent intake configuration. A separate evaluator applies holdout and safety gates. Human approval is required. It is not LLM reasoning, model-weight training, unrestricted self-rewriting, or evidence of clinical improvement. The cases and proposer are intentionally small and predefined. The holdout suite is separate from the proposer but repeated gate checks still risk overfitting.

Only three Boolean nonclinical intake flags can change. Medical safety behavior, resource links, server permissions, and privacy restrictions are outside that patch surface. The version history and policy live in `state.json`, created after a proposal; no user intake is saved there. Restore the initial demonstration by stopping the server and removing only `state.json`.

## Care and coverage scope

- Manually curated official links: HRSA health-center finder, LA County DHS financial assistance, BenefitsCal, and Covered California.
- No live search, actual clinic matches, availability, network verification, prices, program eligibility determinations, or bookings.
- No diagnosis, medication guidance, or symptom-specific treatment recommendations.
- Keyword alerts are illustrative and may miss or misinterpret emergencies, including negations. The app always warns users not to rely on a negative check. This is not validated clinical triage.
- The ZIP field validates format only, not LA County residency. Users are explicitly asked for LA County ZIP codes.
- Links are seed resources, not date-verified eligibility rules. Financial assistance is labeled as distinct from insurance.

## Privacy and deployment limitations

Use fictional data only. The local server does not log intake, and the browser does not use localStorage or cookies. External resource links lead to third-party websites; the app does not send intake values with those links. No external fonts, analytics, or client libraries are loaded. Browser extensions, local device access, and third-party sites remain outside this prototype's controls.

The server binds to localhost and rejects cross-origin browser POSTs. It has no authentication, authorization, TLS, or production-grade HTTP server. Anyone with access to the local service can approve changes. Do not expose it publicly or use real health information. Production requires a privacy/security assessment, proper permissions, clinical review, validated safety workflows, and jurisdiction-specific legal review. Do not claim HIPAA compliance.

## Next development steps

1. Replace the three-rule proposer with an LLM that can output only schema-validated intake-policy patches. Do not allow arbitrary code execution. Keep the existing safety surface locked.
2. Expand clinician-reviewed tests and create a larger one-time independent test set. Separate navigation success from clinical safety metrics.
3. Add licensed/official provider data and geospatial filtering. Track per-field provenance and freshness; keep appointment status unknown unless verified.
4. Add official insurance comparison/enrollment handoffs. Never estimate exact eligibility or plan prices from a language model.
5. Add authenticated operator approval, audit trails without patient content, rollback, and security controls before any deployment.

## Reproducibility

No third-party backend packages, randomness, or external inference calls. Evaluation is deterministic. Record your Python version with `python3 --version` when presenting results. Client uses native DOM and Fetch APIs; fonts have local system fallbacks.
