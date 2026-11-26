"""Artifact EQUIP effects (up to 5 equipped slots, star 0-5, Legendary artifacts 0-7 since the 2026-11-26 patch; the workbooks have 4 slots and 6 stars) exactly as the workbook wires them - a port of the ~32 ``artifact_*_expr()``
generators of ``src/build_fp_mage_workbook.py`` (byte-identical in the 12 builders) and of the aggregate rows of its Artifacts sheet.

What an artifact can do in the workbook (and so here):

* REAL, live: contributes a value that the damage pipeline reads (Attack% / Final Damage / Damage / Skill & Basic Attack Damage / Crit Rate /
  Crit Damage / Boss & Normal Monster Damage / enemy damage taken buckets, branch-only Final Damage, Reindeer's Spear's boss/PvP defence
  correction, Contract of Darkness' boss crit rate, Soul Contract's cooldown decrease, Horn Flute through the companion's ``horn_uptime``).
* REFERENCE-only ("baked into Inputs" convention): the user enters the artifact's stat in the Inputs sheet by hand (Book of Ancient, Athena's
  Gloves, Clear Spring Water, Soul Pouch, Lit Lamp, Star Rock, Cursed Doll, Shamaness Marble, Reindeer's Spear's base Defense Penetration,
  Bottle of Emotion's Final Damage) - equipping contributes NOTHING to the live DPS, the value is only reported (``reference_only``).
* NO DPS EFFECT (a fact, not missing data; ``data.artifacts.ARTIFACT_NO_DPS_EFFECT`` gives the reason): their stat is one the model does not
  use or their content is not modelled (Pink Bean's Giant Rib, Horntail's Scale, Zakum's Stone Piece: raid content; Ancient Text Piece: Guild
  Conquest; Lunar Dew, Mushmom's Cap, Pig's Ribbon: stats the model does not use).
* Arwen's Glass Shoes is LIVE: it adds Companion Summoning Time Increase % (``summon_time_inc_pct``; star 0 = 20, star 5 = 40 user-confirmed,
  linear steps 20..40 by star, user-confirmed) to the Inputs value wherever the companion model reads it.

Star semantics (workbook): star index 0..5 (5 = maximum tier); "Not Unlocked" resolves to star 0 (the equip effect then still applies
at the star-0 value).  The same artifact in two slots is equipped once.

Every function takes plain numbers and mirrors the operation order of the Excel generators; it needs NO workbook.
"""
import math

from .data import artifacts as AD
from .data import artifacts_extra as AX

NONE_LABEL = "(none)"
MAX_SLOTS = 5          # the game gained a 5th artifact slot (2026-11-23).  The workbooks keep 4 slot rows: with 5 equipped the engine composes the verified
#                        per-artifact effects itself (same buckets, same formulas, nothing slot-specific) - not verifiable against Excel (KNOWN_GAPS "Fifth artifact slot")
WORKBOOK_SLOTS = 4     # what the workbooks / golden tests can check
WORKBOOK_MAX_STAR = 5  # the workbooks' star tiers 0..5 (every golden compares at most star 5)
LEGENDARY_MAX_STAR = 7  # patch 2026-11-26: Legendary artifacts reach Awakening Stage 7 (inventory and on-equip effects keep growing at stages 6 and 7)
STAR_OPTIONS = ["Not Unlocked"] + list(range(LEGENDARY_MAX_STAR + 1))      # the superset; an artifact's own limit is ``max_star(key)``
LABEL_TO_KEY = {label: key for key, label in AD.ARTIFACT_LABELS.items()}

# artifacts whose stat is entered by hand in Inputs (see module docstring): equipping changes nothing live
REFERENCE_ONLY = ["book_of_ancient", "athena_gloves", "clear_spring_water", "soul_pouch", "lit_lamp", "star_rock", "cursed_doll",
                  "shamaness_marble", "bottle_of_emotion"]    # (+ Reindeer's Spear's base def pen, Bottle's Attack% IS live)
NO_DPS_EFFECT = list(AD.ARTIFACT_NO_DPS_EFFECT)      # id -> reason in AD.ARTIFACT_NO_DPS_EFFECT
ZERO_ARTIFACTS = NO_DPS_EFFECT                        # old name


def sv(key, star):
    """Star-tier value (CHOOSE(star+1, v0..v5)); stars 6 and 7 (Legendary artifacts, patch 2026-11-26) continue the straight line: every star adds the same step
    (user, 2026-11-26: "every star gives 20 % of the base value"; all tables are exactly ``v0 x (1 + 0.2 x star)``, checked by ``tests/golden/test_patch_2026_11_26.py``)."""
    values = AD.ARTIFACT_STAR_VALUES[key]
    if star < len(values):
        return values[star]
    return values[0] + (values[-1] - values[0]) * star / (len(values) - 1)


