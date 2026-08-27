import unittest
from io import BytesIO

import mido

from toraiz_dump.output import STEP_TICKS, sequence_as_dict, write_midi
from toraiz_dump.protocol import SequencerData, SequencerStep


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
    )


class OutputTests(unittest.TestCase):
    def test_sequence_as_dict_returns_active_steps(self):
        value = sequence_as_dict(make_sequence())

        self.assertEqual(value["length"], 4)
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
        messages = [
            message for message in midi_file.tracks[0] if not message.is_meta
        ]

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


if __name__ == "__main__":
    unittest.main()
