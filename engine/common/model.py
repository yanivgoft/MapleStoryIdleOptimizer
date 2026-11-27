"""The skeleton every class model (``engine/classes/<class>.py`` ``_Model``) shares: the input reader, the content / skill-level prelude and the
small helpers whose text was identical in all twelve classes.  A class sets ``DATA`` to its ``engine/data/<class>.py`` module (unlock levels,
status-engine row sets) and implements ``_build(inp)`` / ``result()``.
"""
from . import companion as comp_mod
from . import content as content_mod
from . import factors
from .. import typed_artifacts


class Inputs:
    """Reads like the verify script's ``_in``: a missing / None value is 0 (an empty Excel cell)."""

    def __init__(self, d):
        self.d = d

    def __call__(self, key):
        v = self.d.get(key)
        return 0 if v is None else v

    def raw(self, key):
        return self.d.get(key)


class ModelBase:
    DATA = None          # the class's engine/data module: UNLOCK_LEVEL, STATUS_PHI_ROWS, STATUS_UNIFORM_ROWS

    # how the class composes the artifact Damage% (Hexagon Necklace) with the typed Damage: "factor" = its own multiplicative term, "additive" = one bucket
    # (Bishop); only read by ``typed_artifacts`` (the typed-includes-artifacts convention)
    TYPED_DAMAGE_COMPOSITION = "factor"

    def __init__(self, inputs):
        # ``typed_includes_artifacts`` (engine default False = the workbooks' convention): the typed stats already contain the equipped artifacts' effects, so derive
        # the character without them first; the pipeline below then adds the effects back live (engine/typed_artifacts.py)
        self.typed_info = None
        if inputs.get(typed_artifacts.FLAG):
            inputs, self.typed_info = typed_artifacts.strip(type(self), inputs)
        self._build(Inputs(inputs))

    # ------------------------------------------------------------------------------------------------------------------
    def unlocked(self, key):
        threshold = self.DATA.UNLOCK_LEVEL.get(key)
        return threshold is None or self.level >= threshold

    def coeff_pct(self, base, fidx, scales, job_step):
        return self.sl.coeff_pct(base, fidx, scales, job_step)

    def gated(self, pairs):
        return factors.level_gated_sum(self.level, pairs)

    def read_content(self, inp, defense=None):
        """The prelude of ``_build``: level, content type, the Sensitivity hook dict (``self.sens``, engine/sensitivity.py, vocabulary in
        engine/common/sens.py: the Sensitivity sheet's block-only terms - baked-in artifact what-ifs, passive-skill deltas, a reused timeline strip,
        a pinned summon time ...; empty without it, every hook is then a no-op), the fight (``Content``: monster type / defense / length / branch
        weight; ``defense`` overrides the Inputs value, e.g. a class whose PvP opponent has the character's own total Defense) and the skill levels.
        Returns the ``Content``."""
        level = self.level = inp.raw("level")
        if level is None:
            raise ValueError("inputs['level'] is required")
        self.content_type = inp.raw("content_type")
        if self.content_type not in content_mod.CONTENT_TYPES:
            raise ValueError(f"unknown content_type {self.content_type!r}")
        self.sens = inp.d.get("_sens") or {}
        ct = self.content = content_mod.Content(self.content_type, inp("chapter_stage"), inp("defense") if defense is None else defense,
                                                inp("boss_normal_weight_choice"))
        self.monster_type = ct.monster_type
        self.normal_weight = ct.normal_weight
        self.monster_defense = ct.monster_defense
        self.fight_duration = ct.fight_duration
        self.fixed_duration_active = ct.fixed_duration_active
        self.sl = factors.SkillLevels(level, inp("skill_lvl_1st"), inp("skill_lvl_2nd"), inp("skill_lvl_3rd"), inp("skill_lvl_4th"),
                                      inp("skill_lvl_all"))
        return ct

    # ---- the companion run ----
    def begin_companion(self, summon_time_inc):
        """No companion result yet; ``summon_time_inc`` = the effective Summoning Time Increase % (Inputs + Arwen's Glass Shoes)."""
        self.companion_result = None
        self.companion_dps = 0.0
        self.comp_host = None
        self.summon_time_inc = summon_time_inc

    def run_companion(self, comp_host, choice, c_level, summon_time_inc, pl_on):
        """The companion model on the finished host: when a companion is chosen (level >= 1) or the player's own stun alone makes the uplift (``pl_on``)."""
        if (choice != "None" and c_level >= 1) or pl_on:
            self.companion_result = comp_mod.run(comp_host, choice if (choice != "None" and c_level >= 1) else "None", c_level, summon_time_inc,
                                                 pin=self.sens.get("comp_pin"))
            self.companion_dps = self.companion_result["comp_blend_dps"]

    # ---- boss / normal branch timing ----
    def timing_factors(self, key):
        """(boss-branch, normal-branch) timing factor of a damage row: the engine's phi (rows it casts), phi_unif (uniformly spread rows)
        or, with the engine off, the uniform 1 + Status Effect Damage x stunned share.  Normal branch: always the uniform stun factor."""
        fn = (1 + self.status_effect_damage / 100 * self.stf_n) * self.ph_n
        if self.status_on:
            if key in self.DATA.STATUS_PHI_ROWS:
                return self.phi_rows.get(key, 1.0), fn
            if key in self.DATA.STATUS_UNIFORM_ROWS:
                return self.phi_unif, fn
            return 1.0, fn
        return (1 + self.status_effect_damage / 100 * self.stf_b) * self.ph_b, fn

    # ---- the result dict ----
    def row_dps(self, key):
        """Blended DPS of one damage row (the class's basic-attack row is a plain attribute, the others live in ``skill_dps``)."""
        raise NotImplementedError

    def derived_extra(self):
        """The class's own entries of ``result()["derived"]`` (they sit between ``cast_rate`` and the stunned shares)."""
        raise NotImplementedError

    def result(self):
        D = self.DATA
        total = self.total_dps
        rows = []
        for key in D.DPS_ROW_ORDER:
            dps = self.row_dps(key)
            share = self.ledger.branch_share(key, dps)
            rows.append(dict(key=key, name=D.SKILL_NAMES[key], dps=dps, share=(dps / total if total else 0.0),
                             boss_dps=(share[0] if share else 0.0), normal_dps=(share[1] if share else 0.0),
                             unlocked=self.unlocked(key)))
        companion = None
        cr = self.companion_result
        if cr is not None:
            w = self.normal_weight
            companion = dict(
                choice=self.companion_choice, level=self.companion_level, dps=self.companion_dps,
                boss_dps=cr["comp_boss_dps"], normal_dps=cr["comp_norm_dps"], share=(self.companion_dps / total if total else 0.0),
                damage=(1 - w) * cr["dmg_b"] + w * cr["dmg_n"], uplift=(1 - w) * cr["upl_b"] + w * cr["upl_n"],
                # DPS split of ``dps``: the companion's own damage and what it does for the player (stun uplift, buff snapshots, boss-phase extension)
                own_dps=(1 - w) * cr["own_boss_dps"] + w * cr["own_norm_dps"], own_boss_dps=cr["own_boss_dps"], own_normal_dps=cr["own_norm_dps"],
                effects_dps=self.companion_dps - ((1 - w) * cr["own_boss_dps"] + w * cr["own_norm_dps"]),
                effects_boss_dps=cr["comp_boss_dps"] - cr["own_boss_dps"], effects_normal_dps=cr["comp_norm_dps"] - cr["own_norm_dps"],
                best_candidate=cr["best"], summon_time_s=cr["s"], window_s=cr["W"],
                details={k: v for k, v in cr.items() if isinstance(v, (int, float, str, bool))},
            )
        boss = self.pb_total + (companion["boss_dps"] if companion else 0.0)
        normal = self.pn_total + (companion["normal_dps"] if companion else 0.0)
        art = self.art_effects.report()
        if self.typed_info is not None and (self.typed_info["base"] or self.typed_info["notes"]):
            art["typed"] = dict(includes_artifacts=True, notes=list(self.typed_info["notes"]), typed=dict(self.typed_info["typed"]),
                                base=dict(self.typed_info["base"]), amounts={k: dict(v) for k, v in self.typed_info["amounts"].items()})
        art.update(horn_flute_uptime=self.art_ctx.horn_uptime, extra_boss_multiplier=self.extra_boss, extra_normal_multiplier=self.extra_norm,
                   hexagon_charm=dict(hex_per_stack=self.art_pre.hex_v, hex_average=self.art_pre.hex_avg, charm_full=self.art_pre.charm_val,
                                      charm_average=self.art_pre.charm_avg, phase_factor_boss=self.ph_b, phase_factor_normal=self.ph_n))
        return dict(
            total_dps=total,
            artifacts=art,
            player_dps=self.player_dps,
            boss_dps=boss,
            normal_dps=normal,
            player_boss_dps=self.pb_total,
            player_normal_dps=self.pn_total,
            skills=rows,
            companion=companion,
            engine_on=self.status_on,
            engine=dict(casts=dict(self.engine_n), phi_unif=self.phi_unif, phi_rows=dict(self.phi_rows)) if self.status_on else None,
            derived=dict(
                attack=self.attack, stat_damage=self.stat_damage, actions_per_second=self.actions_per_second, cast_rate=self.cast_rate,
                **self.derived_extra(),
                stunned_share_boss=self.stf_b, stunned_share_normal=self.stf_n,
                # computed Inputs rows
                monster_type=self.monster_type, chapter=self.content.chapter, stage=self.content.stage,
                breakthrough_normal_weight_pct=self.content.breakthrough_normal_weight_pct,
                breakthrough_stage_index=self.content.breakthrough_stage_index, monster_defense=self.monster_defense,
                fight_duration=self.fight_duration, normal_weight=self.normal_weight, fixed_duration_active=self.fixed_duration_active,
            ),
        )

    # ---- helpers shared by several (not all) classes ----
    def haste(self, base, haste):
        """Cooldown with a level-gated haste factor: ``(base * factor) if level >= threshold else base``."""
        return (base * haste[1]) if haste and self.level >= haste[0] else base

    def maple_mult(self, key):
        if key not in self.DATA.MAPLE_TARGETS:
            return 1.0
        return 1 + (self.DATA.MAPLE_TARGETS[key] / 10) * (self.maple_factor / 1000) / 100

    def monster_blend(self, boss_val, normal_val):
        if self.monster_type == "pvp":
            return boss_val
        return (1 - self.normal_weight) * boss_val + self.normal_weight * normal_val

    def passive_pct(self, key):
        """A passive's own contribution - 0 while locked."""
        p = self.DATA.PASSIVES[key]
        return self.coeff_pct(p["base"], p["fidx"], p["scales"], p["job_step"]) if self.unlocked(key) else 0.0

    def tier(self, spec):
        """Resolve a ``(default, (threshold, value))`` tier at the character's level; a plain value is returned unchanged."""
        if isinstance(spec, tuple):
            default, (threshold, value) = spec
            return value if self.level >= threshold else default
        return spec

    def cast_rate_py(self, key):
        """Casts per second of an action-costing skill: the engine's count with the engine on, else the exact / steady-state count."""
        if key in self.engine_n and self.fight.fixed_duration_active:
            return self.engine_n[key] / self.fight_duration
        eff = self.fight.eff_cooldown(self.skills[key]["cooldown"], self.skills[key]["costs_action"])
        return self.fight.non_buff_casts(eff) / self.fight_duration if self.fight.fixed_duration_active else 1 / eff

    def buff_avg(self, pct, duration, cooldown, costs_action):
        return pct * self.fight.buff_uptime(cooldown, duration, costs_action)

    def branch_multipliers(self, mastery_boss, mastery_normal, targets):
        """(boss branch, normal branch) multiplier of a row: each branch gets its own full (1+damage%/100) [x target count for normal]."""
        # outside the Boss/Normal Damage% buckets the artifacts add boss-only / normal-only multipliers (Reindeer's Spear, Contract of Darkness,
        # branch Final Damage), applied even in PvP (extra_boss / extra_norm are exactly 1.0 with no such artifact equipped)
        if self.monster_type == "pvp":
            return 1.0 * self.extra_boss, 1.0 * self.extra_norm
        targets = min(targets, self.fight.max_enemies_hit)
        boss_term = self.boss_damage + mastery_boss + self.monster_dmg_bonus + self.art_boss_damage
        normal_term = self.normal_damage + mastery_normal + self.monster_dmg_bonus + self.art_normal_damage
        return (1 + boss_term / 100) * self.extra_boss, (1 + normal_term / 100) * targets * self.extra_norm
