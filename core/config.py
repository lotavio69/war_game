"""
config.py — Central configuration for all game parameters.
Change game balance here without touching simulation logic.
"""

# ── Map ────────────────────────────────────────────────────────────────────────
MAP_RADIUS        = 100   # km — threats launch from beyond this radius
CITY_CENTER       = (0, 0)

# ── Simulation timing ──────────────────────────────────────────────────────────
TICK_SECONDS      = 1.0   # simulated seconds per game tick
REAL_TICK_MS      = 200   # milliseconds per tick in real time (5 ticks/sec)

# ── Defended assets ────────────────────────────────────────────────────────────
# Each asset: position (km), strategic weight, and what capability it provides
ASSETS = {
    "Presidential Palace": {
        "pos":              (0, 0),
        "weight":           0.40,
        "critical":         True,    # game over if destroyed
        "capability":       "command",
        "color":            "RED",
    },
    "Military HQ": {
        "pos":              (8, 5),
        "weight":           0.20,
        "critical":         False,
        "capability":       "coordination",
        "color":            "YELLOW",
    },
    "Radar Station Alpha": {
        "pos":              (-15, 10),
        "weight":           0.10,
        "critical":         False,
        "capability":       "detection",
        "color":            "CYAN",
    },
    "Radar Station Beta": {
        "pos":              (18, -8),
        "weight":           0.10,
        "critical":         False,
        "capability":       "detection",
        "color":            "CYAN",
    },
    "Airport": {
        "pos":              (12, -15),
        "weight":           0.10,
        "critical":         False,
        "capability":       "airpower",
        "color":            "GREEN",
    },
    "Power Station": {
        "pos":              (-10, -12),
        "weight":           0.10,
        "critical":         False,
        "capability":       "power",
        "color":            "MAGENTA",
    },
}

# ── Capability cascade thresholds ─────────────────────────────────────────────
# When asset integrity drops below these levels, effects are applied
CASCADE_THRESHOLDS = {
    "detection": {
        0.75: {"radar_range_mult": 0.80, "msg": "Radar coverage reduced to 80%"},
        0.50: {"radar_range_mult": 0.55, "msg": "Radar coverage severely degraded"},
        0.20: {"radar_range_mult": 0.20, "msg": "Radar near failure — massive blind spots"},
        0.00: {"radar_range_mult": 0.00, "msg": "Radar OFFLINE — flying blind"},
    },
    "coordination": {
        0.50: {"intercept_delay": 3,     "msg": "Command delays — +3s interceptor response"},
        0.20: {"intercept_delay": 8,     "msg": "Coordination critical — +8s response delay"},
        0.00: {"intercept_delay": 999,   "msg": "Military HQ DESTROYED — manual coordination only"},
    },
    "power": {
        0.50: {"system_degradation": 0.20, "msg": "Power degraded — all systems -20% efficiency"},
        0.00: {"system_degradation": 0.50, "msg": "Power OFFLINE — all systems -50% efficiency"},
    },
    "airpower": {
        0.00: {"airpower_available": False, "msg": "Airport DESTROYED — no airborne interceptors"},
    },
}

