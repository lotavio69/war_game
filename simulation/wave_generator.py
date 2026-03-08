"""
wave_generator.py — Builds waves of threats with escalating complexity.
"""

import random
from simulation.threat import Threat
from simulation.physics import launch_position
from core.config import WAVES, ASSETS, MAP_RADIUS


class WaveGenerator:
    """
    Generates waves of Threat objects according to the wave
    configuration in config.py. Each wave escalates in complexity.
    """

    def __init__(self, seed: int = None):
        if seed is not None:
            random.seed(seed)

    def generate(self, wave_index: int) -> list:
        """
        Build and return a list of Threat objects for the given wave.
        wave_index 0 = first wave (tutorial), escalates from there.
        """
        # Clamp to last defined wave for waves beyond config
        cfg_index   = min(wave_index, len(WAVES) - 1)
        wave_cfg    = WAVES[cfg_index]

        # Number of threats this wave
        min_t, max_t = wave_cfg["threats"]
        # Extra threats for waves beyond the defined set
        bonus        = max(0, wave_index - (len(WAVES) - 1))
        num_threats  = random.randint(min_t, max_t) + bonus

        weapon_pool  = wave_cfg["weapons"]
        stagger_min, stagger_max = wave_cfg["stagger"]

        threats = []
        Threat.reset_counter()

        # Build target list — weighted toward higher-value targets
        target_names = list(ASSETS.keys())
        target_weights = [ASSETS[t]["weight"] for t in target_names]

        for _ in range(num_threats):
            weapon_type = random.choice(weapon_pool)

            # Weighted target selection
            target_name = random.choices(target_names, weights=target_weights, k=1)[0]
            target_pos  = ASSETS[target_name]["pos"]

            # Launch from random perimeter point
            start_pos   = launch_position(MAP_RADIUS)

            # Stagger launch times so not everything arrives simultaneously
            launch_delay = random.uniform(stagger_min, stagger_max)

            threat = Threat(
                weapon_type  = weapon_type,
                start_pos    = start_pos,
                target_name  = target_name,
                target_pos   = target_pos,
                launch_delay = launch_delay,
            )
            threats.append(threat)

        # Sort by launch delay so early threats are first in list
        threats.sort(key=lambda t: t.launch_delay)
        return threats

    def is_reset_wave(self, wave_index: int) -> bool:
        """True if this wave resets city damage (early tutorial waves)."""
        cfg_index = min(wave_index, len(WAVES) - 1)
        return WAVES[cfg_index].get("reset", False)

    def wave_description(self, wave_index: int) -> str:
        cfg_index = min(wave_index, len(WAVES) - 1)
        base = WAVES[cfg_index]["description"]
        if wave_index >= len(WAVES):
            extra = wave_index - len(WAVES) + 1
            return f"{base} [+{extra} extra threats]"
        return base
