"""Status Effect Damage / KO timeline engine, pass 2 (every class): the cast groups handed to ``src/status_timeline.py`` ``solve`` and the
bookkeeping of its result."""
import status_timeline as stl  # noqa: E402  (src/status_timeline.py through the engine._src shim)


def build_groups(D, unlocked, SKILLS, percast, window_of, cd_of, stun_keys=None, slot_of=None):
    """The timeline's cast groups (``D.STATUS_GROUPS``): per group the damage rows one cast of ``cast`` feeds (weight of one cast = ``percast``),
    the cast's effective cooldown ``cd_of(cast)``, whether it takes an action slot (``slot_of(gid)``, default yes) and - with ``stun_keys``, the
    player's own stun skills - whether the cast is fixed at t = 0 (a stun skill is cast on cooldown from the start)."""
    groups = []
    for gid, cast, ents in D.STATUS_GROUPS:
        entries = []
        for row, typ, win, gate, wk in ents:
            wt = percast(wk)
            if gate and not unlocked(gate):
                wt = 0.0
            entries.append(dict(row=row, typ=typ, w=wt, L=(window_of(SKILLS[win]["window"]) if win else 1),
                                on=(1 if (not gate or unlocked(gate)) else 0)))
        group = dict(id=gid, cd=cd_of(cast), on=unlocked(cast), slot=True if slot_of is None else slot_of(gid), entries=entries)
        if stun_keys is not None:
            group.update(fixed=cast in stun_keys, t0=0.0)
        groups.append(group)
    return groups


def solve_groups(m, D, eng_host, groups, c_slot, engine_n, sens, reuse_strip=True):
    """Pass 2: solve the strip with the groups (Sensitivity may reuse the main strip: ``sens["strip"]``), record the casts of every group row in
    ``engine_n`` and the timing factors on the model (``phi_rows`` / ``phi_unif``).  Returns the strip."""
    E_ENGINE = sens["strip"][1] if (reuse_strip and "strip" in sens) else stl.solve(dict(eng_host, groups=groups, c_slot=c_slot))   # (Sensitivity: main strip reuse)
    for row, pfx in D.STATUS_CAST_PREFIX.items():
        if pfx.startswith("grp."):
            engine_n[row] = E_ENGINE["groups"][pfx[4:]]["n"]
    m.phi_rows = E_ENGINE["rows"]
    m.phi_unif = E_ENGINE["phi_unif"]
    return E_ENGINE
