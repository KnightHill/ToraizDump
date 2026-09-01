"""Command-line interface for listing all stored AS-1 programs."""

from __future__ import annotations

import argparse

from . import __version__
from .cli import autodetect_ports
from .ports import RtMidiPollingInput
from .transport import iter_program_summaries

CATEGORY_CODES = (
    "AR", "BA", "BD", "BR", "DR", "FX", "GT", "HH", "LD", "PD",
    "SN", "ST", "TM", "VX",
)


def main() -> int:
    """Run the stored-program listing command."""

    import mido

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--midi-input",
        help="MIDI input port (defaults to the MIDI output port)",
    )
    parser.add_argument("--midi-output", help="MIDI output port")
    parser.add_argument(
        "-f",
        "--filter",
        choices=CATEGORY_CODES,
        help="only show programs in this category",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="automatically detect TORAIZ MIDI input and output ports",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="response timeout for each program in seconds (default: 2.0)",
    )
    parser.add_argument("--list-ports", action="store_true")
    args = parser.parse_args()

    if args.list_ports:
        print("MIDI input ports:")
        for name in mido.get_input_names():
            print(f"  {name}")
        print("MIDI output ports:")
        for name in mido.get_output_names():
            print(f"  {name}")
        return 0

    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    if args.auto and (args.midi_input or args.midi_output):
        parser.error("--auto cannot be combined with --midi-input or --midi-output")
    if args.auto:
        try:
            input_name, output_name = autodetect_ports(
                mido.get_input_names(), mido.get_output_names()
            )
        except RuntimeError as error:
            parser.error(str(error))
    else:
        if not args.midi_output:
            parser.error("--midi-output, --auto, or --list-ports is required")
        output_name = args.midi_output
        input_name = args.midi_input or output_name

    try:
        with RtMidiPollingInput(input_name) as input_port:
            with mido.open_output(
                output_name, backend="mido.backends.rtmidi"
            ) as output:
                for program in iter_program_summaries(
                    output, input_port, args.timeout
                ):
                    name = program.name or "(unnamed)"
                    if args.filter and not name.startswith(f"{args.filter} "):
                        continue
                    print(
                        f"{program.bank} P{program.program:02d} {name}",
                        flush=True,
                    )
    except (OSError, TimeoutError, ValueError) as error:
        parser.exit(1, f"{parser.prog}: error: {error}\n")
    return 0
