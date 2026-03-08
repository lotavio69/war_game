"""
interceptor.py — Interceptor inventory and assignment management.
"""

import random
from core.config import INTERCEPTORS


class InterceptorBattery:
    """
    Manages inventory and firing for one interceptor type.
    Tracks reload state and computes intercept success probability.
    """

    def __init__(self, itype: str):
        cfg                 = INTERCEPTORS[itype]
        self.itype          = itype
        self.label          = cfg["label"]
        self.count          = cfg["count"]
        self.reload_time    = cfg["reload_time"]
        self.color          = cfg["color"]
        self._success_rates = {
            "icbm":   cfg["vs_icbm"],
            "cruise": cfg["vs_cruise"],
            "rocket": cfg["vs_rocket"],
            "drone":  cfg["vs_drone"],
        }
        self._reloading_until = 0.0     # sim time when next shot is available

    def available(self, sim_time: float) -> bool:
        return self.count > 0 and sim_time >= self._reloading_until

    def fire(self, threat, sim_time: float,
             system_degradation: float = 0.0) -> bool:
        """
        Attempt intercept. Returns True if successful.
        Consumes one interceptor and starts reload timer.
        system_degradation: 0.0–1.0 penalty from power loss cascade.
        """
        if not self.available(sim_time):
            return False

        self.count          -= 1
        self._reloading_until = sim_time + self.reload_time

        base_p  = self._success_rates.get(threat.weapon_type, 0.3)

        # Penalties
        if threat.in_terminal_phase():
            base_p *= 0.30      # nearly impossible in terminal phase

        base_p *= (1.0 - system_degradation)

        success = random.random() < base_p
        if success:
            threat.intercepted = True
        return success

    def success_probability(self, weapon_type: str,
                            in_terminal: bool = False,
                            system_degradation: float = 0.0) -> float:
        """Return display probability for the advisor UI."""
        p = self._success_rates.get(weapon_type, 0.3)
        if in_terminal:
            p *= 0.30
        p *= (1.0 - system_degradation)
        return round(p, 2)

    @property
    def reload_remaining(self) -> float:
        return max(0.0, self._reloading_until)

    def __repr__(self):
        return f"<Battery {self.label} x{self.count}>"


class InterceptorManager:
    """
    Holds all interceptor batteries and manages player assignments.
    """

    def __init__(self):
        self.batteries = {
            itype: InterceptorBattery(itype)
            for itype in INTERCEPTORS
        }
        # Pending assignments: threat_label -> interceptor_type
        self.assignments: dict = {}

    def assign(self, threat_label: str, itype: str) -> bool:
        """Assign an interceptor type to a threat. Returns False if invalid."""
        if itype not in self.batteries:
            return False
        self.assignments[threat_label] = itype
        return True

    def unassign(self, threat_label: str):
        self.assignments.pop(threat_label, None)

    def execute_assignments(self, threats: list, sim_time: float,
                             system_degradation: float = 0.0) -> list:
        """
        Fire all pending assignments. Returns list of result dicts.
        """
        results = []
        for threat in threats:
            if threat.label not in self.assignments:
                continue
            if not threat.is_active:
                self.assignments.pop(threat.label, None)
                continue

            itype   = self.assignments.pop(threat.label)
            battery = self.batteries.get(itype)
            if not battery:
                continue

            if battery.available(sim_time):
                success = battery.fire(threat, sim_time, system_degradation)
                results.append({
                    "threat":       threat.label,
                    "interceptor":  battery.label,
                    "success":      success,
                    "threat_type":  threat.type_label,
                    "target":       threat.target_name,
                })
            else:
                results.append({
                    "threat":       threat.label,
                    "interceptor":  battery.label,
                    "success":      False,
                    "error":        "RELOADING",
                    "threat_type":  threat.type_label,
                    "target":       threat.target_name,
                })
        return results

    def total_available(self) -> int:
        return sum(b.count for b in self.batteries.values())

    def reset(self):
        """Restore all interceptors to initial counts."""
        self.batteries = {
            itype: InterceptorBattery(itype)
            for itype in INTERCEPTORS
        }
        self.assignments = {}
