"""FoundationGuard: the owner's OK for a changed guard file (AI-made, Claude, 2026-11-11; after the Godot game test).

The Godot game test (11 Nov) found that an upload went through after a helper switched the secret scan off, took
a file out of the size check, or made a test weaker, whenever the editing hook was not running to ask the owner. Now
the upload itself stops on such a change until the owner has said yes, in a terminal, for that exact version of the file.

Which changes need the owner's OK:
  - any change to the kit's own code and settings (foundationguard.json, fg/, the AI tools' hook settings);
  - a change to any other guard file or to a test that makes a check weaker (a removed check, a raised limit, a skip);
  - with "gather_asks" on (fg/adds.py), every change to the owner's own guard files that is not only new tests, since
    those went through without a box.
Adding rows to a list, or a change that makes nothing weaker, needs no OK.

  python fg/ownerok.py           list the changes in this upload that need the owner's OK, and which have it
  python fg/ownerok.py --give    the OWNER gives the OK. Run by a helper, the kit's hook opens the AI tool's own
                                 permission box and the owner says yes there; nothing else is needed. Without the
                                 hook running, it needs a real terminal, where the owner types a short code it shows.
                                 A helper can't answer the box. The OK covers that version of each file only:
                                 change the file again and the OK is gone.
An upload a helper runs (fg/push.py, or the project's push_command) that is missing a yes opens the same box itself,
and the yes there is recorded by the upload: nothing else to run.
Every OK is written to the change report. Limit: someone who sets out to fake a terminal can still do it; the server
check (a locked main branch on GitHub) is the lock that holds even then.
"""
import json, os, random, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import paths as P

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
KIT_CODE = ["foundationguard.json", "fg/**", ".claude/**", ".git/hooks/**", ".github/**", ".codex/**", ".cursor/**",
            "AGENTS.md", "REVIEW_PROMPT.md"]
OK_FILE = "owner_ok.json"


