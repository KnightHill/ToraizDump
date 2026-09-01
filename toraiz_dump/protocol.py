"""Pioneer DJ TORAIZ AS-1 SysEx and sequencer data handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

# mido sysex messages contain the bytes between F0 and F7 in ``data``.
DEVICE_PREFIX = (0x00, 0x40, 0x05, 0x00, 0x00, 0x01, 0x08, 0x10)
EDIT_BUFFER_REQUEST = DEVICE_PREFIX + (0x06,)
EDIT_BUFFER_RESPONSE = DEVICE_PREFIX + (0x03,)
PROGRAM_DUMP_REQUEST = DEVICE_PREFIX + (0x05,)
PROGRAM_DUMP_RESPONSE = DEVICE_PREFIX + (0x02,)
PROGRAM_BYTES = 1024
PACKED_BYTES = PROGRAM_BYTES + (PROGRAM_BYTES + 6) // 7
BANK_COUNT = 10
PROGRAMS_PER_BANK = 99

SEQUENCE_LENGTH_INDEX = 95
PROGRAM_NAME_START_INDEX = 107
PROGRAM_NAME_LENGTH = 20
PROGRAM_NAME_END_INDEX = PROGRAM_NAME_START_INDEX + PROGRAM_NAME_LENGTH
MIN_PROGRAM_NAME_PACKED_BYTES = (
    PROGRAM_NAME_END_INDEX + (PROGRAM_NAME_END_INDEX + 6) // 7
)
NOTE_START_INDEX = 128
VELOCITY_START_INDEX = 192
STEP_COUNT = 64
SEQUENCER_BYTES = VELOCITY_START_INDEX + STEP_COUNT
MIN_PACKED_BYTES = SEQUENCER_BYTES + (SEQUENCER_BYTES + 6) // 7
BPM_INDEX = 87
TIME_DIVISION_INDEX = 92


@dataclass(frozen=True)
class TimeDivision:
    """Timing applied to each AS-1 sequencer step."""

    value: str
    description: str
    step_ticks: tuple[int, ...]


# Step lengths use a 480-tick quarter note. Swing divisions alternate a
# two-thirds/one-third pair, matching the AS-1's documented full swing timing.
TIME_DIVISIONS = (
    TimeDivision("2", "half note", (960,)),
    TimeDivision("4", "quarter note", (480,)),
    TimeDivision("8D", "dotted eighth note", (360,)),
    TimeDivision("8", "eighth note", (240,)),
    TimeDivision("8S", "eighth note swing", (320, 160)),
    TimeDivision("8T", "eighth-note triplet", (160,)),
    TimeDivision("16", "sixteenth note", (120,)),
    TimeDivision("16S", "sixteenth note swing", (160, 80)),
    TimeDivision("16T", "sixteenth-note triplet", (80,)),
    TimeDivision("32", "thirty-second note", (60,)),
)
DEFAULT_TIME_DIVISION = TIME_DIVISIONS[6]


@dataclass(frozen=True)
class SequencerStep:
    """One AS-1 sequencer step, using a MIDI note number and velocity."""

    note: int
    velocity: int
    tie: bool = False

    @property
    def is_rest(self) -> bool:
        return self.velocity == 0


@dataclass(frozen=True)
class SequencerData:
    """The sequencer portion of the current AS-1 program edit buffer."""

    length: int
    steps: tuple[SequencerStep, ...]
    raw_length: int
    program_name: str = ""
    bpm: int = 120
    time_division: TimeDivision = DEFAULT_TIME_DIVISION


@dataclass(frozen=True)
class ProgramSummary:
    """The location and name of one stored AS-1 program."""

    bank: str
    program: int
    name: str


def bank_name(bank_index: int) -> str:
    """Return the AS-1 display label for a zero-based bank index."""

    if not 0 <= bank_index < BANK_COUNT:
        raise ValueError(f"bank index must be between 0 and {BANK_COUNT - 1}")
    if bank_index < 5:
        return f"U{bank_index + 1}"
    return f"F{bank_index - 4}"


def _decode_program_name(program: Sequence[int]) -> str:
    """Decode and trim the AS-1's fixed-width ASCII program name."""

    raw_name = bytes(
        program[PROGRAM_NAME_START_INDEX:PROGRAM_NAME_END_INDEX]
    ).rstrip(b" \x00")
    decoded = raw_name.decode("ascii", errors="replace")
    return "".join(
        character if character.isprintable() else "�"
        for character in decoded
    )


def decode_edit_buffer(packed: Sequence[int]) -> bytes:
    """Decode the AS-1 packed-MSB representation into 1,024 program bytes.

    Each packet starts with a byte containing the MSBs of the following seven
    bytes. The first following byte uses bit 0, the second bit 1, and so on.
    """

    if len(packed) != PACKED_BYTES:
        raise ValueError(
            f"expected {PACKED_BYTES} packed bytes, received {len(packed)}"
        )
    return _decode_packed_bytes(packed)


def _decode_packed_bytes(packed: Sequence[int]) -> bytes:
    """Decode a possibly partial AS-1 packed-MSB data block."""

    if any(not 0 <= byte <= 0x7F for byte in packed):
        raise ValueError("packed SysEx data must contain only 7-bit bytes")

    decoded = bytearray()
    for offset in range(0, len(packed), 8):
        msbs = packed[offset]
        for bit in range(7):
            source = offset + 1 + bit
            if source >= len(packed):
                break
            decoded.append(packed[source] | (((msbs >> bit) & 1) << 7))
    return bytes(decoded)


