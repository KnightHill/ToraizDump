#!/usr/bin/env python3
"""Rewrite channel voice messages in a Standard MIDI File."""

from __future__ import annotations

import argparse

import mido


def remap_channel(input_path: str, output_path: str, channel: int) -> None:
    """Copy a MIDI file, changing all channel voice messages to one channel."""

    source = mido.MidiFile(input_path)
    destination = mido.MidiFile(
        type=source.type,
        ticks_per_beat=source.ticks_per_beat,
        charset=source.charset,
    )

    for track in source.tracks:
        destination_track = mido.MidiTrack()
        for message in track:
            if not message.is_meta:
                message = message.copy(channel=channel)
            destination_track.append(message)
        destination.tracks.append(destination_track)

    destination.save(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remap all MIDI channel messages to one channel."
    )
    parser.add_argument("input", help="input Standard MIDI file")
    parser.add_argument("output", help="output Standard MIDI file")
    parser.add_argument(
        "--channel",
        type=int,
        required=True,
        metavar="1-16",
        help="destination MIDI channel (1-16)",
    )
    args = parser.parse_args()

    if not 1 <= args.channel <= 16:
        parser.error("--channel must be between 1 and 16")

    remap_channel(args.input, args.output, args.channel - 1)


if __name__ == "__main__":
    main()
