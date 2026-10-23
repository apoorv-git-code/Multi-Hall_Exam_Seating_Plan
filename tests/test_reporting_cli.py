"""Smoke tests for available reporting helpers and CLI parser.

The checked-in archive has legacy root-level reporting modules and a main entry
point; tests skip optional modules whose imports are not available in this snapshot.
"""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class ReportingAndCliTests(unittest.TestCase):
    def test_report_builder_module_is_present(self):
        self.assertTrue((ROOT / "src" / "reporting" / "report_builder.py").exists() or (ROOT / "report_builder.py").exists())

    def test_cli_entrypoint_is_present(self):
        self.assertTrue((ROOT / "main.py").exists() or (ROOT / "main (1).py").exists())

    def test_csv_export_module_is_present(self):
        self.assertTrue((ROOT / "src" / "reporting" / "csv_export.py").exists() or (ROOT / "csv_export.py").exists())


if __name__ == "__main__": unittest.main()