def max_star(key):
    """Highest Star Level of an artifact: 7 for Legendary, 5 otherwise."""
    return LEGENDARY_MAX_STAR if AD.ARTIFACT_RANK[key] == "Legendary" else WORKBOOK_MAX_STAR


def default_star(key):
    """The workbook's default Star Level of an artifact by rank (Epic 5, Unique 3, Legendary 'Not Unlocked')."""
    return AD.ARTIFACT_RANK_DEFAULT_STAR[AD.ARTIFACT_RANK[key]]


# ----------------------------------------------------------------------------------------------------------------------
# slots
# ----------------------------------------------------------------------------------------------------------------------
def resolve_slots(artifacts):
    """``[{"key": <id or name>, "star": 0..max_star | None | "Not Unlocked"}, ...]`` -> ``{artifact id: star}`` (equipped artifacts only, in slot
    order).  A (none) / blank slot is skipped; the same artifact twice is equipped once (first entry's star wins, like the workbook's one
    star per artifact)."""
    out = {}
    slots = [a for a in (artifacts or []) if a is not None]
    if len(slots) > MAX_SLOTS:
        raise ValueError(f"at most {MAX_SLOTS} artifact slots (got {len(slots)})")
    for a in slots:
        key = a.get("key") if isinstance(a, dict) else a
        if key in (None, "", NONE_LABEL):
            continue
        key = LABEL_TO_KEY.get(key, key)
        if key not in AD.ARTIFACT_LABELS:
            raise ValueError(f"unknown artifact {key!r}")
        star = a.get("star") if isinstance(a, dict) else None
        if star is None or star == "Not Unlocked":
            star = 0
        star = int(star)
        if not 0 <= star <= max_star(key):
            raise ValueError(f"artifact {key!r}: star must be 0..{max_star(key)} (got {star})")
        out.setdefault(key, star)
    return out


def effect_kind(key):
    """'reference_only' | 'no_dps_effect' | 'live' (what equipping the artifact does to the live DPS)."""
    return "reference_only" if key in REFERENCE_ONLY else "no_dps_effect" if key in AD.ARTIFACT_NO_DPS_EFFECT else "live"


def summon_time_inc_pct(eq):
    """Arwen's Glass Shoes: Companion Summoning Time Increase % added to the Inputs value (0 when not equipped).  Star 0 = 20, star 5 = 40
    (user-confirmed 2026-11-19, as are the linear steps in between: ``ARTIFACT_STAR_VALUES`` in the builder)."""
    return sv("arwens_glass_shoes_summon_time_increase_pct", eq["arwens_glass_shoes"]) if "arwens_glass_shoes" in eq else 0


def soul_contract_pct(eq, content_type):
    """Soul Contract: Skill Cooldown Decrease %, Chapter Hunt only; the workbook multiplies EVERY row's effective cooldown by (1 - pct/100)
    after the usual flat-seconds Cooldown Decrease and its 0.1 s floor (``Fight.cd_extra_pct``)."""
    return sv("soul_contract_cooldown_decrease_pct", eq["soul_contract"]) if ("soul_contract" in eq and content_type == "Chapter Hunt") else 0


# ----------------------------------------------------------------------------------------------------------------------
# context
# ----------------------------------------------------------------------------------------------------------------------
class Ctx:
    """The numbers the artifact effects read from the rest of the model."""

    __slots__ = ("content_type", "monster_type", "fight_duration", "pvp_len", "fixed_duration_active", "aps", "startup",
                 "crit_rate", "attack_speed", "horn_uptime")

    def __init__(self, content_type, monster_type, fight_duration, pvp_len, fixed_duration_active, aps=0.0, startup=0.0, crit_rate=0.0,
                 attack_speed=0.0, horn_uptime=0.0):
        self.content_type = content_type
        self.monster_type = monster_type
        self.fight_duration = fight_duration            # the Inputs "Fixed Fight Duration" (0 = steady state and PvP)
        self.pvp_len = pvp_len
        self.fixed_duration_active = fixed_duration_active
        self.aps = aps                                  # Summary Actions Per Second
        self.startup = startup                          # Summary Buff-Casting Startup Delay (0 when the timeline engine is on)
        self.crit_rate = crit_rate                      # Inputs Crit Rate (raw, before artifact sources)
        self.attack_speed = attack_speed                # Inputs Attack Speed (base)
        self.horn_uptime = horn_uptime

    @property
    def pvp(self):
        return self.monster_type == "pvp"

    @property
    def eff_d(self):
        """IF(pvp, PvP fight length, fight duration)."""
        return self.pvp_len if self.pvp else self.fight_duration

    @property
    def steady(self):
        return (not self.pvp) and self.fight_duration == 0


