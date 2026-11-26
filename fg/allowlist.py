"""FoundationGuard: the recommended settings for your AI tool's own boxes (AI-made, Claude, 2026-11-11).

The game's first real morning (11 Nov): the owner couldn't tell the AI tool's own permission boxes from the kit's, and
answered a stream of boxes for reading files and running tests. That evening an unattended session stopped five times
in ten minutes at the AI tool's boxes for ordinary edits; the owner's phone did not show them. The owner, 11 Nov: "it
cant be frustration for the user that stops the work from being done". So this writes a recommended list into the
project's Claude Code settings (.claude/settings.json):

  allowed without the AI tool's box (permissions > allow)
    - ordinary edits and new files inside the project folder: Edit(/**) (Claude Code's edit rule covers its Write,
      Edit, MultiEdit and NotebookEdit tools; "/" is the project's top folder);
    - routine reading, building and testing commands, and the project's own gate and step commands word for word;
    - the kit's push script exactly (python fg/push.py), which pushes only the commit that passed the gate, and the
      project's own push wrapper exactly when push_command in foundationguard.json names it;
    - the Python commands also as the kit's own Python is called (its full path; the game's PC, 11 Nov, had only the
      engine's own Python).
  still asked (permissions > ask, which Claude Code puts above allow)
    - every file the kit guards for itself: the kit (fg/), its settings, the approved list, the frozen numbers, the
      hooks and AI tools' settings (.claude/, .github/, .codex/, .cursor/), the CI workflows and .git/;
    - deletes, git pushes other than the kit's script, and installs;
    - and, because nothing allows them, files outside the project folder and every other command.
The kit's own guard still checks every command and edit first, exactly as strictly: a change to a test, the owner's
own guard folders or a weaker check still opens the kit's box (which the AI tool shows even when the list allows the
edit), and a risky command is still blocked.

  python fg/allowlist.py              show the list
  python fg/allowlist.py --apply      write it into .claude/settings.json (that changes the AI tool's settings, so the
                                      kit's box asks the owner; setup offers it and writes it only on the owner's yes)
  python fg/allowlist.py --who PATH   which box, if any, a helper's edit to PATH opens: the AI tool's, the kit's, none
  python fg/allowlist.py --apply --for FOLDER
                                      for AI sessions that open in another folder (the game's PC, 11 Nov: they open
                                      in the play copy and work in the project). Claude Code reads the settings of the
                                      folder a session opens in, so this writes FOLDER/.claude/settings.local.json (kept
                                      out of git), names the project by its full path in the rules, and adds the
                                      project as a folder those sessions may work in. --who PATH --for FOLDER reads it.
  python fg/allowlist.py --apply --settings FILE   the same, into exactly that settings file
Every run says which folder's sessions the list is for, and names any other copy of the project where Claude Code has
opened sessions on this computer (from its own records), with the command for it.
"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import paths as P

BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
PYTHONS = ("python", "python3", "py")

READ = ["git status", "git diff", "git log", "git show", "git blame", "git ls-files", "git rev-parse", "git fetch",
        "git branch --show-current", "git remote -v", "ls", "wc", "grep", "rg", "tree", "pwd", "which"]
TEST_BUILD = ["pytest", "npm test", "npm run test", "npm run build", "npm run lint", "npx jest", "npx vitest", "node --test",
              "npx playwright test", "npx tsc --noEmit", "dotnet build",
              "dotnet test", "cargo build", "cargo test", "go build", "go test", "gradle test", "./gradlew test",
              "make test"]
PY_TESTS = ["-m pytest", "-m unittest"]
KIT_READS = ["fg/guard.py --check", "fg/copies.py", "fg/lock.py", "fg/ownerok.py", "fg/stages.py --plan",
             "fg/prove.py", "fg/forecast.py", "fg/state.py", "fg/logic.py", "fg/report.py", "fg/webtests.py"]
KIT_PUSH = ["fg/push.py", "fg/push.py --gate"]           # exactly these: --break-glass and the rest still ask
EXACT = {"git branch --show-current", "git remote -v", "pwd", "fg/copies.py", "fg/lock.py", "fg/ownerok.py",
         "fg/logic.py", "fg/report.py"} | set(KIT_PUSH)   # these allow exactly that command (logic.py --command runs any)
NEVER = ("push", "reset", "clean", "checkout", "rebase", "merge", "commit", "rm ", "del ", "mv ", "cp ", "--apply",
         "--give", "--cover", "--confirm", "--baseline", "--allow", "set ", "--force", "curl", "wget", "> ", ">>")
EDITS = "Edit(/**)"                                       # ordinary edits and new files inside the project folder
KIT_ASKS = [".claude/**", ".github/**", ".codex/**", ".cursor/**", ".git/**", "AGENTS.md"]
SHELL_ASK = ["git push", "rm", "rmdir", "git rm", "git clean", "del", "rd", "Remove-Item", "npm install", "npm i",
             "npm uninstall", "yarn add", "pnpm add", "pip install", "pip uninstall", "python -m pip", "python3 -m pip",
             "py -m pip", "winget", "choco", "brew install", "apt-get", "dotnet add", "cargo add", "cargo install",
             "go get", "go install"]


JOINED = re.compile(r"[;&|<>`\n]|\$\(")                 # a command joined to another, or sent into a file


def _rule(cmd, tail=None):
    """Exactly that command, or it and anything after it. tail: the part after the Python command, whose full path may
    hold spaces."""
    exact = cmd in EXACT or (cmd.split(" ", 1)[-1] if tail is None else tail) in EXACT
    return f"Bash({cmd})" if exact else f"Bash({cmd}:*)"


def pythons():
    """Every way a helper may call Python here. The game's PC, 11 Nov: it had only the engine's own Python, called by
    its full path, so rules for python, python3 and py never matched. So also the Python running the kit: as the kit's
    own commands write it (quoted, forward slashes) and as Windows writes it (back slashes)."""
    if BREAK("allowlist_python"):
        return list(PYTHONS)
    exe = sys.executable or ""
    forms = [C.python_cmd()] + [f'"{e}"' for e in (exe, exe.replace("\\", "/")) if e]
    forms += [e for e in (exe, exe.replace("\\", "/")) if e and " " not in e]
    return list(dict.fromkeys(list(PYTHONS) + forms))


def push_commands(cfg):
    """The project's own push wrapper (push_command; the game's PC, 11 Nov: bash Tools/Scripts/safe_push.sh), allowed
    exactly like the kit's push script; every other push still asks. One plain command each: one joined to another
    with && or ; would let anything ride along, so it is left out."""
    if BREAK("allowlist_push_command"):
        return []
    want = cfg.get("push_command") or []
    want = [want] if isinstance(want, str) else list(want)
    return [c.strip() for c in want if isinstance(c, str) and c.strip() and not JOINED.search(c)]


def posix(p):
    """A full path as Claude Code matches it (its permissions page): forward slashes, and a Windows drive C:\\x as /c/x."""
    p = p.replace("\\", "/")
    if not re.match(r"^[A-Za-z]:", p):
        p = os.path.abspath(p).replace("\\", "/")
    m = re.match(r"^([A-Za-z]):/*(.*)$", p)
    if m:
        p = "/" + m.group(1).lower() + "/" + m.group(2)
    return p.rstrip("/") or "/"


def _top(cfg, away):
    """How the list's edit rules start. "/" is the top of the folder the session opens in; for sessions that open
    somewhere else (away), "//" and the project's full path name the project from anywhere."""
    return "/" + posix(cfg["_root"]) + "/" if away else "/"


