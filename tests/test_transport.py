import unittest

import mido

from toraiz_dump.protocol import EDIT_BUFFER_REQUEST, EDIT_BUFFER_RESPONSE, pack_edit_buffer
from toraiz_dump.transport import read_current_sequencer


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


class TransportTests(unittest.TestCase):
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
