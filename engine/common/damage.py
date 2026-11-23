"""Damage-pipeline pieces that are identical across classes (damage reduction, crit/min-max averaging, attack speed)."""


def attack_value(flat_attack, attack_pct):
    """ATTACK = Flat ATTACK x (1 + ATTACK%/100) (Inputs!B31)."""
    return flat_attack * (1 + attack_pct / 100)


def defense_reduction(monster_defense, def_pen):
    """Damage multiplier of the monster's defense after Defense Penetration."""
    return 5000 / (6000 + monster_defense * (1 - def_pen / 100))


def expected_hit(base_hit, min_damage, max_damage, crit_rate, crit_damage):
    """Expected damage of one hit: min/max damage spread averaged, then crit (rate capped at 100%) averaged in."""
    non_crit_min = base_hit * min(min_damage, max_damage) / 100
    non_crit_max = base_hit * max_damage / 100
    non_crit_avg = (non_crit_min + non_crit_max) / 2
    crit_avg = non_crit_avg * (1 + crit_damage / 100)
    cr = min(crit_rate, 100) / 100
    return non_crit_avg * (1 - cr) + crit_avg * cr


def actions_per_second(attack_speed_base, as_bonus):
    """Actions per second from base Attack Speed% and the live Attack-Speed buff bonus (150% combined cap)."""
    return 1 + min(150, 150 * (1 - (1 - attack_speed_base / 150) * (1 - as_bonus / 150))) / 100


def q_roll(chance, n_enemies):
    """Probability that at least one of ``n_enemies`` independent rolls of ``chance`` succeeds (proc chances roll once per attack
    per enemy hit, user 2026-11-04); with an ICD only 'at least one success' matters."""
    return 1 - (1 - chance) ** n_enemies
