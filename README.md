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

## Basic commands

```bash
toraiz-dump --list-ports
toraiz-dump --version
```

## Select MIDI ports

Automatic detection is the simplest option:

```bash
toraiz-dump --auto
```

`--auto` searches MIDI input and output port names for `TORAIZ`, `AS-1`, or
`AS1`, and pairs ports with matching names. If more than one device matches,
specify the ports explicitly.

Use `--list-ports`, then copy the complete names into `--midi-input` and
`--midi-output`. ALSA commonly exposes one bidirectional name, in which case
use that same name for both options:

```bash
toraiz-dump \
  --midi-input "Toraiz AS-1:Toraiz AS-1 MIDI 1 28:0" \
  --midi-output "Toraiz AS-1:Toraiz AS-1 MIDI 1 28:0"
```

When input and output have different names:

```bash
toraiz-dump \
  --midi-input "TORAIZ AS-1 MIDI In" \
  --midi-output "TORAIZ AS-1 MIDI Out"
```

`--midi-input` defaults to the `--midi-output` value when it is omitted.

## Output formats

JSON is the default. These commands are equivalent:

```bash
toraiz-dump --auto
toraiz-dump --auto --output json
toraiz-dump --auto -o json
```

JSON is printed to the terminal and contains the active step records:

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
Only the first `length` step records are returned.
A velocity of `0` represents a rest.
`tie` is `true` when the step sustains the note from the previous step.

To save JSON to a file:

```bash
toraiz-dump --auto > sequence.json
```

Select MIDI output and redirect the binary data to a `.mid` file:

```bash
toraiz-dump --auto --output midi > sequence.mid
# Short form:
toraiz-dump --auto -o midi > sequence.mid
```

The MIDI file uses one 16th-note slot per sequencer step at 120 BPM. Its tempo
can be changed normally in a DAW or MIDI editor. MIDI output contains only the
active number of steps and must be redirected to a file rather than displayed
in the terminal.

Play a saved MIDI file with `amidiplay`:

```bash
amidiplay sequence.mid
```

If the receiving device uses a different MIDI channel, remap the file before
playing it. Channels are numbered 1 through 16:

```bash
python remap_midi_channel.py sequence.mid sequence-ch5.mid --channel 5
amidiplay sequence-ch5.mid
```

Other useful options are `--timeout SECONDS`, `--list-ports`, and `--version`.
Run `toraiz-dump --help` for the complete command-line reference.

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
decodes bit 7 of each note byte as the tie flag and bits 0–6 as the MIDI note
number. It decodes velocity bit 7 as the active-step flag and bits 0–6 as
standard MIDI velocity. It tolerates dump length variations as long as the
complete sequencer region is present.

## Development

The test suite uses Python's built-in `unittest` framework, so no separate
test runner or development dependencies are required. From the project root,
run:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

To run one test module, pass its dotted module name:

```bash
.venv/bin/python -m unittest tests.test_protocol -v
```

The protocol parser can also be used independently of MIDI hardware through
`toraiz_dump.protocol`.

## Disclaimer

This project is independent and unaffiliated with Pioneer DJ, AlphaTheta, or
any of their subsidiaries, brands, or partners. Use it at your own risk. The
author and contributors are not responsible for any damage, data loss, or
other consequences resulting from the use of this software or its interaction
with any hardware or software.
