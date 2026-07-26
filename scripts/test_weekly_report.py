import importlib.util
import sys
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("weekly_report", Path(__file__).with_name("weekly_report.py"))
weekly_report = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = weekly_report
SPEC.loader.exec_module(weekly_report)


class WeeklyReportTests(unittest.TestCase):
    def test_numeric_ranges_use_wave_dash_without_changing_identifiers(self):
        text = "3-5 μm，2.5–4.0 V，DOI: 10.1007/s11220-025-00682-7，2026-7-26"
        self.assertEqual(
            weekly_report.normalize_numeric_ranges(text),
            "3～5 μm，2.5～4.0 V，DOI: 10.1007/s11220-025-00682-7，2026-7-26",
        )

    def test_verified_correspondence_omits_source_from_word_text(self):
        paper = {
            "title": "Example",
            "citation": "Example. DOI: 10.1/example.",
            "correspondence": {
                "author": "Alice Example",
                "unit": "Example University",
                "source_url": "https://journal.example/article",
            },
        }
        draft = weekly_report.draft_literature_from_paper(paper)
        self.assertEqual(draft["corresponding_author_unit"], "通讯作者：Alice Example；单位：Example University。")

    def test_placeholder_correspondence_is_rejected(self):
        self.assertIsNotNone(weekly_report.PLACEHOLDER_CORRESPONDENCE_RE.search("需根据来源进一步确认"))


if __name__ == "__main__":
    unittest.main()
