"""Buccaneer: the DPS model of ``src/verify_buccaneer_workbook.py`` as a function of a plain inputs dict.

    from engine.classes import buccaneer
    result = buccaneer.compute(buccaneer.defaults("World Boss"))

``compute(inputs)`` is bit-identical to the verify script (same operations in the same order); the verify script stays the independent
reference, ``tests/golden/test_buccaneer.py`` compares the two (with no artifact equipped).  Artifact equip effects (``inputs["artifacts"]``, up to 4
slots) are ported in ``engine/artifacts.py`` (shared with FP-Mage / Hero / Paladin / Bishop; the Artifacts sheet of the builders is identical) and wired the way
``src/build_buccaneer_workbook.py`` wires them; the verify script does not model artifacts, so ``tests/golden/test_buccaneer_artifacts.py`` checks them
against the workbook itself (``tests/golden/buccaneer_artifacts_golden.json``, evaluated with ``formulas``).

Inputs dict: the workbook's Inputs keys already resolved for the chosen content type (see ``schema()``), plus ``companion_level`` (the
level of the chosen companion, 0 = not unlocked).  A missing / ``None`` value reads as 0, exactly like a blank workbook cell.

Buccaneer specifics (all in the verify script):

* Hook Bomber is the basic attack (5 hits, 6 from Lv136; target count ``6 + increase``).  Its cast rate is what is left of the actions per second after
  the action-costing skills (Corkscrew Blow, Octopunch, Nautilus Strike) and the actively cast buffs (Nimble Feet, Crossbones, Time Leap, Speed Infusion).
* **Serpent Scale / Assault Mode** is a smoothed steady-state resource loop and stays AVERAGED (never engine-timed): activations every
  ``T = (Sea Serpent Burst cooldown, CDR applied) + half a basic-attack period`` (the basic-attack rate is the AVERAGED model's, ``basic_attacks_per_second_avg``),
  uptime ``u = A / (A + N*T)`` (A = assault duration 10 s / 15 s from Lv94, N = 5 activations / 3 from Lv104).  Serpent Assault fires ``u/T`` per second INSTEAD of
  Sea Serpent Burst (``(1-u)/T`` per second); Raging Serpent Assault's per-cast weight carries ``u`` as a proc chance.  Serpent Scale's Final Damage is
  ``25% x F`` while in Assault Mode plus 4% while rebuilding: ``serpent_scale_avg``.
* Crossbones and Time Leap are timed Final Damage buffs (engine ``CB`` / ``TL``, ``fd_scale = 100 / (100 + FD + rest)``); Serpent Scale and Speed Infusion's
  Final Damage (20% of the Attack Speed it grants, a function of the APS) stay duty-cycle averages: ``final_damage_rest``.  Roll of the Dice's dice component
  (5 s of every 7 s) is the engine's constant Attack% term ``A0``.  Nimble Feet / Speed Infusion's Attack Speed joins the base Attack Speed through the
  150% diminishing-returns stack.
* Corkscrew Blow (21 s, 1.8 s stun) is the player's own stun: part of the timeline and, in Breakthrough / Hero Dungeon, lengthens the boss phase, so from
  Lv63 a "companion" result exists even with no companion chosen (``choice == "None"``: only the stun uplift).
* Octopunch's cooldown (16 s, 11.2 s from Lv134) is shared by Sea Serpent's Rage and Raging Serpent Assault; Sea Serpent's Rage Assault Mark is the global
  damage-taken bonus ``monster_dmg_bonus`` (added to BOTH the Boss and the Normal Monster Damage terms, handed to the companion as ``taken_bucket``).
* Greater Sea Serpent I (Lv72) turns the 130% burst into 430% (3rd-job scaling), Greater Sea Serpent II (Lv110) adds its own Final Damage factor to the burst
  only (``extra_fd_pct``); Maple Hero's Final Damage share targets Serpent Assault (60) and Corkscrew Blow (40).
* Nautilus Strike - Final Attack: 30% per attack per enemy hit, 1 s ICD, ``X/(1+ICD*X)`` over Hook Bomber + the action-costing damage skills, separately for
  the boss branch (N = 1) and the normal branch.
* Artifacts: the Attack% artifacts (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) join the Attack% bucket next
  to Roll of the Dice's dice component (also the strip's constant term ``A0``); the Final Damage artifacts (Candle, Flaming Lava, Horn Flute) multiply on top of
  the Final Damage bucket (Serpent Scale / Crossbones / Time Leap / Speed Infusion are INSIDE that bucket, so the strip's ``fd_scale`` and the companion's
  ``fdpart`` do not see them); Peach Tree / Silver Pendant (enemy damage taken) are part of ``monster_dmg_bonus`` (next to the Assault Mark, added to both Boss
  and Normal Monster Damage terms); Soul Contract's cooldown decrease reaches EVERY cooldown (all rows' effective cooldowns, Assault Mode's interval, the
  Octopunch window of the Assault Mark, Corkscrew Blow's stun) through ``Fight.cd_extra_pct``; Horn Flute's uptime comes from the stub-host run (window of
  candidate 0, which carries Corkscrew Blow's stun) weighted by the strip's damage weights; Arwen's Glass Shoes adds to the companion's Summoning Time Increase.
"""
from .. import _src  # noqa: F401
from ..common import blend as blend_mod
from ..common import classapi
from ..common import companion as comp_mod
from ..common import content as content_mod
from ..common import damage as dmg
from ..common import factors
from ..common import fight as fight_mod
from ..common import model as model_mod
from ..common import schema as schema_mod
from ..common import sens as sens_mod
from ..common import status as status_mod
from ..data import buccaneer as D
from .. import artifacts as art_mod
import status_timeline as stl  # noqa: E402  (src/status_timeline.py through the shim)

CLASS_ID = "buccaneer"
CLASS_NAME = "Buccaneer"
STAT_IDENTITY = {"main": "STR", "sub": "DEX"}

