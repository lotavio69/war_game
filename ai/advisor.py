"""
advisor.py — ComputerAdvisor: stateless threat evaluator.
Takes game state, returns prioritized intercept recommendations.
The advisor never acts — it only advises.
"""

from core.config import INTERCEPTORS


class ComputerAdvisor:
    """
    Evaluates the current threat board and recommends optimal
    interceptor assignments using a multi-factor scoring function.

    Scoring formula:
        score = (target_value × urgency × intercept_payoff) / cost

    Where:
        target_value    = strategic weight of threatened asset
        urgency         = 1 / TTI  (imminent = higher score)
        intercept_payoff = success_probability for best interceptor
        cost            = interceptors_remaining (scarcity factor)
    """

    def __init__(self):
        pass   # stateless — no instance data needed

    def evaluate(self, game_state) -> list:
        """
        Return a list of recommendation dicts, sorted by priority score.
        Each dict: {threat, score, interceptor, probability, reasoning}
        """
        threats     = game_state.detected_threats
        batteries   = game_state.interceptors.batteries
        degradation = game_state.system_degradation
        recommendations = []

        for threat in threats:
            if threat.assigned_interceptor:
                continue    # already handled by player

            best_itype  = None
            best_prob   = 0.0

            # Find best available interceptor for this threat type
            for itype, battery in batteries.items():
                if battery.count == 0:
                    continue
                # Skip airborne if airport is gone
                if itype == "airborne" and not game_state.airpower_available:
                    continue

                prob = battery.success_probability(
                    threat.weapon_type,
                    threat.in_terminal_phase(),
                    degradation,
                )
                if prob > best_prob:
                    best_prob  = prob
                    best_itype = itype

            if best_itype is None:
                # No interceptors available — flag as undefendable
                recommendations.append({
                    "threat":       threat,
                    "score":        0.0,
                    "interceptor":  None,
                    "probability":  0.0,
                    "reasoning":    "NO INTERCEPTORS AVAILABLE",
                    "priority":     "UNDEFENDABLE",
                })
                continue

            # Compute score components
            from core.config import ASSETS
            target_val  = ASSETS.get(
                threat.target_name, {}
            ).get("weight", 0.1)

            tti         = max(threat.tti(), 1.0)
            urgency     = 1.0 / tti

            # Penalize terminal phase — waste of interceptor
            if threat.in_terminal_phase():
                urgency *= 0.2

            # Scarcity: spending interceptors when low is costly
            total_avail = game_state.interceptors.total_available()
            scarcity    = 1.0 + (1.0 / max(total_avail, 1))

            score = (target_val * urgency * best_prob) * scarcity

            # Build human-readable reasoning
            reasoning = self._build_reasoning(
                threat, target_val, tti, best_prob, total_avail
            )

            priority = self._priority_label(score, tti)

            recommendations.append({
                "threat":       threat,
                "score":        round(score * 1000, 2),
                "interceptor":  best_itype,
                "probability":  round(best_prob * 100),
                "reasoning":    reasoning,
                "priority":     priority,
            })

        # Sort by score descending
        recommendations.sort(key=lambda r: r["score"], reverse=True)

        # Flag top recommendation
        if recommendations:
            recommendations[0]["priority"] = "TOP PRIORITY"

        return recommendations

    def _build_reasoning(self, threat, target_val, tti,
                          prob, avail) -> str:
        parts = []
        if target_val >= 0.35:
            parts.append("HIGH-VALUE TARGET")
        if tti < 30:
            parts.append("IMMINENT")
        elif tti < 90:
            parts.append("URGENT")
        if prob >= 0.80:
            parts.append(f"HIGH intercept chance ({prob*100:.0f}%)")
        elif prob >= 0.50:
            parts.append(f"MODERATE chance ({prob*100:.0f}%)")
        else:
            parts.append(f"LOW chance ({prob*100:.0f}%) — consider skipping")
        if avail <= 3:
            parts.append("AMMO CRITICAL")
        return " | ".join(parts) if parts else "Standard threat"

    def _priority_label(self, score, tti) -> str:
        if tti < 15:
            return "!! TERMINAL"
        if score > 0.05:
            return "HIGH"
        if score > 0.01:
            return "MEDIUM"
        return "LOW"
