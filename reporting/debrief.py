"""
debrief.py — Post-wave debrief screen.
Shows what happened, what the player chose, and what the
computer would have recommended, side by side.
"""

import curses


class Debrief:
    """
    Renders the post-wave debrief in the curses window.
    Compares player decisions against advisor recommendations.
    """

    def __init__(self, display):
        self.display = display

    def render(self, game_state, advisor_final: list, clock):
        """
        Show the full debrief screen and wait for ENTER.
        """
        scr     = self.display.scr
        max_y, max_x = scr.getmaxyx()
        scr.erase()

        row = 0
        cp  = self.display._cp
        safe = self.display._safe_addstr

        # ── Header ────────────────────────────────────────────────────────────
        safe(row, 1,
             f"══════  WAVE {game_state.wave_number + 1} DEBRIEF  ══════  "
             f"T+{clock.formatted}",
             curses.color_pair(self.display.CP_CYAN) | curses.A_BOLD)
        row += 2

        # ── Threat outcomes ───────────────────────────────────────────────────
        safe(row, 1, "THREAT OUTCOMES",
             curses.color_pair(self.display.CP_WHITE) | curses.A_BOLD)
        row += 1

        intercepted = 0
        hit         = 0
        for t in game_state.threats:
            if t.intercepted:
                status  = "INTERCEPTED ✓"
                color   = self.display.CP_GREEN
                intercepted += 1
            elif t.impacted:
                status  = f"HIT {t.target_name[:20]} ✗"
                color   = self.display.CP_RED
                hit     += 1
            elif not t.detected:
                status  = "UNDETECTED — passed through"
                color   = self.display.CP_YELLOW
                hit     += 1
            else:
                status  = "ACTIVE (wave ended)"
                color   = self.display.CP_DIM

            line = f"  {t.label}  {t.type_label:<22} → {status}"
            safe(row, 1, line[:max_x - 2], curses.color_pair(color))
            row += 1

        row += 1
        safe(row, 1,
             f"Intercepted: {intercepted}   Hits: {hit}",
             curses.color_pair(self.display.CP_YELLOW))
        row += 2

        # ── Asset status ──────────────────────────────────────────────────────
        safe(row, 1, "ASSET STATUS AFTER WAVE",
             curses.color_pair(self.display.CP_WHITE) | curses.A_BOLD)
        row += 1

        mid = max_x // 2
        for name, asset in game_state.assets.items():
            bar     = asset.integrity_bar(10)
            pct     = f"{asset.integrity_pct}%"
            color   = (self.display.CP_GREEN   if asset.integrity >= 0.70 else
                       self.display.CP_YELLOW  if asset.integrity >= 0.30 else
                       self.display.CP_RED)
            safe(row, 3,
                 f"{name[:28]:<28} [{bar}] {pct:>4}  {asset.status_label}",
                 curses.color_pair(color))
            row += 1

        row += 1

        # ── SII ───────────────────────────────────────────────────────────────
        sii     = game_state.strategic_integrity_index()
        label   = game_state.sii_label()
        sii_color = (self.display.CP_GREEN  if sii >= 60 else
                     self.display.CP_YELLOW if sii >= 30 else
                     self.display.CP_RED)
        safe(row, 1,
             f"Strategic Integrity Index: {sii:.0f}%  —  {label}",
             curses.color_pair(sii_color) | curses.A_BOLD)
        row += 2

        # ── Interceptor usage ─────────────────────────────────────────────────
        safe(row, 1, "INTERCEPTORS REMAINING",
             curses.color_pair(self.display.CP_WHITE) | curses.A_BOLD)
        row += 1
        for itype, battery in game_state.interceptors.batteries.items():
            color = self.display.CP_GREEN if battery.count > 2 else self.display.CP_RED
            safe(row, 3, f"{battery.label:<16} x{battery.count}",
                 curses.color_pair(color))
            row += 1

        row += 1

        # ── Advisor comparison ────────────────────────────────────────────────
        if advisor_final:
            safe(row, 1,
                 "COMPUTER ADVISOR — what it recommended this wave:",
                 curses.color_pair(self.display.CP_CYAN) | curses.A_BOLD)
            row += 1
            for rec in advisor_final[:6]:
                t       = rec["threat"]
                itype   = rec["interceptor"] or "skip"
                prob    = rec["probability"]
                safe(row, 3,
                     f"{t.label}  →  {itype:<14} ({prob}% success probability)",
                     curses.color_pair(self.display.CP_NORMAL))
                row += 1
            row += 1

        # ── Cascade effects active ────────────────────────────────────────────
        active_cascades = [
            msg for a in game_state.assets.values()
            for msg in game_state.cascade_alerts
        ]
        if game_state.cascade_alerts:
            safe(row, 1, "ACTIVE CASCADE EFFECTS:",
                 curses.color_pair(self.display.CP_RED) | curses.A_BOLD)
            row += 1
            for alert in game_state.cascade_alerts[-5:]:
                safe(row, 3, alert[:max_x - 4],
                     curses.color_pair(self.display.CP_RED))
                row += 1
            row += 1

        # ── Footer ────────────────────────────────────────────────────────────
        if row < max_y - 2:
            safe(max_y - 2, 1,
                 "Press [ENTER] for next wave  |  [Q] to quit",
                 curses.color_pair(self.display.CP_DIM))

        scr.refresh()

        # Wait for ENTER or Q
        scr.nodelay(False)
        while True:
            key = scr.getch()
            if key in (curses.KEY_ENTER, 10, 13):
                scr.nodelay(True)
                return "next"
            if key in (ord('q'), ord('Q')):
                scr.nodelay(True)
                return "quit"
