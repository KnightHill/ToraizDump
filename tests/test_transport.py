import unittest
from unittest.mock import patch

import mido

from toraiz_dump.protocol import (
    EDIT_BUFFER_REQUEST,
    EDIT_BUFFER_RESPONSE,
    PROGRAM_DUMP_RESPONSE,
    ProgramSummary,
    make_program_dump_request,
    pack_edit_buffer,
)
from toraiz_dump.transport import (
    iter_program_summaries,
    read_current_sequencer,
    read_program_summary,
)


class FakeOutput:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


class FakeInput:
    def __init__(self, messages=()):
        self.messages = list(messages)

    def poll(self):
        return self.messages.pop(0) if self.messages else None


def edit_buffer_message(raw_length=4):
    program = bytearray(1024)
    program[87] = 120
    program[92] = 6
    program[95] = raw_length
    return mido.Message(
        "sysex",
        data=bytes(EDIT_BUFFER_RESPONSE) + pack_edit_buffer(program),
    )


def program_dump_message(bank_index=0, program_index=0, name="Basic Program"):
    program = bytearray(1024)
    program[107:127] = name.encode("ascii").ljust(20)
    return mido.Message(
        "sysex",
        data=(
            bytes(PROGRAM_DUMP_RESPONSE)
            + bytes((bank_index, program_index))
            + pack_edit_buffer(program)
        ),
    )


class TransportTests(unittest.TestCase):
    def test_reads_one_stored_program(self):
        output = FakeOutput()
        input_port = FakeInput([
            program_dump_message(1, 2, "Wrong Address"),
            program_dump_message(5, 8, "Factory Bass"),
        ])

        summary = read_program_summary(
            output, input_port, 5, 8, timeout=0.1
        )

        self.assertEqual(summary, ProgramSummary("F1", 9, "Factory Bass"))
        self.assertEqual(
            output.messages,
            [mido.Message("sysex", data=make_program_dump_request(5, 8))],
        )

    def test_program_timeout_identifies_the_slot(self):
        with self.assertRaisesRegex(TimeoutError, "U2 P03"):
            read_program_summary(
                FakeOutput(), FakeInput(), 1, 2, timeout=0
            )

    def test_iterates_all_programs_in_address_order(self):
        def fake_read(_output, _input, bank, program, _timeout):
            return ProgramSummary(
                "U1" if bank == 0 else "F5",
                program + 1,
                f"Name {bank}-{program}",
            )

        with patch(
            "toraiz_dump.transport.read_program_summary",
            side_effect=fake_read,
        ) as read:
            summaries = list(iter_program_summaries(object(), object(), 0.5))

        self.assertEqual(len(summaries), 990)
        self.assertEqual(read.call_args_list[0].args[2:], (0, 0, 0.5))
        self.assertEqual(read.call_args_list[-1].args[2:], (9, 98, 0.5))

    def test_reads_response_after_ignoring_unrelated_messages(self):
        output = FakeOutput()
        input_port = FakeInput(
            [
                mido.Message("note_on", note=60),
                mido.Message("sysex", data=(1, 2, 3)),
                edit_buffer_message(),
            ]
        )

        sequence = read_current_sequencer(output, input_port, timeout=0.1)

        self.assertEqual(sequence.length, 5)
        self.assertEqual(
            output.messages, [mido.Message("sysex", data=EDIT_BUFFER_REQUEST)]
        )

    def test_times_out_when_no_response_arrives(self):
        with self.assertRaisesRegex(TimeoutError, "edit-buffer response"):
            read_current_sequencer(FakeOutput(), FakeInput(), timeout=0)

    def test_timeout_reports_rejected_sysex_length_and_reason(self):
        input_port = FakeInput([mido.Message("sysex", data=(1, 2, 3))])

        with self.assertRaisesRegex(
            TimeoutError, r"last SysEx rejected:.*3 payload bytes"
        ):
            read_current_sequencer(FakeOutput(), input_port, timeout=0.02)


if __name__ == "__main__":
    unittest.main()
