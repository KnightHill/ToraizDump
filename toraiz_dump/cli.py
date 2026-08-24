"""Command-line interface for dumping the AS-1's current sequencer."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence

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
            "use --list-ports or specify --input and --output"
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
            "multiple TORAIZ MIDI port pairs found; specify --input and --output"
        )
    return best[1], best[2]


def main() -> int:
    import mido

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", help="MIDI input port (defaults to the output port)")
    parser.add_argument("--output", help="MIDI output port")
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

    if args.auto and (args.input or args.output):
        parser.error("--auto cannot be combined with --input or --output")
    if args.auto:
        try:
            input_name, output_name = autodetect_ports(
                mido.get_input_names(), mido.get_output_names()
            )
        except RuntimeError as error:
            parser.error(str(error))
    else:
        if not args.output:
            parser.error("--output, --auto, or --list-ports is required")
        output_name = args.output
        input_name = args.input or output_name

    with mido.open_output(output_name, backend="mido.backends.rtmidi") as output:
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
