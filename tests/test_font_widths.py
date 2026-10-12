import unittest
from pathlib import Path

FONT_PATH = Path(__file__).parents[1] / "Micro5-Regular-21.bdf"


def load_advance_widths():
    widths = {}
    encoding = None
    for line in FONT_PATH.read_text().splitlines():
        if line.startswith("ENCODING "):
            encoding = int(line.split()[1])
        elif line.startswith("DWIDTH ") and encoding is not None:
            widths[chr(encoding)] = int(line.split()[1])
    return widths


class FontWidthTests(unittest.TestCase):
    def test_display_strings_fit_64_pixels(self):
        widths = load_advance_widths()
        strings = (
            "999:59:59",
            "$999,999",
            "IN 2026",
            "ALL TIME",
            "RAISED",
            "FOR UCSF",
            "EVENT IN",
            "999 DAYS",
            "MORE AT",
            "STJ.WATCH",
        )
        for value in strings:
            with self.subTest(value=value):
                width = sum(widths[character] for character in value)
                self.assertLessEqual(width, 64)

        url_width = sum(widths[character] for character in "STJ.WATCH")
        self.assertEqual(url_width, 64)


if __name__ == "__main__":
    unittest.main()
