#!/usr/bin/env python3
"""Demo: خوشه‌بندی کلیدواژه → گزارش HTML محلی (بدون شبکه)."""
from __future__ import annotations

import argparse
import html
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from persian_seo_normalizer.keyword_cluster import (  # noqa: E402
    ClusterResult,
    KeywordCluster,
    KeywordInput,
    cluster_keywords,
)

DEFAULT_INPUT = ROOT / "data" / "demo_keywords.txt"
DEFAULT_OUTPUT = ROOT / "out" / "demo_report.html"

_INTENT_ORDER = (
    "transactional",
    "commercial",
    "informational",
    "navigational",
    "unknown",
)
_INTENT_RANK = {name: i for i, name in enumerate(_INTENT_ORDER)}


@dataclass(frozen=True)
class TopicHubView:
    """نمای نمایشی هاب موضوعی — فقط برای گزارش، نه موجودیت دامنه."""

    topic_core_fingerprint: str
    topic_core_label: str
    intent_count: int
    keyword_count: int
    clusters: tuple[KeywordCluster, ...]


def load_keyword_inputs(path: Path) -> list[KeywordInput]:
    """هر خط غیرخالی (غیر #) یک کلیدواژه؛ اختیاری: id\\ttext."""
    items: list[KeywordInput] = []
    auto_n = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.lstrip().startswith("#"):
            continue
        if raw.strip() == "" and "\t" not in raw:
            continue
        if "\t" in raw:
            kid, text = raw.split("\t", 1)
            items.append(KeywordInput(keyword_id=kid.strip(), text=text.strip()))
        else:
            auto_n += 1
            items.append(KeywordInput(keyword_id=f"k{auto_n:03d}", text=raw.strip()))
    return items


def group_topic_hubs(result: ClusterResult) -> tuple[TopicHubView, ...]:
    """گروه‌بندی خوشه‌ها بر topic_core_fingerprint برای نمایش."""
    by_fp: dict[str, list[KeywordCluster]] = defaultdict(list)
    for cl in result.clusters:
        by_fp[cl.topic_core_fingerprint].append(cl)

    hubs: list[TopicHubView] = []
    for fp, clusters in by_fp.items():
        ordered = tuple(
            sorted(
                clusters,
                key=lambda c: (_INTENT_RANK.get(c.intent, 99), c.cluster_id),
            )
        )
        label = " ".join(ordered[0].members[0].topic_core_tokens)
        keyword_count = sum(len(c.members) for c in ordered)
        intent_count = len({c.intent for c in ordered})
        hubs.append(
            TopicHubView(
                topic_core_fingerprint=fp,
                topic_core_label=label,
                intent_count=intent_count,
                keyword_count=keyword_count,
                clusters=ordered,
            )
        )
    hubs.sort(
        key=lambda h: (-h.keyword_count, h.topic_core_label, h.topic_core_fingerprint)
    )
    return tuple(hubs)


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _render_cluster(cl: KeywordCluster) -> str:
    codes = ", ".join(_e(c) for c in cl.reason_codes) or "—"
    rows: list[str] = []
    for m in cl.members:
        markers = ", ".join(
            f"{_e(fm.surface)} ({_e(fm.intent)}, @{_e(fm.token_start)})"
            for fm in m.intent_markers
        ) or "—"
        core = " ".join(_e(t) for t in m.topic_core_tokens) or "—"
        rows.append(
            "<tr>"
            f"<td>{_e(m.keyword_id)}</td>"
            f"<td>{_e(m.text)}</td>"
            f"<td><code>{core}</code></td>"
            f"<td>{markers}</td>"
            f"<td>{_e(m.search_demand_status)}</td>"
            f"<td>{_e(m.search_demand if m.search_demand is not None else '—')}</td>"
            "</tr>"
        )
    return (
        f'<section class="cluster" id="c-{_e(cl.cluster_id)}">'
        f"<h3>خوشه <code>{_e(cl.cluster_id)}</code></h3>"
        "<dl>"
        f"<dt>نیت</dt><dd>{_e(cl.intent)}</dd>"
        f"<dt>head</dt><dd>{_e(cl.head_keyword_id)} — {_e(cl.head_text)}</dd>"
        f"<dt>head_decided_by</dt><dd>{_e(cl.head_decided_by)}</dd>"
        f"<dt>reason_codes</dt><dd><code>{codes}</code></dd>"
        "</dl>"
        "<table><thead><tr>"
        "<th>keyword_id</th><th>متن</th><th>topic_core</th>"
        "<th>نشانگرها</th><th>demand_status</th><th>demand</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></section>"
    )


