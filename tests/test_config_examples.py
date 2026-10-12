import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


def configured_year(text, key):
    match = re.search(rf"{key}[^\n]*?(20\d{{2}})", text)
    if match is None:
        raise AssertionError(f"Missing {key} year")
    return int(match.group(1))


class ConfigExampleTests(unittest.TestCase):
    def test_target_year_follows_historical_year(self):
        for path in (ROOT / "secrets.py.example", ROOT / "README.md"):
            with self.subTest(path=path.name):
                text = path.read_text()
                target_year = configured_year(text, "target_date")
                last_year = configured_year(text, "last_year")
                self.assertEqual(target_year, last_year + 1)


if __name__ == "__main__":
    unittest.main()
