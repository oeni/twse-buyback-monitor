import tempfile
import unittest
from pathlib import Path

from twse_buyback.cli import build_parser
from twse_buyback.config import Settings, default_output_dir


class TestDefaults(unittest.TestCase):
    def test_settings_default_to_repository_output_directory(self):
        settings = Settings()
        self.assertEqual(settings.data_dir, default_output_dir())
        self.assertEqual(settings.data_dir.name, "output")

    def test_cli_requires_no_arguments(self):
        args = build_parser().parse_args([])
        self.assertEqual(args.data_dir, default_output_dir())

    def test_output_dir_option_and_legacy_alias_match(self):
        custom = Path(tempfile.mkdtemp())
        primary = build_parser().parse_args(["--output-dir", str(custom)])
        legacy = build_parser().parse_args(["--data-dir", str(custom)])
        self.assertEqual(primary.data_dir, custom)
        self.assertEqual(legacy.data_dir, custom)


if __name__ == "__main__":
    unittest.main()
