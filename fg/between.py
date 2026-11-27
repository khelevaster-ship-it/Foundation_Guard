"""FoundationGuard: guard files changed between two helper steps (AI-made, Claude, 2026-11-13; outside review 6,
findings 2 and 6, Grok, and its fix plan).

Until now every change made outside a step was taken as the owner's (F245), and while a background job might still run
(up to two hours) every change was taken as the job's (F246). Grok showed both holes: a script's delayed write of the
kit's record "this commit passed" was taken as the owner's, and the owner's own save during a job's timer was put back.
Now a change between steps is judged by its kind (fg/tiers.py), with or without a job running (the owner's yes, 13 Nov):

  - a record (only the kit writes those, through its record door) is put back;
  - a switch (the kit's settings, its code, hooks, the AI tools' hook wiring) is put back, unless it is exactly as the
    remote branch has it (the owner pulled a kit update); a change of permission rules only in the AI tool's settings
    is the owner's;
  - the owner's own files stay; a change that is more than new tests (or spaces) is also held, so the upload waits for
    the owner's yes (python fg/ownerok.py lists it).

Limits: a program can call the record door itself, or rewrite the kit's record of the accepted state. A write that lands
while a later step is running is judged as that step's.
"""
import os, time

import door as D
import tiers as T

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
SAID = "between_said"


TIPS = {}                                                # the remote's branch tips, looked up once per judging


def judge(cfg, st, now, changed, SP):
    """Judge each changed file; st (the accepted state) is updated and saved by the caller."""
    import catches as CL
    TIPS.clear()
    base, news = st["files"], st.setdefault("news", [])
    said = st.setdefault(SAID, [])
    gh = SP.github_copy(cfg, changed, now)               # team mode: exactly as GitHub has it is never judged
    for r in changed:
        k = T.kind(r, cfg)
        if r in gh:
            _take(cfg, r, base, now, SP)
            CL.log(cfg, "as on GitHub", f"{r} is exactly as GitHub has it; taken as it is", "", "the check after every step")
            continue
        if k != "record" and SP.yes_of_a_step(cfg, os.path.join(cfg["_root"], r)):
            _take(cfg, r, base, now, SP)                # the owner's yes in a step's box, though its check after didn't run
            CL.log(cfg, "kept", f"{r}: the owner said yes in the kit's box for this change (the check after that step "
                   "didn't run in this session: start a new session so it does)", "", "the check after every step")
            continue
        if k == "record" and not BREAK("records_door_only"):
            _back(cfg, r, base, now, SP, news, said, "the kit's own record; only the kit writes it")
        elif k == "switch" and not BREAK("between_switches") and not _blessed_first(cfg, r, base, now) \
                and not _owners_switch(cfg, r, base, now, SP):
            _back(cfg, r, base, now, SP, news, said, "it can switch the kit off; if you made it yourself, keep it with "
                  f"python fg/steps.py --keep {r} (the kit's box asks you), or ask the helper and say yes in the box")
        elif T.gate_record(r, cfg):                     # the project's gate wrote it (a pass file): taken, not held
            _take(cfg, r, base, now, SP)
        else:
            held = _hold(cfg, r, base, now, SP)
            _take(cfg, r, base, now, SP)
            CL.log(cfg, "changed between steps", f"{r} changed while no helper step was running; the kit assumed it was you and kept it"
                   + ("; the upload waits for the owner's yes (python fg/ownerok.py)" if held else ""), "",
                   "the check after every step")
            news.append({"when": time.strftime("%Y-%m-%d %H:%M"), "what": "changed outside any helper step", "file": r, "kept": ""})


def _back(cfg, r, base, now, SP, news, said, why):
    import catches as CL
    ok, kept = SP._put_back(cfg, r, base.get(r), now[r])
    text = f"{r} changed outside any helper step and was {'put back' if ok else 'NOT put back'} ({why})"
    CL.log(cfg, "put back" if ok else "not put back", text + (f"; the changed copy is kept in {kept}" if kept else ""), "",
           "the check after every step")
    news.append({"when": time.strftime("%Y-%m-%d %H:%M"), "what": "put back" if ok else "could not put back", "file": r,
                 "kept": kept or ""})
    said.append(text)
    if not ok:
        _take(cfg, r, base, now, SP)                   # told once: what couldn't be put back isn't judged again


def _take(cfg, r, base, now, SP):
    SP._keep(cfg, [r] if now[r].get("id") else [])
    if now[r].get("id"):
        base[r] = now[r]
    else:
        base.pop(r, None)