_MAIN_STAT_FIELDS = [
    schema_mod.field("flat_str", "Flat STR", "Main stats", "float", "flat", 0, help="Include Iron Body's own +30 if unlocked."),
    schema_mod.field("str_pct", "STR %", "Main stats", "float", "%", 0),
    schema_mod.field("dex", "DEX", "Main stats", "float", "flat", 0),
]


class _Model(model_mod.ModelBase):
    DATA = D

    # ------------------------------------------------------------------------------------------------------------------
    # ---- per-hit pipeline (reads the FINAL buff buckets, exactly as the verify script's module globals) ----
    def hit_damage(self, coeff_pct_val, is_basic, maple_ratio=0.0, extra_fd_pct=0.0):
        base_damage = self.attack * (coeff_pct_val / 100)
        dmg_reduction = dmg.defense_reduction(self.monster_defense, self.def_pen)
        maple_mult = (1 + maple_ratio * self.maple_hero_pct / 100) if maple_ratio else 1.0
        if extra_fd_pct:
            maple_mult *= (1 + extra_fd_pct / 100)
        final_mult = (1 + (self.final_damage + self.final_damage_extra) / 100) * (1 + self.art_final_damage / 100) * maple_mult
        source_pct = (self.basic_attack_damage + self.art_basic_attack_damage) if is_basic else (self.skill_damage + self.art_skill_damage)
        # Boss/Normal Monster Damage% is deliberately NOT applied here - it is blended per branch (its own multiplier x its own target count)
        base_hit = (
            base_damage * (1 + self.stat_damage / 100) * (1 + self.damage / 100)
            * (1 + self.damage_amp / 100) * dmg_reduction * final_mult * (1 + source_pct / 100)
            * self.attack_bucket_mult * (1 + self.art_joint_damage / 100)
        )
        return dmg.expected_hit(base_hit, self.min_damage, self.max_damage, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                                self.crit_damage + self.crit_damage_bonus)

    def skill_hit(self, key, s):
        """Expected damage of one hit of a damage skill (before the boss/normal branch multipliers)."""
        # a skill mastery MULTIPLIES the skill's damage (game-confirmed 2026-11-03); fold-ins stay additive
        pct = self.coeff_pct(s["base"], s["fidx"], True, s["step"]) * (1 + s.get("mastery", 0) / 100) + s.get("fold", 0)
        return self.hit_damage(pct, False, maple_ratio=s.get("maple_ratio", D.MAPLE_HERO_RATIOS.get(key, 0)))

    # ---- targets and branch blending ----
    def blend_branches(self, key, unit, targets, mastery_boss=0, mastery_normal=0):
        b, n = self.branch_multipliers(mastery_boss, mastery_normal, targets)
        fb, fn = self.timing_factors(key)
        return self.ledger.blend_unit(key, unit, b, n, fb, fn)

    def aps_with_extra_as(self, as_extra):
        # (+ Quick Motion / Agile Knuckles level deltas and Athena's Gloves' direct Attack Speed what-if, Sensitivity only: the block's Actions Per Second, its Speed
        #  Infusion APS and the companion snapshot's all read ``Inputs!attack_speed + delta [+ Athena]``)
        return dmg.actions_per_second(self.attack_speed_base + self.sens.get("attack_speed_extra", 0.0), as_extra)

    def nimble_feet_as_avg(self):
        """Nimble Feet's own duty-cycle-averaged Attack Speed% - independent of the actions per second (fixed 60 s cooldown / 15 s duration)."""
        if not self.unlocked("NIMBLE_FEET"):
            return 0.0
        nf = D.NIMBLE_FEET
        pct = self.coeff_pct(nf["base"], nf["fidx"], False, nf["step"])
        return pct * self.fight.buff_uptime(nf["cooldown"], nf["duration"], True)

    # ------------------------------------------------------------------------------------------------------------------
    def _build(self, inp):
        ct = self.read_content(inp)
        level = self.level
        sens = self.sens
        content_type = self.content_type
        monster_type = self.monster_type
        normal_weight = self.normal_weight
        fight_duration = self.fight_duration
        fixed_duration_active = self.fixed_duration_active
        coeff_pct = self.coeff_pct
        gated = self.gated
        unlocked = self.unlocked
        flat_attack, attack_pct = inp("flat_attack"), inp("attack_pct")
        self.attack = dmg.attack_value(flat_attack, attack_pct)
        if sens.get("mainstat_attack_delta"):      # Sensitivity: the main/sub stat's flat-Attack channel (bug 7), applied before ATTACK%
            self.attack += sens["mainstat_attack_delta"] * (1 + attack_pct / 100)
        flat_str, str_pct, dex_stat = inp("flat_str"), inp("str_pct"), inp("dex")
        self.stat_damage = (flat_str * (1 + str_pct / 100)) * 0.01 + dex_stat * 0.0025
        self.damage = inp("damage")
        self.damage_amp = inp("damage_amp")
        self.boss_damage = inp("boss_damage")
        self.normal_damage = inp("normal_damage")
        self.status_effect_damage = status_effect_damage = inp("status_effect_damage")
        final_damage = inp("final_damage")
        if sens.get("final_damage_factor") is not None:
            # Sensitivity: Buccaneer's workbook block retypes Inputs!final_damage INSIDE the additive Final Damage bucket - a baked-in Final Damage artifact what-if is a
            # factor on the TYPED value ((1 + F/100) x factor - 1), not on the live artifact bucket (``baked_fd_form="typed"`` in engine/sens_specs/buccaneer.py)
            final_damage = ((1 + final_damage / 100) * sens["final_damage_factor"] - 1) * 100
        final_damage += sens.get("final_damage_delta", 0.0)      # (+ Groggy Mastery's level delta, Sensitivity only; the block adds it next to the typed value)
        self.final_damage = final_damage
        self.min_damage = inp("min_damage") + sens.get("min_damage_delta", 0.0)      # (+ Knuckle Mastery's level delta, Sensitivity only)
        self.max_damage = inp("max_damage") + sens.get("max_damage_delta", 0.0)      # (Athena's Gloves' dependent Max Damage, Sensitivity only)
        # Book of Ancient's direct Crit Rate what-if and Shadow Heart's level delta: the workbook block's Ring of Cycles threshold carries both (``roc_threshold_cr_block``)
        self.crit_rate = inp("crit_rate") + sens.get("crit_rate_threshold_extra", 0.0) + sens.get("crit_rate_delta", 0.0)
        self.crit_damage = inp("crit_damage")
        self.attack_speed_base = inp("attack_speed")
        self.def_pen = sens_mod.def_pen_with_dose(inp("def_pen"), sens)   # Sensitivity: Reindeer's Spear equip toggle folds one signed dose of its base Def Pen into the typed value
        self.basic_attack_damage = inp("basic_attack_damage") + sens.get("basic_attack_damage_delta", 0.0)     # (+ Physical Training's level delta, Sensitivity only)
        self.skill_damage = inp("skill_damage")
        basic_attack_target_increase = inp("basic_attack_target_increase")
        summon_time_inc = inp("companion_summon_time_increase_pct")
        self.pvp_len = pvp_len = inp("pvp_fight_length") or content_mod.DEFAULT_PVP_FIGHT_LENGTH
        fight = self.fight = fight_mod.Fight(ct, pvp_len, inp("skill_cooldown_decrease"), inp("buff_duration_increase_pct") + sens.get("bdi_extra", 0.0),
                                             inp("max_enemies_hit"))     # (+ Shamaness Marble what-if, Sensitivity only)
        max_enemies_hit = fight.max_enemies_hit
        buff_duration_increase_pct = fight.bdi
        self.ledger = blend_mod.BranchLedger(normal_weight)

        # ---- artifacts (equip effects): slots, the early quantities (Attack% bucket / Hexagon / Charm) and Soul Contract's cooldown decrease ----
        self.eq = eq = sens["eq"] if "eq" in sens else art_mod.resolve_slots(inp.raw("artifacts"))   # (Sensitivity: an equip-toggle what-if may exceed 4 slots)
        actx = self.art_ctx = art_mod.Ctx(self.content_type, monster_type, fight_duration, pvp_len, fixed_duration_active,
                                          crit_rate=self.crit_rate, attack_speed=self.attack_speed_base)
        pre = self.art_pre = art_mod.Pre(eq, actx)
        # Arwen's Glass Shoes: the companion's effective Summoning Time Increase % = the Inputs value + the artifact (every use below)
        summon_time_inc += art_mod.summon_time_inc_pct(eq)
        fight.cd_extra_pct = art_mod.soul_contract_pct(eq, self.content_type)
        # live artifact terms of the damage pipeline; zero / neutral until the full effects are known (after the buff-casting startup delay)
        self.art_final_damage = self.art_joint_damage = self.art_skill_damage = self.art_basic_attack_damage = 0.0
        self.art_boss_damage = self.art_normal_damage = self.art_crit_rate = 0.0
        self.extra_boss = self.extra_norm = 1.0
        self.ph_b = self.ph_n = 1.0
        eff_cooldown = fight.eff_cooldown
        eff_duration = fight.eff_duration
        duty_cycle_uptime = lambda cooldown, duration: fight.buff_uptime(cooldown, duration, True)  # noqa: E731

        basic_lvl = self.sl.input_level(4)
        self.skill_coefficient_base = skill_coefficient_base = D.HOOK_BOMBER_BASE * factors.get_factor(basic_lvl, 21) / 1000

        # ---- Maple Hero (Serpent Assault / Corkscrew Blow) ----
        mh = D.MAPLE_HERO
        self.maple_hero_pct = coeff_pct(mh["base"], mh["fidx"], True, mh["step"]) if unlocked("MAPLE_HERO_HELPER") else 0.0

        hb_hits0, hb_hits_lvl, hb_hits1 = D.HOOK_BOMBER_HITS
        hook_bomber_targets = 6 + basic_attack_target_increase
        HOOK_BOMBER_HITS = hb_hits1 if level >= hb_hits_lvl else hb_hits0
        hook_bomber_mastery_damage = gated(D.HOOK_BOMBER_MASTERY)
        hook_bomber_mastery_boss_damage = gated(D.HOOK_BOMBER_BOSS_MASTERY)
        hook_bomber_pct = skill_coefficient_base * (1 + hook_bomber_mastery_damage / 100)

        # ---- Actions Per Second: raw Attack Speed + the duty-cycle-averaged AS buffs (Nimble Feet + Speed Infusion) via the diminishing-returns stack ----
        si = D.SPEED_INFUSION
        speed_infusion_pct = coeff_pct(si["base"], si["fidx"], True, si["step"]) if unlocked("SPEED_INFUSION") else 0.0

        def speed_infusion_as_avg():
            return speed_infusion_pct * duty_cycle_uptime(si["cooldown"], si["duration"]) if unlocked("SPEED_INFUSION") else 0.0

        self.as_bonus = self.nimble_feet_as_avg() + speed_infusion_as_avg()
        self.actions_per_second = actions_per_second = self.aps_with_extra_as(self.as_bonus)

        # ---- Status Effect Damage / KO timeline engine (src/status_timeline.py `solve`) ----
        choice, c_level = comp_mod.read_choice(inp)
        self.companion_choice, self.companion_level = choice, c_level
        # The player's own stunning skills (game table): Corkscrew Blow stuns for 1.8 s (cooldown 21 s), cast on cooldown from the start
        player_stun = D.PLAYER_STUN
        pl_on = any(unlocked(e["key"]) for e in player_stun)
        stun_info = comp_mod.stun_probe(ct, fight, pvp_len, choice, c_level, summon_time_inc)
        hasstun = bool(stun_info and stun_info.get("hasstun")) or pl_on
        ko = content_mod.ko_windows(fight_duration)
        self.status_on = status_on = fixed_duration_active and normal_weight == 0 and (content_type in ko or hasstun)

        # Buff-Casting Startup Delay: in fixed-duration fights the character casts every unlocked, actively cast buff sequentially at fight
        # start (1/APS s each) before the first damage-skill cast (0 when the engine is on: buffs are cast when they pay).
        if fixed_duration_active and not status_on:
            self.buff_cast_startup_time = sum(1 for k in D.STARTUP_BUFFS if unlocked(k)) / actions_per_second
        else:
            self.buff_cast_startup_time = 0.0
        fight.startup_time = self.buff_cast_startup_time
        t0_pl = 0.0 if status_on else self.buff_cast_startup_time
        self.pst = pst = [dict(id=e["id"], typ=e["typ"], cd=eff_cooldown(e["cd"], True), dur=e["dur"],
                               p=e["p"], on=unlocked(e["key"]), t0=t0_pl, tick=1.0, win=0.0) for e in player_stun]
        stun_info, stun_pin = comp_mod.stun_windows(ct, fight, pvp_len, pst, choice, c_level, summon_time_inc, sens)
        self.stf_b = stun_pin["stunfracB"]
        self.stf_n = stun_pin["stunfracN"]
        stun_vec = None
        if status_on:
            # (the verify script raises KeyError here when no companion is chosen and Corkscrew Blow is locked, i.e. level < 63 in a KO content: the
            # companion model's early return carries no stun_vector.  The engine reads that as "no companion stun" instead of crashing.)
            comp_stun = stun_info["stun_vector"](stl.NB_MAX) if "stun_vector" in stun_info else [0.0] * stl.NB_MAX
            stun_vec = [min(1.0, a + b) for a, b in zip(comp_stun, stl.pl_stun_vector([dict(e, t0=0.0) for e in pst], fight_duration, stl.NB_MAX))]

        # ---- Octopunch's live cooldown (shared by Sea Serpent's Rage / Raging Serpent Assault) and the cast-rate rows ----
        oc_base, oc_level, oc_haste = D.OCTOPUNCH_COOLDOWN
        octopunch_cooldown = (oc_base * oc_haste) if level >= oc_level else oc_base
        self.octopunch_cooldown = octopunch_cooldown
        cast_cooldowns = dict(CORKSCREW_BLOW=D.CORKSCREW_COOLDOWN, OCTOPUNCH=octopunch_cooldown, NAUTILUS_STRIKE=D.NAUTILUS_STRIKE_COOLDOWN)
        skill_cast_rows = [(k, cast_cooldowns[k]) for k in D.SKILL_CAST_ROWS]
        buff_cast_rows = list(D.BUFF_CAST_ROWS)

        def cast_rate_with(counts):
            """Skill + buff cast rate; ``counts`` maps row key -> engine cast count (the engine's schedule), other rows use the averaged formulas."""
            if fixed_duration_active:
                tot = 0.0
                for k, cd in skill_cast_rows:
                    if unlocked(k):
                        tot += counts[k] if k in counts else fight.non_buff_casts(eff_cooldown(cd, True))
                for k, cd in buff_cast_rows:
                    if unlocked(k):
                        tot += counts[k] if k in counts else fight.exact_casts(eff_cooldown(cd, True))
                return tot / fight_duration
            return sum(1 / eff_cooldown(cd, True) for k, cd in skill_cast_rows + buff_cast_rows if unlocked(k))

        # The AVERAGED model's cast rate / Hook Bomber rate (pre-engine cast counts): the Assault Mode interval and uptime read this one
        self.cast_rate_avg = cast_rate_avg = cast_rate_with({})
        self.hook_bomber_per_second_avg = hook_bomber_per_second_avg = max(0, actions_per_second - cast_rate_avg)

        # ---- Assault Mode economy: activations every T = SSB cooldown + half a basic-attack period ----
        cd0, reductions = D.SSB_COOLDOWN
        ssb_cooldown = cd0
        for lv_, red in reductions:
            ssb_cooldown = ssb_cooldown - (red if level >= lv_ else 0)
        self.serpent_T = serpent_T = eff_cooldown(ssb_cooldown, True) + (0.5 / hook_bomber_per_second_avg if hook_bomber_per_second_avg > 0 else 0.0)
        ad0, ad_lvl, ad_extra = D.ASSAULT_DURATION
        assault_duration = ad0 + (ad_extra if level >= ad_lvl else 0)
        an0, an_lvl, an1 = D.ACTIVATIONS_TO_ASSAULT
        activations_to_assault = an1 if level >= an_lvl else an0
        self.uptime = uptime = (
            assault_duration / (assault_duration + activations_to_assault * serpent_T)
            if unlocked("SERPENT_SCALE_FD") else 0.0
        )

        # ---- Global Final Damage bucket: Serpent Scale (Assault-Mode-gated) + Crossbones + Time Leap + Speed Infusion (live AS-linked formula) ----
        sc = D.SERPENT_SCALE
        serpent_scale_pct = coeff_pct(sc["base"], sc["fidx"], True, sc["step"]) if unlocked("SERPENT_SCALE_FD") else 0.0
        # +25% FD while in Assault Mode (uptime u) + average 2 held scales x 2% = 4% while rebuilding (1-u)
        self.serpent_scale_avg = serpent_scale_avg = (serpent_scale_pct * uptime + sc["held_scales_pct"] * (1 - uptime)) if unlocked("SERPENT_SCALE_FD") else 0.0
        cb, tl = D.CROSSBONES, D.TIME_LEAP
        self.crossbones_full = crossbones_full = coeff_pct(cb["base"], cb["fidx"], True, cb["step"]) if unlocked("CROSSBONES_FD") else 0.0
        self.time_leap_full = time_leap_full = (coeff_pct(tl["base"], tl["fidx"], True, tl["step"]) + gated(tl["gated"])) if unlocked("TIME_LEAP_FD") else 0.0
        # Speed Infusion FD = 20% of Attack Speed WHILE the buff is up (APS incl. its own +AS), over its uptime.
        self.speed_infusion_full = speed_infusion_full = (si["fd_share"] * (self.aps_with_extra_as(self.nimble_feet_as_avg() + speed_infusion_pct) - 1)
                                                          if unlocked("SPEED_INFUSION") else 0.0)
        speed_infusion_avg = speed_infusion_full * duty_cycle_uptime(si["cooldown"], si["duration"]) if unlocked("SPEED_INFUSION") else 0.0
        self.final_damage_rest = final_damage_rest = serpent_scale_avg + speed_infusion_avg     # the Final Damage the engine does not time
        crossbones_pct = crossbones_full * duty_cycle_uptime(cb["cooldown"], cb["duration"]) if unlocked("CROSSBONES_FD") else 0.0
        time_leap_pct = time_leap_full * duty_cycle_uptime(tl["cooldown"], tl["duration"]) if unlocked("TIME_LEAP_FD") else 0.0
        self.final_damage_extra = final_damage_rest + crossbones_pct + time_leap_pct            # averaged model (engine off)

        # ---- Attack% bucket: Roll of the Dice's dice component only (real 5s/7s duty cycle) ----
        rd = D.ROLL_OF_THE_DICE
        self.roll_of_dice_pct = roll_of_dice_pct = coeff_pct(rd["base"], rd["fidx"], True, rd["step"]) * rd["duty"][0] / rd["duty"][1] if unlocked("ROLL_OF_THE_DICE_DICE") else 0.0
        # artifact Attack% (Old Music Box, Secret Map, Reindeer's Spear, Alliance Badge, Bottle of Emotion, Charm's average) joins the same additive bucket
        # Dark Clarity's level delta (Sensitivity only: its value is baked into Inputs!attack_pct) joins the same additive Attack% bucket as the dice component everywhere
        # the workbook block sums it (``bucket_avg_block``, the strip's A0, the companion's snapshot)
        roll_of_dice_pct = roll_of_dice_pct + sens.get("attack_mult_delta", 0.0)
        self.attack_bucket_mult = 1 + (roll_of_dice_pct + pre.agg_attack_pct) / 100

        self.crit_rate_bonus = 0.0
        self.crit_damage_bonus = 0.0
        # Sea Serpent's Rage Assault Mark: +15% x f21 damage taken for 5s (x (1+BDI)) per Octopunch cast.
        sw = D.SSR_WEAKEN
        ssr_weaken_pct = coeff_pct(sw["base"], sw["fidx"], True, sw["step"]) if unlocked("SSR_WEAKEN") else 0.0
        self.monster_dmg_bonus = ssr_weaken_pct * min(1.0, sw["duration"] * (1 + buff_duration_increase_pct / 100) / eff_cooldown(octopunch_cooldown, True))
        ssr_monster_dmg_bonus = self.monster_dmg_bonus      # (+ Peach Tree / Silver Pendant once the artifact effects are known, below)

        # ---- Engine pass 1: the buff schedule (independent of the skill weights) ----
        self.engine_n = ENGINE_N = {}
        E_ENGINE = None
        e1 = None
        E_FS = {}
        self.phi_rows = {}
        self.phi_unif = 1.0
        eng_base = dict(T=fight_duration, S=status_effect_damage, ko=ko.get(content_type, []), hex_v=pre.hex_v, hex_period=20, hex_max=3,
                        hex_avg=pre.hex_avg, charm_v=pre.charm_val, c_slot=0.0, stun=stun_vec, groups=[])

        def engine_buff(bid, F):
            key, bcd0, bdur0 = D.BUFF_SPEC[bid]
            cd_, dur_ = eff_cooldown(bcd0, True), eff_duration(bdur0)
            return dict(id=bid, kind="ramp", F=F, dur=min(dur_, cd_), cd=cd_, on=unlocked(key), p0=1, p1=1, ramp_t=1, dur0=1)

        eng_host = None
        if status_on:
            fd_scale = 100 / (100 + final_damage + final_damage_rest)
            buffs = [engine_buff("CB", crossbones_full * fd_scale), engine_buff("TL", time_leap_full * fd_scale)]
            eng_host = dict(eng_base, A0=roll_of_dice_pct + pre.a0, buffs=buffs)
            e1 = sens["strip"][0] if "strip" in sens else stl.solve(eng_host)   # Sensitivity may reuse the main strip
            self.attack_bucket_mult = e1["Bbuff_mean"]
            self.final_damage_extra = final_damage_rest
            for bid, (key, _cd0, _dur0) in D.BUFF_SPEC.items():
                ENGINE_N[key] = e1["buffs"][bid]["n"]
        attack_bucket_mult = self.attack_bucket_mult
        self.e1 = e1
        # Final Damage of all four buffs at the CURRENT cast counts (Summary R_FD_ALL: the engine's counts for Crossbones / Time Leap when it is on): the bucket the
        # Sensitivity sheet's "mult"-kind Final Damage sweep bumps by 1% (``SensSpec.mult_extra``)
        self.final_damage_all = (serpent_scale_avg
                                 + (crossbones_full * fight.buff_uptime(cb["cooldown"], cb["duration"], True, casts=ENGINE_N.get("CROSSBONES_FD")) if unlocked("CROSSBONES_FD") else 0.0)
                                 + (time_leap_full * fight.buff_uptime(tl["cooldown"], tl["duration"], True, casts=ENGINE_N.get("TIME_LEAP_FD")) if unlocked("TIME_LEAP_FD") else 0.0)
                                 + speed_infusion_avg)

        # ---- artifact effects (full): everything that needs the action rate / startup delay / the timeline's status multiplier ----
        actx.aps, actx.startup = actions_per_second, self.buff_cast_startup_time
        # Companion!horn_uptime (computed whether or not Horn Flute is equipped, like the workbook): the share of the player's boss DAMAGE dealt
        # while the companion is out (candidate-0 timing, which already carries the player's own Corkscrew Blow stun in Breakthrough / Hero Dungeon).  The
        # summon timing is damage-independent, so the stub-host run (with the player's stun entries) reports it.
        s0, w0, d_comp, period, ts_window = comp_mod.horn_window(actx, monster_type, fight_duration, pvp_len, summon_time_inc, stun_pin,
                                                                 choice, c_level)
        dw = art_mod.damage_weights(fight_duration, pre.hex_v, roll_of_dice_pct + pre.a0, pre.charm_val, e1["mult"] if status_on else None)
        actx.horn_uptime = art_mod.horn_flute_uptime(actx, dw, s0, w0, d_comp, period, ts_window)
        eff = self.art_effects = art_mod.Effects(eq, actx, pre)
        self.art_crit_rate = eff.agg_crit_rate                                     # (no live Crit-Rate-buff source in this kit: ``crit_rate_bonus`` stays 0)
        self.crit_damage_bonus = eff.agg_crit_damage                               # (no other live Crit-Damage-buff source in this kit)
        self.crit_damage_bonus += sens.get("crit_damage_delta", 0.0)               # (Sensitivity: Book of Ancient's dependent Crit Damage while Crit Rate is swept)
        self.crit_damage_bonus += sens_mod.boa_crit_damage_delta(                  # (Book of Ancient equip what-if: pct x the crit-rate total, Sensitivity only)
            sens, self.crit_rate + self.crit_rate_bonus + self.art_crit_rate)
        # the FULL live crit-rate total (Inputs + artifact bucket; CLAUDE.md item 13): what the cube / equipment tables test against the 100% cap
        self.crit_rate_total = self.crit_rate + self.crit_rate_bonus + self.art_crit_rate
        self.art_boss_damage, self.art_normal_damage = eff.agg_boss_damage + sens.get("boss_damage_extra", 0.0), eff.agg_normal_damage   # (+ Star Rock what-if)
        self.art_final_damage = eff.agg_final_damage
        self.art_joint_damage = eff.agg_damage                                     # Hexagon Damage%; enemy damage taken sits in monster_dmg_bonus (below)
        self.art_skill_damage, self.art_basic_attack_damage = eff.agg_skill_damage, eff.agg_basic_attack_damage
        self.extra_boss, self.extra_norm = eff.extras(actx, self.monster_defense, self.def_pen,
                                                      self.crit_rate + self.crit_rate_bonus + self.art_crit_rate, self.crit_damage + self.crit_damage_bonus)
        # Hexagon / Charm differ between the two phases of Breakthrough / Hero Dungeon: per-phase timing factor (engine-off rows)
        self.attack_bucket_avg = roll_of_dice_pct + pre.agg_attack_pct
        self.ph_b, self.ph_n = art_mod.phase_state_ratios(content_type, fight_duration, pre.hex_v, pre.hex_avg, self.attack_bucket_avg,
                                                          pre.charm_val, pre.charm_avg)
        # Peach Tree Herb Pouch / Silver Pendant (enemy damage taken) sit in the same global bucket as the Assault Mark (Summary R_MONSTER_DMG_BONUS)
        self.monster_dmg_bonus = ssr_monster_dmg_bonus + eff.agg_enemy_dmg_taken

        # ---- Hook Bomber (basic attack) hit (needed by the engine weights) ----
        self.hook_bomber_hit = hook_bomber_hit = self.hit_damage(hook_bomber_pct, True)

        # ---- Sea Serpent Burst / Serpent Assault pieces ----
        sb = D.SEA_SERPENT_BURST
        gss1 = level >= D.GSS1_LEVEL
        sea_serpent_burst_pct = (
            coeff_pct(sb["base"][1] if gss1 else sb["base"][0], sb["fidx"], True, sb["step"][1] if gss1 else sb["step"][0]) * (1 + gated(sb["mastery"]) / 100)
            if unlocked("SEA_SERPENT_BURST") else 0.0
        )
        g2 = D.GSS_II_FD
        gss2_fd_pct = coeff_pct(g2["base"], g2["fidx"], True, g2["step"]) if unlocked("GSS_II_FD") else 0.0
        sea_serpent_burst_hit = self.hit_damage(sea_serpent_burst_pct, False, extra_fd_pct=gss2_fd_pct)
        sh0, sh_lvl, sh_extra = D.SSB_HITS
        ssb_hits = sh0 + (sh_extra if level >= sh_lvl else 0)
        st0, st_steps = D.SSB_TARGETS
        ssb_targets = st0
        for lv_, extra in st_steps:
            ssb_targets = ssb_targets + (extra if level >= lv_ else 0)
        sa = D.SERPENT_ASSAULT
        serpent_assault_pct = (coeff_pct(sa["base"], sa["fidx"], True, sa["step"]) * (1 + gated(sa["mastery"]) / 100)) if unlocked("SERPENT_ASSAULT") else 0.0
        serpent_assault_hit = self.hit_damage(serpent_assault_pct, False, maple_ratio=D.MAPLE_HERO_RATIOS.get("SERPENT_ASSAULT", 0))

        # ---- Other damage skills ----
        SKILLS = self.skills = {}
        for key, t in D.DAMAGE_SKILLS.items():
            cooldown = octopunch_cooldown if t["cooldown"] == "octopunch" else t["cooldown"]
            hits = t["hits"]
            if isinstance(hits, tuple):          # ("boss", hits on boss / PvP, hits otherwise)
                hits = hits[1] if monster_type in ("boss", "pvp") else hits[2]
            s = dict(step=t["step"], cooldown=cooldown, hits=hits, base=t["base"], fidx=t["fidx"], scales=True,
                     mastery=gated(t["mastery"]), mastery_boss=0, mastery_normal=0,
                     costs_action=t["costs_action"], targets=t["targets"])
            if "icd" in t:
                s["icd"] = t["icd"]
                s["window"] = t["window"]
            if t.get("proc_chance") == "assault_uptime":
                s["proc_chance"] = uptime
            if key in D.MAPLE_HERO_RATIOS:
                s["maple_ratio"] = D.MAPLE_HERO_RATIOS[key]
            SKILLS[key] = s
        self.normal_targets = {k: v["targets"] for k, v in SKILLS.items()}

        # ---- Status/KO engine pass 2: the damage skills' casts (weight of one cast = its boss damage before any timing factor) ----
        if status_on:
            def percast(key):
                if not unlocked(key):
                    return 0.0
                sk = SKILLS[key]
                hits = sk["hits"] * (fight_mod.ticks(fight.capped_window(sk["window"]), sk["icd"]) if sk.get("icd") else 1)
                return (sk.get("proc_chance", 1.0) * hits * self.skill_hit(key, sk)
                        * self.branch_multipliers(sk.get("mastery_boss", 0), sk.get("mastery_normal", 0), sk["targets"])[0])
            c_slot = HOOK_BOMBER_HITS * hook_bomber_hit * self.branch_multipliers(hook_bomber_mastery_boss_damage, 0, hook_bomber_targets)[0]
            groups = status_mod.build_groups(D, unlocked, SKILLS, percast, fight.capped_window,
                                             lambda cast: eff_cooldown(SKILLS[cast]["cooldown"], True),
                                             stun_keys={e["key"] for e in player_stun})
            E_ENGINE = status_mod.solve_groups(self, D, eng_host, groups, c_slot, ENGINE_N, sens, reuse_strip=False)
            E_FS = E_ENGINE["fs"]
        self.e_engine = E_ENGINE

        # ---- Cast rate with the engine's cast counts ----
        engine_cast_keys = {k for k, _cd in skill_cast_rows + buff_cast_rows}
        self.cast_rate = cast_rate = cast_rate_with({k: v for k, v in ENGINE_N.items() if k in engine_cast_keys})
        self.hook_bomber_per_second = hook_bomber_per_second = max(0, actions_per_second - cast_rate)

        # ---- Hook Bomber (basic attack) DPS ----
        self.hook_bomber_dps = hook_bomber_dps = (
            self.blend_branches("HOOK_BOMBER", HOOK_BOMBER_HITS * hook_bomber_hit * hook_bomber_per_second, hook_bomber_targets,
                                hook_bomber_mastery_boss_damage, 0)
            if unlocked("HOOK_BOMBER") else 0.0)

        # ---- Sea Serpent Burst / Serpent Assault: one activation every T seconds, split (1-u)/u ----
        self.sea_serpent_burst_dps = sea_serpent_burst_dps = (
            self.blend_branches("SEA_SERPENT_BURST", ssb_hits * sea_serpent_burst_hit * ((1 - uptime) if unlocked("SERPENT_ASSAULT") else 1.0) / serpent_T,
                                ssb_targets)
            if unlocked("SEA_SERPENT_BURST") else 0.0
        )
        self.serpent_assault_dps = serpent_assault_dps = (
            self.blend_branches("SERPENT_ASSAULT", sa["hits"] * serpent_assault_hit * uptime / serpent_T, sa["targets"])
            if unlocked("SERPENT_ASSAULT") else 0.0
        )

        skill_dps = {}
        for key, s in SKILLS.items():
            if not unlocked(key):
                skill_dps[key] = 0.0
                continue
            hd = self.skill_hit(key, s)
            proc_prob = s.get("proc_chance", 1.0)
            eff_cd = eff_cooldown(s["cooldown"], s["costs_action"])
            if status_on and key in ENGINE_N:
                # engine casts: a DoT row's hits = hits per full window x effective casts (last window truncated at the fight end)
                per_cast = s["hits"] * (fight_mod.ticks(fight.capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                rate = per_cast * (E_FS[key] if key in D.STATUS_FS_KEYS else ENGINE_N[key]) / fight_duration
            elif fixed_duration_active:
                rate = fight.non_buff_total_hits(eff_cd, s["hits"], s.get("icd"), s.get("window")) / fight_duration
            else:
                hits = s["hits"] * (fight_mod.ticks(fight.capped_window(s["window"]), s["icd"]) if s.get("icd") else 1)
                rate = hits / eff_cd
            skill_dps[key] = self.blend_branches(key, proc_prob * rate * hd, s["targets"], s.get("mastery_boss", 0), s.get("mastery_normal", 0))

        # ---- Nautilus Strike - Final Attack: any attack, 30% chance per attack per enemy hit, 1s ICD => X/(1+ICD*X),
        #      X = sum over Hook Bomber + the action-costing damage skills of rate*(1-(1-c)^N) (N=1 on boss/PvP) ----
        self.nautilus_x = None
        if unlocked("NAUTILUS_FINAL_ATTACK"):
            fa = D.NAUTILUS_FINAL_ATTACK
            sources = [(hook_bomber_per_second, hook_bomber_targets)]
            for k in D.NAUTILUS_TRIGGER_KEYS:
                if unlocked(k):
                    cd_ = eff_cooldown(SKILLS[k]["cooldown"], SKILLS[k]["costs_action"])
                    casts = ENGINE_N[k] if (status_on and k in ENGINE_N) else fight.non_buff_casts(cd_)
                    sources.append((((casts / fight_duration) if fixed_duration_active else (1 / cd_)), SKILLS[k]["targets"]))
            hit = self.hit_damage(coeff_pct(fa["base"], fa["fidx"], True, fa["step"]), False)
            chance, icd = fa["chance"], fa["icd"]
            x_boss = chance * sum(r for r, _ in sources)
            x_norm = sum(r * dmg.q_roll(chance, min(t, max_enemies_hit)) for r, t in sources)
            self.nautilus_x = (x_boss, x_norm)
            b, n = self.branch_multipliers(0, 0, 1)
            fb, fn = self.timing_factors("NAUTILUS_FINAL_ATTACK")
            bp, np_ = x_boss / (1 + icd * x_boss) * hit * b * fb, x_norm / (1 + icd * x_norm) * hit * n * fn
            self.ledger.pairs["NAUTILUS_FINAL_ATTACK"] = (bp, np_, True, b * fb, n * fn)
            skill_dps["NAUTILUS_FINAL_ATTACK"] = (1 - normal_weight) * bp + normal_weight * np_
        else:
            skill_dps["NAUTILUS_FINAL_ATTACK"] = 0.0
        self.skill_dps = skill_dps
        self.player_dps = hook_bomber_dps + sea_serpent_burst_dps + serpent_assault_dps + sum(skill_dps.values())

        # ---- player's boss-only / normal-only totals (the companion's damage-share weights; rows in the verify script's insertion order) ----
        row_dps = [("HOOK_BOMBER", hook_bomber_dps), ("SEA_SERPENT_BURST", sea_serpent_burst_dps), ("SERPENT_ASSAULT", serpent_assault_dps)] + list(skill_dps.items())
        self.pb_total, self.pn_total, self.pu_total = self.ledger.split_totals(row_dps, D.STATUS_UNIFORM_ROWS)

        # ---- companion: src/companion_python_model.py fed with this model's own pipeline numbers ----
        self.begin_companion(summon_time_inc)          # (effective Summoning Time Increase % = Inputs + Arwen's Glass Shoes)
        if (choice != "None" and c_level >= 1) or pl_on or sens.get("want_comp_host"):   # (Sensitivity: the comparison tables need the host with no companion / stun too)
            basic_b, basic_n = self.ledger.pairs.get("HOOK_BOMBER", (0.0, 0.0))[:2]
            fdpart = 1 + (final_damage + serpent_scale_avg + crossbones_full + time_leap_full + speed_infusion_full) / 100
            boss_pct = self.boss_damage + self.art_boss_damage + self.monster_dmg_bonus
            norm_pct = self.normal_damage + self.art_normal_damage + self.monster_dmg_bonus
            comp_host = dict(comp_mod.host_common(self, pre, eff, basic_b, basic_n),
                unit=self.hit_damage(100.0, True) / 100, sd=self.skill_damage + self.art_skill_damage, aps=actions_per_second,
                avgbuff=attack_bucket_mult * (1 + (final_damage + self.final_damage_extra) / 100), attack_bucket_avg=self.attack_bucket_avg,
                agg_damage_avg=self.art_joint_damage,
                avgbuff_snap=lambda charm, extra: (1 + (roll_of_dice_pct + pre.agg_attack_pct - pre.charm_avg + charm + extra) / 100) * fdpart,
                boss_pct=boss_pct, norm_pct=norm_pct, cr_total=self.crit_rate + self.crit_rate_bonus + self.art_crit_rate,
                cd_total=self.crit_damage + self.crit_damage_bonus, def_pen=self.def_pen,
                taken_bucket=0.0 if monster_type == "pvp" else ((1 - normal_weight) * boss_pct + normal_weight * norm_pct), pst=pst)
            self.comp_host = comp_host
            self.run_companion(comp_host, choice, c_level, summon_time_inc, pl_on)
        self.total_dps = self.player_dps + self.companion_dps

    # ------------------------------------------------------------------------------------------------------------------
    def row_dps(self, key):
        return {"HOOK_BOMBER": self.hook_bomber_dps, "SEA_SERPENT_BURST": self.sea_serpent_burst_dps,
                "SERPENT_ASSAULT": self.serpent_assault_dps}.get(key, self.skill_dps.get(key, 0.0))

    def derived_extra(self):
        return dict(
            cast_rate_avg=self.cast_rate_avg, basic_attacks_per_second=self.hook_bomber_per_second,
            basic_attacks_per_second_avg=self.hook_bomber_per_second_avg, avg_buff_mult=self.attack_bucket_mult, as_bonus=self.as_bonus,
            attack_bucket_mult=self.attack_bucket_mult,
            skill_coefficient_base=self.skill_coefficient_base, buff_cast_startup_time=self.buff_cast_startup_time,
            crit_damage_bonus=self.crit_damage_bonus, final_damage_extra=self.final_damage_extra, final_damage_rest=self.final_damage_rest,
            monster_dmg_bonus=self.monster_dmg_bonus, def_pen_effective=self.def_pen, maple_hero_pct=self.maple_hero_pct,
            assault_mode_uptime=self.uptime, serpent_interval_s=self.serpent_T, serpent_scale_avg=self.serpent_scale_avg,
            crossbones_full=self.crossbones_full, time_leap_full=self.time_leap_full, speed_infusion_full=self.speed_infusion_full,
            roll_of_dice_pct=self.roll_of_dice_pct, octopunch_cooldown=self.octopunch_cooldown,
        )


fields, schema, defaults = classapi.make(CLASS_ID, CLASS_NAME, STAT_IDENTITY, _MAIN_STAT_FIELDS, D)
artifact_schema = classapi.artifact_schema


def model(inputs):
    """The evaluated model object (everything ``compute`` reports plus the internals engine/sensitivity.py reads: ``comp_host``, ``e1`` /
    ``e_engine`` (the timeline strip), ``art_effects`` ...).  Same input dict as ``compute``; honours ``inputs["_sens"]`` (engine/common/sens.py)."""
    return _Model(inputs)


def compute(inputs):
    """DPS of one Buccaneer setup.  ``inputs``: dict (see module docstring / ``schema()``); returns a JSON-friendly dict:

    total_dps / player_dps / boss_dps / normal_dps / player_boss_dps / player_normal_dps, skills (per damage row: key, name, dps, share,
    boss_dps, normal_dps, unlocked), companion (None or dps/boss/normal/share + model details; choice "None" = Corkscrew Blow stun uplift only),
    engine_on (Status/KO timeline engine), engine (its cast counts and timing factors), derived (ATTACK, STAT_DAMAGE, actions/s, buff
    multipliers, Assault Mode uptime / interval, Final Damage pieces, computed Inputs rows ...).
    """
    return _Model(inputs).result()
