import unittest
from io import BytesIO, StringIO

import mido
from blessed import Terminal

from toraiz_dump.output import (
    STEP_TICKS,
    sequence_as_dict,
    sequence_as_display,
    write_midi,
)
from toraiz_dump.protocol import TIME_DIVISIONS, SequencerData, SequencerStep


class ColorTerminal:
    """Deterministic terminal colors independent of the test runner's TERM."""

    normal = "\033[0m"

    @staticmethod
    def color_rgb(red, green, blue):
        return f"\033[38;2;{red};{green};{blue}m"


COLOR_TERMINAL = ColorTerminal()


def make_sequence():
    return SequencerData(
        length=4,
        steps=(
            SequencerStep(note=60, velocity=100),
            SequencerStep(note=0, velocity=0),
            SequencerStep(note=64, velocity=90),
            SequencerStep(note=67, velocity=80),
            SequencerStep(note=72, velocity=127),
        ),
        raw_length=3,
        program_name="Test Program",
        bpm=123,
        time_division=TIME_DIVISIONS[6],
    )


class OutputTests(unittest.TestCase):
    def test_sequence_as_dict_returns_active_steps(self):
        value = sequence_as_dict(make_sequence())

        self.assertEqual(value["length"], 4)
        self.assertEqual(value["program_name"], "Test Program")
        self.assertEqual(value["bpm"], 123)
        self.assertEqual(value["time_division"], "16")
        self.assertEqual(len(value["steps"]), 4)
        self.assertEqual(
            value["steps"][1],
            {"note": 0, "velocity": 0, "rest": True, "tie": False},
        )

    def test_write_midi_uses_sixteenth_note_steps_and_rests(self):
        output = BytesIO()
        write_midi(make_sequence(), output)
        output.seek(0)

        midi_file = mido.MidiFile(file=output)
        meta_messages = [
            message for message in midi_file.tracks[0] if message.is_meta
        ]
        messages = [
            message for message in midi_file.tracks[0] if not message.is_meta
        ]

        self.assertEqual(
            next(message for message in meta_messages
                 if message.type == "set_tempo").tempo,
            mido.bpm2tempo(123),
        )
        self.assertIn(
            mido.MetaMessage("text", text="TORAIZ AS-1 TimeDiv: 16", time=0),
            meta_messages,
        )

        self.assertEqual(
            [
                (message.type, message.note, message.velocity, message.time)
                for message in messages
            ],
            [
                ("note_on", 60, 100, 0),
                ("note_off", 60, 0, STEP_TICKS),
                ("note_on", 64, 90, STEP_TICKS),
                ("note_off", 64, 0, STEP_TICKS),
                ("note_on", 67, 80, 0),
                ("note_off", 67, 0, STEP_TICKS),
            ],
        )

    def test_write_midi_sustains_tied_steps(self):
        sequence = SequencerData(
            length=3,
            steps=(
                SequencerStep(note=60, velocity=100),
                SequencerStep(note=60, velocity=100, tie=True),
                SequencerStep(note=64, velocity=90),
            ),
            raw_length=2,
        )
        output = BytesIO()

        write_midi(sequence, output)
        output.seek(0)
        messages = [message for message in mido.MidiFile(file=output).tracks[0]
                    if not message.is_meta]

        self.assertEqual(
            [(message.type, message.note, message.time) for message in messages],
            [
                ("note_on", 60, 0),
                ("note_off", 60, STEP_TICKS * 2),
                ("note_on", 64, 0),
                ("note_off", 64, STEP_TICKS),
            ],
        )

    def test_write_midi_uses_full_swing_step_timing(self):
        sequence = SequencerData(
            length=3,
            steps=tuple(
                SequencerStep(note=60 + index, velocity=100)
                for index in range(3)
            ),
            raw_length=2,
            time_division=TIME_DIVISIONS[7],
        )
        output = BytesIO()

        write_midi(sequence, output)
        output.seek(0)
        messages = [message for message in mido.MidiFile(file=output).tracks[0]
                    if not message.is_meta]

        self.assertEqual(
            [(message.type, message.time) for message in messages],
            [
                ("note_on", 0),
                ("note_off", 160),
                ("note_on", 0),
                ("note_off", 80),
                ("note_on", 0),
                ("note_off", 160),
            ],
        )

    def test_sequence_as_display_glues_tied_steps(self):
        sequence = SequencerData(
            length=4,
            steps=(
                SequencerStep(note=60, velocity=100),
                SequencerStep(note=60, velocity=100, tie=True),
                SequencerStep(note=0, velocity=0),
                SequencerStep(note=64, velocity=90),
            ),
            raw_length=3,
        )

        self.assertEqual(
            sequence_as_display(sequence, terminal=COLOR_TERMINAL),
            "Program: (unnamed)\n"
            "BPM: 120\n"
            "Time division: 16 (sixteenth note)\n"
            "Length: 4\n█▉░▉\n\033[38;2;80;160;255m▔▔▔▔\033[0m",
        )

    def test_sequence_as_display_colors_four_step_groups(self):
        sequence = SequencerData(
            length=5,
            steps=tuple(SequencerStep(note=60, velocity=100) for _ in range(5)),
            raw_length=4,
        )

        self.assertEqual(
            sequence_as_display(sequence, terminal=COLOR_TERMINAL),
            "Program: (unnamed)\nBPM: 120\n"
            "Time division: 16 (sixteenth note)\n"
            "Length: 5\n▉▉▉▉▉\n"
            "\033[38;2;80;160;255m▔▔▔▔\033[0m"
            "\033[38;2;180;120;255m▔\033[0m",
        )

    def test_sequence_display_omits_colors_for_redirected_output(self):
        sequence = make_sequence()
        terminal = Terminal(stream=StringIO())

        display = sequence_as_display(sequence, terminal=terminal)

        self.assertNotIn("\033", display)


if __name__ == "__main__":
    unittest.main()