def _blessed_first(cfg, r, base, now):
    """The owner's own kit command wrote it (fg/door.py), read from the kit's own record. The game's PC, 27 Nov: after
    the owner's kit update changed 12 files, each was first looked up on the remote (up to 8 s each) before this quick
    check was reached, so every helper step ran past the guard's 20 s and was refused. The quick check now comes first."""
    if BREAK("between_door_first"):
        return False
    return D.blesses(cfg, r, base.get(r), now[r])


def _owners_switch(cfg, r, base, now, SP):
    """A switch the owner may change outside a step: exactly as a remote branch has it (a kit update pulled), or the AI
    tool's settings with only their permission rules changed."""
    was, new = SP._old_and_new(cfg, r, base.get(r))
    if new is not None and was is not None and SP._only_permission_rules(r, was or b"{}", new):
        return True
    return _as_remote(cfg, r, now, SP) or _as_the_owner_made_it_elsewhere(cfg, r, now, SP)


def _as_the_owner_made_it_elsewhere(cfg, r, now, SP):
    """Exactly as another copy of this project holds it now, where the owner's own kit command wrote it (a door line,
    fg/door.py) and the kit accepted it. The game's PC, 20 Nov: the owner updated the kit in the working copy and
    committed it; before it was uploaded, the nightly's checkout moved its run folder (a worktree) to that commit, and
    the kit put the six old kit files back there, so the night refused its folder as not clean."""
    if BREAK("between_owner_elsewhere") or not now[r].get("id") or r.startswith(".git/"):
        return False
    import proofstore as PS
    for c in SP._copies(cfg):
        try:
            if os.path.samefile(c["_root"], cfg["_root"]):
                continue
            there = SP._entry(os.path.join(c["_root"], r)).get("id")
            kept = (((SP._state(c) or {}).get("files") or {}).get(r) or {}).get("id")
            if not there or kept != there or (there != now[r]["id"] and not _same_but_line_endings(cfg, c, r)):
                continue
            if any(not x.get("_bad") and x.get("path") == r.replace("\\", "/") and x.get("after") == there
                   for x in PS.read(c, D.BOOK)):
                return True
        except (OSError, KeyError, TypeError, ValueError):
            continue
    return False


def _as_remote(cfg, r, now, SP):
    """Exactly as a remote branch has it now (a removal: gone there and from this copy's own last commit too). Never a
    file in git's own folder, which no remote has."""
    root = cfg["_root"]
    if r.startswith(".git/"):
        return False
    if not now[r].get("id") and SP._blob_at(root, "HEAD", r):
        return False
    gid = SP._as_git(root, [r], now).get(r) if now[r].get("id") else None
    if root not in TIPS or BREAK("between_remote_once"):      # one look at the remote for all the files (27 Nov)
        try:
            import ownerok as OK
            TIPS[root] = list((OK._remote_heads(root) or {}).values())
        except Exception:
            TIPS[root] = []
    tips = TIPS[root]
    if not tips:
        return False
    p = SP._git(root, "cat-file", "--batch-check=%(objectname)", data=("\n".join(f"{t}:{r}" for t in tips) + "\n").encode())
    got = p.stdout.decode("utf-8", "replace").splitlines() if p and p.returncode == 0 else []
    return (gid in got) if gid else any(g.endswith(" missing") for g in got)


def _same_but_line_endings(cfg, c, r):
    """The two copies' files differ only in line endings (F516: git checks a file out with Windows line endings in one
    folder while the owner's update wrote plain ones in the other; the game's PC, 20 Nov)."""
    if BREAK("between_elsewhere_line_endings"):
        return False
    plain = lambda root: open(os.path.join(root, r), "rb").read().replace(b"\r\n", b"\n")
    return plain(cfg["_root"]) == plain(c["_root"])


def _hold(cfg, r, base, now, SP):
    """The owner's own change that is more than new tests or spaces waits for the owner's yes at the upload."""
    if BREAK("between_held"):
        return False
    if SP._free_now(cfg, r, base, now):
        return False
    was, new = SP._old_and_new(cfg, r, base.get(r))
    import layout as LY
    if was and new is not None and LY.only_layout(r, was, new):
        return False
    gid = SP._as_git(cfg["_root"], [r], now).get(r) if now[r].get("id") else "deleted"
    hp = os.path.join(SP._dir(cfg), "held.json")
    h = SP._read_json(hp, {}) or {}
    h[r] = gid
    SP._write_json(hp, h)
    return True

