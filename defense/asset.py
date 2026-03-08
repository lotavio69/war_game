"""
asset.py — DefendedAsset class.
Tracks integrity, applies damage, triggers cascade effects.
"""

from core.config import CASCADE_THRESHOLDS


class DefendedAsset:
    """
    Represents a single defended installation.
    Tracks structural integrity and the downstream capability
    effects that cascade from damage.
    """

    def __init__(self, name: str, config: dict):
        self.name           = name
        self.pos            = config["pos"]
        self.weight         = config["weight"]
        self.critical       = config["critical"]
        self.capability     = config["capability"]
        self.color          = config["color"]

        self.integrity      = 1.0        # 1.0 = fully intact, 0.0 = destroyed
        self._prev_integrity = 1.0       # to detect threshold crossings

        # Active cascade effects — updated when integrity changes
        self.cascade_effects = {}
        self.cascade_messages = []       # messages to show player on damage

    # ── Damage ────────────────────────────────────────────────────────────────

    def apply_damage(self, amount: float) -> list:
        """
        Reduce integrity by amount. Returns list of cascade
        messages triggered by crossing thresholds.
        """
        if self.integrity <= 0:
            return []

        self.integrity      = max(0.0, self.integrity - amount)
        messages            = self._check_cascades()
        self._prev_integrity = self.integrity
        return messages

    def _check_cascades(self) -> list:
        """
        Check if any cascade thresholds were crossed since last update.
        Returns newly triggered cascade messages.
        """
        triggered = []
        thresholds = CASCADE_THRESHOLDS.get(self.capability, {})

        for threshold, effects in sorted(thresholds.items(), reverse=True):
            crossed = (self._prev_integrity > threshold >= self.integrity)
            if crossed:
                self.cascade_effects.update(
                    {k: v for k, v in effects.items() if k != "msg"}
                )
                triggered.append(
                    f"!! {self.name.upper()} — {effects['msg']}"
                )
        return triggered

    def reset(self):
        """Restore to full integrity (used for tutorial waves)."""
        self.integrity       = 1.0
        self._prev_integrity = 1.0
        self.cascade_effects = {}
        self.cascade_messages = []

    # ── Display helpers ───────────────────────────────────────────────────────

    @property
    def integrity_pct(self) -> int:
        return int(self.integrity * 100)

    @property
    def is_destroyed(self) -> bool:
        return self.integrity <= 0.0

    @property
    def status_label(self) -> str:
        if self.integrity >= 0.80:
            return "INTACT"
        elif self.integrity >= 0.50:
            return "DAMAGED"
        elif self.integrity >= 0.20:
            return "CRITICAL"
        elif self.integrity > 0:
            return "FAILING"
        return "DESTROYED"

    def integrity_bar(self, width: int = 10) -> str:
        """ASCII progress bar for integrity."""
        filled = int(self.integrity * width)
        empty  = width - filled
        return "█" * filled + "░" * empty

    def __repr__(self):
        return f"<Asset {self.name} {self.integrity_pct}%>"
