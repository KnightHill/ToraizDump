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
            {"note": step.note, "velocity": step.velocity, "rest": step.is_rest}
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

    pending_ticks = 0
    for step in sequence.steps[: sequence.length]:
        if step.is_rest:
            pending_ticks += STEP_TICKS
            continue
        track.append(mido.Message(
            "note_on",
            note=step.note,
            velocity=step.velocity,
            time=pending_ticks,
        ))
        track.append(mido.Message(
            "note_off",
            note=step.note,
            velocity=0,
            time=STEP_TICKS,
        ))
        pending_ticks = 0

    track.append(mido.MetaMessage("end_of_track", time=pending_ticks))
    midi_file.save(file=file)
