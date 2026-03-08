"""
display.py — CursesDisplay: all terminal rendering.
This is the ONLY module that touches the terminal.
Everything else is completely display-agnostic.
"""

import curses
from core.config import BASE_RADAR_RANGE


class CursesDisplay:
    """
    Renders the full game UI using curses.
    Divides the terminal into fixed panels:

    ┌─────────────────────────────────────────────────────┐
    │  HEADER — wave, time, SII, pause status             │
    ├──────────────────────┬──────────────────────────────│
    │  THREAT BOARD        │  DEFENDED ASSETS             │
    │  (detected threats,  │  (integrity bars,            │
    │   TTI, confidence)   │   cascade effects)           │
    ├──────────────────────┴──────────────────────────────│
    │  ADVISOR PANEL  (toggle with [A])                   │
    ├─────────────────────────────────────────────────────│
    │  INTERCEPTOR INVENTORY                              │
    ├─────────────────────────────────────────────────────│
    │  EVENT LOG  (scrolling last N messages)             │
    ├─────────────────────────────────────────────────────│
    │  COMMAND PROMPT                                     │
    └─────────────────────────────────────────────────────┘
    """

    # Color pair IDs
    CP_NORMAL   = 1
    CP_RED      = 2
    CP_YELLOW   = 3
    CP_GREEN    = 4
    CP_CYAN     = 5
    CP_MAGENTA  = 6
    CP_WHITE    = 7
    CP_DIM      = 8

    COLOR_MAP = {
        "RED":      CP_RED,
        "YELLOW":   CP_YELLOW,
        "GREEN":    CP_GREEN,
        "CYAN":     CP_CYAN,
        "MAGENTA":  CP_MAGENTA,
        "WHITE":    CP_WHITE,
    }

    def __init__(self, stdscr):
        self.scr    = stdscr
        self._init_colors()
        self.scr.clear()
        curses.curs_set(0)

        self.show_advisor   = True
        self.max_y, self.max_x = self.scr.getmaxyx()

    def _init_colors(self):
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(self.CP_NORMAL,    curses.COLOR_WHITE,   -1)
        curses.init_pair(self.CP_RED,       curses.COLOR_RED,     -1)
        curses.init_pair(self.CP_YELLOW,    curses.COLOR_YELLOW,  -1)
        curses.init_pair(self.CP_GREEN,     curses.COLOR_GREEN,   -1)
        curses.init_pair(self.CP_CYAN,      curses.COLOR_CYAN,    -1)
        curses.init_pair(self.CP_MAGENTA,   curses.COLOR_MAGENTA, -1)
        curses.init_pair(self.CP_WHITE,     curses.COLOR_WHITE,   -1)
        curses.init_pair(self.CP_DIM,       curses.COLOR_BLACK,   -1)

    def _cp(self, name: str):
        return curses.color_pair(self.COLOR_MAP.get(name, self.CP_NORMAL))

    def _safe_addstr(self, y, x, text, attr=0):
        """Write text clipped to screen bounds."""
        try:
            if 0 <= y < self.max_y and 0 <= x < self.max_x:
                available = self.max_x - x - 1
                self.scr.addstr(y, x, text[:available], attr)
        except curses.error:
            pass

    def _hline(self, y, char="─"):
        self._safe_addstr(y, 0, char * (self.max_x - 1),
                          curses.color_pair(self.CP_DIM))

    # ── Main render ───────────────────────────────────────────────────────────

    def render(self, game_state, advisor_recs: list,
               clock, input_handler):
        self.max_y, self.max_x = self.scr.getmaxyx()
        self.scr.erase()

        row = 0
        row = self._render_header(row, game_state, clock)
        row = self._render_threat_and_asset_panels(row, game_state)
        if self.show_advisor:
            row = self._render_advisor(row, advisor_recs, game_state)
        row = self._render_interceptors(row, game_state)
        row = self._render_event_log(row, game_state)
        row = self._render_command_prompt(row, game_state, input_handler)

        self.scr.refresh()

    # ── Header ────────────────────────────────────────────────────────────────

    def _render_header(self, row, gs, clock) -> int:
        sii     = gs.strategic_integrity_index()
        label   = gs.sii_label()
        paused  = " [PAUSED]" if clock.paused else ""
        radar   = f"{gs.effective_radar_range:.0f}km"

        title   = f" THREAT DEFENSE COMMAND  │  Wave {gs.wave_number + 1}"
        status  = f"T+{clock.formatted}  │  SII: {sii:.0f}%  │  Radar: {radar}{paused} "

        self._safe_addstr(row, 0, title.ljust(self.max_x - len(status) - 1),
                          curses.color_pair(self.CP_CYAN) | curses.A_BOLD)
        self._safe_addstr(row, self.max_x - len(status) - 1, status,
                          curses.color_pair(self.CP_YELLOW))
        row += 1
        self._hline(row)
        row += 1

        # SII color bar
        sii_color = (self.CP_GREEN if sii >= 60 else
                     self.CP_YELLOW if sii >= 30 else self.CP_RED)
        bar_width = 40
        filled    = int((sii / 100) * bar_width)
        bar       = "█" * filled + "░" * (bar_width - filled)
        self._safe_addstr(row, 1,
                          f"Strategic Integrity: [{bar}] {label}",
                          curses.color_pair(sii_color))
        row += 1

        # Cascade alerts
        for alert in gs.cascade_alerts[-2:]:
            self._safe_addstr(row, 1, f"!! {alert}",
                              curses.color_pair(self.CP_RED) | curses.A_BOLD)
            row += 1

        self._hline(row)
        row += 1
        return row

    # ── Threat board + Asset panel (side by side) ─────────────────────────────

    def _render_threat_and_asset_panels(self, row, gs) -> int:
        mid         = self.max_x // 2
        start_row   = row

        # --- LEFT: Threat board ---
        self._safe_addstr(row, 1,
                          "DETECTED THREATS",
                          curses.color_pair(self.CP_WHITE) | curses.A_BOLD)
        self._safe_addstr(row, mid + 1,
                          "DEFENDED ASSETS",
                          curses.color_pair(self.CP_WHITE) | curses.A_BOLD)
        row += 1

        # Column headers
        hdr = f"{'ID':<5}{'TYPE':<20}{'TARGET':<22}{'TTI':<8}{'CONF':<8}{'ASSIGN'}"
        self._safe_addstr(row, 1, hdr[:mid - 2],
                          curses.color_pair(self.CP_DIM))
        row += 1

        threats     = gs.detected_threats
        asset_list  = list(gs.assets.values())
        max_rows    = max(len(threats), len(asset_list), 1)

        for i in range(max_rows):
            # Threat row
            if i < len(threats):
                t       = threats[i]
                assign  = gs.interceptors.assignments.get(t.label, "")
                tti_str = t.tti_formatted()
                conf    = t.confidence_label()
                target  = t.estimated_target()[:20]

                # Color by urgency
                tti_val = t.tti()
                color   = (self.CP_RED    if tti_val < 30  else
                           self.CP_YELLOW if tti_val < 90  else
                           self.CP_NORMAL)

                threat_line = (
                    f"{t.label:<5}"
                    f"{t.type_label[:18]:<20}"
                    f"{target:<22}"
                    f"{tti_str:<8}"
                    f"{conf:<8}"
                    f"{assign}"
                )
                self._safe_addstr(row, 1, threat_line[:mid - 2],
                                  curses.color_pair(color))
            else:
                self._safe_addstr(row, 1, "  —", curses.color_pair(self.CP_DIM))

            # Asset row
            if i < len(asset_list):
                a       = asset_list[i]
                bar     = a.integrity_bar(8)
                pct     = f"{a.integrity_pct:>3}%"
                status  = a.status_label

                asset_color = (self.CP_GREEN   if a.integrity >= 0.70 else
                               self.CP_YELLOW  if a.integrity >= 0.30 else
                               self.CP_RED)

                name_col = a.name[:20].ljust(20)
                asset_line = f"{name_col} [{bar}] {pct} {status}"
                self._safe_addstr(row, mid + 1, asset_line,
                                  curses.color_pair(asset_color))

            row += 1

        self._hline(row)
        row += 1
        return row

    # ── Advisor panel ─────────────────────────────────────────────────────────

    def _render_advisor(self, row, recs: list, gs) -> int:
        self._safe_addstr(row, 1,
                          "COMPUTER ADVISOR  (press [A] to hide)",
                          curses.color_pair(self.CP_CYAN) | curses.A_BOLD)
        row += 1

        if not recs:
            self._safe_addstr(row, 3,
                              "No active threats detected.",
                              curses.color_pair(self.CP_DIM))
            row += 1
        else:
            for rec in recs[:5]:    # show top 5
                t       = rec["threat"]
                itype   = rec["interceptor"] or "NONE"
                prob    = rec["probability"]
                pri     = rec["priority"]
                reason  = rec["reasoning"]

                pri_color = (self.CP_RED    if "TOP"      in pri or "TERMINAL" in pri else
                             self.CP_YELLOW if "HIGH"     in pri else
                             self.CP_DIM)

                line = (f"  {t.label} [{pri:<12}]  "
                        f"→ {itype:<12} ({prob}%)  {reason}")
                self._safe_addstr(row, 1, line[:self.max_x - 2],
                                  curses.color_pair(pri_color))
                row += 1

        self._hline(row)
        row += 1
        return row

    # ── Interceptor inventory ─────────────────────────────────────────────────

    def _render_interceptors(self, row, gs) -> int:
        self._safe_addstr(row, 1,
                          "INTERCEPTORS",
                          curses.color_pair(self.CP_WHITE) | curses.A_BOLD)
        row += 1
        col = 2
        for itype, battery in gs.interceptors.batteries.items():
            available   = battery.count > 0
            color       = self.CP_GREEN if available else self.CP_RED
            airborne_tag = " [AIRPORT DOWN]" \
                           if itype == "airborne" \
                           and not gs.airpower_available else ""

            entry = (f"[{battery.label}] x{battery.count}"
                     f"{airborne_tag}  "
                     f"Key: {'P' if itype=='patriot' else 'I' if itype=='iron_dome' else 'B'}")
            self._safe_addstr(row, col, entry,
                              curses.color_pair(color))
            col += len(entry) + 4
            if col > self.max_x - 30:
                col  = 2
                row += 1

        row += 1
        self._hline(row)
        row += 1
        return row

    # ── Event log ─────────────────────────────────────────────────────────────

    def _render_event_log(self, row, gs) -> int:
        self._safe_addstr(row, 1,
                          "EVENT LOG",
                          curses.color_pair(self.CP_WHITE) | curses.A_BOLD)
        row += 1
        # Show last 4 events
        visible = gs.event_log[-4:]
        for msg in visible:
            color = (self.CP_RED    if "IMPACT"      in msg or "HIT"   in msg else
                     self.CP_GREEN  if "INTERCEPTED" in msg              else
                     self.CP_YELLOW if "!!"          in msg              else
                     self.CP_NORMAL)
            self._safe_addstr(row, 3, msg[:self.max_x - 4],
                              curses.color_pair(color))
            row += 1
        while row < self.max_y - 3:
            row += 1
            break   # don't expand, just leave space
        self._hline(row)
        row += 1
        return row

    # ── Command prompt ────────────────────────────────────────────────────────

    def _render_command_prompt(self, row, gs, input_handler) -> int:
        buf = input_handler.get_buffer()

        # ── Line 1: global key reference ──────────────────────────────────────
        cmds = "[SPACE]Pause  [/]Advisor  [ESC]Quit  |  Assign: T##P/I/B/X  [BKSP]delete"
        self._safe_addstr(row, 1, cmds[:self.max_x - 2],
                          curses.color_pair(self.CP_DIM))
        row += 1

        # ── Line 2: command prompt with live buffer echo ───────────────────────
        prompt      = f"CMD> {buf}_"
        buf_color   = (curses.color_pair(self.CP_CYAN) | curses.A_BOLD
                       if buf else
                       curses.color_pair(self.CP_DIM))
        self._safe_addstr(row, 1, prompt, buf_color)
        row += 1

        # ── Line 3: contextual hint — appears as soon as T## is recognised ────
        hint = self._build_hint(buf, gs)
        if hint:
            self._safe_addstr(row, 5, hint,
                              curses.color_pair(self.CP_YELLOW))
        else:
            # Keep the row reserved so layout doesn't shift
            self._safe_addstr(row, 5, "",
                              curses.color_pair(self.CP_DIM))
        row += 1

        return row

    def _build_hint(self, buf: str, gs) -> str:
        """
        Return a contextual hint string based on what the player has typed so far.
        Empty string if no hint is appropriate yet.
        """
        if not buf:
            return ""

        b = buf.upper()

        # Must start with T
        if b[0] != 'T':
            return "  (commands start with T##  e.g. T01)"

        # Extract digits after T
        i = 1
        while i < len(b) and b[i].isdigit():
            i += 1
        digits = b[1:i]

        if not digits:
            return "  (enter threat number  e.g. T01  T02 ...)"

        # We have T##  — check if this threat exists and is active
        threat_label = f"T{int(digits):02d}"
        threat = next(
            (t for t in gs.detected_threats if t.label == threat_label),
            None
        )

        if not threat:
            return f"  ({threat_label} not on detected threat board)"

        # Threat found — show interceptor options with availability
        batteries   = gs.interceptors.batteries
        airpower    = gs.airpower_available

        parts = []
        labels = [
            ('P', 'patriot',   'Patriot'),
            ('I', 'iron_dome', 'IronDome'),
            ('B', 'airborne',  'Airborne'),
        ]
        for key, itype, name in labels:
            bat     = batteries.get(itype)
            if not bat:
                continue
            if itype == 'airborne' and not airpower:
                parts.append(f"[{key}]{name}:OFFLINE")
            elif bat.count == 0:
                parts.append(f"[{key}]{name}:0")
            else:
                prob = bat.success_probability(threat.weapon_type,
                                               threat.in_terminal_phase(),
                                               gs.system_degradation)
                parts.append(f"[{key}]{name}x{bat.count}({int(prob*100)}%)")

        parts.append("[X]Unassign")

        target  = threat.estimated_target()[:20]
        tti     = threat.tti_formatted()
        return (f"  {threat_label} → {threat.type_label} | "
                f"target:{target} TTI:{tti} | "
                + "  ".join(parts))

    # ── Special screens ───────────────────────────────────────────────────────

    def render_wave_intro(self, wave_number: int, description: str,
                          reset: bool, clock):
        self.scr.erase()
        mid_y = self.max_y // 2
        self._safe_addstr(mid_y - 2, (self.max_x - 30) // 2,
                          f"══════  WAVE {wave_number + 1}  ══════",
                          curses.color_pair(self.CP_CYAN) | curses.A_BOLD)
        self._safe_addstr(mid_y, (self.max_x - len(description)) // 2,
                          description,
                          curses.color_pair(self.CP_YELLOW))
        reset_txt = "City reset to full integrity." if reset else \
                    "Damage carries over from previous wave."
        self._safe_addstr(mid_y + 1, (self.max_x - len(reset_txt)) // 2,
                          reset_txt,
                          curses.color_pair(self.CP_DIM))
        self._safe_addstr(mid_y + 3, (self.max_x - 26) // 2,
                          "Press [ENTER] to begin...",
                          curses.color_pair(self.CP_WHITE))
        self.scr.refresh()

    def render_game_over(self, game_state, clock):
        self.scr.erase()
        mid_y   = self.max_y // 2
        sii     = game_state.strategic_integrity_index()
        label   = game_state.sii_label()
        reason  = game_state.game_over_reason

        self._safe_addstr(mid_y - 3, (self.max_x - 20) // 2,
                          "══════  GAME OVER  ══════",
                          curses.color_pair(self.CP_RED) | curses.A_BOLD)
        self._safe_addstr(mid_y - 1, (self.max_x - len(reason)) // 2,
                          reason,
                          curses.color_pair(self.CP_RED))
        self._safe_addstr(mid_y + 1, (self.max_x - 30) // 2,
                          f"Final SII: {sii:.0f}%  —  {label}",
                          curses.color_pair(self.CP_YELLOW))
        self._safe_addstr(mid_y + 2, (self.max_x - 30) // 2,
                          f"Survived {game_state.wave_number} wave(s)",
                          curses.color_pair(self.CP_WHITE))
        self._safe_addstr(mid_y + 4, (self.max_x - 20) // 2,
                          "Press [Q] to exit.",
                          curses.color_pair(self.CP_DIM))
        self.scr.refresh()

    def render_capability_warning(self, game_state):
        """Flash a warning when survival probability drops critically."""
        prob    = game_state.survival_probability()
        msg     = (f"!! CRITICAL: Survival probability {prob:.0f}%  "
                   f"— Continue [ENTER] or Surrender [Q]")
        y       = self.max_y - 4
        self._safe_addstr(y, 1, msg[:self.max_x - 2],
                          curses.color_pair(self.CP_RED) | curses.A_BOLD)
        self.scr.refresh()

    def toggle_advisor(self):
        self.show_advisor = not self.show_advisor
