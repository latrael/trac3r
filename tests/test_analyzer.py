import csv
import unittest
from pathlib import Path

from backend.engine.analyzer import (
    analyze,
    check_duplicate_timestamps,
    check_missing_values,
    check_replayed_rows,
    check_timestamp_gaps,
    check_value_spikes,
)


ROOT = Path(__file__).resolve().parents[1]


def load_dataset(path: str) -> list[dict]:
    with (ROOT / path).open(newline="") as handle:
        return list(csv.DictReader(handle))


class AnalyzerTests(unittest.TestCase):
    def test_missing_values(self):
        dataset = [
            {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": ""},
        ]

        flags, deduction = check_missing_values(dataset)
        result = analyze(dataset)

        self.assertIn("Missing values detected: value is null in 1 rows", flags)
        self.assertEqual(deduction, 0.10)
        self.assertEqual(result["trustScore"], 0.90)

    def test_duplicate_timestamps(self):
        dataset = [
            {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
            {"timestamp": "2026-04-29T19:00:00Z", "source": "node2", "value": 1210},
        ]

        flags, deduction = check_duplicate_timestamps(dataset)
        result = analyze(dataset)

        self.assertIn(
            "Duplicate timestamp detected: 2026-04-29T19:00:00Z appears 2 times",
            flags,
        )
        self.assertEqual(deduction, 0.20)
        self.assertEqual(result["trustScore"], 0.80)

    def test_timestamp_gaps(self):
        dataset = [
            {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
            {"timestamp": "2026-04-29T19:01:00Z", "source": "node2", "value": 1210},
            {"timestamp": "2026-04-29T19:03:00Z", "source": "node1", "value": 1205},
        ]

        flags, deduction = check_timestamp_gaps(dataset)
        result = analyze(dataset)

        self.assertTrue(any(flag.startswith("Timestamp gap detected") for flag in flags))
        self.assertEqual(deduction, 0.20)
        self.assertEqual(result["trustScore"], 0.80)

    def test_value_spikes(self):
        dataset = [
            {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
            {"timestamp": "2026-04-29T19:01:00Z", "source": "node2", "value": 1210},
            {"timestamp": "2026-04-29T19:02:00Z", "source": "node1", "value": 1190},
            {"timestamp": "2026-04-29T19:03:00Z", "source": "node2", "value": 7200},
        ]

        flags, deduction = check_value_spikes(dataset)
        result = analyze(dataset)

        self.assertTrue(any(flag.startswith("Major value spike detected") for flag in flags))
        self.assertEqual(deduction, 0.30)
        self.assertEqual(result["trustScore"], 0.70)

    def test_replayed_rows(self):
        row = {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200}
        flags, deduction = check_replayed_rows([row, row.copy()])

        self.assertIn(
            "Replayed row detected: row 2 is an exact duplicate of row 1",
            flags,
        )
        self.assertEqual(deduction, 0.30)

    def test_status_thresholds(self):
        self.assertEqual(
            analyze([
                {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
                {"timestamp": "2026-04-29T19:01:00Z", "source": "node2", "value": 1210},
            ])["status"],
            "verified",
        )
        self.assertEqual(
            analyze([
                {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
                {"timestamp": "2026-04-29T19:00:00Z", "source": "node2", "value": ""},
            ])["status"],
            "warning",
        )
        self.assertEqual(
            analyze([
                {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
                {"timestamp": "2026-04-29T19:01:00Z", "source": "node2", "value": 1210},
                {"timestamp": "2026-04-29T19:02:00Z", "source": "node1", "value": 1190},
                {"timestamp": "2026-04-29T19:03:00Z", "source": "node2", "value": 7200},
            ])["status"],
            "warning",
        )
        self.assertEqual(
            analyze([
                {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
                {"timestamp": "2026-04-29T19:00:00Z", "source": "node2", "value": 1210},
                {"timestamp": "2026-04-29T19:01:00Z", "source": "node1", "value": 1190},
                {"timestamp": "2026-04-29T19:02:00Z", "source": "node2", "value": 7200},
            ])["status"],
            "flagged",
        )

    def test_clean_dataset(self):
        result = analyze(load_dataset("demo-data/clean_dataset.csv"))

        self.assertEqual(result["status"], "verified")
        self.assertGreaterEqual(result["trustScore"], 0.90)
        self.assertEqual(result["flags"], [])

    def test_tampered_dataset(self):
        result = analyze(load_dataset("demo-data/tampered_dataset.csv"))

        self.assertEqual(result["status"], "flagged")
        self.assertLessEqual(result["trustScore"], 0.60)
        self.assertGreaterEqual(len(result["flags"]), 3)


if __name__ == "__main__":
    unittest.main()