def _git(root, *a):
    return subprocess.run(["git"] + list(a), cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")


def upload_range(cfg):
    """What this upload sends: from this branch's copy on the remote, or (a new branch) from where it left the remote's
    main line. Never a commit recorded for another branch (the Godot game test: a weakening undone was called
    weaker because it was compared with the wrong branch)."""
    root = cfg["_root"]
    br = _git(root, "branch", "--show-current").stdout.strip()
    if BREAK("ownerok_range"):
        import secretscan as SS
        return SS.default_range(cfg)
    heads = None if BREAK("ownerok_remote") else _remote_heads(root)
    if heads is not None:                            # read from the remote itself, not this copy's record of it
        tip = heads.get(br) if br else None
        if tip and not _have(root, tip):             # the remote's branch holds a commit this copy hasn't: fetch it
            _git(root, "fetch", "-q", "origin", f"refs/heads/{br}")
        if tip:                                      # (still missing: the push can't land either, it isn't a fast-forward)
            return f"{tip}..HEAD" if _have(root, tip) else None
        best = _nearest(root, list(heads.values()))
    else:                                            # the remote can't be reached: the last copy of it read here
        if br and _git(root, "rev-parse", "--verify", "-q", f"origin/{br}").returncode == 0:
            return f"origin/{br}..HEAD"
        best = _nearest_on_remote(root)
    if best:
        return best + "..HEAD"
    import steps as SP                                 # nothing on the remote yet: the last passed commit, if it is in
    last = SP.passed(cfg)                              # this history and the kit recorded it (review 6, F265)
    if last and _git(root, "merge-base", "--is-ancestor", last, "HEAD").returncode == 0:
        return last + "..HEAD"
    return None


def _remote_heads(root):
    """{branch: commit} as the remote has them now, or None when it can't be reached. Outside review 3 (Claude, 12 Nov,
    finding 4): the upload was measured from the local copy of the remote branch, which git fetch . HEAD:refs/remotes/
    origin/BR moves, so a weakened test gathered at night went up with no yes. The remote's own answer can't be moved
    from here."""
    # 15 Nov: the game's PC still held the owner's old git login; ls-remote waited for a sign-in nobody could see, for
    # longer than the kit's 20 s, so every step timed out and a play copy moved to the new main was put back. It may
    # never ask for a login, and gives up after 8 s ("can't be reached", which trusts nothing new).
    quiet = {} if BREAK("remote_heads_waits") else {"GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
    if BREAK("remote_heads_waits"):
        try:
            p = subprocess.run(["git", "ls-remote", "--heads", "origin"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            return None
        code, text = p.returncode, p.stdout
    else:
        code, text = _limited(["git", "ls-remote", "--heads", "origin"], root, dict(os.environ, **quiet), 8)
    if code != 0:
        return None
    out = {}
    for line in text.splitlines():
        sha, _, ref = line.partition("\t")
        if ref.startswith("refs/heads/"):
            out[ref[len("refs/heads/"):]] = sha.strip()
    return out


def _limited(cmd, cwd, env, seconds):
    """(exit code, output) of a command stopped, with everything it started, after so many seconds; (None, "") then.
    A plain timeout stops git but on Windows still waits for what git started (a login helper, a transport)."""
    import tempfile
    win = os.name == "nt"
    with tempfile.TemporaryFile() as out:
        try:
            p = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=out, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                 **({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if win else {"start_new_session": True}))
        except OSError:
            return None, ""
        try:
            p.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            if win:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
            else:
                import signal
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except OSError:
                    pass
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            return None, ""
        out.seek(0)
        return p.returncode, out.read().decode("utf-8", "replace")


def _have(root, sha):
    return _git(root, "cat-file", "-e", sha + "^{commit}").returncode == 0


def _nearest(root, commits):
    """The newest commit of this history that one of these remote commits holds (a new branch's starting point)."""
    bases = {_git(root, "merge-base", c, "HEAD").stdout.strip() for c in commits if _have(root, c)} - {""}
    depth = lambda c: int(_git(root, "rev-list", "--count", c).stdout.strip() or 0)
    return max(sorted(bases), key=depth) if bases else None


def _nearest_on_remote(root):
    """A new branch: the newest commit of this history that is already on the remote (its nearest remote branch)."""
    refs = _git(root, "for-each-ref", "--format=%(refname)", "refs/remotes/origin").stdout.split()
    bases = {_git(root, "merge-base", r, "HEAD").stdout.strip() for r in refs if not r.endswith("/HEAD")} - {""}
    depth = lambda c: int(_git(root, "rev-list", "--count", c).stdout.strip() or 0)
    return max(sorted(bases), key=depth) if bases else None


_BLOBS = {}       # (folder, "rev:path") -> (git's id or None, text or None): one process, one look per version


def _prefetch(root, specs):
    """Read these versions ("rev:path") with one git call. The game's PC, 26 Nov: after a merge of 38 test files the
    owner-OK list made about three git calls a file, past the AI tool's 20 s limit for the guard on Windows, so the
    upload was blocked (F554)."""
    todo = [x for x in dict.fromkeys(specs) if (root, x) not in _BLOBS and "\n" not in x]
    if not todo or BREAK("ownerok_batch"):
        return
    p = subprocess.run(["git", "cat-file", "--batch"], cwd=root, capture_output=True,
                       input=("\n".join(todo) + "\n").encode("utf-8"))
    if p.returncode != 0:
        return
    out, i = p.stdout, 0
    for x in todo:
        j = out.find(b"\n", i)
        if j < 0:
            return
        head = out[i:j].decode("utf-8", "replace").split()
        if len(head) == 3 and head[1] in ("blob", "tree", "commit", "tag"):
            n = int(head[2])
            body = out[j + 1:j + 1 + n].decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
            _BLOBS[(root, x)] = (head[0], body if head[1] == "blob" else None)
            i = j + 1 + n + 1
        else:
            _BLOBS[(root, x)] = (None, None)
            i = j + 1


def _blob(root, spec):
    _prefetch(root, [spec])
    if (root, spec) in _BLOBS:
        return _BLOBS[(root, spec)]
    r = _git(root, "rev-parse", "-q", "--verify", spec)
    oid = r.stdout.strip() or None
    t = _git(root, "show", spec) if oid else None
    return oid, (t.stdout if t is not None and t.returncode == 0 else None)


def _old_new(root, rng, f):
    base = rng.split("..")[0]
    return (_blob(root, f"{base}:{f}")[1] or ""), (_blob(root, f"HEAD:{f}")[1] or "")


def _version(root, f):
    return _blob(root, f"HEAD:{f}")[0] or "deleted"


def _kit_is_new(root, rng):
    """True for the upload that puts the kit into the project: its files have no "before" to be weaker than."""
    has = lambda rev: _git(root, "cat-file", "-e", rev + ":fg/guard.py").returncode == 0
    return has("HEAD") and not has(rng.split("..")[0])


LESS = "This check now CATCHES LESS: "             # round 9 follow-up: a weaker check is named as one, first


def _why(cfg, f, old, new):
    """Why a changed file needs the owner's OK, or None."""
    import ledgers as LG
    reasons = LG.weaker(cfg, f, old, new)
    if reasons:                                  # the kit's own code: its line rules guess (the game's PC, 13 Nov: a moved
        kit = P.matches(f, KIT_CODE) and not BREAK("ownerok_kit_maybe")      # line in push.py read as CATCHES LESS)
        return ("" if BREAK("ownerok_less") else KIT_MAYBE if kit else LESS) + "; ".join(reasons[:3])
    if P.matches(f, KIT_CODE) and old != new:
        return "the kit's own code or settings changed"
    return None


def needing_ok(cfg, rng=None):
    """[(file, why, version)] for every change in this upload that needs the owner's OK, and the tests that stopped
    running since the last pass (round 8, fg/ranbefore.py)."""
    import ranbefore as RB
    return _changed_files(cfg, rng) + RB.items(cfg)


def _changed_files(cfg, rng):
    import cards as CD
    root = cfg["_root"]
    rng = rng or upload_range(cfg)
    if not rng or BREAK("ownerok_off") or _kit_is_new(root, rng):
        return []
    changed = [f for f in _git(root, "diff", "--name-only", rng).stdout.split("\n") if f]
    globs = C.guard_globs(cfg)
    base = rng.split("..")[0]
    for k in [k for k in _BLOBS if k[0] == root and not k[1].startswith(base + ":")]:
        del _BLOBS[k]                                   # HEAD may have moved since the last list: read it again
    _prefetch(root, [x for f in changed if P.matches(f, globs) or CD.TEST_FILE.search(f) or CD.approved_check_file(f)
                     for x in (f"{base}:{f}", f"HEAD:{f}")])
    gathered = _gathered(cfg, root, rng)
    out = []
    for f in changed:
        guarded = P.matches(f, globs) or CD.TEST_FILE.search(f)
        if not (guarded or CD.approved_check_file(f)):
            continue
        old, new = _old_new(root, rng, f)
        why = guarded and (_why(cfg, f, old, new) or (gathered and _not_only_adds(cfg, f, old, new)))
        if not why and not BREAK("approved_check_ok"):          # the game, 15 Nov: the owner said yes, and the kit had
            why = "; ".join(CD._approved_check_changed(cfg, f, old, new))   # no way to take it; the helper moved code
        if why and not _owner_wrote(cfg, root, f):
            out.append((f, why, _version(root, f)))
    return _with_held(cfg, root, changed, out)


def _owner_wrote(cfg, root, f):
    """The file is exactly as the owner's own kit command wrote it (a door line, fg/door.py: their terminal, or their
    yes in the kit's box for that command). The game's PC, 20 Nov: the owner updated the kit himself in his own window,
    and the upload then asked his yes for "what the helper changed", marked "MAY now CATCH LESS". He already said yes
    to exactly this content, so it is not asked again."""
    if BREAK("ownerok_owner_wrote"):
        return False
    try:
        import door as D
        import proofstore as PS
        import steps as SP
        if _git(root, "diff", "--quiet", "HEAD", "--", f).returncode != 0:
            return False                                # changed again since the commit: judged as any change
        now = SP._entry(os.path.join(root, f)).get("id")
        return bool(now) and any(not x.get("_bad") and x.get("path") == f and x.get("after") == now
                                 for x in PS.read(cfg, D.BOOK))
    except Exception:
        return False


HELD = "changed and committed in one step without your yes (the kit put the file back on disk)"


def _with_held(cfg, root, changed, out):
    """12 Nov: a file changed and committed in one step without a yes is listed, its held note first."""
    import steps as SP
    for f, v in SP.held(cfg).items():
        if f in changed and _version(root, f) == v:
            out = [x for x in out if x[0] != f] + [(f, HELD + "".join("; " + x[1] for x in out if x[0] == f), v)]
    return out


def _gathered(cfg, root, rng):
    """Were the owner's asks being gathered for this upload (now, or in the settings it started from)? Then every change
    to a guard file that went through without a box is listed here for the owner's one yes (fg/adds.py)."""
    if BREAK("gather_upload"):
        return False
    try:
        before = json.loads(_old_new(root, rng, "foundationguard.json")[0] or "{}")
    except ValueError:
        before = {}
    import review as RV
    return bool(cfg.get("gather_asks") or RV.on(cfg) or (isinstance(before, dict) and before.get("gather_asks")))


def _same_text(root, a, b):
    """Two git versions hold the same text (line endings ignored: a Windows checkout may store them either way)."""
    if not a or not b or b == "deleted":
        return False
    if a == b:
        return True
    get = lambda v: _git(root, "cat-file", "blob", v)
    x, y = get(a), get(b)
    if x.returncode or y.returncode:
        return False
    return x.stdout.replace("\r\n", "\n") == y.stdout.replace("\r\n", "\n")


def _boxed(cfg, f, v):
    """The game's PC, 23 Nov 20:34 UTC: the owner allowed a foundationguard.json edit in the box (the box said it may
    catch less), and the upload asked his yes again; F532 had carried a box yes over only for gathered changes. Any
    version the owner's box let through counts as his yes at the upload, once: the upload that carries it uses it up
    (fg/push.py) (F540)."""
    if BREAK("box_yes_any"):
        return False
    import steps as SP
    return _same_text(cfg["_root"], SP.box_yes(cfg).get(f), v)


def used_box_yeses(cfg, todo):
    """After an upload: the box yeses it carried are used up, so they can't cover the same text again later (F540)."""
    import steps as SP
    try:
        book = SP.box_yes(cfg)
        left = {f: v for f, v in book.items() if not any(f == t[0] and _same_text(cfg["_root"], v, t[2]) for t in todo)}
        if left != book:
            SP._write_json(os.path.join(SP._home(cfg), SP.BOX_YES), left)
    except Exception:
        pass


def give_in_terminal(cfg):
    """The game's PC, 23 Nov 21:07 UTC: the owner ran the upload in his own window, and it stopped with "1 decision for
    you" and no way to give the yes there. In the owner's own terminal the upload now asks the typed yes itself (F541)."""
    import door as D
    if BREAK("upload_typed_yes") or not (D.terminal() or BREAK("ownerok_tty")):
        return False
    todo = missing(cfg)
    if not todo or not _typed_yes(cfg, todo):
        return False
    import ledger as LG
    LG.grant(cfg, todo, "terminal", "\n".join(explain(cfg, todo)))
    import catches as CL
    CL.log(cfg, "owner ok", "owner said yes in a terminal at the upload to: " + ", ".join(f for f, _, _ in todo))
    print("OWNER-OK: recorded (your typed yes at this upload).")
    return True


def _not_only_adds(cfg, f, old, new):
    import adds as AD
    if not (P.matches(f, C.guard_globs(cfg)) and AD.owners_own(cfg, f)):
        return None                                  # the kit's own files asked at once; they were never gathered
    import steps as SP
    if not BREAK("box_yes_kept") and _same_text(cfg["_root"], SP.box_yes(cfg).get(f), _version(cfg["_root"], f)):
        return None                                  # the owner already said yes to exactly this in the box (23 Nov)
    why = AD.only_adds(f, old, new, cfg)
    return (_maybe_less(f, old, new) + "changed while your asks were gathered: " + why) if why else None


MAYBE_LESS = "This check MAY now CATCH LESS (a check line changed and the kit can't tell): "
KIT_MAYBE = "The kit's own code MAY now CATCH LESS (the kit judges its own code by line rules that can be wrong): "


def _maybe_less(f, old, new):
    """Round 9 follow-up: in the away walkthrough a changed check line the kit can't judge is flagged too, not hidden."""
    import weaken as W
    return "" if BREAK("ownerok_less") or not any(r.startswith(W.UNSURE) for r in W.for_the_box(f, old, new)) else MAYBE_LESS


def given(cfg):
    """{item: version} for the owner's OKs that still count (fg/ledger.py: the exact version, not run out, not used up,
    not replaced, and as the kit wrote it)."""
    import ledger as LG
    return LG.live(cfg)


def missing(cfg, rng=None):
    """The changes that still need the owner's OK (an OK for an older version of the file does not count)."""
    ok = given(cfg)
    has = (lambda f, v: f in ok) if BREAK("ownerok_version") else (lambda f, v: ok.get(f) == v or _boxed(cfg, f, v))
    import review as RV
    todo = [(f, why, v) for f, why, v in needing_ok(cfg, rng) if not has(f, v)]
    done = RV.passed(cfg, todo)                      # the reviewer's PASS stands in for the owner's yes (the owner, 16 Nov)
    return [(f, why + ((". " + RV.words_for(cfg, f, v)) if RV.words_for(cfg, f, v) else ""), v)
            for f, why, v in todo if f not in done]


def card(items):
    lines = "; ".join(f"{f} ({why})" for f, why, _ in items[:4]) + ("; and more" if len(items) > 4 else "")
    import ranbefore as RB
    gone = any(f == RB.ITEM for f, _, _ in items)
    title = ("Tests that passed before didn't run, and that needs your yes before it is uploaded" if len(items) == 1 and gone
             else "A guard was changed and needs your yes before it is uploaded")
    return {"who": "you", "title": title,
            "happened": lines + ".",
            "means": "A helper changed something that guards your project, so it may catch less from now on.",
            "action": "Not uploaded. If you asked for this, tell the helper \"yes, ask me\": it runs "
                      "python fg/ownerok.py --give and a permission box asks you; or run the upload in your own window "
                      "and type the code it shows. If you did not, tell the helper \"no, put it back\".",
            "evidence": [f for f, _, _ in items]}


NOTE = "ownerok_asking"
NOTE_SECONDS = 1800        # the game's PC, 16 Nov: a yes given after 2 minutes in the box was lost, and --give fell to a
                           # typed code; the note is now cleared by the next helper step instead (fg/guard.py)


def write_note(cfg):
    """Written by the guard hook just before it asks the owner in the AI tool's permission box."""
    p = os.path.join(cfg["_root"], cfg.get("state_dir", ".foundationguard"), NOTE)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(str(time.time()))
    _recorded(cfg, [p])


def _recorded(cfg, paths):
    """The owner's yes and its one-time note go through the kit's record door (review 6, F265): written any other way
    between two helper steps, they are put back."""
    import steps as SP
    SP.recorded(cfg, paths)


def clear_note(cfg):
    p = os.path.join(cfg["_root"], cfg.get("state_dir", ".foundationguard"), NOTE)
    if os.path.exists(p):
        try:
            os.remove(p)
            _recorded(cfg, [p])
        except OSError:
            pass


def _take_note(cfg):
    """True (and the note is used up) when the hook asked the owner moments ago."""
    p = os.path.join(cfg["_root"], cfg.get("state_dir", ".foundationguard"), NOTE)
    try:
        with open(p) as f:
            fresh = time.time() - float(f.read().strip()) < (120 if BREAK("owner_note_short") else NOTE_SECONDS)
        os.remove(p)
        _recorded(cfg, [p])
        return fresh
    except (OSError, ValueError):
        return False


def _kind(f):
    import cards as CD
    import ranbefore as RB
    if f == RB.ITEM:
        return "tests that stopped running"
    if P.matches(f, KIT_CODE):
        return "the kit's own code or settings"
    return "a test" if CD.TEST_FILE.search(f) else "a file that guards your project"


def _helper_words(root, rng, f):
    """What the helper wrote in its commit messages for this file (its own words; the kit doesn't check them)."""
    if not rng:
        return ""
    subjects = [s for s in _git(root, "log", "--format=%s", rng, "--", f).stdout.split("\n") if s.strip()]
    return " / ".join(dict.fromkeys(subjects[:3]))


def _size(root, rng, f):
    parts = _git(root, "diff", "--numstat", rng, "--", f).stdout.split() if rng else []
    if len(parts) < 2 or not parts[0].isdigit():
        return ""
    return f" ({parts[1]} line(s) taken out, {parts[0]} added)"


def explain(cfg, todo, rng=None):
    """the owner, 13 Nov: before the code, say in plain words what the owner is saying yes to: each item, what kind of thing it
    is, what changed and the helper's own reason from its commit."""
    if BREAK("ownerok_explain"):
        return [f"  {f}: {why}" for f, why, _ in todo]
    root, rng = cfg["_root"], rng or upload_range(cfg)
    out = []
    for i, (f, why, _) in enumerate(todo, 1):
        words = _helper_words(root, rng, f) if _kind(f) != "tests that stopped running" else ""
        out += [f"{i}. {f}: {_kind(f)}", f"   What changed: {why}{_size(root, rng, f)}",
                f"   The helper's reason, from its commit (its own words, not checked): {words}" if words else
                "   The helper gave no reason in its commit. Ask it why before you say yes."]
        if rng and _kind(f) != "tests that stopped running":
            out.append(f"   To see every line of it, ask your helper to show you:  git diff {_short(rng)} -- {f}")
    return out


def _short(rng):
    import re
    return re.sub(r"\b([0-9a-f]{9})[0-9a-f]{31}\b", r"\1", rng)


def brief(cfg, todo):
    """One line per item for the permission box: what it is, what changed and the helper's reason."""
    if BREAK("ownerok_explain"):
        return "; ".join(f"{f} ({why})" for f, why, _ in todo[:4])
    rng = upload_range(cfg)
    items = [_brief_one(cfg["_root"], rng, f, why) for f, why, _ in todo[:4]]
    return "; ".join(items) + ("; and more" if len(todo) > 4 else "")


def _few(why):
    """The game's PC, 21 Nov 12:50 UTC: the upload's box named all 28 approvals whose row moved in a record file, one
    after another, and the owner had to scroll (his rule: never scroll the box). The box names the first and counts
    the rest; the owner's window (python fg/ownerok.py) still lists every one."""
    if BREAK("brief_many_reasons"):
        return why
    parts = [p for p in str(why).split("; ") if p]
    if len(parts) > 2:
        why = f"{parts[0]}; and {len(parts) - 1} more like it (python fg/ownerok.py lists them all)"
    return why if len(why) <= 260 else why[:257].rstrip() + "..."


def _brief_one(root, rng, f, why):
    why = _few(why)
    words = _helper_words(root, rng, f)
    reason = f"; the helper's reason: {words}" if words else ""
    return f"{f} ({_kind(f)}: {why}{reason})"


def _typed_yes(cfg, todo):
    print(f"WHAT YOU ARE SAYING YES TO ({len(todo)} item(s)). Each one guards your project, so it may catch less afterwards:")
    for line in explain(cfg, todo):
        print(line)
    print("Say yes only if you asked for all of these. If any surprises you, say no and ask your helper about it.")
    code = "".join(random.choice("ABCDEFGHJKMNPQRSTUVWXYZ") for _ in range(4))
    try:
        return input(f"To say yes, type {code} and press Enter (anything else says no): ").strip().upper() == code
    except (EOFError, OSError):                      # no keyboard after all (a helper's run): a plain no, not a crash
        print("\nOWNER-OK: no keyboard here, so no typed yes. The owner says yes in the permission box that opens "
              "when a helper runs this, or types the code in their own terminal.")
        return False


def give(cfg):
    asked = _take_note(cfg)                          # the owner said yes in the AI tool's permission box just now
    import door as D                                 # Windows: the NUL device a helper's run gets also says "terminal"
    terminal = D.terminal() or BREAK("ownerok_tty")
    if not missing(cfg) and not BREAK("owner_ok_spoken"):
        print("OWNER-OK: nothing in this upload needs your OK."); return 0
    if not (asked or terminal):
        print("OWNER-OK: no yes from the owner. The owner says yes in the permission box that opens when a helper runs "
              "this (that box comes from the kit's hook), or by running it in a terminal. A helper can't give it here.")
        return 1
    todo = missing(cfg)
    if not todo:
        print("OWNER-OK: nothing in this upload needs your OK."); return 0
    if not asked and not _typed_yes(cfg, todo):
        print("OWNER-OK: no OK given. Nothing changed."); return 1
    import ledger as LG
    LG.grant(cfg, todo, "permission box" if asked else "terminal", "\n".join(explain(cfg, todo)))
    import catches as CL
    CL.log(cfg, "owner ok", ("owner said yes in the permission box to: " if asked else "owner said yes in a terminal to: ")
           + ", ".join(f for f, _, _ in todo))
    print("OWNER-OK: recorded. The upload can go now."); return 0


def give_at_upload(cfg):
    """The yes given in the box the kit's hook opened on the upload itself (fg/guard.py, fg/push.py): the game's PC,
    19 Nov, where the AI tool's own safety check would not let the helper run this script at all, so the owner said
    yes in a box and then had to give the same yes again in a terminal. True when a yes was recorded."""
    if BREAK("upload_asks") or not _take_note(cfg):
        return False
    todo = missing(cfg)
    if not todo:
        return False
    import ledger as LG
    LG.grant(cfg, todo, "permission box", "\n".join(explain(cfg, todo)))
    import catches as CL
    CL.log(cfg, "owner ok", "owner said yes in the permission box at the upload to: " + ", ".join(f for f, _, _ in todo))
    print("OWNER-OK: recorded (your yes in the box at this upload).")
    return True


def main(argv):
    cfg = C.load()
    if "--give" in argv:
        return give(cfg)
    if "--at-upload" in argv and not BREAK("at_upload_flag"):
        # The game's PC, 20 Nov: its upload script runs a ten-minute gate before fg/push.py. The owner said yes in the
        # box on the upload, the helper's other steps in those ten minutes ended the note, and the upload stopped with
        # "the owner has not said yes". A project's own upload script calls this first, so the yes is taken at once.
        give_at_upload(cfg)
        return 0
    import review as RV
    todo, need = missing(cfg), needing_ok(cfg)
    done = RV.passed(cfg, need)
    for f, why, _ in need:
        mine = next((t for t in todo if t[0] == f), None)
        print(f"  {'NEEDS YOUR OK' if mine else 'reviewer PASS' if f in done else 'ok given    '}  {f}: {mine[1] if mine else why}")
    print(f"OWNER-OK: {len(need)} change(s) need the owner's OK; {len(todo)} still without it.")
    return 1 if todo else 0


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]) and os.environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
