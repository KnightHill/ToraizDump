"""Command-line interface for dumping the AS-1's current sequencer."""

from __future__ import annotations

import argparse
import json

import mido

from .transport import read_current_sequencer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="MIDI input port (defaults to the output port)")
    parser.add_argument("--output", help="MIDI output port")
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--list-ports", action="store_true")
    args = parser.parse_args()

    if args.list_ports:
        for name in mido.get_ioport_names():
            print(name)
        return 0
    if not args.output:
        parser.error("--output is required unless --list-ports is used")

    input_name = args.input or args.output
    with mido.open_output(args.output, backend="mido.backends.rtmidi") as output:
        with mido.open_input(input_name, backend="mido.backends.rtmidi") as input_port:
            sequence = read_current_sequencer(output, input_port, args.timeout)

    print(json.dumps({
        "length": sequence.length,
        "steps": [
            {"note": step.note, "velocity": step.velocity, "rest": step.is_rest}
            for step in sequence.steps
        ],
    }, indent=2))
    return 0
