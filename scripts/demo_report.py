#!/usr/bin/env python3
"""Demo: خوشه‌بندی کلیدواژه → گزارش HTML محلی (بدون شبکه)."""
from __future__ import annotations

import argparse
import html
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))

from persian_seo_normalizer.keyword_cluster import (  # noqa: E402
    ClusterResult,
    KeywordInput,
    cluster_keywords,
)

DEFAULT_INPUT = ROOT / "data" / "demo_keywords.txt"
DEFAULT_OUTPUT = ROOT / "out" / "demo_report.html"


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


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_demo_html(result: ClusterResult, *, input_count: int) -> str:
    """ساخت HTML کامل از ClusterResult — همه متن‌ها از دیتاکلاس‌ها."""
    singleton_n = sum(1 for c in result.clusters if len(c.members) == 1)
    cluster_n = len(result.clusters)
    singleton_pct = (
        f"{(100.0 * singleton_n / cluster_n):.0f}%" if cluster_n else "—"
    )
    intent_counts = Counter(c.intent for c in result.clusters)

    summary_bits = [
        f"<li>ورودی: <strong>{_e(input_count)}</strong></li>",
        f"<li>خوشه: <strong>{_e(cluster_n)}</strong></li>",
        f"<li>تک‌عضوی: <strong>{_e(singleton_n)}</strong> "
        f"(<strong>{_e(singleton_pct)}</strong>)</li>",
        f"<li>ردشده: <strong>{_e(len(result.skipped))}</strong></li>",
    ]
    dist_items = "".join(
        f"<li>{_e(intent)}: <strong>{_e(n)}</strong></li>"
        for intent, n in sorted(intent_counts.items())
    )
    summary_bits.append(f"<li>توزیع نیت:<ul>{dist_items}</ul></li>")

    cluster_sections: list[str] = []
    for cl in result.clusters:
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
        cluster_sections.append(
            f'<section class="cluster" id="c-{_e(cl.cluster_id)}">'
            f"<h2>خوشه <code>{_e(cl.cluster_id)}</code></h2>"
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
h1, h2 {{ font-weight: 700; }}
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
.cluster, .skipped, .summary {{
  margin-bottom: 2rem;
  padding: 1rem;
  background: #fff;
  border: 1px solid #ddd;
}}
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
{"".join(cluster_sections)}
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
    print(f"wrote {args.output} clusters={len(result.clusters)} skipped={len(result.skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