# ----------------------------------------------------------------------------------------------------------------------
# time-dependent shapes (ports of the artifact_*_expr generators)
# ----------------------------------------------------------------------------------------------------------------------
def hexagon_avg_stacks(c):
    """One-time battle-start ramp: 0 stacks for 20 s, +1 every 20 s, capped at 3 (steady state = 3)."""
    eff_d = c.eff_d
    if c.steady:
        return 3
    if eff_d <= 20:
        return 0
    if eff_d <= 40:
        return (eff_d - 20) / eff_d
    if eff_d <= 60:
        return (2 * eff_d - 60) / eff_d
    return (3 * eff_d - 120) / eff_d


def charm_uptime(c):
    """Charm of the Undead: first active at t = 10 s, then 5 s on every 10 s; steady state = the 50% duty cycle."""
    eff_d = c.eff_d
    if c.steady:
        return 0.5
    dprime = max(0, eff_d - 10)
    full_cycles = math.floor(dprime / 10)
    remainder = dprime - 10 * full_cycles
    active = 5 * full_cycles + min(remainder, 5)
    return active / eff_d


def roc_startup_uptime(c):
    """Ring of Cycles starts 5 s into the fight; the first ``startup`` s are buff casting anyway, so only [startup, D] counts."""
    if c.steady:
        return 1
    eff_d = c.eff_d
    if eff_d - c.startup <= 0:
        return 1
    return max(0, eff_d - max(5, c.startup)) / (eff_d - c.startup)


def rainbow_uptime(c):
    """Rainbow-colored Snail Shell: the first 15 s of the fight (fixed-duration / PvP content only)."""
    if c.pvp:
        return min(15, c.pvp_len) / c.pvp_len
    if c.fixed_duration_active:
        return min(15, c.fight_duration) / c.fight_duration
    return 0


def old_music_box_uptime(content_type):
    """Content-type uptime assumption: never in Chapter Hunt / Breakthrough / the five Growth Dungeons, always in World Boss / PvP, 60/70 in
    Chapter Boss."""
    if content_type in ("Chapter Hunt", "Breakthrough") or content_type in AD.GROWTH_DUNGEON_CONTENT_TYPES:
        return 0
    if content_type in ("World Boss", "PvP"):
        return 1
    if content_type == "Chapter Boss":
        return 60 / 70
    return 0


def boss_appear_time(content_type):
    return 20 if content_type == "Breakthrough" else (30 if content_type == "Hero Dungeon" else 0)


def chalice_uptimes(c):
    """(normal-branch uptime, boss-branch uptime) of Chalice's 30 s Final Damage window at the END of the fight (steady state: a per-kill
    proc chance at an assumed kill rate)."""
    t = c.fight_duration
    appear = boss_appear_time(c.content_type)
    normal_phase_end = appear if c.monster_type == "breakthrough" else t
    activation_start = max(0, t - 30)
    if c.monster_type == "normal" and t == 0:
        normal_uptime = 1 - (1 - AD.CHALICE_PROC_CHANCE) ** (AD.CHALICE_KILLS_PER_MINUTE * 30 / 60)
    elif t == 0 or normal_phase_end == 0:
        normal_uptime = 0
    else:
        normal_uptime = max(0, normal_phase_end - activation_start) / normal_phase_end
    boss_window = t - normal_phase_end
    boss_uptime = 0 if boss_window == 0 else max(0, t - max(activation_start, normal_phase_end)) / boss_window
    return normal_uptime, boss_uptime


def peach_uptime(aps):
    """Poisson-refreshed fixed 5 s window: 1 - exp(-lambda * 5), lambda = 0.2 x actions per second."""
    lam = 0.2 * aps
    return 1 - math.exp(-lam * 5)


