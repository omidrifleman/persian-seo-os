# Ezafe gold corpus — NOTICE

## Purpose

`ezafe_gold.jsonl` holds **one short Persian sentence per record** (not a
paragraph) for **human-blind** ezafe labeling. Labels attach to **character
spans** (`char_spans`) on `text`; token index is display-only. Labels must
never be pre-filled from `detect_ezafe`.

Guidelines: [`docs/gold-ezafe-guidelines.md`](../../docs/gold-ezafe-guidelines.md).

## Sources and licenses (current corpus)

| `source` | `source_kind` | n | License / terms |
| --- | --- | ---: | --- |
| `fa.wikipedia.org` | `wiki` | 120 | **CC BY-SA 4.0** |
| `tarafdari.com` | `magazine` | 21 | site terms (eval snippet) |
| `digiato.com` | `magazine` | 14 | site terms (eval snippet) |
| `hamshahrionline.ir` | `news` | 14 | site terms (eval snippet) |
| `digikala.com` | `ecommerce` | 14 | site terms (eval snippet) |
| `blog.okala.com` | `ecommerce` | 9 | site terms (eval snippet) |
| `modiseh.com` | `ecommerce` | 8 | site terms (eval snippet) |
| `basalam.com` | `ecommerce` | 4 | site terms (eval snippet) |
| `emalls.ir` | `ecommerce` | 3 | site terms (eval snippet) |
| `okala.com` | `ecommerce` | 2 | site terms (eval snippet) |

Each non-wiki record is a **single sentence** (`source_url` + `collected_at`).
Full-page redistribution is not intended.

`technolife.ir` remains **excluded** (`Content-Signal: ai-train=no`).

## robots.txt / Content-Signal (kept domains)

Checked 2026-07-28 with UA `persian-seo-os-ezafe-gold/0.1`:

| Domain | Outcome | Kept? |
| --- | --- | --- |
| digiato.com | allow `/` | yes |
| tarafdari.com | allow root | yes |
| digikala.com | allow `/mag/` | yes |
| blog.okala.com | allow `/` | yes |
| okala.com | allow `/` | yes |
| hamshahrionline.ir | allow `/` | yes |
| basalam.com | allow `/`, no ai-train=no | yes |
| emalls.ir | allow `/`, no ai-train=no | yes |
| modiseh.com | allow `/`, no ai-train=no | yes |
| torob.com | allow `/` but harvest often times out; not required for ≥3-domain ecommerce | optional |
| technolife.ir | `ai-train=no` → unclear for ML gold | **no** |
| fa.wikipedia.org | MediaWiki API under Wikimedia etiquette (not HTML `/w/` crawl) | yes |

## Token contract

- `tokens` + required `char_spans` + `tokenizer_source=dadmatools` +
  `dadmatools_version` + `tokens_minted_at`
- Verify (env-gated Dadma cache): `python scripts/verify_gold_tokens.py`
- Eval refuses to score on mismatch

## Labeling batch 1

- Worksheet: `ezafe_worksheet_batch1_seed20260728.csv` (UTF-8 BOM)
- Manifest: `ezafe_worksheet_batch1_seed20260728.manifest.json` (ids + seed)
- Stratified: 25 wiki + 25 commercial; no batch-2 overlap via manifest ids

## Workflow

1. Expand ecommerce if needed: `python scripts/expand_ecommerce_gold.py`
2. Remint spans: `python scripts/remint_gold_char_spans.py`
3. Verify: `python scripts/verify_gold_tokens.py`
4. Worksheet: `python scripts/make_ezafe_worksheet.py --seed 20260728`
5. Human labels → `ingest_ezafe_worksheet.py`
6. Eval: `python scripts/eval_ezafe_gold.py`