def routine(cfg, away=False):
    """The allow rules, in Claude Code's own words. away: for sessions that open in another folder."""
    out = [_rule(c) for c in list(READ) + list(TEST_BUILD)]
    out += [_rule(f"{p} {t}", t) for p in pythons() for t in PY_TESTS + KIT_READS]
    for c in [cfg.get("gate_command")] + [s.get("command") for s in cfg.get("gate_steps") or [] if isinstance(s, dict)]:
        if c and not any(w in f" {c} " for w in NEVER):
            out.append(f"Bash({c})")             # the project's own test run, word for word
    out += [f"Bash({c})" for c in push_commands(cfg)]     # the project's own push wrapper, exactly
    if not BREAK("allowlist_edits"):
        out.append(f"Edit({_top(cfg, away)}**)")  # 11 Nov: ordinary edits need no box from the AI tool
        out += [_rule(f"{p} {k}", k) for p in pythons() for k in KIT_PUSH]
    return list(dict.fromkeys(out))


def kit_files(cfg):
    """The files the kit guards for itself: never covered by the edit allowance. The owner's own guard folders
    (guard_paths: tests and the like) are left to the kit's hook, which asks about them itself, so that adding a new
    test stays free (helpers_add_tests)."""
    g = [x for x in C.guard_globs(cfg) if x not in (cfg.get("guard_paths") or []) and x not in (cfg.get("guard_decisions") or {})]
    import ownerok as OK
    return list(dict.fromkeys(g + OK.KIT_CODE + KIT_ASKS + ["APPROVED.md"]))