def sealed_bottle_stacks(c):
    """Sealed Bottle (patch 2026-11-26): every enemy the player or the companion defeats adds a stack (+1 % Normal, +2 % Boss Monster Damage), up to 10 (30 in
    Chapter Breakthrough).  ``(average stacks in the normal-monster branch, stacks in the boss branch)``: continuous hunting fills the 10 stacks within seconds
    (the Chalice kill rate, ``CHALICE_KILLS_PER_MINUTE``); Breakthrough / Hero Dungeon kill their normal monsters first (the boss appears at ``boss_appear_time``): the
    normal phase ramps from 0 at that kill rate, the boss phase starts with whatever was collected; boss-only content and PvP defeat nobody: no stacks."""
    if c.monster_type == "normal":
        return float(AX.SEALED_BOTTLE_STACKS), float(AX.SEALED_BOTTLE_STACKS)
    if c.monster_type == "breakthrough":
        cap = AX.SEALED_BOTTLE_STACKS_BREAKTHROUGH if c.content_type == "Breakthrough" else AX.SEALED_BOTTLE_STACKS
        appear = boss_appear_time(c.content_type)
        k = AD.CHALICE_KILLS_PER_MINUTE / 60
        reach = cap / k                                           # seconds until the stacks are full
        avg = k * appear / 2 if appear <= reach else (cap * reach / 2 + cap * (appear - reach)) / appear
        return avg, min(float(cap), k * appear)
    return 0.0, 0.0


def silver_avg_stacks(aps):
    """M/M/5/5 Erlang-loss mean stack count, offered load rho = 0.15 x aps x 5."""
    rho = 0.15 * aps * 5
    weights = [rho ** n / f for n, f in enumerate([1, 1, 2, 6, 24, 120])]
    wsum = weights[0] + weights[1] + weights[2] + weights[3] + weights[4] + weights[5]
    weighted = 0 * weights[0] + 1 * weights[1] + 2 * weights[2] + 3 * weights[3] + 4 * weights[4] + 5 * weights[5]
    return weighted / wsum


# ----------------------------------------------------------------------------------------------------------------------
# damage-weight vector (shared by Horn Flute's uptime and the companion snapshot): act x hexagon x (1 + Attack%) x status multiplier
# ----------------------------------------------------------------------------------------------------------------------
NB_MAX = 75


