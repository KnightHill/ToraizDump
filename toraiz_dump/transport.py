"""mido/rtmidi transport for requesting the AS-1 edit buffer."""

from __future__ import annotations

import time

import mido

from .protocol import EDIT_BUFFER_REQUEST, parse_edit_buffer_response


def read_current_sequencer(
    output: mido.ports.BaseOutput,
    input_port: mido.ports.BaseInput,
    timeout: float = 2.0,
):
    """Request and parse the currently selected AS-1 program's sequencer."""

    output.send(mido.Message("sysex", data=EDIT_BUFFER_REQUEST))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        message = input_port.receive(block=True, timeout=max(0, deadline - time.monotonic()))
        if message is None or message.type != "sysex":
            continue
        try:
            return parse_edit_buffer_response(message.data)
        except ValueError:
            # Ignore unrelated SysEx traffic while waiting for the AS-1 reply.
            continue
    raise TimeoutError("timed out waiting for the AS-1 edit-buffer response")
