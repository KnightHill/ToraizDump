import pytest

from toraiz_dump.protocol import (
    EDIT_BUFFER_RESPONSE,
    MIN_PACKED_BYTES,
    PACKED_BYTES,
    decode_edit_buffer,
    pack_edit_buffer,
    parse_edit_buffer_response,
)


def make_program():
    program = bytearray(1024)
    program[170] = 4
    for index in range(64):
        program[256 + index] = 36 + index
        program[320 + index] = 0 if index == 2 else 127 - index
    return program


def test_packed_round_trip_preserves_all_bytes():
    program = bytes((index * 53) % 256 for index in range(1024))
    packed = pack_edit_buffer(program)
    assert len(packed) == PACKED_BYTES
    assert decode_edit_buffer(packed) == program


def test_parse_sequencer_data():
    program = make_program()
    response = bytes(EDIT_BUFFER_RESPONSE) + pack_edit_buffer(program)
    sequence = parse_edit_buffer_response(response)

    assert sequence.length == 16
    assert sequence.length_code == 4
    assert sequence.steps[0].note == 36
    assert sequence.steps[0].velocity == 127
    assert sequence.steps[2].is_rest
    assert len(sequence.steps) == 64


def test_parse_accepts_mido_payload_without_f0_f7():
    program = make_program()
    payload = bytes(EDIT_BUFFER_RESPONSE) + pack_edit_buffer(program)
    assert parse_edit_buffer_response(payload).length == 16


def test_parse_accepts_only_the_data_needed_for_the_sequencer():
    program = make_program()
    packed = pack_edit_buffer(program)
    payload = bytes(EDIT_BUFFER_RESPONSE) + packed[:MIN_PACKED_BYTES]

    sequence = parse_edit_buffer_response(payload)

    assert sequence.length == 16
    assert sequence.steps[-1].note == 99
    assert sequence.steps[-1].velocity == 64


def test_parse_accepts_trailing_firmware_data():
    program = make_program()
    payload = bytes(EDIT_BUFFER_RESPONSE) + pack_edit_buffer(program) + b"\x00\x01"

    assert parse_edit_buffer_response(payload).length == 16


def test_parse_rejects_response_too_short_for_sequencer():
    payload = bytes(EDIT_BUFFER_RESPONSE) + b"\x00" * (MIN_PACKED_BYTES - 1)

    with pytest.raises(ValueError, match=rf"too short.*{MIN_PACKED_BYTES - 1}"):
        parse_edit_buffer_response(payload)


@pytest.mark.parametrize("value", [b"", b"\xf0", b"\xf0\x00\xf7"])
def test_rejects_invalid_response(value):
    with pytest.raises(ValueError):
        parse_edit_buffer_response(value)


def test_decode_rejects_wrong_size():
    with pytest.raises(ValueError, match="packed bytes"):
        decode_edit_buffer(b"\x00" * 8)
