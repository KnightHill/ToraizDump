"""Interactive terminal selector for stored TORAIZ AS-1 programs."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from typing import Any

from blessed import Terminal

from .ports import RtMidiPollingInput
from .programs_cli import create_parser, resolve_port_names
from .protocol import ProgramSummary
from .transport import iter_program_summaries


def _program_label(program: ProgramSummary) -> str:
    """Return one display line for a stored program."""

    return f"{program.bank} P{program.program:02d} {program.name or '(unnamed)'}"


def _bank_index(bank: str) -> int:
    """Convert an AS-1 bank label to its zero-based MIDI bank value."""

    if len(bank) != 2 or bank[0] not in ("U", "F") or bank[1] not in "12345":
        raise ValueError(f"invalid AS-1 bank label: {bank!r}")
    offset = 0 if bank[0] == "U" else 5
    return offset + int(bank[1]) - 1


def activate_program(
    output: Any, program: ProgramSummary, midi_channel: int = 1
) -> None:
    """Select a stored AS-1 program on a user-facing MIDI channel (1-16)."""

    import mido

    if not 1 <= midi_channel <= 16:
        raise ValueError("MIDI channel must be between 1 and 16")
    mido_channel = midi_channel - 1
    output.send(
        mido.Message(
            "control_change",
            channel=mido_channel,
            control=32,
            value=_bank_index(program.bank),
        )
    )
    output.send(
        mido.Message(
            "program_change",
            channel=mido_channel,
            program=program.program - 1,
        )
    )


def _previous_bank(programs: Sequence[ProgramSummary], selected: int) -> int:
    """Return the first row of the bank before the selected bank."""

    current_bank = programs[selected].bank
    current_start = selected
    while current_start > 0 and programs[current_start - 1].bank == current_bank:
        current_start -= 1
    if current_start == 0:
        return selected

    previous_bank = programs[current_start - 1].bank
    previous_start = current_start - 1
    while previous_start > 0 and programs[previous_start - 1].bank == previous_bank:
        previous_start -= 1
    return previous_start


def _next_bank(programs: Sequence[ProgramSummary], selected: int) -> int:
    """Return the first row of the bank after the selected bank."""

    current_bank = programs[selected].bank
    for index in range(selected + 1, len(programs)):
        if programs[index].bank != current_bank:
            return index
    return selected


def _move_selection(
    programs: Sequence[ProgramSummary], selected: int, key_name: str, page: int
) -> int:
    """Calculate the selected row after one navigation key."""

    last = len(programs) - 1
    if key_name == "KEY_UP":
        return max(0, selected - 1)
    if key_name == "KEY_DOWN":
        return min(last, selected + 1)
    if key_name == "KEY_LEFT":
        return _previous_bank(programs, selected)
    if key_name == "KEY_RIGHT":
        return _next_bank(programs, selected)
    if key_name == "KEY_PGUP":
        return max(0, selected - page)
    if key_name == "KEY_PGDOWN":
        return min(last, selected + page)
    if key_name == "KEY_HOME":
        return 0
    if key_name == "KEY_END":
        return last
    return selected


def _draw(
    terminal: Any, programs: Sequence[ProgramSummary], selected: int
) -> int:
    """Draw one selector frame and return the number of visible rows."""

    width = max(20, terminal.width or 80)
    visible_rows = max(1, (terminal.height or 24) - 4)
    top = max(0, selected - visible_rows // 2)
    top = min(top, max(0, len(programs) - visible_rows))
    visible = programs[top : top + visible_rows]

    lines = [
        terminal.bold("TORAIZ AS-1 programs"),
        f"{len(programs)} programs  |  arrows: move  Enter: select  Esc/q: cancel",
    ]
    for row, program in enumerate(visible, start=top):
        label = _program_label(program)[:width]
        lines.append(terminal.reverse(label) if row == selected else label)
    selected_label = (
        f"Selected {selected + 1}/{len(programs)}: "
        f"{_program_label(programs[selected])}"
    )
    lines.append(selected_label[:width])
    print(terminal.home + terminal.clear + "\n".join(lines), end="", flush=True)
    return visible_rows


def select_program(
    programs: Sequence[ProgramSummary],
    terminal: Any | None = None,
    on_select: Callable[[ProgramSummary], None] | None = None,
) -> ProgramSummary | None:
    """Interactively select programs, or return ``None`` when cancelled.

    When ``on_select`` is provided, Enter activates the highlighted program
    and keeps the selector open.  Without a callback, Enter retains the
    original one-shot return behavior for callers that only need a selection.
    """

    if not programs:
        raise ValueError("no programs match the requested filter")

    terminal = terminal or Terminal()
    if not terminal.is_a_tty:
        raise OSError("interactive selection requires a terminal")

    selected = 0
    with terminal.fullscreen(), terminal.cbreak(), terminal.hidden_cursor():
        while True:
            page = _draw(terminal, programs, selected)
            key = terminal.inkey()
            key_name = key.name or ""
            if key_name == "KEY_ENTER" or str(key) in ("\n", "\r"):
                program = programs[selected]
                if on_select is None:
                    return program
                on_select(program)
                continue
            if key_name == "KEY_ESCAPE" or str(key).lower() == "q":
                return None
            selected = _move_selection(programs, selected, key_name, page)


def main() -> int:
    """Load the AS-1 program names and run the interactive selector."""

    import mido

    parser = create_parser(description="Interactively select a TORAIZ AS-1 program")
    parser.add_argument(
        "--midi-channel",
        "--midi-out-channel",
        type=int,
        choices=range(1, 17),
        default=1,
        metavar="1-16",
        help="MIDI output channel used to select a program (default: 1)",
    )
    args = parser.parse_args()

    if args.list_ports:
        print("MIDI input ports:")
        for name in mido.get_input_names():
            print(f"  {name}")
        print("MIDI output ports:")
        for name in mido.get_output_names():
            print(f"  {name}")
        return 0

    input_name, output_name = resolve_port_names(parser, args, mido)
    terminal = Terminal()

    try:
        programs: list[ProgramSummary] = []
        with mido.open_output(
            output_name, backend="mido.backends.rtmidi"
        ) as output:
            with RtMidiPollingInput(input_name) as input_port:
                for program in iter_program_summaries(
                    output, input_port, args.timeout
                ):
                    print(
                        f"\rReading programs: {_program_label(program)}"
                        f"{terminal.clear_eol}",
                        end="",
                        file=sys.stderr,
                        flush=True,
                    )
                    if args.filter and not program.name.startswith(f"{args.filter} "):
                        continue
                    programs.append(program)
            print(
                "\r" + terminal.clear_eol,
                end="",
                file=sys.stderr,
                flush=True,
            )
            def activate_selected(program: ProgramSummary) -> None:
                activate_program(output, program, args.midi_channel)
                print(f"Selected {_program_label(program)}", flush=True)

            select_program(programs, on_select=activate_selected)
    except (OSError, TimeoutError, ValueError) as error:
        parser.exit(1, f"{parser.prog}: error: {error}\n")
    except KeyboardInterrupt:
        return 130

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
