"""
physics.py — Geometric and trajectory calculations.
All spatial math lives here; nothing else does coordinate arithmetic.
"""

import math
import random


def distance(pos_a: tuple, pos_b: tuple) -> float:
    """Euclidean distance between two (x, y) positions in km."""
    return math.sqrt((pos_a[0] - pos_b[0])**2 + (pos_a[1] - pos_b[1])**2)


def direction_vector(from_pos: tuple, to_pos: tuple) -> tuple:
    """
    Unit vector pointing from from_pos toward to_pos.
    Returns (dx, dy) each in range [-1, 1].
    """
    dist = distance(from_pos, to_pos)
    if dist == 0:
        return (0.0, 0.0)
    return (
        (to_pos[0] - from_pos[0]) / dist,
        (to_pos[1] - from_pos[1]) / dist,
    )


def move_toward(pos: tuple, target: tuple, speed_kms: float, dt: float) -> tuple:
    """
    Move pos toward target at speed (km/s) over dt seconds.
    Returns new position. Will not overshoot.
    """
    step    = speed_kms * dt
    dist    = distance(pos, target)
    if dist <= step:
        return target                   # arrived
    dx, dy  = direction_vector(pos, target)
    return (pos[0] + dx * step, pos[1] + dy * step)


def apply_cep(target_pos: tuple, cep_km: float) -> tuple:
    """
    Apply circular error probable to a target position.
    Returns the actual impact point — offset from intended target
    by a random amount with 50% chance of landing within cep_km.
    Uses Rayleigh distribution to model real CEP behavior.
    """
    # Rayleigh sigma from CEP: sigma = CEP / sqrt(ln(4))
    sigma   = cep_km / math.sqrt(math.log(4))
    offset  = random.gauss(0, sigma)
    angle   = random.uniform(0, 2 * math.pi)
    return (
        target_pos[0] + offset * math.cos(angle),
        target_pos[1] + offset * math.sin(angle),
    )


def launch_position(map_radius: float) -> tuple:
    """
    Generate a random launch point on the perimeter of the map.
    Threats always originate outside the defended area.
    """
    angle = random.uniform(0, 2 * math.pi)
    # Launch from just outside the map radius
    r     = map_radius * random.uniform(1.05, 1.30)
    return (r * math.cos(angle), r * math.sin(angle))


def time_to_impact(pos: tuple, target: tuple, speed_kms: float) -> float:
    """Estimated seconds until threat reaches target from current position."""
    dist = distance(pos, target)
    if speed_kms <= 0:
        return float('inf')
    return dist / speed_kms


def in_radar_range(threat_pos: tuple, radar_pos: tuple, radar_range: float) -> bool:
    """True if threat is within radar detection range."""
    return distance(threat_pos, radar_pos) <= radar_range


def blast_damage(impact_pos: tuple, asset_pos: tuple,
                 blast_radius: float, base_damage: float) -> float:
    """
    Calculate damage to an asset from a nearby impact.
    Damage falls off linearly from base_damage at ground zero
    to 0 at blast_radius.
    """
    dist = distance(impact_pos, asset_pos)
    if dist >= blast_radius:
        return 0.0
    falloff = 1.0 - (dist / blast_radius)
    return base_damage * falloff
