import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from toraiz_dump.programs_cli import main
from toraiz_dump.protocol import ProgramSummary


class ContextValue:
    def __init__(self, value=None):
        self.value = value or object()

    def __enter__(self):
        return self.value

    def __exit__(self, *_exc_info):
        return None


class ProgramsCliTests(unittest.TestCase):
    @patch("toraiz_dump.programs_cli.iter_program_summaries")
    @patch("toraiz_dump.programs_cli.RtMidiPollingInput")
    @patch("mido.open_output")
    def test_prints_one_line_per_program(
        self, open_output, polling_input, iter_summaries
    ):
        open_output.return_value = ContextValue()
        polling_input.return_value = ContextValue()
        iter_summaries.return_value = iter((
            ProgramSummary("U1", 1, "Basic Program"),
            ProgramSummary("F5", 99, ""),
        ))
        output = io.StringIO()

        with patch.object(
            sys,
            "argv",
            ["toraiz-programs", "--midi-output", "TORAIZ AS-1"],
        ):
            with redirect_stdout(output):
                result = main()

        self.assertEqual(result, 0)
        self.assertEqual(
            output.getvalue(),
            "U1 P01 Basic Program\nF5 P99 (unnamed)\n",
        )

    def test_version_option(self):
        output = io.StringIO()
        with patch.object(sys, "argv", ["toraiz-programs", "--version"]):
            with redirect_stdout(output):
                with self.assertRaises(SystemExit) as raised:
                    main()

        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(output.getvalue(), "toraiz-programs 0.4.0\n")

    @patch("toraiz_dump.programs_cli.iter_program_summaries")
    @patch("toraiz_dump.programs_cli.RtMidiPollingInput")
    @patch("mido.open_output")
    def test_timeout_exits_without_a_traceback(
        self, open_output, polling_input, iter_summaries
    ):
        open_output.return_value = ContextValue()
        polling_input.return_value = ContextValue()
        iter_summaries.side_effect = TimeoutError("timed out waiting for U2 P03")
        errors = io.StringIO()

        with patch.object(
            sys,
            "argv",
            ["toraiz-programs", "--midi-output", "TORAIZ AS-1"],
        ):
            with redirect_stderr(errors):
                with self.assertRaises(SystemExit) as raised:
                    main()

        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(
            errors.getvalue(),
            "toraiz-programs: error: timed out waiting for U2 P03\n",
        )


if __name__ == "__main__":
    unittest.main()
