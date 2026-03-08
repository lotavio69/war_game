"""
clock.py — Simulation clock management.
"""

import time


class SimClock:
    """
    Tracks simulated time and real-time pacing.
    Simulated time advances in fixed ticks; real time
    is controlled by REAL_TICK_MS to keep the game playable.
    """

    def __init__(self, tick_seconds: float, real_tick_ms: int):
        self.tick_seconds   = tick_seconds    # simulated seconds per tick
        self.real_tick_ms   = real_tick_ms    # real milliseconds per tick
        self.sim_time       = 0.0             # total simulated seconds elapsed
        self.tick_count     = 0
        self._last_tick     = time.time()
        self.paused         = False

    def tick(self) -> float:
        """
        Advance one tick. Blocks in real time to maintain pacing.
        Returns the simulated dt (seconds) for this tick.
        """
        if not self.paused:
            # Real-time pacing — sleep remainder of tick window
            now     = time.time()
            elapsed = now - self._last_tick
            wait    = (self.real_tick_ms / 1000.0) - elapsed
            if wait > 0:
                time.sleep(wait)
            self._last_tick  = time.time()
            self.sim_time   += self.tick_seconds
            self.tick_count += 1
        return self.tick_seconds

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused     = False
        self._last_tick = time.time()   # reset so we don't rush after pause

    def toggle_pause(self):
        if self.paused:
            self.resume()
        else:
            self.pause()

    @property
    def formatted(self) -> str:
        """Return simulated time as MM:SS string."""
        mins = int(self.sim_time) // 60
        secs = int(self.sim_time) % 60
        return f"{mins:02d}:{secs:02d}"
