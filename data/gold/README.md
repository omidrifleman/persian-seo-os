# Ezafe gold corpus — NOTICE

## Status: PAUSED (2026-07-28)

Human labeling and F1 gate for customer-facing ezafe audit are **stopped**.
ASSUMPTION-008 is `FROZEN`: optional written kasreh is not a spelling error;
SEO value of `fa.text.missing_ezafe_kasreh` does not justify labeling cost.
`EZAFE_CUSTOMER_AUDIT_ENABLED` stays `False`. Shim + unit tests remain.

### Resume only if all are true
1. Explicit product decision to re-open ASSUMPTION-008.
2. Budget for blind human labels on the cleaned corpus (≥200 verified,
   stratified commercial vs wiki).
3. Acceptance thresholds locked in ADR-0009 before enabling customer audit.

Batch-1 worksheet/manifest were removed; do not regenerate unless resuming.

## Purpose

One short Persian **body** sentence per record for (future) blind ezafe
labeling. Labels attach to `char_spans` on `text`. Boilerplate is rejected by
`persian_seo_normalizer.ezafe_gold_filters`.

Guidelines: [`docs/gold-ezafe-guidelines.md`](../../docs/gold-ezafe-guidelines.md).

## Current corpus (after body-filter clean)

| `source_kind` | n |
| --- | ---: |
| `wiki` | 120 |
| `ecommerce` | 80 |

Ecommerce domains (snippet license): digikala.com, modiseh.com, blog.okala.com,
basalam.com, emalls.ir.

`technolife.ir` excluded (`Content-Signal: ai-train=no`).

## Filter / template report

See `ezafe_filter_report.json`. Wiki template dedupe uses
`sentence_template_fingerprint` (skeleton + `keyword_fingerprint`, max 3/cluster).

## Token contract

- Dadma tokens + required `char_spans` + version metadata
- `python scripts/verify_gold_tokens.py` (Dadma cache env-gated)

## Offline tooling (kept, not actively labeling)

1. `python scripts/clean_rebuild_ezafe_gold.py`
2. `python scripts/remint_gold_char_spans.py`
3. `python scripts/verify_gold_tokens.py`
4. Worksheet/ingest/eval only after resume decision above
