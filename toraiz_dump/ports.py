"""MIDI port adapters used by the command-line application."""

from __future__ import annotations

from typing import Any

import mido
import rtmidi


class RtMidiPollingInput:
    """Input port using RtMidi's native queue instead of Mido's callback thread.

    Mido's RtMidi input backend installs a Python callback even when callers use
    ``poll()``. On some ALSA systems, closing that callback-backed input can
    hang. RtMidi also provides a native polling queue, which is sufficient for
    this one-shot request/response application and has a simpler shutdown path.
    """

    def __init__(self, name: str, *, midi_in: Any | None = None) -> None:
        self.name = name
        self._rt = midi_in if midi_in is not None else rtmidi.MidiIn()
        self.closed = True

        names = self._rt.get_ports()
        try:
            port_number = names.index(name)
        except ValueError:
            self._rt.delete()
            available = ", ".join(repr(item) for item in names) or "none"
            raise OSError(
                f"unknown MIDI input port {name!r}; available inputs: {available}"
            ) from None

        try:
            # Receive SysEx, but discard timing clock and active sensing messages.
            self._rt.ignore_types(sysex=False, timing=True, active_sense=True)
            self._rt.open_port(port_number, "toraiz-dump input")
        except Exception:
            self._rt.delete()
            raise
        self.closed = False

    def poll(self) -> mido.Message | None:
        """Return the next queued message, or ``None`` when the queue is empty."""

        event = self._rt.get_message()
        if event is None:
            return None
        message_bytes, _delta_time = event
        try:
            return mido.Message.from_bytes(message_bytes)
        except ValueError:
            return None

    def close(self) -> None:
        if self.closed:
            return
        try:
            self._rt.close_port()
        finally:
            self._rt.delete()
            self.closed = True

    def __enter__(self) -> RtMidiPollingInput:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()
