import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from toraiz_dump.cli import autodetect_ports, main
from toraiz_dump.protocol import SequencerData, SequencerStep


class ContextValue:
    def __init__(self, value=None):
        self.value = value or object()

    def __enter__(self):
        return self.value

    def __exit__(self, *_exc_info):
        return None


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
        self.assertEqual(output.getvalue(), "toraiz-dump 0.5.0\n")

    @patch("toraiz_dump.cli.read_current_sequencer")
    @patch("toraiz_dump.cli.RtMidiPollingInput")
    @patch("mido.open_output")
    def test_strudel_format_writes_file_and_prints_display(
        self, open_output, polling_input, read_sequence
    ):
        open_output.return_value = ContextValue()
        polling_input.return_value = ContextValue()
        read_sequence.return_value = SequencerData(
            length=2,
            steps=(
                SequencerStep(note=60, velocity=100),
                SequencerStep(note=0, velocity=0),
            ),
            raw_length=1,
            program_name="Test",
            bpm=120,
        )

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "sequence.strudel"
            output = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "toraiz-dump",
                    "--midi-output",
                    "TORAIZ AS-1",
                    "--format",
                    "strudel",
                    "--output",
                    str(destination),
                ],
            ):
                with redirect_stdout(output):
                    result = main()

            self.assertEqual(result, 0)
            self.assertEqual(
                destination.read_text(encoding="utf-8"),
                'setcpm(120/4)\nnote("<60 ~>*16")\n.sound("supersaw")\n',
            )
            self.assertIn("Program: Test", output.getvalue())

    @patch("toraiz_dump.cli.write_midi")
    @patch("toraiz_dump.cli.read_current_sequencer")
    @patch("toraiz_dump.cli.RtMidiPollingInput")
    @patch("mido.open_output")
    def test_midi_format_still_prints_display(
        self, open_output, polling_input, read_sequence, write_midi
    ):
        open_output.return_value = ContextValue()
        polling_input.return_value = ContextValue()
        read_sequence.return_value = SequencerData(
            length=1,
            steps=(SequencerStep(note=60, velocity=100),),
            raw_length=0,
            program_name="MIDI Test",
        )

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "sequence.mid"
            output = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "toraiz-dump",
                    "--midi-output",
                    "TORAIZ AS-1",
                    "--format",
                    "midi",
                    "--output",
                    str(destination),
                ],
            ):
                with redirect_stdout(output):
                    result = main()

        self.assertEqual(result, 0)
        write_midi.assert_called_once()
        self.assertIn("Program: MIDI Test", output.getvalue())


if __name__ == "__main__":
    unittest.main()
