"""
threat.py — Threat class representing a single incoming weapon.
Each threat is self-contained: it knows its position, target,
detection status, and updates itself each tick.
"""

import random
from simulation.physics import (
    move_toward, time_to_impact, distance, apply_cep
)
from core.config import WEAPONS


class Threat:
    """
    A single incoming threat. Moves toward its target each tick,
    subject to detection probability and interception.
    """

    # Unique ID counter across all instances
    _id_counter = 0

    def __init__(self, weapon_type: str, start_pos: tuple,
                 target_name: str, target_pos: tuple, launch_delay: float = 0.0):

        Threat._id_counter += 1
        self.tid            = Threat._id_counter
        self.label          = f"T{self.tid:02d}"

        profile             = WEAPONS[weapon_type]
        self.weapon_type    = weapon_type
        self.type_label     = profile["label"]
        self.speed          = profile["speed_kms"]
        self.stealth        = profile["stealth_factor"]
        self.blast_radius   = profile["blast_radius"]
        self.base_damage    = profile["base_damage"]
        self.cep            = profile["cep"]
        self.terminal_phase = profile["terminal_phase"]   # seconds
        self.color          = profile["color"]
        self.symbol         = profile["symbol"]

        self.pos            = start_pos
        self.target_name    = target_name
        self.target_pos     = target_pos
        self.impact_pos     = apply_cep(target_pos, self.cep)  # actual aim point

        self.launch_delay   = launch_delay    # seconds before this threat activates
        self.active         = False           # becomes True after launch delay
        self.detected       = False
        self.intercepted    = False
        self.impacted       = False

        # Detection confidence: builds up as threat stays in radar range
        self.detection_confidence = 0.0      # 0.0 = unknown, 1.0 = fully tracked

        # Interception assignment
        self.assigned_interceptor = None     # interceptor type assigned by player

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, dt: float, elapsed_sim_time: float,
               radar_positions: list, effective_radar_range: float):
        """
        Advance one tick: handle launch delay, movement, detection rolling.
        """
        # Wait for launch delay
        if elapsed_sim_time < self.launch_delay:
            return

        if not self.active:
            self.active = True

        if self.intercepted or self.impacted:
            return

        # Move toward impact point
        self.pos = move_toward(self.pos, self.impact_pos, self.speed, dt)

        # Check if we've arrived
        if distance(self.pos, self.impact_pos) < 0.1:
            self.impacted = True
            return

        # Detection rolling — check each radar
        self._roll_detection(radar_positions, effective_radar_range, dt)

    def _roll_detection(self, radar_positions: list,
                        effective_radar_range: float, dt: float):
        """
        Each tick, roll for detection against each radar.
        Confidence accumulates — a briefly glimpsed drone
        might not be confirmed immediately.
        """
        in_range = any(
            distance(self.pos, rpos) <= effective_radar_range
            for rpos in radar_positions
        )

        if in_range:
            # Detection probability scales with stealth factor and dt
            # Higher dt (3s ticks) means faster confidence buildup
            p_detect = self.stealth * min(dt / 3.0, 1.0)
            if random.random() < p_detect:
                self.detection_confidence = min(
                    1.0, self.detection_confidence + 0.50
                )
            # Lower threshold so threats appear on board quickly
            if self.detection_confidence >= 0.20 and not self.detected:
                self.detected = True
        else:
            # Slowly lose confidence when out of range
            self.detection_confidence = max(
                0.0, self.detection_confidence - 0.05
            )

    # ── Computed properties ────────────────────────────────────────────────────

    def tti(self) -> float:
        """Time to impact in seconds from current position."""
        return time_to_impact(self.pos, self.impact_pos, self.speed)

    def tti_formatted(self) -> str:
        t = self.tti()
        if t == float('inf'):
            return "--:--"
        if t > 9999:
            return ">99m"
        mins = int(t) // 60
        secs = int(t) % 60
        return f"{mins:02d}:{secs:02d}"

    def in_terminal_phase(self) -> bool:
        """True if TTI is within the terminal phase window — nearly unstoppable."""
        return self.tti() <= self.terminal_phase

    def confidence_label(self) -> str:
        if self.detection_confidence >= 0.80:
            return "HIGH"
        elif self.detection_confidence >= 0.50:
            return "MEDIUM"
        elif self.detection_confidence > 0:
            return "LOW"
        return "UNKNOWN"

    def estimated_target(self) -> str:
        """What the player sees — confidence affects accuracy of displayed target."""
        if self.detection_confidence >= 0.60:
            return self.target_name
        elif self.detection_confidence >= 0.30:
            return "Unknown (est. near " + self.target_name[:8] + ")"
        return "Unknown"

    @property
    def is_active(self) -> bool:
        return self.active and not self.intercepted and not self.impacted

    @classmethod
    def reset_counter(cls):
        cls._id_counter = 0
