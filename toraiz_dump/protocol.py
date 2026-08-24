"""Pioneer DJ TORAIZ AS-1 SysEx and sequencer data handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

# mido sysex messages contain the bytes between F0 and F7 in ``data``.
DEVICE_PREFIX = (0x00, 0x40, 0x05, 0x00, 0x00, 0x01, 0x08, 0x10)
EDIT_BUFFER_REQUEST = DEVICE_PREFIX + (0x06,)
EDIT_BUFFER_RESPONSE = DEVICE_PREFIX + (0x03,)
PROGRAM_BYTES = 1024
PACKED_BYTES = PROGRAM_BYTES + (PROGRAM_BYTES + 6) // 7

SEQUENCE_LENGTH_INDEX = 170
NOTE_START_INDEX = 256
VELOCITY_START_INDEX = 320
STEP_COUNT = 64


@dataclass(frozen=True)
class SequencerStep:
    """One AS-1 sequencer step, using a MIDI note number and velocity."""

    note: int
    velocity: int

    @property
    def is_rest(self) -> bool:
        return self.velocity == 0


@dataclass(frozen=True)
class SequencerData:
    """The sequencer portion of the current AS-1 program edit buffer."""

    length: int
    steps: tuple[SequencerStep, ...]
    length_code: int


def decode_edit_buffer(packed: Sequence[int]) -> bytes:
    """Decode the AS-1 packed-MSB representation into 1,024 program bytes.

    Each packet starts with a byte containing the MSBs of the following seven
    bytes. The first following byte uses bit 0, the second bit 1, and so on.
    """

    if len(packed) != PACKED_BYTES:
        raise ValueError(
            f"expected {PACKED_BYTES} packed bytes, received {len(packed)}"
        )
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
    return bytes(decoded[:PROGRAM_BYTES])


def parse_edit_buffer_response(data: Iterable[int]) -> SequencerData:
    """Validate and parse an AS-1 edit-buffer SysEx response.

    ``data`` may be either mido's payload (bytes between F0/F7) or a complete
    SysEx byte sequence including F0 and F7.
    """

    payload = tuple(data)
    if payload and payload[0] == 0xF0:
        if payload[-1:] != (0xF7,):
            raise ValueError("complete SysEx response is missing F7")
        payload = payload[1:-1]
    elif payload and payload[-1] == 0xF7:
        raise ValueError("payload must not end with F7 unless it starts with F0")

    expected_size = len(EDIT_BUFFER_RESPONSE) + PACKED_BYTES
    if len(payload) != expected_size:
        raise ValueError(
            f"expected {expected_size} response payload bytes, received {len(payload)}"
        )
    if payload[: len(EDIT_BUFFER_RESPONSE)] != EDIT_BUFFER_RESPONSE:
        raise ValueError("not an AS-1 edit-buffer response")

    program = decode_edit_buffer(payload[len(EDIT_BUFFER_RESPONSE) :])
    length_code = program[SEQUENCE_LENGTH_INDEX]
    if not 0 <= length_code <= 6:
        raise ValueError(f"invalid AS-1 sequence length code: {length_code}")

    steps = tuple(
        SequencerStep(
            note=program[NOTE_START_INDEX + index],
            velocity=program[VELOCITY_START_INDEX + index],
        )
        for index in range(STEP_COUNT)
    )
    return SequencerData(
        length=1 << length_code,
        steps=steps,
        length_code=length_code,
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
