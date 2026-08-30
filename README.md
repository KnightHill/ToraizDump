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

Dump commands require `-o`/`--output` to specify the file where the result is
saved.

## Select MIDI ports

Automatic detection is the simplest option:

```bash
toraiz-dump --auto --output sequence.json
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
toraiz-dump --auto --format json --output sequence.json
toraiz-dump --auto -f json -o sequence.json
```

Every dump also prints the program name, sequence length, and a compact visual
display of the active steps to the terminal. A note is shown as a seven-eighth
block (`▉`), leaving a narrow gap before the next step, while a rest is shown
as a light shade block (`░`). When a step is tied to the preceding note, that
preceding block becomes full (`█`) to close the gap and show the sustained
connection.

The line beneath the steps divides the sequence into four-step groups using
alternating blue and purple upper bars. For example:

```text
Program: Basic Program
Length: 8
█▉░▉▉░█▉
▔▔▔▔▔▔▔▔
```

The JSON file contains the active step records:

```json
{
  "program_name": "Basic Program",
  "length": 16,
  "steps": [
    {"note": 60, "velocity": 100, "rest": false, "tie": false},
    {"note": 62, "velocity": 0, "rest": true, "tie": false}
  ]
}
```

`program_name` is the name stored in the current AS-1 edit buffer.
`length` is the displayed sequence length from 1 through 64.
Only the first `length` step records are returned.
A velocity of `0` represents a rest.
`tie` is `true` when the step sustains the note from the previous step.

To save JSON to a file:

```bash
toraiz-dump --auto --output sequence.json
```

Select MIDI output and save it to a `.mid` file:

```bash
toraiz-dump --auto --format midi --output sequence.mid
# Short form:
toraiz-dump --auto -f midi -o sequence.mid
```

The MIDI file uses one 16th-note slot per sequencer step at 120 BPM. Its tempo
can be changed normally in a DAW or MIDI editor. MIDI output contains only the
active number of steps and is saved to the file specified by `--output`.

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
program layout (length at byte 95, the 20-character program name at bytes
107–126, notes at bytes 128–191, and velocities at bytes 192–255) rather than
treating MIDI NRPN numbers as program offsets. It decodes bit 7 of each note
byte as the tie flag and bits 0–6 as the MIDI note number. It decodes velocity
bit 7 as the active-step flag and bits 0–6 as standard MIDI velocity. It
tolerates dump length variations as long as the complete sequencer region is
present.

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

To preview the sequence display with different note, rest, and tie patterns:

```bash
.venv/bin/python test-display.py
```

The protocol parser can also be used independently of MIDI hardware through
`toraiz_dump.protocol`.

## Disclaimer

This project is independent and unaffiliated with Pioneer DJ, AlphaTheta, or
any of their subsidiaries, brands, or partners. Use it at your own risk. The
author and contributors are not responsible for any damage, data loss, or
other consequences resulting from the use of this software or its interaction
with any hardware or software.
