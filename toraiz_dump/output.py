"""Output encoders for decoded AS-1 sequencer data."""

from __future__ import annotations

from typing import BinaryIO

import mido

from .protocol import SequencerData

TICKS_PER_BEAT = 480
STEP_TICKS = TICKS_PER_BEAT // 4
DEFAULT_TEMPO = 500_000  # 120 BPM


def sequence_as_dict(sequence: SequencerData) -> dict[str, object]:
    """Return the JSON-compatible representation of a sequence."""

    return {
        "length": sequence.length,
        "steps": [
            {
                "note": step.note,
                "velocity": step.velocity,
                "rest": step.is_rest,
                "tie": step.tie,
            }
            for step in sequence.steps[: sequence.length]
        ],
    }


def write_midi(sequence: SequencerData, file: BinaryIO) -> None:
    """Write the active AS-1 sequence as a type-0 Standard MIDI File."""

    midi_file = mido.MidiFile(type=0, ticks_per_beat=TICKS_PER_BEAT)
    track = mido.MidiTrack()
    midi_file.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name="TORAIZ AS-1 Sequence"))
    track.append(mido.MetaMessage("set_tempo", tempo=DEFAULT_TEMPO))

    events: list[tuple[int, mido.Message]] = []
    active_note: int | None = None
    for index, step in enumerate(sequence.steps[: sequence.length]):
        position = index * STEP_TICKS
        if step.tie and active_note is not None:
            continue
        if step.is_rest:
            if active_note is not None:
                events.append((position, mido.Message(
                    "note_off", note=active_note, velocity=0,
                )))
                active_note = None
            continue
        if active_note is not None:
            events.append((position, mido.Message(
                "note_off", note=active_note, velocity=0,
            )))
        events.append((position, mido.Message(
            "note_on", note=step.note, velocity=step.velocity,
        )))
        active_note = step.note

    end_position = sequence.length * STEP_TICKS
    if active_note is not None:
        events.append((end_position, mido.Message(
            "note_off", note=active_note, velocity=0,
        )))

    previous_position = 0
    for position, message in events:
        message.time = position - previous_position
        track.append(message)
        previous_position = position
    track.append(mido.MetaMessage("end_of_track", time=end_position - previous_position))
    midi_file.save(file=file)
