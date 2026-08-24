# TORAIZ AS-1 MIDI Dumper

Reads the sequencer data from the currently selected program on a Pioneer DJ
TORAIZ AS-1 using MIDI SysEx, `mido`, and `python-rtmidi`.

The AS-1 exposes the current program as an edit-buffer dump. One request
returns all 64 sequencer steps; individual step queries are not required.

## Installation

```bash
python -m pip install -e .
```

The AS-1 must be connected over USB MIDI or through a MIDI interface. Make
sure its MIDI SysEx input/output settings allow SysEx communication.

## Find MIDI ports

```bash
toraiz-dump --list-ports
```

Show the installed version with:

```bash
toraiz-dump --version
```

## Dump the current sequencer

Try automatic TORAIZ port detection:

```bash
toraiz-dump --auto
```

`--auto` searches MIDI input and output port names for `TORAIZ`, `AS-1`, or
`AS1`, and pairs ports with matching names. If more than one device matches,
specify the ports explicitly.

When the device uses the same port for MIDI input and output:

```bash
toraiz-dump --output "TORAIZ AS-1"
```

With separate ports:

```bash
toraiz-dump \
  --output "TORAIZ AS-1 MIDI Out" \
  --input "TORAIZ AS-1 MIDI In"
```

The result is printed as JSON:

```json
{
  "length": 16,
  "steps": [
    {"note": 60, "velocity": 100, "rest": false},
    {"note": 62, "velocity": 0, "rest": true}
  ]
}
```

`length` is the displayed sequence length from 1 through 64.
All 64 step records are returned; only the first `length` steps are active.
A velocity of `0` represents a rest.

## Protocol

The dumper sends this SysEx request, shown including `F0` and `F7`:

```text
F0 00 40 05 00 00 01 08 10 06 F7
```

The AS-1 responds with an edit-buffer dump containing 1,024 program bytes,
documented as 1,171 MIDI-safe packed bytes. The parser validates the response
header and reconstructs the bytes needed for the sequencer. It reads the raw
program layout (length at byte 95, notes at bytes 128–191, and velocities at
bytes 192–255) rather than treating MIDI NRPN numbers as program offsets. It
decodes velocity bit 7 as the active-step flag and bits 0–6 as standard MIDI
velocity. It tolerates dump length variations as long as the complete
sequencer region is present.

## Development

Run the test suite with:

```bash
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
```

The protocol parser can also be used independently of MIDI hardware through
`toraiz_dump.protocol`.

## Disclaimer

This project is independent and unaffiliated with Pioneer DJ, AlphaTheta, or
any of their subsidiaries, brands, or partners. Use it at your own risk. The
author and contributors are not responsible for any damage, data loss, or
other consequences resulting from the use of this software or its interaction
with any hardware or software.
