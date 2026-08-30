import unittest

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
    program[95] = 15
    program[107:127] = b"Test Program".ljust(20)
    for index in range(64):
        program[128 + index] = 36 + index
        program[192 + index] = 0 if index == 2 else 0x80 | (127 - index)
    return program


class ProtocolTests(unittest.TestCase):
    def test_packed_round_trip_preserves_all_bytes(self):
        program = bytes((index * 53) % 256 for index in range(1024))
        packed = pack_edit_buffer(program)
        self.assertEqual(len(packed), PACKED_BYTES)
        self.assertEqual(decode_edit_buffer(packed), program)

    def test_parse_sequencer_data(self):
        program = make_program()
        response = bytes(EDIT_BUFFER_RESPONSE) + pack_edit_buffer(program)
        sequence = parse_edit_buffer_response(response)

        self.assertEqual(sequence.length, 16)
        self.assertEqual(sequence.raw_length, 15)
        self.assertEqual(sequence.program_name, "Test Program")
        self.assertEqual(sequence.steps[0].note, 36)
        self.assertEqual(sequence.steps[0].velocity, 127)
        self.assertTrue(sequence.steps[2].is_rest)
        self.assertEqual(len(sequence.steps), 64)

    def test_program_name_replaces_malformed_characters(self):
        program = make_program()
        program[107:127] = b"Bad\xffName".ljust(20)
        payload = bytes(EDIT_BUFFER_RESPONSE) + pack_edit_buffer(program)

        sequence = parse_edit_buffer_response(payload)

        self.assertEqual(sequence.program_name, "Bad�Name")

    def test_program_name_trims_null_padding(self):
        program = make_program()
        program[107:127] = b"Short Name".ljust(20, b"\x00")
        payload = bytes(EDIT_BUFFER_RESPONSE) + pack_edit_buffer(program)

        sequence = parse_edit_buffer_response(payload)

        self.assertEqual(sequence.program_name, "Short Name")

    def test_velocity_high_bit_marks_an_active_step(self):
        program = make_program()
        program[192] = 0x80 | 100
        program[193] = 100
        payload = bytes(EDIT_BUFFER_RESPONSE) + pack_edit_buffer(program)

        sequence = parse_edit_buffer_response(payload)

        self.assertEqual(sequence.steps[0].velocity, 100)
        self.assertFalse(sequence.steps[0].is_rest)
        self.assertEqual(sequence.steps[1].velocity, 0)
        self.assertTrue(sequence.steps[1].is_rest)

    def test_note_high_bit_marks_a_tie(self):
        program = make_program()
        program[128] = 0x80 | 60
        payload = bytes(EDIT_BUFFER_RESPONSE) + pack_edit_buffer(program)

        step = parse_edit_buffer_response(payload).steps[0]

        self.assertEqual(step.note, 60)
        self.assertTrue(step.tie)

    def test_parse_accepts_mido_payload_without_f0_f7(self):
        program = make_program()
        payload = bytes(EDIT_BUFFER_RESPONSE) + pack_edit_buffer(program)
        self.assertEqual(parse_edit_buffer_response(payload).length, 16)

    def test_nrpn_170_is_not_treated_as_the_raw_length_offset(self):
        program = make_program()
        program[170] = 68
        payload = bytes(EDIT_BUFFER_RESPONSE) + pack_edit_buffer(program)

        sequence = parse_edit_buffer_response(payload)

        self.assertEqual(sequence.length, 16)
        self.assertEqual(sequence.steps[42].note, 68)

    def test_parse_accepts_only_the_data_needed_for_the_sequencer(self):
        program = make_program()
        packed = pack_edit_buffer(program)
        payload = bytes(EDIT_BUFFER_RESPONSE) + packed[:MIN_PACKED_BYTES]

        sequence = parse_edit_buffer_response(payload)

        self.assertEqual(sequence.length, 16)
        self.assertEqual(sequence.steps[-1].note, 99)
        self.assertEqual(sequence.steps[-1].velocity, 64)

    def test_parse_accepts_trailing_firmware_data(self):
        program = make_program()
        payload = (
            bytes(EDIT_BUFFER_RESPONSE) + pack_edit_buffer(program) + b"\x00\x01"
        )

        self.assertEqual(parse_edit_buffer_response(payload).length, 16)

    def test_parse_rejects_response_too_short_for_sequencer(self):
        payload = bytes(EDIT_BUFFER_RESPONSE) + b"\x00" * (MIN_PACKED_BYTES - 1)

        with self.assertRaisesRegex(
            ValueError, rf"too short.*{MIN_PACKED_BYTES - 1}"
        ):
            parse_edit_buffer_response(payload)

    def test_rejects_invalid_response(self):
        for value in (b"", b"\xf0", b"\xf0\x00\xf7"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_edit_buffer_response(value)

    def test_decode_rejects_wrong_size(self):
        with self.assertRaisesRegex(ValueError, "packed bytes"):
            decode_edit_buffer(b"\x00" * 8)


if __name__ == "__main__":
    unittest.main()