def still_ask(cfg, away=False):
    """The ask rules: guard files, deletes, other pushes and installs. Claude Code asks for these even when an allow
    rule also matches."""
    if BREAK("allowlist_guard_ask"):
        return []
    top = _top(cfg, away)
    return list(dict.fromkeys([f"Edit({top}{g})" for g in kit_files(cfg)] + [f"Bash({c}:*)" for c in SHELL_ASK]))


# ---- how Claude Code reads these rules (its permissions page): deny first, then ask, then allow; nothing matching asks.
# The kit uses this to show which box an edit opens (--who) and in its own tests. It reads only the kinds of rule above.

def _same(a, b):
    return bool(a and b) and os.path.normcase(posix(a)) == os.path.normcase(posix(b))


def _under(rule_path, root):
    """The rest of a "//" rule after the project's full path, or None when it names somewhere else."""
    top = posix(root) + "/" if root else None
    full = rule_path[1:]
    if not top or not os.path.normcase(full).startswith(os.path.normcase(top)):
        return None
    return full[len(top):]


def _edit_match(rule_path, rel, root=None, anchor=None):
    """Does an edit rule cover rel, a path inside the project? A "/..." rule starts at the top of the folder the session
    opens in (anchor; the project unless named), so it never reaches a file outside that folder. A "//..." rule is a
    full path: it covers the project only when it names it."""
    rel = rel.replace("\\", "/")
    if rel == ".." or rel.startswith("../") or os.path.isabs(rel) or re.match(r"^[A-Za-z]:/", rel):
        return False
    if rule_path.startswith("//"):
        g = _under(rule_path, root)
        return g is not None and (g == "**" or P.matches(rel, [g]))
    if root and anchor and not _same(root, anchor):
        rel = P.rel(os.path.join(root, rel), anchor)          # the project seen from the session's own folder
        if rel.startswith("..") or os.path.isabs(rel):
            return False
    g = rule_path[1:] if rule_path.startswith("/") else rule_path
    return g == "**" or P.matches(rel, [g])


def _bash_match(rule_cmd, part):
    if rule_cmd.endswith(":*"):
        pre = rule_cmd[:-2]
        return part == pre or part.startswith(pre + " ")
    return part == rule_cmd


RULE = re.compile(r"^(\w+)\((.*)\)$")


def _matches(rule, tool, target, root=None, anchor=None):
    m = RULE.match(rule)
    if not m:
        return False
    kind, body = m.groups()
    if tool == "Edit":
        return kind == "Edit" and _edit_match(body, target, root, anchor)
    return kind == "Bash" and any(_bash_match(body, p.strip()) for p in re.split(r"&&|\|\||;|\|", target) if p.strip())


def _all_parts_allowed(allow, cmd):
    parts = [p.strip() for p in re.split(r"&&|\|\||;|\|", cmd) if p.strip()]
    return bool(parts) and all(any(_bash_match(RULE.match(r).group(2), p) for r in allow if r.startswith("Bash(")) for p in parts)


def app_says(settings, tool, target, root=None, anchor=None):
    """('ask' | 'allow' | 'deny', the rule or None) for an edit to a project-relative path (tool 'Edit') or a command
    (tool 'Bash'), by the rules in settings. root: the project's folder; anchor: the folder the session opens in."""
    perm = (settings or {}).get("permissions") or {}
    for kind in ("deny", "ask"):
        hit = next((r for r in perm.get(kind) or [] if _matches(r, tool, target, root, anchor)), None)
        if hit:
            return kind, hit
    allow = perm.get("allow") or []
    if tool == "Edit":
        hit = next((r for r in allow if _matches(r, "Edit", target, root, anchor)), None)
        return ("allow", hit) if hit else ("ask", None)
    return ("allow", "every part allowed") if _all_parts_allowed(allow, target) else ("ask", None)


def _load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def _settings(folder):
    """The rules a session that opens in folder reads from it: .claude/settings.json and .claude/settings.local.json."""
    perm = {}
    for name in ("settings.json", "settings.local.json"):
        p = os.path.join(folder, ".claude", name)
        try:
            got = (_load(p).get("permissions") or {}) if os.path.exists(p) else {}
        except ValueError:
            got = {}
        for kind, rules in got.items():
            if isinstance(rules, list):
                perm.setdefault(kind, []).extend(rules)
    return {"permissions": perm}


