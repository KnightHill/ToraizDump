import mido
import pytest

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


def edit_buffer_message(length_code=4):
    program = bytearray(1024)
    program[170] = length_code
    return mido.Message(
        "sysex",
        data=bytes(EDIT_BUFFER_RESPONSE) + pack_edit_buffer(program),
    )


def test_reads_response_after_ignoring_unrelated_messages():
    output = FakeOutput()
    input_port = FakeInput([
        mido.Message("note_on", note=60),
        mido.Message("sysex", data=(1, 2, 3)),
        edit_buffer_message(),
    ])

    sequence = read_current_sequencer(output, input_port, timeout=0.1)

    assert sequence.length == 16
    assert output.messages == [mido.Message("sysex", data=EDIT_BUFFER_REQUEST)]


def test_times_out_when_no_response_arrives():
    with pytest.raises(TimeoutError, match="edit-buffer response"):
        read_current_sequencer(FakeOutput(), FakeInput(), timeout=0)
