# Ezafe gold corpus — NOTICE

## Purpose

`ezafe_gold.jsonl` holds **one short Persian sentence per record** (not a
paragraph) for **human-blind** ezafe (kasreh-ezafe) labeling and later offline
evaluation. Labels must never be pre-filled from `detect_ezafe` or any other
model. Token *boundaries* may follow DadmaTools after an alignment dry-run;
that is not a label leak (see guidelines).

Guidelines: [`docs/gold-ezafe-guidelines.md`](../../docs/gold-ezafe-guidelines.md).

## Sources and licenses

| `source` (domain) | `source_kind` | n sentences | License / terms |
| --- | --- | ---: | --- |
| `fa.wikipedia.org` | `wikipedia` | 120 | **CC BY-SA 4.0** — attribution via `page_title`, `revision_id`, `source_url` |
| `tarafdari.com` | `blog_portal` | 21 | `source-site-terms (snippet for evaluation only)` |
| `digiato.com` | `blog_portal` | 14 | same |
| `hamshahrionline.ir` | `news_portal` | 14 | same |
| `blog.okala.com` | `shop_mag` | 9 | same |
| `digikala.com` | `shop_mag` | 7 | same |

Each non-wiki record is a **single sentence** harvested once from a public HTML
page (`source_url` + `collected_at`). Full-page redistribution is not intended.

`technolife.ir` (15 sentences) was **removed**: robots.txt carries
`Content-Signal: ai-train=no`, so status for an ML-eval gold set is not clear.
Unclear → drop, do not keep ambiguous rows.

Sampling is a **one-time online harvest** (`scripts/collect_ezafe_gold.py`).
Unit tests must not call that script or the network.

## Token contract (alignment dry-run)

Dry-run on 185 unlabeled sentences (`scripts/dryrun_ezafe_alignment.py`,
2026-07-28):

| | n_aligned | n_unaligned | rate |
| --- | ---: | ---: | ---: |
| hand whitespace tokens | 3 | 182 | **98.4%** fail |
| after Dadma token remint | 185 | 0 | 0% |

Dominant mismatch buckets before remint: punctuation 114, other 30, zwnj 19,
number 18, latin 1. Decision: **worksheet `tokens` = DadmaTools boundaries**.
`ezafe` labels remain null until human blind labeling. Summary file:
`alignment_dryrun_summary.json`.

## robots.txt check (2026-07-28)

UA used for harvest: `persian-seo-os-ezafe-gold/0.1 …`

| Domain | robots outcome for harvested URL | Kept? |
| --- | --- | --- |
| `digiato.com` | `User-agent: *` allows `/` (only wp-admin etc. disallowed) | yes |
| `tarafdari.com` | allows site root; disallows Drupal internals | yes |
| `digikala.com` | allows `/mag/` (query/checkout paths disallowed) | yes |
| `blog.okala.com` | allows `/` (wp-admin disallowed) | yes |
| `hamshahrionline.ir` | allows `/` | yes |
| `technolife.ir` | Allow `/` but `Content-Signal: ai-train=no` → **unclear for ML gold** | **no** |
| `fa.wikipedia.org` | HTML crawlers: `Disallow: /w/`; harvest used **MediaWiki API** under Wikimedia API etiquette (identified UA + throttle), CC BY-SA | yes |

## Record fields (selected)

- `text`, `tokens` — one sentence and token boundaries for the worksheet
- `ezafe` — `null` until human ingest; then `0|1` per token
- `verified`, `ambiguous`, `labeled_by`, `labeled_at`
- `strata` — sampling strata tags (quotas), not gold labels
- `source` — concrete domain (`fa.wikipedia.org`, `digiato.com`, …)
- `source_kind` — bucket (`wikipedia`, `blog_portal`, `shop_mag`, `news_portal`)
- `source_url`, `license`, `collected_at`
- Wikipedia extras: `page_title`, `revision_id`

## Workflow

1. Collect (once): `python scripts/collect_ezafe_gold.py`
2. Source normalize: `python scripts/migrate_ezafe_sources.py`
3. Alignment dry-run: `python scripts/dryrun_ezafe_alignment.py`  
   (no worksheet until this report is reviewed)
4. Worksheet: `python scripts/make_ezafe_worksheet.py`
5. Human labels in Excel/LibreOffice
6. Ingest: `python scripts/ingest_ezafe_worksheet.py --worksheet … --labeled-by NAME`
7. Eval (offline, needs Dadma cache): `python scripts/eval_ezafe_gold.py`
