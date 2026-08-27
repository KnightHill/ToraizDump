import io
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from toraiz_dump.cli import autodetect_ports, main


class CliTests(unittest.TestCase):
    def test_autodetects_one_bidirectional_port(self):
        self.assertEqual(
            autodetect_ports(["TORAIZ AS-1"], ["TORAIZ AS-1"]),
            ("TORAIZ AS-1", "TORAIZ AS-1"),
        )

    def test_autodetects_separate_matching_ports(self):
        self.assertEqual(
            autodetect_ports(
                ["TORAIZ AS-1 MIDI In"], ["TORAIZ AS-1 MIDI Out"]
            ),
            ("TORAIZ AS-1 MIDI In", "TORAIZ AS-1 MIDI Out"),
        )

    def test_autodetect_rejects_missing_port_direction(self):
        with self.assertRaisesRegex(RuntimeError, "both TORAIZ"):
            autodetect_ports(["TORAIZ AS-1 MIDI In"], ["Other MIDI Out"])

    def test_autodetect_rejects_ambiguous_devices(self):
        with self.assertRaisesRegex(RuntimeError, "multiple"):
            autodetect_ports(
                ["TORAIZ AS-1 MIDI In", "TORAIZ AS-1 MIDI In"],
                ["TORAIZ AS-1 MIDI Out", "TORAIZ AS-1 MIDI Out"],
            )

    def test_version_option(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["toraiz-dump", "--version"]):
            with redirect_stdout(output):
                with self.assertRaises(SystemExit) as raised:
                    main()

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(output.getvalue(), "toraiz-dump 0.2.2\n")


if __name__ == "__main__":
    unittest.main()
