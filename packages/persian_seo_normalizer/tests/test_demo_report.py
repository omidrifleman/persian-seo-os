"""تست ابزار نمایش خوشه‌بندی (demo_report) — بدون شبکه."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "packages"))

import demo_report  # noqa: E402


class DemoReportTest(unittest.TestCase):
    def test_writes_html_with_rtl_and_cluster_ids(self) -> None:
        demo_txt = ROOT / "data" / "demo_keywords.txt"
        self.assertTrue(demo_txt.is_file())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo_report.html"
            result = demo_report.write_demo_report(demo_txt, out)
            self.assertTrue(out.is_file())
            body = out.read_text(encoding="utf-8")
            self.assertIn('dir="rtl"', body)
            self.assertIn('lang="fa"', body)
            self.assertGreater(len(result.clusters), 0)
            for cl in result.clusters:
                self.assertIn(cl.cluster_id, body)

    def test_tarahi_site_hub_is_one_group_with_four_intents(self) -> None:
        demo_txt = ROOT / "data" / "demo_keywords.txt"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo_report.html"
            result = demo_report.write_demo_report(demo_txt, out)
            body = out.read_text(encoding="utf-8")
            hubs = demo_report.group_topic_hubs(result)
            tarahi = [h for h in hubs if h.topic_core_label == "طراحی سایت"]
            self.assertEqual(len(tarahi), 1)
            hub = tarahi[0]
            self.assertEqual(hub.intent_count, 4)
            self.assertEqual(
                {c.intent for c in hub.clusters},
                {
                    "transactional",
                    "commercial",
                    "informational",
                    "unknown",
                },
            )
            hub_marker = f'id="hub-{hub.topic_core_fingerprint}"'
            self.assertEqual(body.count(hub_marker), 1)
            self.assertIn('data-topic-core="طراحی سایت"', body)
            self.assertIn('data-intent-count="4"', body)
            hub_pos = body.index(hub_marker)
            later_hubs = [
                h
                for h in hubs
                if h.topic_core_fingerprint != hub.topic_core_fingerprint
            ]
            next_pos = min(
                (body.index(f'id="hub-{h.topic_core_fingerprint}"') for h in later_hubs),
                default=len(body),
            )
            # اگر هاب طراحی سایت اول نباشد، next_pos باید بعد از hub_pos باشد
            if next_pos < hub_pos:
                # هاب دیگری قبل است؛ مرز پایانی = ابتدای هاب بعدی بعد از این هاب
                after = [
                    body.index(f'id="hub-{h.topic_core_fingerprint}"')
                    for h in later_hubs
                    if body.index(f'id="hub-{h.topic_core_fingerprint}"') > hub_pos
                ]
                next_pos = min(after) if after else body.index('class="skipped"')
            section = body[hub_pos:next_pos]
            self.assertEqual(section.count('class="cluster"'), 4)
            for cl in hub.clusters:
                self.assertIn(f'id="c-{cl.cluster_id}"', section)
            self.assertNotIn("تک‌عضوی", body)
            self.assertIn("هاب موضوعی", body)
            self.assertIn("میانگین نیت در هر هاب", body)


if __name__ == "__main__":
    unittest.main()
