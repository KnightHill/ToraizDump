"""mido/rtmidi transport for requesting the AS-1 edit buffer."""

from __future__ import annotations

import time
from collections.abc import Iterator

import mido

from .protocol import (
    EDIT_BUFFER_REQUEST,
    BANK_COUNT,
    PROGRAMS_PER_BANK,
    ProgramSummary,
    SequencerData,
    bank_name,
    make_program_dump_request,
    parse_edit_buffer_response,
    parse_program_dump_response,
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


def read_program_summary(
    output: mido.ports.BaseOutput,
    input_port: mido.ports.BaseInput,
    bank_index: int,
    program_index: int,
    timeout: float = 2.0,
) -> ProgramSummary:
    """Request the name and location of one stored AS-1 program."""

    request = make_program_dump_request(bank_index, program_index)
    output.send(mido.Message("sysex", data=request))
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
            return parse_program_dump_response(
                message.data,
                expected_bank=bank_index,
                expected_program=program_index,
            )
        except ValueError as error:
            last_rejection = f"{error} (received {len(message.data)} payload bytes)"

    location = f"{bank_name(bank_index)} P{program_index + 1:02d}"
    detail = f"; last SysEx rejected: {last_rejection}" if last_rejection else ""
    raise TimeoutError(f"timed out waiting for {location}{detail}")


def iter_program_summaries(
    output: mido.ports.BaseOutput,
    input_port: mido.ports.BaseInput,
    timeout: float = 2.0,
) -> Iterator[ProgramSummary]:
    """Read every user-bank program followed by every factory-bank program."""

    for bank_index in range(BANK_COUNT):
        for program_index in range(PROGRAMS_PER_BANK):
            yield read_program_summary(
                output,
                input_port,
                bank_index,
                program_index,
                timeout,
            )
