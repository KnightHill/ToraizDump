"""mido/rtmidi transport for requesting the AS-1 edit buffer."""

from __future__ import annotations

import time

import mido

from .protocol import (
    EDIT_BUFFER_REQUEST,
    SequencerData,
    parse_edit_buffer_response,
)

POLL_INTERVAL = 0.01


def read_current_sequencer(
    output: mido.ports.BaseOutput,
    input_port: mido.ports.BaseInput,
    timeout: float = 2.0,
) -> SequencerData:
    """Request and parse the currently selected AS-1 program's sequencer."""

    output.send(mido.Message("sysex", data=EDIT_BUFFER_REQUEST))
    deadline = time.monotonic() + timeout
    last_rejection: str | None = None
    while time.monotonic() < deadline:
        message = input_port.poll()
        if message is None:
            time.sleep(min(POLL_INTERVAL, max(0, deadline - time.monotonic())))
            continue
        if message.type != "sysex":
            continue
        try:
            return parse_edit_buffer_response(message.data)
        except ValueError as error:
            # Ignore unrelated SysEx traffic while waiting for the AS-1 reply.
            last_rejection = f"{error} (received {len(message.data)} payload bytes)"
            continue
    detail = f"; last SysEx rejected: {last_rejection}" if last_rejection else ""
    raise TimeoutError(f"timed out waiting for the AS-1 edit-buffer response{detail}")