def render_demo_html(result: ClusterResult, *, input_count: int) -> str:
    """ساخت HTML کامل از ClusterResult — همه متن‌ها از دیتاکلاس‌ها."""
    hubs = group_topic_hubs(result)
    hub_n = len(hubs)
    avg_intents = (
        f"{(sum(h.intent_count for h in hubs) / hub_n):.2f}" if hub_n else "—"
    )
    intent_counts = Counter(c.intent for c in result.clusters)

    summary_bits = [
        f"<li>ورودی: <strong>{_e(input_count)}</strong></li>",
        f"<li>خوشه: <strong>{_e(len(result.clusters))}</strong></li>",
        f"<li>هاب موضوعی: <strong>{_e(hub_n)}</strong></li>",
        f"<li>میانگین نیت در هر هاب: <strong>{_e(avg_intents)}</strong></li>",
        f"<li>ردشده: <strong>{_e(len(result.skipped))}</strong></li>",
    ]
    dist_items = "".join(
        f"<li>{_e(intent)}: <strong>{_e(n)}</strong></li>"
        for intent, n in sorted(intent_counts.items())
    )
    summary_bits.append(f"<li>توزیع نیت خوشه‌ها:<ul>{dist_items}</ul></li>")

    hub_sections: list[str] = []
    for hub in hubs:
        clusters_html = "".join(_render_cluster(cl) for cl in hub.clusters)
        hub_sections.append(
            f'<section class="hub" id="hub-{_e(hub.topic_core_fingerprint)}" '
            f'data-topic-core="{_e(hub.topic_core_label)}" '
            f'data-intent-count="{_e(hub.intent_count)}">'
            f"<h2>هاب موضوعی: {_e(hub.topic_core_label)}</h2>"
            "<dl>"
            f"<dt>fingerprint</dt><dd><code>{_e(hub.topic_core_fingerprint)}</code></dd>"
            f"<dt>تعداد نیت</dt><dd>{_e(hub.intent_count)}</dd>"
            f"<dt>تعداد کلیدواژه</dt><dd>{_e(hub.keyword_count)}</dd>"
            "</dl>"
            f"{clusters_html}"
            "</section>"
        )

    skip_rows: list[str] = []
    for s in result.skipped:
        skip_rows.append(
            "<tr>"
            f"<td>{_e(s.keyword_id)}</td>"
            f"<td>{_e(s.text)}</td>"
            f"<td><code>{_e(s.reason_code)}</code></td>"
            f"<td>{_e(s.reason_fa)}</td>"
            "</tr>"
        )
    skipped_table = (
        "<section class=\"skipped\"><h2>ردشده‌ها (skipped)</h2>"
        "<table><thead><tr>"
        "<th>keyword_id</th><th>متن</th><th>reason_code</th><th>reason_fa</th>"
        "</tr></thead><tbody>"
        + ("".join(skip_rows) if skip_rows else "<tr><td colspan=\"4\">—</td></tr>")
        + "</tbody></table></section>"
    )

    return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8"/>
<title>گزارش خوشه‌بندی کلیدواژه</title>
<style>
body {{
  font-family: Vazirmatn, Tahoma, sans-serif;
  margin: 1.5rem;
  line-height: 1.6;
  color: #1a1a1a;
  background: #fafafa;
}}
h1, h2, h3 {{ font-weight: 700; }}
code {{ font-family: Consolas, "Courier New", monospace; font-size: 0.9em; }}
table {{
  border-collapse: collapse;
  width: 100%;
  margin: 0.75rem 0 1.5rem;
  background: #fff;
}}
th, td {{
  border: 1px solid #ccc;
  padding: 0.4rem 0.6rem;
  text-align: right;
  vertical-align: top;
}}
th {{ background: #eee; }}
.hub, .cluster, .skipped, .summary {{
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: #fff;
  border: 1px solid #ddd;
}}
.hub {{ border-color: #999; }}
.cluster {{ margin: 1rem 0 0; background: #f9f9f9; }}
dl {{ display: grid; grid-template-columns: 10rem 1fr; gap: 0.25rem 1rem; }}
dt {{ font-weight: 700; }}
dd {{ margin: 0; }}
</style>
</head>
<body>
<h1>گزارش خوشه‌بندی کلیدواژه</h1>
<section class="summary">
<h2>خلاصه</h2>
<ul>
{"".join(summary_bits)}
</ul>
</section>
{"".join(hub_sections)}
{skipped_table}
</body>
</html>
"""


def write_demo_report(
    input_path: Path,
    output_path: Path,
) -> ClusterResult:
    items = load_keyword_inputs(input_path)
    result = cluster_keywords(items)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_doc = render_demo_html(result, input_count=len(items))
    output_path.write_text(html_doc, encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="گزارش HTML خوشه‌بندی کلیدواژه")
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"فایل کلیدواژه (پیش‌فرض: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"خروجی HTML (پیش‌فرض: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args(argv)
    result = write_demo_report(args.input, args.output)
    hubs = group_topic_hubs(result)
    print(
        f"wrote {args.output} clusters={len(result.clusters)} "
        f"hubs={len(hubs)} skipped={len(result.skipped)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
