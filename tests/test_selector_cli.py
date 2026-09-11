import io
import unittest
from contextlib import nullcontext, redirect_stdout

from toraiz_dump.protocol import ProgramSummary
from toraiz_dump.selector_cli import (
    _bank_index,
    _move_selection,
    _next_bank,
    _previous_bank,
    _program_label,
    activate_program,
    select_program,
)


PROGRAMS = (
    ProgramSummary("U1", 1, "BA First"),
    ProgramSummary("U1", 2, "BA Second"),
    ProgramSummary("U2", 1, "LD Third"),
    ProgramSummary("F1", 1, ""),
)


class FakeKey(str):
    def __new__(cls, value, name=None):
        key = super().__new__(cls, value)
        key.name = name
        return key


class FakeTerminal:
    width = 60
    height = 10
    is_a_tty = True
    home = ""
    clear = ""

    def __init__(self, keys):
        self.keys = iter(keys)

    def bold(self, value):
        return value

    def reverse(self, value):
        return f">{value}<"

    def fullscreen(self):
        return nullcontext()

    def cbreak(self):
        return nullcontext()

    def hidden_cursor(self):
        return nullcontext()

    def inkey(self):
        return next(self.keys)


class FakeOutput:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


class SelectorCliTests(unittest.TestCase):
    def test_program_label_includes_location_and_name(self):
        self.assertEqual(_program_label(PROGRAMS[0]), "U1 P01 BA First")
        self.assertEqual(_program_label(PROGRAMS[-1]), "F1 P01 (unnamed)")

    def test_bank_labels_map_to_as1_midi_bank_values(self):
        self.assertEqual(_bank_index("U1"), 0)
        self.assertEqual(_bank_index("U5"), 4)
        self.assertEqual(_bank_index("F1"), 5)
        self.assertEqual(_bank_index("F5"), 9)

    def test_activate_program_sends_bank_then_program_change(self):
        output = FakeOutput()

        activate_program(output, ProgramSummary("F2", 17, "Test"), midi_channel=7)

        self.assertEqual(len(output.messages), 2)
        bank, program = output.messages
        self.assertEqual(bank.type, "control_change")
        self.assertEqual(bank.channel, 6)
        self.assertEqual(bank.control, 32)
        self.assertEqual(bank.value, 6)
        self.assertEqual(program.type, "program_change")
        self.assertEqual(program.channel, 6)
        self.assertEqual(program.program, 16)

    def test_activate_program_rejects_invalid_midi_channel(self):
        with self.assertRaisesRegex(ValueError, "between 1 and 16"):
            activate_program(FakeOutput(), PROGRAMS[0], midi_channel=0)

    def test_up_and_down_stay_inside_the_list(self):
        self.assertEqual(_move_selection(PROGRAMS, 0, "KEY_UP", 2), 0)
        self.assertEqual(_move_selection(PROGRAMS, 0, "KEY_DOWN", 2), 1)
        self.assertEqual(_move_selection(PROGRAMS, 3, "KEY_DOWN", 2), 3)

    def test_left_and_right_move_between_banks(self):
        self.assertEqual(_next_bank(PROGRAMS, 0), 2)
        self.assertEqual(_previous_bank(PROGRAMS, 3), 2)
        self.assertEqual(_move_selection(PROGRAMS, 1, "KEY_RIGHT", 2), 2)
        self.assertEqual(_move_selection(PROGRAMS, 2, "KEY_LEFT", 2), 0)

    def test_page_home_and_end_navigation(self):
        self.assertEqual(_move_selection(PROGRAMS, 0, "KEY_PGDOWN", 2), 2)
        self.assertEqual(_move_selection(PROGRAMS, 3, "KEY_PGUP", 2), 1)
        self.assertEqual(_move_selection(PROGRAMS, 2, "KEY_HOME", 2), 0)
        self.assertEqual(_move_selection(PROGRAMS, 1, "KEY_END", 2), 3)

    def test_down_arrow_then_enter_selects_second_program(self):
        terminal = FakeTerminal((
            FakeKey("", "KEY_DOWN"),
            FakeKey("\n", "KEY_ENTER"),
        ))
        with redirect_stdout(io.StringIO()):
            selected = select_program(PROGRAMS, terminal)

        self.assertEqual(selected, PROGRAMS[1])

    def test_q_cancels_selection(self):
        terminal = FakeTerminal((FakeKey("q"),))
        with redirect_stdout(io.StringIO()):
            selected = select_program(PROGRAMS, terminal)

        self.assertIsNone(selected)


if __name__ == "__main__":
    unittest.main()
