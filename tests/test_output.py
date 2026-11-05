import re
import unittest
from io import BytesIO

import mido

from toraiz_dump.output import (
    PIANO_ROLL_OCTAVE_BACKGROUNDS,
    STEP_TICKS,
    _note_name,
    sequence_as_dict,
    sequence_as_display,
    sequence_as_piano_roll,
    sequence_as_strudel,
    write_midi,
)
from toraiz_dump.protocol import TIME_DIVISIONS, SequencerData, SequencerStep


ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(value):
    return ANSI_ESCAPE.sub("", value)


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

    def test_sequence_as_strudel_formats_notes_and_rests(self):
        self.assertEqual(
            sequence_as_strudel(make_sequence()),
            'setcpm(123/4)\nnote("<60 ~ 64 67>*16")\n.sound("supersaw")',
        )

    def test_sequence_as_strudel_elongates_notes_across_ties(self):
        sequence = SequencerData(
            length=5,
            steps=(
                SequencerStep(note=60, velocity=100),
                SequencerStep(note=60, velocity=100, tie=True),
                SequencerStep(note=60, velocity=100, tie=True),
                SequencerStep(note=0, velocity=0),
                SequencerStep(note=64, velocity=90),
            ),
            raw_length=4,
            bpm=120,
        )

        self.assertEqual(
            sequence_as_strudel(sequence),
            'setcpm(120/4)\nnote("<60@3 ~ 64>*16")\n.sound("supersaw")',
        )

    def test_sequence_as_strudel_treats_initial_tie_as_a_note(self):
        sequence = SequencerData(
            length=1,
            steps=(SequencerStep(note=60, velocity=100, tie=True),),
            raw_length=0,
        )

        self.assertIn('note("<60>*16")', sequence_as_strudel(sequence))

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

    def test_sequence_as_display_includes_piano_roll(self):
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

        rendered = sequence_as_display(sequence)
        plain = strip_ansi(rendered)

        self.assertIn("Length: 4\nPiano roll:", plain)
        self.assertIn("Piano roll:\nSteps 1-4", plain)
        self.assertIn("C4 ■■──    ", plain)
        self.assertIn("E4       ■■", plain)

    def test_sequence_as_display_has_no_compact_step_strip(self):
        sequence = SequencerData(
            length=5,
            steps=tuple(SequencerStep(note=60, velocity=100) for _ in range(5)),
            raw_length=4,
        )

        rendered = sequence_as_display(sequence)

        self.assertIn("Length: 5\nPiano roll:", rendered)
        self.assertNotIn("▉", rendered)
        self.assertNotIn("░", rendered)
        self.assertNotIn("█", rendered)

    def test_note_names_use_c4_for_middle_c(self):
        self.assertEqual(_note_name(0), "C-1")
        self.assertEqual(_note_name(60), "C4")
        self.assertEqual(_note_name(61), "C#4")
        self.assertEqual(_note_name(127), "G9")

    def test_piano_roll_renders_only_rows_with_notes(self):
        sequence = SequencerData(
            length=5,
            steps=(
                SequencerStep(note=60, velocity=100),
                SequencerStep(note=0, velocity=0, tie=True),
                SequencerStep(note=0, velocity=0),
                SequencerStep(note=64, velocity=90),
                SequencerStep(note=64, velocity=90, tie=True),
            ),
            raw_length=4,
        )

        rendered = sequence_as_piano_roll(sequence)

        self.assertEqual(
            strip_ansi(rendered),
            "Piano roll:\n"
            "Steps 1-5\n"
            "   1 2 3 4 5 \n"
            "E4       ■■──\n"
            "C4 ■■──      ",
        )
        self.assertNotIn("│", rendered)
        self.assertIn("\033[48;2;35;40;48m", rendered)
        self.assertIn("\033[48;2;48;54;64m", rendered)

    def test_piano_roll_treats_initial_tied_note_as_attack(self):
        sequence = SequencerData(
            length=1,
            steps=(SequencerStep(note=60, velocity=100, tie=True),),
            raw_length=0,
        )

        self.assertIn("C4 ■■", strip_ansi(sequence_as_piano_roll(sequence)))

    def test_piano_roll_reports_all_rest_sequence(self):
        sequence = SequencerData(
            length=2,
            steps=(
                SequencerStep(note=0, velocity=0),
                SequencerStep(note=0, velocity=0, tie=True),
            ),
            raw_length=1,
        )

        self.assertEqual(
            sequence_as_piano_roll(sequence),
            "Piano roll:\n(no active notes)",
        )

    def test_piano_roll_supports_full_midi_range(self):
        sequence = SequencerData(
            length=2,
            steps=(
                SequencerStep(note=0, velocity=100),
                SequencerStep(note=127, velocity=100),
            ),
            raw_length=1,
        )

        rendered = sequence_as_piano_roll(sequence)
        self.assertIn("G9", rendered)
        self.assertIn("C-1", rendered)

    def test_piano_roll_uses_different_label_backgrounds_per_octave(self):
        sequence = SequencerData(
            length=2,
            steps=(
                SequencerStep(note=60, velocity=100),
                SequencerStep(note=72, velocity=100),
            ),
            raw_length=1,
        )

        rendered = sequence_as_piano_roll(sequence)

        self.assertIn(PIANO_ROLL_OCTAVE_BACKGROUNDS[4], rendered)
        self.assertIn(PIANO_ROLL_OCTAVE_BACKGROUNDS[5], rendered)

    def test_piano_roll_wraps_without_omitting_steps(self):
        sequence = SequencerData(
            length=64,
            steps=tuple(
                SequencerStep(note=60, velocity=100) for _ in range(64)
            ),
            raw_length=63,
        )

        rendered = sequence_as_piano_roll(sequence, width=9)

        self.assertIn("Steps 1-4", rendered)
        self.assertIn("Steps 5-8", rendered)
        self.assertIn("Steps 61-64", rendered)
        self.assertEqual(rendered.count("■■"), 64)


if __name__ == "__main__":
    unittest.main()
