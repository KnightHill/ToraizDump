"""Show the sequence display with representative step patterns.

Run from the project root with::

    .venv/bin/python test-display.py
"""

from toraiz_dump.output import sequence_as_display
from toraiz_dump.protocol import SequencerData, SequencerStep


def note(midi_note: int = 60, velocity: int = 100) -> SequencerStep:
    """Create an active sequencer step."""

    return SequencerStep(note=midi_note, velocity=velocity)


def rest() -> SequencerStep:
    """Create a rest step."""

    return SequencerStep(note=0, velocity=0)


def tie(midi_note: int = 60, velocity: int = 100) -> SequencerStep:
    """Create an active step tied to the preceding note."""

    return SequencerStep(note=midi_note, velocity=velocity, tie=True)


def tied_rest() -> SequencerStep:
    """Create a rest carrying the tie flag."""

    return SequencerStep(note=0, velocity=0, tie=True)


def show_pattern(name: str, steps: tuple[SequencerStep, ...]) -> None:
    """Render one labeled pattern using the application display function."""

    sequence = SequencerData(
        length=len(steps),
        steps=steps,
        raw_length=len(steps) - 1,
    )
    print(f"\n{name}")
    print(sequence_as_display(sequence))


def main() -> None:
    patterns = (
        ("All notes", tuple(note(60 + index) for index in range(16))),
        ("All rests", tuple(rest() for _ in range(16))),
        (
            "Alternating notes and rests",
            tuple(note(60 + index) if index % 2 == 0 else rest()
                  for index in range(16)),
        ),
        (
            "Tied note pairs",
            tuple(
                step
                for midi_note in (60, 62, 64, 65, 67, 69, 71, 72)
                for step in (note(midi_note), tie(midi_note))
            ),
        ),
        (
            "Mixed notes, rests, and ties",
            (
                note(60), tie(60), rest(), note(62),
                note(64), tie(64), tie(64), rest(),
                rest(), note(67), tie(67), tied_rest(),
                note(69), rest(), note(71), tie(71),
            ),
        ),
        (
            "Tie crossing a four-step group boundary",
            (note(60), rest(), note(62), note(64), tie(64), rest(), note(67), rest()),
        ),
        (
            "Partial final group",
            (note(60), rest(), note(62), tie(62), rest(), note(64)),
        ),
    )

    for name, steps in patterns:
        show_pattern(name, steps)


if __name__ == "__main__":
    main()