def who(cfg, path, folder=None):
    """Plain words: which box a helper's edit to path opens, in a session that opens in folder (the project unless
    named)."""
    root = cfg["_root"]
    folder = folder or root
    rel = P.rel(path if os.path.isabs(path) else os.path.join(root, path), root)
    if rel.startswith("..") or os.path.isabs(rel):
        return f"{rel}: outside the project folder. Your AI tool's own box asks (nothing allows it)."
    kind, rule = app_says(_settings(folder), "Edit", rel, root, folder)
    app = (f"your AI tool asks (its rule {rule})" if rule else "your AI tool asks (no rule allows it)") if kind == "ask" \
        else ("your AI tool refuses it (" + rule + ")") if kind == "deny" else f"your AI tool lets it through ({rule})"
    kit = "the kit has nothing to ask"
    if P.matches(rel, kit_files(cfg)):
        kit = "the kit's box asks too, labelled \"FoundationGuard:\""
    elif P.matches(rel, C.guard_globs(cfg)):
        import adds as AD
        kit = ("the kit's box asks, labelled \"FoundationGuard:\"" +
               (", unless the change only adds new tests" if AD.is_test_file(rel, cfg) and cfg.get("helpers_add_tests", True) else "") +
               (" (or it waits for your one yes before the upload: gather_asks)" if cfg.get("gather_asks") else ""))
    return f"{rel}: {app}; {kit}."


def _show(p):
    return os.path.abspath(p).replace("\\", "/")


def target(cfg, folder=None, settings=None):
    """(the settings file the list goes in, the folder whose AI sessions read it). Claude Code reads the settings of the
    folder a session opens in (its settings page), so a list for sessions that open somewhere else goes there."""
    root = cfg["_root"]
    if BREAK("allowlist_for"):
        folder = settings = None
    if settings:
        p = os.path.abspath(settings)
        d = os.path.dirname(p)
        return p, (os.path.dirname(d) if os.path.basename(d) == ".claude" else d)
    if folder and not _same(folder, root):
        return os.path.join(os.path.abspath(folder), ".claude", "settings.local.json"), os.path.abspath(folder)
    return os.path.join(root, ".claude", "settings.json"), root


def sessions_seen(folders):
    """Which of these folders Claude Code has opened sessions in on this computer, newest first, from its own records:
    a folder in ~/.claude/projects (or CLAUDE_CONFIG_DIR/projects) named after the session's folder, with every
    character but letters and digits turned into "-". A hint only: records that were cleared show nothing."""
    base = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude"), "projects")
    seen = []
    for f in folders:
        d = os.path.join(base, re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(f)))
        if os.path.isdir(d):
            seen.append((os.path.getmtime(d), f))
    return [f for _, f in sorted(seen, reverse=True)]


def elsewhere(cfg, opens):
    """A line for each other copy of the project where AI sessions have opened: the list for opens doesn't reach them."""
    if BREAK("allowlist_for"):
        return []
    import copies as CP
    root = cfg["_root"]
    out = []
    for d in sessions_seen([root] + CP.copies(root)):
        if not _same(d, opens):
            how = "python fg/allowlist.py --apply" + ("" if _same(d, root) else f' --for "{_show(d)}"')
            out.append(f"FoundationGuard: AI sessions have also opened in {_show(d)}; this list doesn't reach them. "
                       f"For those:  {how}")
    return out


def covers(cfg, opens):
    """Which folder's sessions the list is for, and what it lets through there."""
    root, mine = cfg["_root"], ["the kit's push script"] + push_commands(cfg)
    edits = ("ordinary edits in this project" if _same(opens, root) else
             f"ordinary edits in the project ({_show(root)}, added as a folder those sessions may work in; edits in "
             f"{_show(opens)} itself still ask)")
    return (f"It is for AI sessions that open in {_show(opens)}. Their AI tool lets {edits}, routine reading, building "
            f"and testing, and {', '.join(mine)} go without its own box; it still asks about guard files, settings, "
            "deletes, other pushes, installs and anything outside the project. The kit still checks every command and edit.")


