# Ezafe gold corpus — NOTICE

## Purpose

One short Persian **body** sentence per record for blind ezafe labeling.
Labels attach to `char_spans` on `text`. Boilerplate (nav/footer/cards) is
rejected by `persian_seo_normalizer.ezafe_gold_filters`.

Guidelines: [`docs/gold-ezafe-guidelines.md`](../../docs/gold-ezafe-guidelines.md).

## Current corpus (after body-filter clean)

| `source_kind` | n |
| --- | ---: |
| `wiki` | 120 |
| `ecommerce` | 80 |

Ecommerce domains (snippet license): digikala.com, modiseh.com, blog.okala.com,
basalam.com, emalls.ir. Harvest prefers `<p>` inside `article`/`main`, not
header/footer/nav.

`technolife.ir` excluded (`Content-Signal: ai-train=no`).

## Filter / template report

See `ezafe_filter_report.json` for rejection reason counts and samples.
Wiki template dedupe: `sentence_template_fingerprint` (skeleton +
`keyword_fingerprint`, max 3 per cluster).

## Token contract

- Dadma tokens + required `char_spans` + version metadata
- `python scripts/verify_gold_tokens.py` (Dadma cache env-gated)

## Labeling batch 1

- `ezafe_worksheet_batch1_seed20260728.csv` — UTF-8 BOM
- `labelable=0` rows have `ezafe=-` (punct/number/latin/control); do not relabel
- Manifest lists ids for batch-2 non-overlap

## Workflow

1. `python scripts/clean_rebuild_ezafe_gold.py`
2. `python scripts/remint_gold_char_spans.py`
3. `python scripts/verify_gold_tokens.py`
4. `python scripts/make_ezafe_worksheet.py --seed 20260728`
5. Human labels → ingest → eval
