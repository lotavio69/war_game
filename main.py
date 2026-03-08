"""
main.py — Entry point and main game loop.
Ties all modules together. This file orchestrates; it does not simulate.
"""

import curses
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config      import TICK_SECONDS, REAL_TICK_MS
from core.clock       import SimClock
from core.game_state  import GameState
from simulation.wave_generator import WaveGenerator
from ai.advisor       import ComputerAdvisor
from ui.display       import CursesDisplay
from ui.input_handler import InputHandler, Command
from reporting.debrief import Debrief


def run_game(stdscr):
    # ── Initialization ────────────────────────────────────────────────────────
    clock       = SimClock(TICK_SECONDS, REAL_TICK_MS)
    state       = GameState()

    # ── Open log file for this session ────────────────────────────────────────
    from core.config import LOG_TO_FILE, LOG_FILE
    if LOG_TO_FILE:
        import datetime
        with open(LOG_FILE, "a") as f:
            f.write(f"\n{'═' * 60}\n")
            f.write(f"SESSION START — "
                    f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'═' * 60}\n")
    generator   = WaveGenerator()
    advisor     = ComputerAdvisor()
    display     = CursesDisplay(stdscr)
    inp         = InputHandler(stdscr)
    debrief     = Debrief(display)

    wave_index  = 0

    # ── Wave loop ─────────────────────────────────────────────────────────────
    while True:
        # ── Wave intro screen ─────────────────────────────────────────────────
        reset       = generator.is_reset_wave(wave_index)
        description = generator.wave_description(wave_index)

        state.reset_for_wave(full_reset=reset)
        state.wave_number = wave_index
        state.log_wave_marker(f"WAVE {wave_index + 1} BEGIN — {description}")

        display.render_wave_intro(wave_index, description, reset, clock)

        # Wait for ENTER to start wave
        stdscr.nodelay(False)
        while True:
            key = stdscr.getch()
            if key in (curses.KEY_ENTER, 10, 13):
                break
            if key in (ord('q'), ord('Q')):
                return
        stdscr.nodelay(True)

        # ── Generate threats ──────────────────────────────────────────────────
        threats = generator.generate(wave_index)
        state.load_threats(threats)
        state.wave_active = True

        # Reset clock for this wave
        clock.sim_time  = 0.0
        clock.paused    = False

        # Snapshot of advisor recommendations at wave start (for debrief)
        advisor_snapshot = []

        # ── Tick loop ─────────────────────────────────────────────────────────
        while state.wave_active:
            dt = clock.tick()

            if clock.paused:
                # Still render + accept input while paused
                advisor_recs = advisor.evaluate(state)
                display.render(state, advisor_recs, clock, inp)
                cmd = inp.get_command()
                _handle_command(cmd, state, display, clock, inp)
                continue

            sim_time = clock.sim_time

            # ── Update all threats ─────────────────────────────────────────
            radar_positions = state.radar_positions()
            for threat in state.threats:
                threat.update(
                    dt          = dt,
                    elapsed_sim_time = sim_time,
                    radar_positions  = radar_positions,
                    effective_radar_range = state.effective_radar_range,
                )

            # ── Execute any pending intercept assignments ──────────────────
            results = state.interceptors.execute_assignments(
                state.active_threats, sim_time, state.system_degradation
            )
            for r in results:
                if r.get("error"):
                    state.log(f"FAILED: {r['interceptor']} reloading — "
                              f"{r['threat']} undefended!")
                elif r["success"]:
                    state.log(f"INTERCEPTED: {r['threat']} "
                              f"({r['threat_type']}) → {r['target']}")
                else:
                    state.log(f"MISSED: {r['interceptor']} failed on "
                              f"{r['threat']} — still inbound!")
            state.intercept_results.extend(results)

            # ── Resolve impacts ────────────────────────────────────────────
            impact_events = state.resolve_impacts()
            for ev in impact_events:
                state.log(ev)

            # ── Check game over ────────────────────────────────────────────
            if state.game_over:
                state.log_wave_marker(
                    f"GAME OVER — {state.game_over_reason} | "
                    f"SII: {state.strategic_integrity_index()}%"
                )
                display.render_game_over(state, clock)
                stdscr.nodelay(False)
                while True:
                    key = stdscr.getch()
                    if key in (ord('q'), ord('Q'), curses.KEY_ENTER, 10, 13):
                        break
                return

            # ── Capability collapse warning ────────────────────────────────
            if state.is_capability_collapsed():
                display.render_capability_warning(state)

            # ── Advisor evaluation ─────────────────────────────────────────
            advisor_recs = advisor.evaluate(state)
            if not advisor_snapshot and advisor_recs:
                advisor_snapshot = advisor_recs.copy()

            # ── Render ────────────────────────────────────────────────────
            display.render(state, advisor_recs, clock, inp)

            # ── Input ─────────────────────────────────────────────────────
            cmd = inp.get_command()
            _handle_command(cmd, state, display, clock, inp)

            if cmd.type == Command.QUIT:
                return

            # ── Wave end condition ─────────────────────────────────────────
            # Only end when every threat that has launched is resolved
            launched = [t for t in state.threats if t.active or t.intercepted or t.impacted]
            all_resolved = launched and all(
                t.intercepted or t.impacted for t in launched
            )
            # Also check nothing is still waiting to launch
            still_launching = any(
                not t.active and not t.intercepted and not t.impacted
                for t in state.threats
            )
            if all_resolved and not still_launching:
                state.wave_active = False

        # ── Debrief ───────────────────────────────────────────────────────────
        state.log_wave_marker(
            f"WAVE {wave_index + 1} END — SII: {state.strategic_integrity_index()}% "
            f"— {state.sii_label()}"
        )
        result = debrief.render(state, advisor_snapshot, clock)
        if result == "quit":
            return

        wave_index += 1


def _handle_command(cmd: Command, state, display, clock, inp):
    """Apply a parsed command to game state."""
    if cmd.type == Command.PAUSE:
        clock.toggle_pause()
        state.log("Game paused." if clock.paused else "Game resumed.")

    elif cmd.type == Command.ADVISOR:
        display.toggle_advisor()

    elif cmd.type == Command.ASSIGN:
        threat_label    = cmd.data.get("threat")
        itype           = cmd.data.get("interceptor")
        # Validate threat exists and is active
        threat = next(
            (t for t in state.detected_threats if t.label == threat_label),
            None
        )
        if threat and not state.airpower_available and itype == "airborne":
            state.log("!! Airport destroyed — airborne interceptors unavailable")
        elif threat:
            state.interceptors.assign(threat_label, itype)
            state.log(f"Assigned {itype} → {threat_label} ({threat.type_label})")
        else:
            state.log(f"Unknown or inactive threat: {threat_label}")

    elif cmd.type == Command.UNASSIGN:
        threat_label = cmd.data.get("threat")
        state.interceptors.unassign(threat_label)
        state.log(f"Removed assignment for {threat_label}")

    elif cmd.type == Command.FIRE:
        # Assignments are automatically executed each tick;
        # FIRE is an explicit "execute now" in case player wants immediate action
        results = state.interceptors.execute_assignments(
            state.active_threats,
            0,   # immediate
            state.system_degradation,
        )
        for r in results:
            if r["success"]:
                state.log(f"FIRED: {r['interceptor']} → {r['threat']} — HIT!")
            else:
                state.log(f"FIRED: {r['interceptor']} → {r['threat']} — MISS!")


def main():
    try:
        curses.wrapper(run_game)
    except KeyboardInterrupt:
        pass
    print("\nThank you for playing Threat Defense Command.\n")


if __name__ == "__main__":
    main()
