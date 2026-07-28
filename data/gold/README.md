# Ezafe gold corpus — NOTICE

## Purpose

`ezafe_gold.jsonl` holds short Persian sentences for **human-blind** ezafe
(kasreh-ezafe) labeling and later offline evaluation. Labels must never be
pre-filled from `detect_ezafe` or any other model.

Guidelines: [`docs/gold-ezafe-guidelines.md`](../../docs/gold-ezafe-guidelines.md).

## Sources and licenses

| Source field | Origin | License / terms |
| --- | --- | --- |
| `fa.wikipedia` | Persian Wikipedia page extracts via MediaWiki API | **CC BY-SA 4.0** — attribution via `page_title`, `revision_id`, `source_url` |
| `shop_mag` / `blog_portal` / `news_portal` | Short sentences scraped once from public HTML magazine/blog/news landing pages | Recorded as `source-site-terms (snippet for evaluation only)`; keep `source_url` + `collected_at`. Redistribution of full page text is not intended — only short evaluation snippets. |

Sampling is a **one-time online harvest** (`scripts/collect_ezafe_gold.py`).
Unit tests must not call that script or the network.

## Record fields (selected)

- `text`, `tokens` — sentence and raw tokens for the worksheet
- `ezafe` — `null` until human ingest; then `0|1` per token
- `verified`, `ambiguous`, `labeled_by`, `labeled_at`
- `strata` — sampling strata tags (quotas), not gold labels
- `source`, `source_url`, `license`, `collected_at`
- Wikipedia extras: `page_title`, `revision_id`

## Workflow

1. Collect (once): `python scripts/collect_ezafe_gold.py`
2. Worksheet: `python scripts/make_ezafe_worksheet.py`
3. Human labels in Excel/LibreOffice
4. Ingest: `python scripts/ingest_ezafe_worksheet.py --worksheet data/gold/ezafe_worksheet.csv --labeled-by NAME`
5. Eval (offline, needs Dadma cache): `python scripts/eval_ezafe_gold.py`
