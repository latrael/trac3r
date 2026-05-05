import csv
import unittest
from pathlib import Path

from backend.engine.analyzer import analyze


ROOT = Path(__file__).resolve().parents[1]


def load_dataset(path: str) -> list[dict]:
    with (ROOT / path).open(newline="") as handle:
        return list(csv.DictReader(handle))


class AnalyzerTests(unittest.TestCase):
    def test_missing_values(self):
        result = analyze([
            {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": ""},
        ])

        self.assertIn("Missing values detected: value is null in 1 rows", result["flags"])
        self.assertLessEqual(result["trustScore"], 0.90)

    def test_duplicate_timestamps(self):
        result = analyze([
            {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
            {"timestamp": "2026-04-29T19:00:00Z", "source": "node2", "value": 1210},
        ])

        self.assertIn(
            "Duplicate timestamp detected: 2026-04-29T19:00:00Z appears 2 times",
            result["flags"],
        )

    def test_timestamp_gaps(self):
        result = analyze([
            {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
            {"timestamp": "2026-04-29T19:01:00Z", "source": "node2", "value": 1210},
            {"timestamp": "2026-04-29T19:03:00Z", "source": "node1", "value": 1205},
        ])

        self.assertTrue(any(flag.startswith("Timestamp gap detected") for flag in result["flags"]))

    def test_value_spikes(self):
        result = analyze([
            {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200},
            {"timestamp": "2026-04-29T19:01:00Z", "source": "node2", "value": 1210},
            {"timestamp": "2026-04-29T19:02:00Z", "source": "node1", "value": 1190},
            {"timestamp": "2026-04-29T19:03:00Z", "source": "node2", "value": 7200},
        ])

        self.assertTrue(any(flag.startswith("Major value spike detected") for flag in result["flags"]))

    def test_replayed_rows(self):
        row = {"timestamp": "2026-04-29T19:00:00Z", "source": "node1", "value": 1200}
        result = analyze([row, row.copy()])

        self.assertIn(
            "Replayed row detected: row 2 is an exact duplicate of row 1",
            result["flags"],
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