# ── Weapon profiles ────────────────────────────────────────────────────────────
WEAPONS = {
    "icbm": {
        "label":            "ICBM",
        "speed_kms":        7.0,          # km/s
        "detection_range":  80,           # km from radar
        "stealth_factor":   1.0,          # fully visible on radar
        "blast_radius":     8,            # km
        "base_damage":      0.95,         # integrity damage on direct hit
        "cep":              0.3,          # circular error probable (km)
        "terminal_phase":   15,           # seconds — window where interception is near-impossible
        "color":            "RED",
        "symbol":           "▼",
    },
    "cruise": {
        "label":            "Cruise Missile",
        "speed_kms":        0.25,
        "detection_range":  35,           # harder to detect — low altitude
        "stealth_factor":   0.65,
        "blast_radius":     3,
        "base_damage":      0.55,
        "cep":              0.05,
        "terminal_phase":   8,
        "color":            "YELLOW",
        "symbol":           "→",
    },
    "rocket": {
        "label":            "Short-Range Rocket",
        "speed_kms":        0.3,
        "detection_range":  50,
        "stealth_factor":   0.90,
        "blast_radius":     1.5,
        "base_damage":      0.30,
        "cep":              1.5,
        "terminal_phase":   5,
        "color":            "YELLOW",
        "symbol":           "↑",
    },
    "drone": {
        "label":            "Drone",
        "speed_kms":        0.04,
        "detection_range":  20,
        "stealth_factor":   0.25,         # hard to detect
        "blast_radius":     0.5,
        "base_damage":      0.20,
        "cep":              0.02,
        "terminal_phase":   3,
        "color":            "CYAN",
        "symbol":           "◆",
    },
}

# ── Interceptor profiles ───────────────────────────────────────────────────────
INTERCEPTORS = {
    "patriot": {
        "label":            "Patriot",
        "count":            6,
        "vs_icbm":          0.75,
        "vs_cruise":        0.85,
        "vs_rocket":        0.70,
        "vs_drone":         0.40,
        "reload_time":      15,           # seconds between shots
        "color":            "GREEN",
    },
    "iron_dome": {
        "label":            "Iron Dome",
        "count":            12,
        "vs_icbm":          0.10,
        "vs_cruise":        0.65,
        "vs_rocket":        0.90,
        "vs_drone":         0.80,
        "reload_time":      5,
        "color":            "CYAN",
    },
    "airborne": {
        "label":            "Airborne",
        "count":            4,
        "vs_icbm":          0.30,
        "vs_cruise":        0.90,
        "vs_rocket":        0.45,
        "vs_drone":         0.85,
        "reload_time":      45,
        "color":            "MAGENTA",
    },
}

# ── Base radar range (km) — modified by cascade effects ───────────────────────
BASE_RADAR_RANGE  = 60

# ── Wave definitions ──────────────────────────────────────────────────────────
# Each wave: min/max threats, allowed weapon types, stagger range (seconds)
WAVES = [
    {   # Wave 1 — tutorial
        "description":  "Single rocket attack — learn the basics",
        "threats":      (1, 2),
        "weapons":      ["rocket"],
        "stagger":      (0, 10),
        "reset":        True,
    },
    {   # Wave 2 — introduce cruise
        "description":  "Mixed rocket and cruise missile attack",
        "threats":      (2, 4),
        "weapons":      ["rocket", "rocket", "cruise"],
        "stagger":      (0, 20),
        "reset":        True,
    },
    {   # Wave 3 — introduce ICBM
        "description":  "ICBM strike with rocket cover",
        "threats":      (3, 5),
        "weapons":      ["icbm", "rocket", "cruise"],
        "stagger":      (0, 30),
        "reset":        True,
    },
    {   # Wave 4 — introduce drones
        "description":  "Drone swarm with missile support",
        "threats":      (5, 8),
        "weapons":      ["drone", "drone", "drone", "rocket", "cruise"],
        "stagger":      (0, 40),
        "reset":        False,   # no reset — damage carries over
    },
    {   # Wave 5+ — full chaos, escalating
        "description":  "Coordinated multi-vector assault",
        "threats":      (6, 12),
        "weapons":      ["icbm", "cruise", "cruise", "rocket", "rocket",
                         "rocket", "drone", "drone"],
        "stagger":      (0, 60),
        "reset":        False,
    },
]

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_TO_FILE       = True
LOG_FILE          = "game.log"
SII_THRESHOLDS = {
    80: "DECISIVE VICTORY",
    60: "TACTICAL VICTORY",
    40: "PYRRHIC SURVIVAL",
    20: "STRATEGIC DEFEAT",
     0: "TOTAL DEFEAT",
}
