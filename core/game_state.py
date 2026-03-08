"""
game_state.py — GameState: the single source of truth for all game data.
All modules read from and write to this object through defined methods.
"""

import datetime
from core.config import ASSETS, BASE_RADAR_RANGE, LOG_TO_FILE, LOG_FILE
from defense.asset import DefendedAsset
from defense.interceptor import InterceptorManager
from simulation.physics import blast_damage


class GameState:
    """
    Central game state object. Passed to every module that needs
    to read or modify the state of the world.
    """

    def __init__(self):
        # Assets — build from config
        self.assets: dict[str, DefendedAsset] = {
            name: DefendedAsset(name, cfg)
            for name, cfg in ASSETS.items()
        }

        # Interceptors
        self.interceptors = InterceptorManager()

        # Active threats this wave
        self.threats: list = []

        # Wave tracking
        self.wave_number    = 0
        self.wave_active    = False

        # Event log for this wave (shown in message panel)
        self.event_log: list[str] = []

        # Cascade alert messages (shown prominently)
        self.cascade_alerts: list[str] = []

        # Intercept results this wave
        self.intercept_results: list[dict] = []

        # Game over state
        self.game_over      = False
        self.game_over_reason = ""

        # Computed capability state — updated each tick
        self._effective_radar_range     = BASE_RADAR_RANGE
        self._coordination_delay        = 0
        self._system_degradation        = 0.0
        self._airpower_available        = True

    # ── Radar & capability ─────────────────────────────────────────────────────

    def update_capabilities(self):
        """
        Recompute effective capabilities from all asset cascade effects.
        Called once per tick after damage is applied.
        """
        radar_mult      = 1.0
        coord_delay     = 0
        sys_degrad      = 0.0
        airpower        = True

        for asset in self.assets.values():
            fx = asset.cascade_effects
            if "radar_range_mult" in fx:
                radar_mult      = min(radar_mult, fx["radar_range_mult"])
            if "intercept_delay" in fx:
                coord_delay     = max(coord_delay, fx["intercept_delay"])
            if "system_degradation" in fx:
                sys_degrad      = max(sys_degrad, fx["system_degradation"])
            if "airpower_available" in fx:
                airpower        = fx["airpower_available"]

        self._effective_radar_range = BASE_RADAR_RANGE * radar_mult
        self._coordination_delay    = coord_delay
        self._system_degradation    = sys_degrad
        self._airpower_available    = airpower

    @property
    def effective_radar_range(self) -> float:
        return self._effective_radar_range

    @property
    def system_degradation(self) -> float:
        return self._system_degradation

    @property
    def airpower_available(self) -> bool:
        return self._airpower_available

    # ── Radar positions ────────────────────────────────────────────────────────

    def radar_positions(self) -> list:
        """Return positions of all non-destroyed radar assets."""
        return [
            a.pos for a in self.assets.values()
            if a.capability == "detection" and not a.is_destroyed
        ]

    # ── Threat management ──────────────────────────────────────────────────────

    def load_threats(self, threats: list):
        self.threats            = threats
        self.intercept_results  = []
        self.event_log          = []
        self.cascade_alerts     = []

    @property
    def active_threats(self) -> list:
        return [t for t in self.threats if t.is_active]

    @property
    def detected_threats(self) -> list:
        return [t for t in self.active_threats if t.detected]

    # ── Impact resolution ──────────────────────────────────────────────────────

    def resolve_impacts(self) -> list:
        """
        Check all threats that have impacted this tick.
        Apply blast damage to assets. Return list of impact event strings.
        """
        events = []
        for threat in self.threats:
            if not threat.impacted:
                continue
            if hasattr(threat, '_resolved'):
                continue
            threat._resolved = True

            # Calculate damage to each asset
            for asset in self.assets.values():
                dmg = blast_damage(
                    threat.impact_pos,
                    asset.pos,
                    threat.blast_radius,
                    threat.base_damage,
                )
                if dmg > 0:
                    messages = asset.apply_damage(dmg)
                    self.cascade_alerts.extend(messages)
                    events.append(
                        f"IMPACT: {threat.type_label} hit near "
                        f"{asset.name} — damage {dmg*100:.0f}%"
                    )

                    # Check critical asset destroyed
                    if asset.critical and asset.is_destroyed:
                        self.game_over        = True
                        self.game_over_reason = (
                            f"{asset.name} has been destroyed. "
                            f"Command authority lost."
                        )

        self.update_capabilities()
        return events

    # ── Scoring ────────────────────────────────────────────────────────────────

    def strategic_integrity_index(self) -> float:
        """
        Weighted integrity score across all assets. 0–100.
        """
        sii = sum(
            a.integrity * a.weight
            for a in self.assets.values()
        )
        return round(sii * 100, 1)

    def sii_label(self) -> str:
        from core.config import SII_THRESHOLDS
        sii = self.strategic_integrity_index()
        for threshold in sorted(SII_THRESHOLDS.keys(), reverse=True):
            if sii >= threshold:
                return SII_THRESHOLDS[threshold]
        return "TOTAL DEFEAT"

    # ── Capability collapse detection ──────────────────────────────────────────

    def is_capability_collapsed(self) -> bool:
        """
        True if the defensive situation is mathematically near-hopeless:
        radar gone AND coordination destroyed AND active threats remain.
        """
        radar_gone  = self._effective_radar_range < (BASE_RADAR_RANGE * 0.25)
        coord_gone  = self._coordination_delay >= 999
        has_threats = len(self.active_threats) > 0
        return radar_gone and coord_gone and has_threats

    def survival_probability(self) -> float:
        """
        Rough estimate of survival probability given current state.
        Used to warn player of near-hopeless situations.
        """
        base    = self.strategic_integrity_index() / 100.0
        radar_f = self._effective_radar_range / BASE_RADAR_RANGE
        coord_f = 1.0 if self._coordination_delay < 5 else 0.4
        return round(base * radar_f * coord_f * 100, 1)

    # ── Wave reset ─────────────────────────────────────────────────────────────

    def reset_for_wave(self, full_reset: bool = False):
        """
        Prepare for next wave. full_reset restores all assets (tutorial waves).
        """
        if full_reset:
            for asset in self.assets.values():
                asset.reset()
            self.interceptors.reset()

        self.threats            = []
        self.intercept_results  = []
        self.event_log          = []
        self.cascade_alerts     = []
        self.wave_active        = False
        self.update_capabilities()

    # ── Logging ────────────────────────────────────────────────────────────────

    def log(self, message: str):
        """Add a message to the wave event log and optionally write to file."""
        self.event_log.append(message)
        if len(self.event_log) > 50:
            self.event_log = self.event_log[-50:]

        if LOG_TO_FILE:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(LOG_FILE, "a") as f:
                f.write(f"[{ts}] WAVE {self.wave_number + 1} | {message}\n")

    def log_wave_marker(self, label: str):
        """Write a visible section marker to the log file."""
        if not LOG_TO_FILE:
            return
        ts      = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        border  = "─" * 60
        with open(LOG_FILE, "a") as f:
            f.write(f"\n{border}\n")
            f.write(f"[{ts}] {label}\n")
            f.write(f"{border}\n")
