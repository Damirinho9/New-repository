#!/usr/bin/env python3
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAPPER = ROOT / "mapper.py"
REDUCER = ROOT / "reducer.py"


def run_script(script: Path, data: str) -> str:
    result = subprocess.run(
        [sys.executable, str(script)],
        input=data,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout


class WordCountScriptsTest(unittest.TestCase):
    def test_mapper_emits_word_count_pairs(self):
        actual = run_script(MAPPER, "hadoop hdfs\nhadoop data\n")
        self.assertEqual(
            actual,
            "hadoop\t1\nhdfs\t1\nhadoop\t1\ndata\t1\n",
        )

    def test_reducer_aggregates_adjacent_sorted_keys(self):
        actual = run_script(
            REDUCER,
            "apple\t1\napple\t2\nbanana\t1\n",
        )
        self.assertEqual(actual, "apple\t3\nbanana\t1\n")

    def test_complete_local_pipeline(self):
        source = "hadoop hdfs hadoop\nhdfs yarn\n"
        mapped = run_script(MAPPER, source)
        ordered = "".join(
            sorted(
                mapped.splitlines(keepends=True),
                key=lambda row: row.split("\t", 1)[0].encode("utf-8"),
            )
        )
        actual = run_script(REDUCER, ordered)
        self.assertEqual(
            actual,
            "hadoop\t2\nhdfs\t2\nyarn\t1\n",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
