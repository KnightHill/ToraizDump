"""Output encoders for decoded AS-1 sequencer data."""

from __future__ import annotations

from typing import BinaryIO

import mido

from .protocol import SequencerData

TICKS_PER_BEAT = 480
# Kept as the default sixteenth-note duration for callers that import it.
STEP_TICKS = TICKS_PER_BEAT // 4
NOTE_NAMES = (
    "C", "C#", "D", "D#", "E", "F",
    "F#", "G", "G#", "A", "A#", "B",
)
PIANO_ROLL_CELL_WIDTH = 2


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


def _note_name(note: int) -> str:
    """Return a MIDI note name using the convention where note 60 is C4."""

    return f"{NOTE_NAMES[note % 12]}{note // 12 - 1}"


def _piano_roll_cells(
    sequence: SequencerData,
) -> tuple[list[tuple[int, str] | None], list[int]]:
    """Return the rendered cell at each step and the pitches that sound."""

    cells: list[tuple[int, str] | None] = []
    pitches: list[int] = []
    active_note: int | None = None
    for step in sequence.steps[: sequence.length]:
        if step.tie and active_note is not None:
            cells.append((active_note, "─"))
            pitches.append(active_note)
        elif step.is_rest:
            cells.append(None)
            active_note = None
        else:
            active_note = step.note
            cells.append((active_note, "■"))
            pitches.append(active_note)
    return cells, pitches


def _roll_row(values: list[str]) -> str:
    """Join piano-roll cells with a divider after each four-step group."""

    return "│".join(
        "".join(values[offset : offset + 4])
        for offset in range(0, len(values), 4)
    )


def _piano_roll_cell(cell: tuple[int, str] | None, note: int) -> str:
    """Render one fixed-width piano-roll cell for a pitch row."""

    if cell is None or cell[0] != note:
        return " " * PIANO_ROLL_CELL_WIDTH
    return cell[1] * PIANO_ROLL_CELL_WIDTH


def sequence_as_piano_roll(sequence: SequencerData, width: int = 80) -> str:
    """Return a pitch-by-step terminal piano roll for the active sequence."""

    cells, pitches = _piano_roll_cells(sequence)
    if not pitches:
        return "Piano roll:\n(no active notes)"

    pitch_rows = sorted(set(pitches), reverse=True)
    label_width = max(len(_note_name(note)) for note in pitch_rows)
    prefix_width = label_width + 1

    # Each additional four-step group also needs one divider. Very narrow
    # terminals still show at least one full group.
    group_width = 4 * PIANO_ROLL_CELL_WIDTH
    available = max(group_width, width - prefix_width)
    groups_per_block = max(1, (available + 1) // (group_width + 1))
    steps_per_block = groups_per_block * 4

    lines = ["Piano roll:"]
    for start in range(0, len(cells), steps_per_block):
        end = min(len(cells), start + steps_per_block)
        if start:
            lines.append("")
        lines.append(f"Steps {start + 1}-{end}")
        ruler = [
            f"{(index + 1) % 10:<{PIANO_ROLL_CELL_WIDTH}}"
            for index in range(start, end)
        ]
        lines.append(" " * prefix_width + _roll_row(ruler))
        for note in pitch_rows:
            values = [
                _piano_roll_cell(cell, note)
                for cell in cells[start:end]
            ]
            lines.append(f"{_note_name(note):>{label_width}} " + _roll_row(values))
    return "\n".join(lines)


def sequence_as_display(sequence: SequencerData, *, width: int = 80) -> str:
    """Return sequence metadata followed by a terminal piano roll."""

    program_name = sequence.program_name or "(unnamed)"
    return (
        f"Program: {program_name}\n"
        f"BPM: {sequence.bpm}\n"
        f"Time division: {sequence.time_division.value} "
        f"({sequence.time_division.description})\n"
        f"Length: {sequence.length}\n"
        f"{sequence_as_piano_roll(sequence, width)}"
    )


def sequence_as_strudel(sequence: SequencerData) -> str:
    """Return a Strudel mini-notation pattern using fixed sixteenth-note steps."""

    tokens: list[tuple[str, int]] = []
    active_note_index: int | None = None

    for step in sequence.steps[: sequence.length]:
        if step.tie and active_note_index is not None:
            note, weight = tokens[active_note_index]
            tokens[active_note_index] = (note, weight + 1)
            continue
        if step.is_rest:
            tokens.append(("~", 1))
            active_note_index = None
        else:
            tokens.append((str(step.note), 1))
            active_note_index = len(tokens) - 1

    notation = " ".join(
        f"{token}@{weight}" if weight > 1 else token
        for token, weight in tokens
    )
    return (
        f"setcpm({sequence.bpm}/4)\n"
        f'note("<{notation}>*16")\n.sound("supersaw")'
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