def _sysex_payload(data: Iterable[int]) -> tuple[int, ...]:
    """Normalize a complete SysEx message or a mido SysEx payload."""

    payload = tuple(data)
    if payload and payload[0] == 0xF0:
        if payload[-1:] != (0xF7,):
            raise ValueError("complete SysEx response is missing F7")
        return payload[1:-1]
    if payload and payload[-1] == 0xF7:
        raise ValueError("payload must not end with F7 unless it starts with F0")
    return payload


def make_program_dump_request(bank_index: int, program_index: int) -> tuple[int, ...]:
    """Build a request for one stored program using zero-based indices."""

    bank_name(bank_index)
    if not 0 <= program_index < PROGRAMS_PER_BANK:
        raise ValueError(
            f"program index must be between 0 and {PROGRAMS_PER_BANK - 1}"
        )
    return PROGRAM_DUMP_REQUEST + (bank_index, program_index)


def parse_program_dump_response(
    data: Iterable[int],
    *,
    expected_bank: int | None = None,
    expected_program: int | None = None,
) -> ProgramSummary:
    """Validate a stored-program response and extract its program name."""

    payload = _sysex_payload(data)
    if payload[: len(PROGRAM_DUMP_RESPONSE)] != PROGRAM_DUMP_RESPONSE:
        raise ValueError("not an AS-1 stored-program response")

    address_start = len(PROGRAM_DUMP_RESPONSE)
    if len(payload) < address_start + 2:
        raise ValueError("AS-1 stored-program response is missing its address")
    bank_index, program_index = payload[address_start:address_start + 2]
    bank_label = bank_name(bank_index)
    if not 0 <= program_index < PROGRAMS_PER_BANK:
        raise ValueError(f"invalid AS-1 program index: {program_index}")
    if expected_bank is not None and bank_index != expected_bank:
        raise ValueError(
            f"response bank is {bank_label}, expected {bank_name(expected_bank)}"
        )
    if expected_program is not None and program_index != expected_program:
        raise ValueError(
            f"response program is P{program_index + 1:02d}, "
            f"expected P{expected_program + 1:02d}"
        )

    packed = payload[address_start + 2:]
    if len(packed) < MIN_PROGRAM_NAME_PACKED_BYTES:
        raise ValueError(
            "AS-1 stored-program response is too short for its name: "
            f"expected at least {MIN_PROGRAM_NAME_PACKED_BYTES} packed bytes, "
            f"received {len(packed)}"
        )
    program = _decode_packed_bytes(packed)
    return ProgramSummary(
        bank=bank_label,
        program=program_index + 1,
        name=_decode_program_name(program),
    )


def parse_edit_buffer_response(data: Iterable[int]) -> SequencerData:
    """Validate and parse an AS-1 edit-buffer SysEx response.

    ``data`` may be either mido's payload (bytes between F0/F7) or a complete
    SysEx byte sequence including F0 and F7.
    """

    payload = _sysex_payload(data)

    if payload[: len(EDIT_BUFFER_RESPONSE)] != EDIT_BUFFER_RESPONSE:
        raise ValueError("not an AS-1 edit-buffer response")

    packed = payload[len(EDIT_BUFFER_RESPONSE) :]
    if len(packed) < MIN_PACKED_BYTES:
        raise ValueError(
            "AS-1 edit-buffer response is too short for sequencer data: "
            f"expected at least {MIN_PACKED_BYTES} packed bytes, received {len(packed)}"
        )

    # The documented dump contains 1,171 packed bytes, but sequencer parsing
    # only depends on the first 256 decoded bytes. Accept longer or shorter
    # firmware variants as long as all sequencer fields are present.
    program = _decode_packed_bytes(packed)
    bpm = program[BPM_INDEX]
    if not 30 <= bpm <= 250:
        raise ValueError(f"invalid AS-1 BPM value: {bpm}")

    raw_time_division = program[TIME_DIVISION_INDEX]
    if not 0 <= raw_time_division < len(TIME_DIVISIONS):
        raise ValueError(
            f"invalid AS-1 time division value: {raw_time_division}"
        )

    raw_length = program[SEQUENCE_LENGTH_INDEX]
    if not 0 <= raw_length < STEP_COUNT:
        raise ValueError(f"invalid AS-1 sequence length value: {raw_length}")

    steps = tuple(
        SequencerStep(
            note=program[NOTE_START_INDEX + index] & 0x7F,
            # Bit 7 marks an active step; bits 0-6 hold MIDI velocity.
            velocity=(program[VELOCITY_START_INDEX + index] & 0x7F)
            if program[VELOCITY_START_INDEX + index] & 0x80
            else 0,
            tie=bool(program[NOTE_START_INDEX + index] & 0x80),
        )
        for index in range(STEP_COUNT)
    )
    return SequencerData(
        length=raw_length + 1,
        steps=steps,
        raw_length=raw_length,
        program_name=_decode_program_name(program),
        bpm=bpm,
        time_division=TIME_DIVISIONS[raw_time_division],
    )


def pack_edit_buffer(program: Sequence[int]) -> bytes:
    """Pack raw program bytes; useful for tests and fixture generation."""

    if len(program) != PROGRAM_BYTES:
        raise ValueError(f"expected {PROGRAM_BYTES} program bytes")
    packed = bytearray()
    for offset in range(0, PROGRAM_BYTES, 7):
        group = program[offset : offset + 7]
        msbs = sum(((byte >> 7) & 1) << bit for bit, byte in enumerate(group))
        packed.append(msbs)
        packed.extend(byte & 0x7F for byte in group)
    return bytes(packed)