def damage_weights(fight_duration, hex_v, a0, charm_v, mult=None, nb_max=NB_MAX):
    """``dw`` column of the timeline strip: ``act_i x hexf_i x (1 + (A0 + charm_i)/100) x mult_i`` (mult only while the timeline engine is on,
    else 1) over 1-second bins; ``act_i`` = share of the bin inside the fight."""
    out = []
    for i in range(nb_max):
        act = max(0.0, min(1.0, fight_duration - i))
        hexf = 1 + hex_v * min(3, i // 20) / 100
        charm = charm_v if (i >= 10 and (i - 10) % 10 < 5) else 0.0
        m = mult[i] if (mult is not None and i < len(mult)) else 1.0
        out.append(act * hexf * (1 + (a0 + charm) / 100) * m)
    return out


def horn_flute_uptime(c, dw, s0, w0, d, period, time_window):
    """``Companion!horn_uptime``: the share of the player's boss DAMAGE dealt while the summoned companion is out (candidate-0 timing).
    Steady state: min(1, D/period); otherwise sum(dw x overlap)/sum(dw), falling back to the time share when there is no fixed fight length.
    ``w0`` is the companion window of candidate 0 (0 when no companion is chosen - the workbook's W_0 is 0 then, so the damage-weighted
    share is 0 too).  ``time_window`` = max(0, min(D, Tend_0 - s0)) of the workbook's time-share fallback."""
    if c.steady:
        return min(1, d / period)
    total = sum(dw)
    if total > 0:
        num = 0.0
        end = s0 + w0
        for i, w in enumerate(dw):
            ov = max(0.0, min(i + 1, end) - max(i, s0))
            num += w * ov
        return num / total
    return min(1, time_window / period)


def phase_state_ratios(content_type, fight_duration, hex_v, hex_avg, bucket_avg, charm_v, charm_avg):
    """(boss-phase factor, normal-phase factor) for contents whose normal-monster phase comes first (Breakthrough: boss at 20 s; Hero Dungeon:
    30 s).  The averaged model uses the fight-average Hexagon stacks and Charm duty; each phase has its own: Hexagon adds a stack every 20 s,
    Charm is up 5 s of every 10 s from second 10.  factor = (state of that phase)/(fight average), applied to every damage row of that branch;
    both are 1 where there is no phase split or neither artifact is equipped (``phase_state_ratios`` of the builder)."""
    tb0 = boss_appear_time(content_type)
    if tb0 <= 0 or (hex_v == 0 and charm_v == 0):
        return 1.0, 1.0

    def stacks(a, b):
        return (max(0, b - max(a, 20)) + max(0, b - max(a, 40)) + max(0, b - max(a, 60))) / (b - a)

    def charm_on(t):
        x = max(0, t - 10)
        return 5 * math.floor(x / 10) + min(5, x - 10 * math.floor(x / 10))

    def ratio(a, b):
        hex_ratio = (1 + hex_v * stacks(a, b) / 100) / (1 + hex_avg / 100)
        duty = (charm_on(b) - charm_on(a)) / (b - a)
        atk_ratio = (1 + (bucket_avg - charm_avg + charm_v * duty) / 100) / (1 + bucket_avg / 100)
        return hex_ratio * atk_ratio
    return ratio(tb0, fight_duration), ratio(0, tb0)


# ----------------------------------------------------------------------------------------------------------------------
# early (pre-engine) quantities: what the timeline strip and the companion snapshot need before the damage rows exist
# ----------------------------------------------------------------------------------------------------------------------
class Pre:
    """Attack% bucket, Hexagon Necklace and Charm of the Undead - the artifact inputs of the timeline strip (A0, hex_v, charm_v, hex_avg)."""

    def __init__(self, eq, c):
        def on(k):
            return k in eq

        def val(k, key):
            return sv(key, eq[k])
        self.omb = val("old_music_box", "old_music_box_attack_pct") * old_music_box_uptime(c.content_type) if on("old_music_box") else 0
        self.secret_map_attack = val("secret_map", "secret_map_attack_pct") if on("secret_map") else 0
        self.reindeer_attack = val("reindeer_spear", "reindeer_spear_attack_pct") if on("reindeer_spear") else 0
        self.alliance = val("alliance_badge", "alliance_badge_attack_pct") if on("alliance_badge") else 0
        self.bottle_attack = val("bottle_of_emotion", "bottle_of_emotion_attack_pct") if on("bottle_of_emotion") else 0
        self.shiny_watch_attack = val("shiny_watch", "shiny_watch_attack_pct") if on("shiny_watch") else 0                  # (patch 2026-11-26)
        self.mummydog_attack = val("mummydogs_bandages", "mummydogs_bandages_attack_pct") if on("mummydogs_bandages") else 0   # (HP assumed to stay above 50 %)
        self.charm_val = val("charm_of_the_undead", "charm_of_the_undead_attack_pct") if on("charm_of_the_undead") else 0   # full value while active
        self.charm_avg = self.charm_val * charm_uptime(c) if on("charm_of_the_undead") else 0                                # fight average
        # AGG_ATTACK_PCT sums in this order (Artifacts sheet)
        self.agg_attack_pct = (self.omb + self.secret_map_attack + self.reindeer_attack + self.alliance + self.bottle_attack + self.charm_avg
                               + self.shiny_watch_attack + self.mummydog_attack)
        self.hex_v = val("hexagon_necklace", "hexagon_necklace_damage") if on("hexagon_necklace") else 0                       # per stack
        self.hex_avg = self.hex_v * hexagon_avg_stacks(c) if on("hexagon_necklace") else 0
        self.a0 = self.agg_attack_pct - self.charm_avg                                    # strip A0: the Attack% bucket without Charm


# ----------------------------------------------------------------------------------------------------------------------
# full effects
# ----------------------------------------------------------------------------------------------------------------------
class Effects:
    """All equip effects for one setup.  ``rows`` mirrors the named rows of the Artifacts sheet; the AGG_* attributes its bucket totals."""

    def __init__(self, eq, c, pre=None):
        self.equipped = dict(eq)
        pre = pre or Pre(eq, c)
        self.pre = pre

        def on(k):
            return k in eq

        def val(k, key):
            return sv(key, eq[k])
        rows = {}
        self.rows = rows
        pvp = c.pvp
        ct = c.content_type

        # ---- Rainbow-colored Snail Shell, Ring of Cycles (Crit Rate), Book of Ancient (reference), Icy Soul Rock ----
        ru = rainbow_uptime(c)
        rows["rainbow_crit_rate"] = val("rainbow_snail_shell", "rainbow_snail_shell_crit_rate") * ru if on("rainbow_snail_shell") else 0
        rows["rainbow_crit_damage"] = val("rainbow_snail_shell", "rainbow_snail_shell_crit_damage") * ru if on("rainbow_snail_shell") else 0
        rows["icy_soul_rock"] = 1.5 * val("icy_soul_rock", "icy_soul_rock_crit_damage") if on("icy_soul_rock") else 0
        thr = c.crit_rate + rows["rainbow_crit_rate"]                                       # Ring of Cycles threshold (excl. itself)
        rows["roc_threshold_cr"] = thr
        up = roc_startup_uptime(c)
        roc = on("ring_of_cycles")
        rows["roc_crit_rate"] = up * (val("ring_of_cycles", "ring_of_cycles_crit_rate") if (roc and thr < 100) else 0)
        rows["roc_skill_damage"] = up * (val("ring_of_cycles", "ring_of_cycles_skill_damage") if (roc and thr >= 100) else 0)
        rows["roc_excess_points"] = min(100, thr - 100) if (roc and thr >= 100) else 0
        rows["roc_basic_attack_damage"] = (up * rows["roc_excess_points"] * val("ring_of_cycles", "ring_of_cycles_basic_attack_damage_per_point")
                                           if roc else 0)

        # ---- Candle ----
        eff_d = c.eff_d
        eff_active = True if pvp else c.fixed_duration_active
        appear = boss_appear_time(ct)
        rows["candle_final_damage"] = val("candle", "candle_final_damage") if (on("candle") and eff_active) else 0
        if on("candle") and eff_active:
            rows["candle_boss_damage"] = max(0, min(40, eff_d) - max(20, appear)) / (eff_d - appear) * val("candle", "candle_boss_damage")
        else:
            rows["candle_boss_damage"] = 0

        # ---- Peach Tree Herb Pouch / Silver Pendant (enemy damage taken) ----
        rows["peach_enemy_dmg_taken"] = (val("peach_tree", "peach_tree_enemy_dmg_taken") * peach_uptime(c.aps)
                                         if (on("peach_tree") and ct != "Chapter Hunt") else 0)
        rows["silver_enemy_dmg_taken"] = (val("silver_pendant", "silver_pendant_enemy_dmg_taken") * silver_avg_stacks(c.aps)
                                          if (on("silver_pendant") and ct != "Chapter Hunt") else 0)

        # ---- Hexagon / Charm / Old Music Box / Secret Map / Reindeer / Bottle / Alliance (Attack% and Damage buckets) ----
        rows["hexagon_avg_stacks"] = hexagon_avg_stacks(c)
        rows["hexagon_damage"] = pre.hex_avg
        rows["charm_of_the_undead"] = pre.charm_avg
        rows["old_music_box_attack_pct"] = pre.omb
        rows["secret_map_attack_pct"] = pre.secret_map_attack
        rows["reindeer_spear_attack_pct"] = pre.reindeer_attack
        rows["alliance_badge"] = pre.alliance
        rows["bottle_of_emotion_attack_pct"] = pre.bottle_attack
        rows["shiny_watch_attack_pct"] = pre.shiny_watch_attack
        rows["mummydogs_bandages_attack_pct"] = pre.mummydog_attack
        growth = ct in AD.GROWTH_DUNGEON_CONTENT_TYPES
        rows["secret_map_final_dmg_normal"] = (val("secret_map", "secret_map_final_damage") * (3 if growth else 1)
                                               if (on("secret_map") and not pvp) else 0)

        # ---- Final Damage sources ----
        rows["flaming_lava"] = val("flaming_lava", "flaming_lava_final_damage_debuffed") if (on("flaming_lava") and ct != "Chapter Hunt") else 0
        horn_full = val("horn_flute", "horn_flute_final_damage") * (2 if ct == "Chapter Boss" else 1) if on("horn_flute") else 0
        self.horn_full = horn_full
        rows["horn_flute"] = horn_full * c.horn_uptime if on("horn_flute") else 0
        per_target = val("fire_flower", "fire_flower_final_damage_per_target") if on("fire_flower") else 0
        rows["fire_flower_normal"] = 10 * per_target if on("fire_flower") else 0
        rows["fire_flower_boss"] = 1 * per_target if on("fire_flower") else 0
        chalice_gate = on("chalice") and c.monster_type in ("normal", "breakthrough")
        cn, cb = chalice_uptimes(c)
        star_val = val("chalice", "chalice_final_damage") if on("chalice") else 0
        rows["chalice_normal"] = star_val * cn if chalice_gate else 0
        rows["chalice_boss"] = star_val * cb if chalice_gate else 0
        self.chalice_full = star_val if chalice_gate else 0
        # ---- Sealed Bottle (patch 2026-11-26): +6 % Final Damage always; kill stacks of Normal / Boss Monster Damage ----
        rows["sealed_bottle_final_damage"] = val("sealed_bottle", "sealed_bottle_final_damage") if on("sealed_bottle") else 0
        stacks_normal, stacks_boss = sealed_bottle_stacks(c)
        rows["sealed_bottle_stacks_normal"], rows["sealed_bottle_stacks_boss"] = stacks_normal, stacks_boss
        rows["sealed_bottle_normal"] = val("sealed_bottle", "sealed_bottle_normal_damage_per_kill") * stacks_normal if on("sealed_bottle") else 0
        rows["sealed_bottle_boss"] = val("sealed_bottle", "sealed_bottle_boss_damage_per_kill") * stacks_boss if on("sealed_bottle") else 0
        # Shiny Watch: the summoned companion's Final Damage grows by this much per stack (the companion model averages the ramp over its window)
        self.watch_per_stack = val("shiny_watch", "shiny_watch_companion_final_damage_per_stack") if on("shiny_watch") else 0.0
        # ---- Boss / Normal Monster Damage ----
        rows["sayrams_necklace_normal"] = val("sayrams_necklace", "sayrams_necklace_normal_damage") if on("sayrams_necklace") else 0
        rows["sayrams_necklace_boss"] = val("sayrams_necklace", "sayrams_necklace_boss_damage") if on("sayrams_necklace") else 0
        # ---- Contract of Darkness (boss crit rate), Reindeer's Spear base def pen (reference + the boss/PvP correction), Soul Contract ----
        rows["contract_of_darkness_crit_rate_bonus"] = (val("contract_of_darkness", "contract_of_darkness_crit_rate")
                                                        if (on("contract_of_darkness") and not pvp) else 0)
        rows["reindeer_spear_base_def_pen_reference"] = val("reindeer_spear", "reindeer_spear_def_pen") if on("reindeer_spear") else 0
        rows["soul_contract_pct"] = soul_contract_pct(eq, ct)

        # ---- aggregate buckets (Artifacts sheet rows, same summation order) ----
        self.agg_crit_rate = rows["roc_crit_rate"] + rows["rainbow_crit_rate"]
        self.agg_crit_damage = rows["rainbow_crit_damage"] + rows["icy_soul_rock"]
        self.agg_final_damage = ((1 + rows["candle_final_damage"] / 100) * (1 + rows["flaming_lava"] / 100) * (1 + rows["horn_flute"] / 100)
                                 * (1 + rows["sealed_bottle_final_damage"] / 100) - 1) * 100
        self.agg_boss_damage = rows["candle_boss_damage"] + rows["sayrams_necklace_boss"] + rows["sealed_bottle_boss"]
        self.agg_normal_damage = rows["sayrams_necklace_normal"] + rows["sealed_bottle_normal"]
        self.agg_enemy_dmg_taken = rows["peach_enemy_dmg_taken"] + rows["silver_enemy_dmg_taken"]
        self.agg_damage = rows["hexagon_damage"]
        self.agg_attack_pct = (rows["old_music_box_attack_pct"] + rows["secret_map_attack_pct"] + rows["reindeer_spear_attack_pct"]
                               + rows["alliance_badge"] + rows["bottle_of_emotion_attack_pct"] + rows["charm_of_the_undead"]
                               + rows["shiny_watch_attack_pct"] + rows["mummydogs_bandages_attack_pct"])
        self.agg_fd_normal_only = rows["secret_map_final_dmg_normal"] + rows["fire_flower_normal"] + rows["chalice_normal"]
        self.agg_fd_boss_only = rows["fire_flower_boss"] + rows["chalice_boss"]
        self.agg_skill_damage = rows["roc_skill_damage"]
        self.agg_basic_attack_damage = rows["roc_basic_attack_damage"]
        self.soul_contract_pct = rows["soul_contract_pct"]
        self.spear_def_pen = rows["reindeer_spear_base_def_pen_reference"]
        self.cod_crit = rows["contract_of_darkness_crit_rate_bonus"]
        rows["arwens_glass_shoes_summon_time_increase_pct"] = self.summon_time_inc = summon_time_inc_pct(eq)

        # ---- reference-only values (baked into Inputs by the user; never summed into anything live) ----
        ref = {}
        self.reference_only = ref
        if on("book_of_ancient"):
            ref["book_of_ancient_crit_damage"] = (val("book_of_ancient", "book_of_ancient_crit_damage_pct_of_crit_rate") / 100
                                                  * (c.crit_rate + rows["roc_crit_rate"] + rows["rainbow_crit_rate"]))
            ref["book_of_ancient_crit_rate"] = val("book_of_ancient", "book_of_ancient_crit_rate")
        if on("athena_gloves"):
            ref["athena_max_damage"] = val("athena_gloves", "athena_gloves_max_damage_pct_of_attack_speed") / 100 * c.attack_speed
            ref["athena_attack_speed"] = val("athena_gloves", "athena_gloves_attack_speed")
        if on("clear_spring_water"):
            ref["clear_spring_water_final_damage"] = val("clear_spring_water", "clear_spring_water_final_damage") if growth else 0
        if on("soul_pouch"):
            ref["soul_pouch_final_damage"] = val("soul_pouch", "soul_pouch_final_damage") if pvp else 0
        if on("lit_lamp"):
            ref["lit_lamp_final_damage"] = val("lit_lamp", "lit_lamp_final_damage") if ct == "World Boss" else 0
        if on("star_rock"):
            ref["star_rock_boss_damage"] = val("star_rock", "star_rock_boss_damage")
        if on("cursed_doll"):
            ref["cursed_doll_final_damage"] = val("cursed_doll", "cursed_doll_final_damage")
        if on("shamaness_marble"):
            ref["shamaness_marble_buff_duration_increase_pct"] = val("shamaness_marble", "shamaness_marble_buff_duration_increase_pct")
        if on("reindeer_spear"):
            ref["reindeer_spear_base_def_pen"] = rows["reindeer_spear_base_def_pen_reference"]
        if on("bottle_of_emotion"):
            per_point = sv("bottle_of_emotion_final_damage_per_3pct_as", eq["bottle_of_emotion"]) / 3
            cap = sv("bottle_of_emotion_final_damage_cap", eq["bottle_of_emotion"])
            ref["bottle_of_emotion_final_damage"] = min(cap, max(0, per_point * (c.attack_speed - 60)))

    # ---- boss / normal branch multipliers outside the Boss/Normal Damage% buckets ----
    def extras(self, c, monster_defense, def_pen, crit_rate_total, crit_damage_total):
        """(extra_boss_mult, extra_normal_mult) of every damage row: Reindeer's Spear's boss/PvP defence correction x Contract of Darkness'
        crit-blend correction x boss-only Final Damage; normal: normal-only Final Damage.  A term whose artifact is not equipped is skipped
        (it is exactly 1 in the workbook up to ~1e-16 rounding noise)."""
        boss = 1.0
        if self.spear_def_pen:
            extra_mult = 1 if c.pvp else 2        # PvP: 2x total (1 extra), boss: 3x total (2 extra); the 1x is baked into Inputs.def_pen
            def_pen_boss = 100 * (1 - (1 - def_pen / 100) * (1 - self.spear_def_pen / 100) ** extra_mult)
            spear_ratio = ((5000 / (6000 + monster_defense * (1 - def_pen_boss / 100)))
                           / (5000 / (6000 + monster_defense * (1 - def_pen / 100))))
            boss = boss * spear_ratio
        if self.cod_crit:
            lo, hi = 1.0, 1.0 * (1 + crit_damage_total / 100)        # L, M of any row: M = L x (1 + crit damage); only the ratio matters
            cr_base = min(100, crit_rate_total)
            cr_boss = min(100, crit_rate_total + self.cod_crit)
            boss = boss * ((lo * (1 - cr_boss / 100) + hi * (cr_boss / 100)) / (lo * (1 - cr_base / 100) + hi * (cr_base / 100)))
        if self.agg_fd_boss_only:
            boss = boss * (1 + self.agg_fd_boss_only / 100)
        norm = (1 + self.agg_fd_normal_only / 100) if self.agg_fd_normal_only else 1.0
        return boss, norm

    # ---- result block ----
    def report(self, names=True):
        eq = self.equipped
        return dict(
            equipped=[dict(key=k, name=AD.ARTIFACT_LABELS[k], star=s, rank=AD.ARTIFACT_RANK[k], effect=effect_kind(k),
                           no_dps_effect=k in AD.ARTIFACT_NO_DPS_EFFECT, reason=AD.ARTIFACT_NO_DPS_EFFECT.get(k))
                      for k, s in eq.items()],
            buckets=dict(
                attack_pct=self.agg_attack_pct, final_damage=self.agg_final_damage, damage=self.agg_damage,
                skill_damage=self.agg_skill_damage, basic_attack_damage=self.agg_basic_attack_damage, crit_rate=self.agg_crit_rate,
                crit_damage=self.agg_crit_damage, boss_damage=self.agg_boss_damage, normal_damage=self.agg_normal_damage,
                enemy_damage_taken=self.agg_enemy_dmg_taken, final_damage_normal_only=self.agg_fd_normal_only,
                final_damage_boss_only=self.agg_fd_boss_only, soul_contract_cooldown_decrease_pct=self.soul_contract_pct,
                contract_of_darkness_boss_crit_rate=self.cod_crit, reindeer_spear_extra_def_pen_unit=self.spear_def_pen,
                companion_summon_time_increase_pct=self.summon_time_inc,
            ),
            rows=dict(self.rows),
            reference_only=dict(self.reference_only),
            notes=["reference_only artifacts: their stat is entered by hand in Inputs (workbook convention); equipping changes nothing live"],
        )
