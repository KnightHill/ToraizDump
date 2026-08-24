import mido
import pytest

from toraiz_dump.ports import RtMidiPollingInput


class FakeMidiIn:
    def __init__(self, ports=("TORAIZ AS-1",), events=()):
        self.ports = list(ports)
        self.events = list(events)
        self.calls = []

    def get_ports(self):
        return self.ports

    def ignore_types(self, **kwargs):
        self.calls.append(("ignore_types", kwargs))

    def open_port(self, number, name):
        self.calls.append(("open_port", number, name))

    def get_message(self):
        return self.events.pop(0) if self.events else None

    def close_port(self):
        self.calls.append(("close_port",))

    def delete(self):
        self.calls.append(("delete",))


def test_polling_input_receives_sysex_without_a_callback():
    midi_in = FakeMidiIn(events=[([0xF0, 1, 2, 3, 0xF7], 0.0)])

    with RtMidiPollingInput("TORAIZ AS-1", midi_in=midi_in) as port:
        assert port.poll() == mido.Message("sysex", data=(1, 2, 3))
        assert port.poll() is None

    assert ("ignore_types", {
        "sysex": False,
        "timing": True,
        "active_sense": True,
    }) in midi_in.calls
    assert midi_in.calls[-2:] == [("close_port",), ("delete",)]


def test_polling_input_rejects_an_unknown_port():
    midi_in = FakeMidiIn(ports=("Other MIDI",))

    with pytest.raises(OSError, match="unknown MIDI input port.*Other MIDI"):
        RtMidiPollingInput("TORAIZ AS-1", midi_in=midi_in)

    assert midi_in.calls == [("delete",)]