def _write(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _add_folder(perm, root):
    """The project as a folder sessions that open elsewhere may read and work in (Claude Code's additionalDirectories)."""
    dirs = perm.setdefault("additionalDirectories", [])
    if not any(_same(d, root) for d in dirs):
        dirs.append(_show(root))


def apply(cfg, folder=None, settings=None):
    p, opens = target(cfg, folder, settings)
    away = not _same(opens, cfg["_root"])
    if not os.path.isdir(opens):
        print(f"FoundationGuard: there is no folder {_show(opens)}; nothing changed."); return 1
    try:
        data = _load(p) if os.path.exists(p) else {}
    except ValueError:
        print(f"FoundationGuard: {_show(p)} is not valid JSON; nothing changed."); return 1
    perm = data.setdefault("permissions", {})
    allow, ask = perm.setdefault("allow", []), perm.setdefault("ask", [])
    new = [r for r in routine(cfg, away) if r not in allow]
    new_ask = [r for r in still_ask(cfg, away) if r not in ask]
    if BREAK("allowlist_apply"):
        new, new_ask = [], []
    allow += new
    ask += new_ask
    if away:
        _add_folder(perm, cfg["_root"])
    _write(p, data)
    if away and os.path.basename(p) == "settings.local.json":
        import copies as CP
        CP._keep_out_of_git(opens)
    print(f"FoundationGuard: the recommended list is in {_show(p)} ({len(new)} allow and {len(new_ask)} ask rules "
          "added). " + covers(cfg, opens))
    for line in elsewhere(cfg, opens):
        print(line)
    return 0


SUMMARY = ("Recommended list for your AI tool's own boxes: it lets ordinary edits and new files in this project, routine "
           "reading, building and testing, and the kit's push script go without the AI tool's box. Guard files, "
           "settings, deletes, other pushes, installs and anything outside the project still ask. The kit still checks "
           "everything. (The whole list: python fg/allowlist.py)")


def _keyboard():
    """Is the input a real keyboard? Windows CI, 11 Nov: Windows counts the empty input NUL as a terminal, so on
    Windows only a real console counts."""
    try:
        if not sys.stdin.isatty():
            return False
        if os.name != "nt":
            return True
        import ctypes, msvcrt
        mode = ctypes.c_uint32()
        return bool(ctypes.windll.kernel32.GetConsoleMode(msvcrt.get_osfhandle(sys.stdin.fileno()), ctypes.byref(mode)))
    except Exception:
        return False


def _owner_at_terminal():
    """A terminal the owner opened: a real keyboard, and not a command an AI tool is running (Claude Code marks its
    commands with CLAUDECODE)."""
    return _keyboard() and not os.environ.get("CLAUDECODE")


ASK_HELPER = ("FoundationGuard asks the owner: may the kit write its recommended list into your AI tool's settings? "
              "Why: without it, a helper working on its own stops at your AI tool's box for every file edit. "
              "To answer: tell the helper yes, and it runs  python fg/allowlist.py --apply  (the kit's box then asks you "
              "once); or type that command yourself in a terminal.")


def offer(cfg, yes_flag=False, at_terminal=None, read=input):
    """Setup's last step: offer the recommended list and write it only on the owner's yes. yes_flag: the owner already
    said yes (setup --allow-routine, which the kit's box asks about). Returns True when the list was written."""
    if yes_flag:
        return apply(cfg) == 0
    at_terminal = _owner_at_terminal() if at_terminal is None else at_terminal
    if not at_terminal:
        print(ASK_HELPER); return False
    print("FoundationGuard: " + SUMMARY)
    try:
        said = read("FoundationGuard asks: write this list now? Type yes and press Enter (anything else skips it): ") or ""
    except (EOFError, OSError):                   # nobody there to type: the helper passes the question on instead
        print(); print(ASK_HELPER); return False
    if said.strip().lower() == "yes" or BREAK("setup_offer_yes"):
        return apply(cfg) == 0
    print("FoundationGuard: not written. You can add it later:  python fg/allowlist.py --apply")
    return False


def _opt(argv, name):
    return argv[argv.index(name) + 1] if name in argv[:-1] else None


def main(argv):
    cfg = C.load()
    folder, settings = _opt(argv, "--for"), _opt(argv, "--settings")
    if "--apply" in argv:
        return apply(cfg, folder, settings)
    if "--who" in argv[:-1]:
        print("FoundationGuard: " + who(cfg, _opt(argv, "--who"), target(cfg, folder, settings)[1])); return 0
    p, opens = target(cfg, folder, settings)
    away = not _same(opens, cfg["_root"])
    print("FoundationGuard: " + SUMMARY)
    print(f"For AI sessions that open in {_show(opens)} (--apply writes it into {_show(p)}).")
    print("Allowed without the AI tool's own box:")
    for r in routine(cfg, away):
        print("  " + r)
    print("Still asked (these win over the allowed ones):")
    for r in still_ask(cfg, away):
        print("  " + r)
    for line in elsewhere(cfg, opens):
        print(line)
    return 0


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]) and os.environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
