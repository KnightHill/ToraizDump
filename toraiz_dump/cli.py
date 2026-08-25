"""Command-line interface for dumping the AS-1's current sequencer."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence

from . import __version__
from .output import sequence_as_dict, write_midi
from .ports import RtMidiPollingInput
from .transport import read_current_sequencer


def _port_tokens(name: str) -> set[str]:
    """Normalize a port name for matching its input/output pair."""

    tokens = set(re.findall(r"[a-z0-9]+", name.lower()))
    tokens -= {"in", "input", "out", "output", "midi", "port"}
    return tokens


def autodetect_ports(
    input_names: Sequence[str], output_names: Sequence[str]
) -> tuple[str, str]:
    """Find the most likely TORAIZ input/output port pair.

    A matching name is preferred for devices exposing one bidirectional port.
    For separate ports, common normalized name tokens are used. Ambiguous or
    missing matches raise ``RuntimeError`` with an actionable message.
    """

    def is_toraiz(name: str) -> bool:
        lowered = name.lower()
        return "toraiz" in lowered or "as-1" in lowered or "as1" in lowered

    inputs = [name for name in input_names if is_toraiz(name)]
    outputs = [name for name in output_names if is_toraiz(name)]
    if not inputs or not outputs:
        raise RuntimeError(
            "could not find both TORAIZ MIDI input and output ports; "
            "use --list-ports or specify --midi-input and --midi-output"
        )

    pairs: list[tuple[int, str, str]] = []
    for output in outputs:
        for input_name in inputs:
            shared = len(_port_tokens(output) & _port_tokens(input_name))
            score = shared * 10 + (100 if output == input_name else 0)
            pairs.append((score, input_name, output))

    pairs.sort(reverse=True)
    best = pairs[0]
    if len(pairs) > 1 and pairs[1][0] == best[0]:
        raise RuntimeError(
            "multiple TORAIZ MIDI port pairs found; "
            "specify --midi-input and --midi-output"
        )
    return best[1], best[2]


def main() -> int:
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
        "-o",
        "--output",
        choices=("json", "midi"),
        default="json",
        help="output format (default: json)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="automatically detect TORAIZ MIDI input and output ports",
    )
    parser.add_argument("--timeout", type=float, default=2.0)
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

    with RtMidiPollingInput(input_name) as input_port:
        with mido.open_output(output_name, backend="mido.backends.rtmidi") as output:
            sequence = read_current_sequencer(output, input_port, args.timeout)
            if args.output == "midi":
                write_midi(sequence, sys.stdout.buffer)
                sys.stdout.buffer.flush()
            else:
                print(json.dumps(sequence_as_dict(sequence), indent=2), flush=True)
    return 0
