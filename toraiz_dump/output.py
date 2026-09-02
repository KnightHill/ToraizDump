"""Output encoders for decoded AS-1 sequencer data."""

from __future__ import annotations

from typing import BinaryIO

import mido
from blessed import Terminal

from .protocol import SequencerData

TICKS_PER_BEAT = 480
# Kept as the default sixteenth-note duration for callers that import it.
STEP_TICKS = TICKS_PER_BEAT // 4


def sequence_as_dict(sequence: SequencerData) -> dict[str, object]:
    """Return the JSON-compatible representation of a sequence."""

    return {
        "program_name": sequence.program_name,
        "bpm": sequence.bpm,
        "time_division": sequence.time_division.value,
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


def sequence_as_display(
    sequence: SequencerData,
    terminal: Terminal | None = None,
) -> str:
    """Return a compact visual representation of the active sequence steps.

    A regular note occupies seven eighths of its cell.  A tie on the current
    step extends the preceding note to a full cell.  The line below the steps
    marks groups of four with alternating blue and purple upper eighth blocks.
    """

    terminal = terminal or Terminal()
    group_colors = (
        terminal.color_rgb(80, 160, 255),
        terminal.color_rgb(180, 120, 255),
    )

    boxes: list[str] = []
    for index, step in enumerate(sequence.steps[: sequence.length]):
        if step.tie and index:
            boxes[index - 1] = "█"
        if step.is_rest:
            boxes.append("░")
        else:
            boxes.append("▉")

    display = "".join(boxes)
    group_line = "".join(
        f"{group_colors[group % 2]}"
        f"{'▔' * min(4, len(boxes) - group * 4)}{terminal.normal}"
        for group in range((len(boxes) + 3) // 4)
    )
    program_name = sequence.program_name or "(unnamed)"
    return (
        f"Program: {program_name}\n"
        f"BPM: {sequence.bpm}\n"
        f"Time division: {sequence.time_division.value} "
        f"({sequence.time_division.description})\n"
        f"Length: {sequence.length}\n{display}\n{group_line}"
    )


def write_midi(sequence: SequencerData, file: BinaryIO) -> None:
    """Write the active AS-1 sequence as a type-0 Standard MIDI File."""

    midi_file = mido.MidiFile(type=0, ticks_per_beat=TICKS_PER_BEAT)
    track = mido.MidiTrack()
    midi_file.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name="TORAIZ AS-1 Sequence"))
    track.append(mido.MetaMessage(
        "set_tempo", tempo=mido.bpm2tempo(sequence.bpm),
    ))
    track.append(mido.MetaMessage(
        "text", text=f"TORAIZ AS-1 TimeDiv: {sequence.time_division.value}",
    ))

    events: list[tuple[int, mido.Message]] = []
    active_note: int | None = None
    position = 0
    for index, step in enumerate(sequence.steps[: sequence.length]):
        if step.tie and active_note is not None:
            pass
        elif step.is_rest:
            if active_note is not None:
                events.append((position, mido.Message(
                    "note_off", note=active_note, velocity=0,
                )))
                active_note = None
        else:
            if active_note is not None:
                events.append((position, mido.Message(
                    "note_off", note=active_note, velocity=0,
                )))
            events.append((position, mido.Message(
                "note_on", note=step.note, velocity=step.velocity,
            )))
            active_note = step.note
        position += sequence.time_division.step_ticks[
            index % len(sequence.time_division.step_ticks)
        ]

    end_position = position
    if active_note is not None:
        events.append((end_position, mido.Message(
            "note_off", note=active_note, velocity=0,
        )))

    previous_position = 0
    for position, message in events:
        message.time = position - previous_position
        track.append(message)
        previous_position = position
    track.append(mido.MetaMessage(
        "end_of_track", time=end_position - previous_position,
    ))
    midi_file.save(file=file)
