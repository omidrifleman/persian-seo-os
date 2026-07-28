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


if __name__ == "__main__":
    unittest.main()
