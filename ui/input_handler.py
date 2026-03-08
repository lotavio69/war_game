"""
input_handler.py — Non-blocking keyboard input and command parsing.
Translates raw keypresses into structured command objects.
"""

import curses
from typing import Optional


# ── Command types ──────────────────────────────────────────────────────────────
class Command:
    ASSIGN      = "assign"       # assign interceptor to threat
    UNASSIGN    = "unassign"     # remove assignment
    FIRE        = "fire"         # execute all pending assignments
    PAUSE       = "pause"        # toggle pause
    ADVISOR     = "advisor"      # toggle advisor panel
    NEXT_WAVE   = "next_wave"    # advance after wave ends
    QUIT        = "quit"
    NONE        = "none"

    def __init__(self, ctype: str, **kwargs):
        self.type = ctype
        self.data = kwargs

    def __repr__(self):
        return f"<Command {self.type} {self.data}>"


class InputHandler:
    """
    Reads keypresses from a curses window and parses them
    into Command objects. Non-blocking — returns Command.NONE
    if no key is pressed.

    Input scheme:
        [SPACE]     Pause / resume
        [/]         Toggle advisor recommendations
        [ESC]       Quit
        [ENTER]     Confirm / next wave
        [BKSP]      Delete last character in buffer

        Assignment (all letters free — no conflicts):
        T##P        Assign Patriot to threat ##      e.g. T01P
        T##I        Assign Iron Dome to threat ##    e.g. T02I
        T##B        Assign Airborne to threat ##     e.g. T03B
        T##X        Remove assignment from threat ## e.g. T01X
    """

    def __init__(self, window):
        self.window           = window
        self.window.nodelay(True)
        self.window.keypad(True)

        self._input_buffer    = ""
        self._selected_threat = None

    def get_command(self) -> Command:
        """
        Poll for a keypress and return the corresponding Command.
        Returns Command(NONE) if nothing was pressed.
        """
        try:
            key = self.window.getch()
        except Exception:
            return Command(Command.NONE)

        if key == -1:
            return Command(Command.NONE)

        ch = chr(key) if 32 <= key <= 126 else None

        # ── Global keys — no letter conflicts ─────────────────────────────────
        if key == ord(' '):                          # Space → pause
            self._input_buffer = ""
            return Command(Command.PAUSE)

        if key == 27:                                # ESC → quit
            self._input_buffer = ""
            return Command(Command.QUIT)

        if ch == '/':                                # / → toggle advisor
            self._input_buffer = ""
            return Command(Command.ADVISOR)

        if key in (curses.KEY_ENTER, 10, 13):        # Enter → next wave
            self._input_buffer = ""
            return Command(Command.NEXT_WAVE)

        if key in (curses.KEY_BACKSPACE, 127, 8):    # Backspace → edit buffer
            self._input_buffer = self._input_buffer[:-1]
            return Command(Command.NONE)

        # ── Assignment input — all letters available ───────────────────────────
        if ch:
            self._input_buffer += ch
            cmd = self._try_parse_assignment(self._input_buffer)
            if cmd:
                self._input_buffer = ""
                return cmd
            # Clear if too long or doesn't start with T
            if len(self._input_buffer) > 15:
                self._input_buffer = ""
            if self._input_buffer and self._input_buffer[0].upper() != 'T':
                self._input_buffer = ""

        return Command(Command.NONE)

    def _try_parse_assignment(self, buf: str) -> Optional[Command]:
        """
        Try to parse buffer as an assignment command.
        Valid formats:
            "T01p"     → assign patriot to T01
            "T01i"     → assign iron_dome to T01
            "T01b"     → assign airborne to T01
            "T01x"     → unassign T01
        """
        buf = buf.strip().upper()

        # Need at least T + 2 digit number + 1 letter
        if len(buf) < 4:
            return None

        if buf[0] != 'T':
            return None

        # Extract threat number
        i = 1
        while i < len(buf) and buf[i].isdigit():
            i += 1

        if i < 2:
            return None

        threat_num  = buf[1:i]
        threat_label = f"T{int(threat_num):02d}"
        action       = buf[i:] if i < len(buf) else ""

        if not action:
            return None

        interceptor_map = {
            'P': 'patriot',
            'I': 'iron_dome',
            'B': 'airborne',
        }

        if action == 'X':
            return Command(Command.UNASSIGN, threat=threat_label)

        itype = interceptor_map.get(action[0])
        if itype:
            return Command(Command.ASSIGN,
                           threat=threat_label,
                           interceptor=itype)

        return None

    def get_buffer(self) -> str:
        """Return current input buffer (for display in command prompt)."""
        return self._input_buffer

    def clear_buffer(self):
        self._input_buffer = ""
