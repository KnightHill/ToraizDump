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


def test_sequence_as_dict_preserves_all_steps():
    value = sequence_as_dict(make_sequence())

    assert value["length"] == 4
    assert value["steps"][1] == {"note": 0, "velocity": 0, "rest": True}


def test_write_midi_uses_sixteenth_note_steps_and_rests():
    output = BytesIO()
    write_midi(make_sequence(), output)
    output.seek(0)

    midi_file = mido.MidiFile(file=output)
    messages = [message for message in midi_file.tracks[0] if not message.is_meta]

    assert [(message.type, message.note, message.velocity, message.time)
            for message in messages] == [
        ("note_on", 60, 100, 0),
        ("note_off", 60, 0, STEP_TICKS),
        ("note_on", 64, 90, STEP_TICKS),
        ("note_off", 64, 0, STEP_TICKS),
        ("note_on", 67, 80, 0),
        ("note_off", 67, 0, STEP_TICKS),
    ]
