"""FoundationGuard command guard (AI-made, Claude, 2026-11-08).

A PreToolUse hook for AI coding sessions (Claude Code: matcher "Bash"; other agents: call `guard.py --check "<cmd>"`).
It reads the hook JSON on stdin, looks at every command the line would run (including ones wrapped in bash -c, sh -c,
eval, python -c, env/sudo/command prefixes, chains and pipes) and blocks, with exit code 2 and a reason on stderr:
  - any direct `git push` when push_only_via_wrapper is on (the kit's push wrapper pushes only a tested commit),
    and always: force pushes (every spelling), deletes of remote branches or tags, mirror pushes, pushes to a
    protected branch;
  - work-destroying git: reset --hard/--merge, clean -f, branch -D/-M, checkout/restore/switch that discard changes,
    history rewrites, ref deletes, reflog expiry, tag deletes, stash clear;
  - commits, merges, rebases and resets while the folder is on a protected branch;
  - `gh pr merge` with --admin/--auto, or without the owner's sign-off line when one is required;
  - heavy jobs while a listed program runs (for Unreal: no builds or tests while the owner's game or editor is open);
  - anything matching the config's extra rules.
v0.3, the guards guard themselves: a change to a guard file (the approved list, the sign-off file, checks and
baselines named in guard_paths, hooks, this kit, its config and baselines) by an editing tool, or by a shell command
that writes to one, needs the owner's OK in the agent's own permission prompt ("ask"), which the agent can't give
itself. Hook matcher: "Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit|Monitor".
It is a guard against mistakes, not a sandbox: a determined program can always get round a text check.
"""
import itertools, json, os, re, shlex, subprocess, sys, time
T0 = time.time()          # when this check began: the check after every step leaves its note within half the time limit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# v0.8.7 (owner, 11 Nov: "Yes get 1 done"): a guard that crashes must BLOCK. An AI tool reads a hook that dies with an
# error as "no answer" and runs the command anyway, so before this a broken kit file, a broken foundationguard.json or
# input the guard could not read let every command through. Set up before the kit's own files load, so a broken one
# is caught too.
# 11 Nov (the game's first real morning): the owner couldn't tell the AI tool's own boxes from the kit's. Everything
# the kit says to the owner starts with this label; the AI tool's own boxes never do.
LABEL = "FoundationGuard: " if os.environ.get("FG_BREAK", "") != "kit_label" else ""

HERE = os.path.dirname(os.path.abspath(__file__))     # kept: the crash report names the kit even when __file__ is gone
CRASH = ("the guard itself failed (%s), so this was blocked to be safe; nothing ran. To get past it on purpose, the owner "
         "(not the helper) fixes the cause (python fg/guard.py --check \"the command\" shows the error), or switches the "
         "guard hook off by hand in the AI tool's settings and back on afterwards.")


def _agent_flag():
    a = sys.argv
    return a[a.index("--agent") + 1] if "--agent" in a[:-1] else None


def _fail_closed(why):
    """Block in the calling tool's own words (or with exit 2, which every supported tool reads as a refusal)."""
    reason = CRASH % why
    if sys.argv[1:2] == ["--check"]:
        print("BLOCK: " + reason); sys.stdout.flush(); os._exit(2)
    out, code = "", 2
    try:
        import agents as _AG
        agent = globals().get("AGENT") or _agent_flag() or "claude"
        out, code = _AG.answer(agent, "block", reason, globals().get("SHELL_CALL", True))
    except BaseException:                       # the adapters themselves are broken: exit 2 still refuses
        pass
    sys.stderr.write(LABEL + "blocked. " + reason + "\n")
    if out:
        print(out)
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(code)


def _crash_hook(kind, err, tb):
    if os.environ.get("FG_BREAK", "") == "guard_fail_closed":
        return sys.__excepthook__(kind, err, tb)
    _fail_closed("%s: %s%s" % (kind.__name__, str(err)[:200], _crash_place(kind, err, tb)))


def _crash_place(kind, err, tb):
    """Where in the kit it failed, and the whole trace kept in ~/.foundationguard/guard_crash.log (the game's PC, 16 Nov:
    "IndexError: list index out of range" with two kits loaded, and nobody could tell which one or where)."""
    if os.environ.get("FG_BREAK", "") == "guard_crash_place":
        return ""
    try:
        import traceback
        last = traceback.extract_tb(tb)[-1]
        where = " at %s line %d, kit %s" % (os.path.basename(last.filename), last.lineno, HERE)
        d = os.path.join(os.path.expanduser("~"), ".foundationguard")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "guard_crash.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S %z") + where + "\n" + "".join(traceback.format_exception(kind, err, tb))
                    + "the call: " + str(globals().get("CALL", ""))[:4000] + "\n\n")
        return where + " (the whole trace: ~/.foundationguard/guard_crash.log)"
    except Exception:
        return ""


def _stuck_place():
    """Where the check was when its time ran out, and the whole stack kept in ~/.foundationguard/guard_crash.log (the
    game's PC, 19 Nov: every step was refused with "ran past its time limit" and nobody could tell what was slow)."""
    if os.environ.get("FG_BREAK", "") == "guard_stuck_place":
        return ""
    try:
        import threading, traceback
        stack = traceback.extract_stack(sys._current_frames()[threading.main_thread().ident])
        ours = [f for f in stack if os.path.dirname(os.path.abspath(f.filename)) == HERE] or stack
        last = ours[-1]
        where = " in %s line %d (%s), kit %s" % (os.path.basename(last.filename), last.lineno, last.name, HERE)
        d = os.path.join(os.path.expanduser("~"), ".foundationguard")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "guard_crash.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S %z") + " ran past its time limit" + where + "\n"
                    + "".join(traceback.format_list(stack)) + "the call: " + str(globals().get("CALL", ""))[:4000] + "\n\n")
        return where + " (the whole stack: ~/.foundationguard/guard_crash.log)"
    except Exception:
        return ""


TIME_LIMIT = 20.0        # seconds: below the AI tools' own limits for a hook (Claude Code 60 s; Codex, Copilot 30 s as installed)


def _time_limit():
    """The project's guard_time_limit in foundationguard.json (1 to 25 s), else 20 s."""
    try:
        here = os.path.abspath(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        while not os.path.exists(os.path.join(here, "foundationguard.json")):
            if os.path.dirname(here) == here:
                return TIME_LIMIT
            here = os.path.dirname(here)
        with open(os.path.join(here, "foundationguard.json"), encoding="utf-8-sig") as f:
            return max(1.0, min(25.0, float(json.load(f).get("guard_time_limit", TIME_LIMIT))))
    except Exception:
        return TIME_LIMIT


def _watch():
    """Block when the check runs past its time limit (an outside review, 12 Nov, claim C8): an AI tool takes a hook that
    runs past its own limit as an error and lets the call go ahead, so a check stuck on a slow git (a lock, a network
    drive) would let the command through. The guard blocks first."""
    if os.environ.get("FG_BREAK", "") == "guard_time_limit" or sys.argv[1:2] in (["--check"], ["--status"]):
        return
    import threading
    limit = _time_limit()
    t = threading.Timer(limit, lambda: _fail_closed("the check ran past its time limit (%g s)%s" % (limit, _stuck_place())))
    t.daemon = True
    t.start()


BIG_INPUT = 8000         # bytes of hook input: above this the check runs in a child process that can be stopped


def _big_input_apart():
    """Check a long input in a child process, stopped at the time limit (outside review 3, Claude, 12 Nov, finding 8):
    the time limit above is a timer in this process, and it can't fire while one long regular expression runs, so a
    crafted command of 30,000 here-document lines ran 66 s, past Claude Code's own 60 s, and the call would have gone
    ahead. A child can always be stopped; when it is, the command is blocked. Short inputs, nearly all, stay here."""
    if os.environ.get("FG_BREAK", "") == "big_input_child" or "--child" in sys.argv or \
            sys.argv[1:2] in (["--check"], ["--status"]) or {"--help", "-h"} & set(sys.argv[1:]):
        return
    raw = sys.stdin.buffer.read()
    if len(raw) <= BIG_INPUT:
        import io
        sys.stdin = io.TextIOWrapper(io.BytesIO(raw), encoding=sys.stdin.encoding, errors=sys.stdin.errors)
        return
    limit = _time_limit()
    try:
        p = subprocess.run([sys.executable, os.path.abspath(__file__)] + sys.argv[1:] + ["--child"], input=raw,
                           capture_output=True, timeout=max(0.5, limit - 1.0))
    except subprocess.TimeoutExpired:
        _fail_closed("the check of this long command ran past its time limit (%g s)" % limit)
    sys.stdout.buffer.write(p.stdout); sys.stderr.buffer.write(p.stderr)
    sys.stdout.flush(); sys.stderr.flush()
    os._exit(p.returncode if p.returncode in (0, 2) else 2)


if __name__ == "__main__":
    sys.excepthook = _crash_hook
    _watch()
    _big_input_apart()
import config as C
import paths as P
import weaken as W
import catches as CL
import pywrites as PW
import agents as AG
import adds as AD
import ownerwords as OW, gitsettings as GS
import about as AB
import box as BX
import review as RV

AGENT, SHELL_CALL = "claude", True     # which AI tool's hook called us (fg/agents.py), and whether for a shell command
STEP = {"cfg": None, "data": None, "free": [], "loud": [], "gathered": []}   # for the check after the step (fg/steps.py): what this step may change


def _step_note(asked):
    """Leave the note the check after the step reads (fg/steps.py). Never in the way of the guard's own answer."""
    if STEP["cfg"] is None or BREAK("steps_check") or AB.ON[0]:
        return
    try:
        import steps as SP
        SP.before(STEP["cfg"], STEP["data"] or {}, asked, STEP["free"], deadline=T0 + _time_limit() / 2, loud=STEP["loud"],
                  gathered=STEP["gathered"])
    except Exception:
        pass


def _say(kind, reason):
    """Block or ask, in the calling tool's own words, then stop."""
    if AB.ON[0]:
        AB.say(kind)                           # --about: only which files the box names (fg/about.py)
    if kind == "ask":
        _step_note(True)                       # the step runs only if the owner says yes in the box
    out, code = AG.answer(AGENT, kind, reason, SHELL_CALL)
    if code == 2:
        sys.stderr.write(LABEL + "blocked. " + reason + "\n")
    if out:
        print(out)
    sys.exit(code)

PREFIXES = {"sudo", "command", "builtin", "exec", "nohup", "time", "nice", "doas", "xargs", "then", "do", "else", "!"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh", "fish", "pwsh", "powershell", "cmd", "cmd.exe", "bash.exe", "sh.exe"}
GIT_OPTS_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
BREAK = lambda k: os.environ.get("FG_BREAK", "") == k
# A wider reading added after the outside reviews (12 Nov) is off under its own break and under any other one, so that
# each older row is still proven on its own: prove.py turns on one break at a time, and a wider reading could otherwise
# catch what that break lets through.
WIDER = lambda k: os.environ.get("FG_BREAK", "") == ""
SEP = re.compile(r"\s*(?:&&|\|\||;|\||&|\n)\s*")


def _in_quote(cmd, i, q, cur):
    """One character inside quotes. Returns (next index, quote still open or None)."""
    ch = cmd[i]
    cur.append(ch)
    if ch == "\\" and q == '"' and i + 1 < len(cmd):
        cur.append(cmd[i + 1]); return i + 2, q
    return i + 1, (None if ch == q else q)


def _split_at(cmd, i):
    """How many characters a separator at cmd[i] takes (0: not a separator)."""
    if cmd.startswith(("&&", "||", "$("), i):
        return 2
    return 1 if cmd[i] in ";|&\n()`" else 0


def split_chain(cmd, with_seps=False):
    """Split a shell line on && || ; | & and newlines, outside quotes. with_seps: (part, the separator after it)."""
    out, cur, q, i = [], [], None, 0
    while i < len(cmd):
        ch = cmd[i]
        if q:
            i, q = _in_quote(cmd, i, q, cur); continue
        if ch in "'\"":
            q = ch; cur.append(ch); i += 1; continue
        if ch == "\\" and i + 1 < len(cmd):
            cur += [ch, cmd[i + 1]]; i += 2; continue
        n = _split_at(cmd, i)
        if n:
            out.append(("".join(cur), cmd[i:i + n])); cur = []; i += n; continue
        cur.append(ch); i += 1
    out.append(("".join(cur), ""))
    keep = [(s.strip(), sep) for s, sep in out if s.strip()]
    return keep if with_seps else [s for s, _ in keep]


ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
WRAPPERS = ("stdbuf", "ionice", "chronic", "unbuffer", "caffeinate", "systemd-run", "flock")


def _skip_opts(tk, with_arg=(), stop=()):
    """Drop leading options; the ones in with_arg take a value too."""
    while tk and tk[0].startswith("-") and tk[0] not in stop:
        tk = tk[2:] if tk[0] in with_arg else tk[1:]
    return tk


def _strip_env(tk):
    tk = tk[1:]
    while tk and (tk[0].startswith("-") or ASSIGN.match(tk[0])):
        tk = tk[1:]
    return tk


def _strip_timeout(tk):                                       # timeout [opts] DURATION cmd ...
    tk = _skip_opts(tk[1:], ("-s", "-k", "--signal", "--kill-after"))
    return tk[1:] if tk and re.match(r"^\d+(\.\d+)?[smhd]?$", tk[0]) else tk


def _strip_wrapper(t, tk):
    tk = _skip_opts(tk[1:])
    return tk[1:] if t == "flock" and tk else tk              # flock FILE cmd


# Outside review 3 (Grok, 12 Nov): f(){ git push --force; }; f went through, because a command after "{" was not read
# as a command. Nor was one after "if", "while", "until", "coproc", "function NAME", or cmd's "call".
STRUCTURE = {"{", "}", "if", "elif", "while", "until", "coproc", "call"}


def _unbrace(tk):
    """{git push --force} written without spaces (PowerShell allows it): the braces come off the words."""
    tk = [tk[0][1:]] + tk[1:] if tk and tk[0].startswith("{") and tk[0] != "{" else tk
    if tk and tk[-1].endswith("}") and tk[-1].count("}") > tk[-1].count("{"):
        tk = tk[:-1] + ([tk[-1][:-1]] if tk[-1][:-1] else [])
    return [t for t in tk if t]


def _strip_one(tk):
    """Remove one prefix word (VAR=x, env, sudo, timeout ...). Returns the rest, or None when there is none."""
    t = tk[0]
    if WIDER("shell_words"):
        if t == "{":
            return _unbrace(tk[1:])
        if t in STRUCTURE or t.lower() == "call" or (t == "." and len(tk) > 1 and tk[1].startswith("{")):
            return tk[1:]
        if t == "function" and len(tk) > 1:
            return tk[2:]
        if t.startswith("{") and not t.startswith("{}"):
            return _unbrace(tk)
    if ASSIGN.match(t):
        return tk[1:]
    if t == "env":
        return _strip_env(tk)
    if t in PREFIXES:
        return _skip_opts(tk[1:], ("-u", "-n", "-g"), ("-c",))   # sudo -u x, nice -n 5 ...
    if t in ("timeout", "gtimeout"):
        return _strip_timeout(tk)
    if t in WRAPPERS:
        return _strip_wrapper(t, tk)
    return None


def strip_prefixes(tk):
    while tk:
        if tk[0] == "cd":
            return []
        rest = _strip_one(tk)
        if rest is None:
            break
        tk = rest
    return tk


def _shell_inner(b, tk):
    """bash -c '...', cmd /c ..., bash <<< '...'."""
    if "<<<" in tk and tk.index("<<<") + 1 < len(tk) and not BREAK("guard_round2"):
        return [tk[tk.index("<<<") + 1]]                      # bash <<< 'git ...' (a here-string is code)
    for k, t in enumerate(tk[1:], 1):
        if t not in ("-c", "-lc", "-ic", "/c", "/C", "/k", "/K", "-Command", "-command") or k + 1 >= len(tk):
            continue
        if b in ("cmd", "pwsh", "powershell") and not BREAK("guard_round3"):
            return [" ".join(tk[k + 1:])]                     # cmd /c git clean -fdx: everything after /c is the command
        if WIDER("shell_functions") and k + 3 <= len(tk) - 1:  # bash -c 'git "$@"' x push --force: $0 is x, $@ the rest
            return [tk[k + 1], _put_positionals(tk[k + 1], tk[k + 3:])]
        return [tk[k + 1]]
    return []


# Outside review 3 (Grok, 12 Nov): set -- git push --force; "$@" and f(){ git "$@"; }; f push --force went through.
# Words handed to a function or set with "set --" are written in where "$@", "$*" or "$1" stand.
POSITIONAL = re.compile(r'"\$(?:@|\{@\})"|"\$(?:\*|\{\*\})"|\$(?:@|\{@\}|\*|\{\*\})|"\$\{?([1-9])\}?"|\$\{?([1-9])\}?')


def _put_positionals(text, args):
    def one(m):
        s = m.group(0)
        if m.group(1) or m.group(2):
            n = int(m.group(1) or m.group(2))
            a = args[n - 1] if n <= len(args) else ""
            return shlex.quote(a) if s.startswith('"') else a
        if s.startswith('"') and "@" in s:
            return " ".join(shlex.quote(a) for a in args)
        return shlex.quote(" ".join(args)) if s.startswith('"') else " ".join(args)
    return POSITIONAL.sub(one, text)


def _start_inner(tk):
    """Start-Process git -ArgumentList 'push --force', start "" git push --force: the program and its words."""
    ps = tk[0].lower() in ("start-process", "saps") or any(t.lower() in ("-argumentlist", "-args", "-filepath") for t in tk)
    if not ps:                                                # cmd's start ["title"] [/options] command ...
        rest = [t for t in tk[1:] if t and not t.startswith("/")]
        return [" ".join(shlex.quote(t) for t in rest)] if rest else []
    prog, args, k, loose = None, [], 1, []
    while k < len(tk):
        t = tk[k].lower()
        if t in ("-filepath", "-file") and k + 1 < len(tk):
            prog = tk[k + 1]; k += 2; continue
        if t in ("-argumentlist", "-args") and k + 1 < len(tk):
            args += [a for a in tk[k + 1].split(",") if a]; k += 2; continue
        if t in ("-workingdirectory", "-verb", "-windowstyle", "-redirectstandardoutput", "-redirectstandarderror",
                 "-redirectstandardinput", "-credential", "-environment"):
            k += 2; continue
        if not t.startswith("-"):
            loose.append(tk[k])
        k += 1
    if prog is None and loose:
        prog, loose = loose[0], loose[1:]
    if not args and loose:
        args = [a for t in loose for a in t.split(",") if a]
    return [" ".join([prog] + args)] if prog else []


PS_CMDLET = re.compile(r"^(?:[a-z]+-[a-z]+|icm|%|foreach|sajb)$")


def _script_blocks(tk):
    """Invoke-Command -ScriptBlock { git push --force }, ForEach-Object { ... }: the code inside the braces."""
    out, k = [], 1
    while k < len(tk):
        if tk[k].startswith("{") and not tk[k].startswith("{}"):
            j = next((i for i in range(k, len(tk)) if tk[i].endswith("}") and (i > k or tk[i] != "{")), len(tk) - 1)
            words = _unbrace(tk[k:j + 1] if tk[k] != "{" else tk[k + 1:j + 1])
            if words:
                out.append(" ".join(shlex.quote(w) for w in words))
            k = j + 1; continue
        k += 1
    return out


def _watch_inner(tk):                                         # watch -n 60 "cmd": runs cmd again and again
    rest = tk[1:]
    while rest and rest[0].startswith("-"):
        takes = rest[0] in ("-n", "--interval", "-d") and len(rest) > 1 and not rest[1].startswith("-")
        rest = rest[2:] if takes else rest[1:]
    return [" ".join(rest)] if rest else []


def _find_inner(tk):                                          # find ... -exec / -execdir / -ok cmd {} \;
    out = []
    for k, t in enumerate(tk):
        if t in ("-exec", "-execdir", "-ok", "-okdir"):
            end = next((j for j in range(k + 1, len(tk)) if tk[j] in (";", "+", "\\;")), len(tk))
            out.append(" ".join(shlex.quote(x) for x in tk[k + 1:end] if x != "{}"))
    return out


RUNS_CODE = re.compile(r"system|subprocess|popen|exec|spawn|check_output|check_call|\.call\(|\.run\(|`|qx|IO\.popen|Open3", re.I)


def _code_inner(code):
    """git commands inside a python/node/perl/ruby -c program."""
    if not BREAK("guard_code_strings") and not RUNS_CODE.search(code):
        return []                                             # code that only prints or stores the words runs nothing
    quoted = r"(['\"])(.*?)\1" if BREAK("guard_round3") else r"(['\"`])(.*?)\1"
    out = [m.group(2) for m in re.finditer(quoted, code) if "git" in m.group(2) or "gh " in m.group(2)]
    if WIDER("code_git_anywhere"):              # two outside reviews, 12 Nov: exec("...os.system(\\"git push --force\\")")
        flat = code.replace('\\"', '"').replace("\\'", "'")
        out += [m.group(0).strip() for m in re.finditer(r"\b(?:git|gh)\s+[^'\"`\n;)\]]+", flat)]
    lists = r"\[([^\[\]]*)\]" if BREAK("guard_round2") else r"[\[(]([^\[\]()]*)[\])]"
    for lst in re.finditer(lists, code):        # argument lists: ['git', 'reset', '--hard'] or system("git", "branch", "-D")
        words = [m.group(2) for m in re.finditer(r"(['\"])(.*?)\1", lst.group(1))]
        if words and base(words[0]) in ("git", "gh"):
            out.append(" ".join(shlex.quote(w) for w in words))
    return out


def _interp_inner(tk):
    for k, t in enumerate(tk[1:], 1):
        if t in ("-c", "-e") and k + 1 < len(tk):
            return _code_inner(tk[k + 1])
    return []


def nested(tk):
    """Commands hidden inside this one: bash -c '...', eval '...', python -c '...os.system(...)...'."""
    if not tk:
        return []
    b = base(tk[0])
    if b in SHELLS:
        return _shell_inner(b, tk)
    if b == "eval":
        return [" ".join(tk[1:])]
    if WIDER("windows_shells"):             # outside review 3 (Grok, 12 Nov): PowerShell's ways to run words
        if b in ("invoke-expression", "iex"):
            return [" ".join(t for t in tk[1:] if t.lower() not in ("-command", "-c"))]
        if b in ("start-process", "saps", "start"):
            return _start_inner(tk)
        if PS_CMDLET.match(b):
            return _script_blocks(tk)
    if b in ("watch", "find") and not BREAK("guard_round3"):
        return _watch_inner(tk) if b == "watch" else _find_inner(tk)
    if re.match(r"^(python|python3|py|node|perl|ruby)(\d|\.)*$", b):
        return _interp_inner(tk)
    return []

def tokens(seg):
    try:
        return shlex.split(seg, posix=True)
    except ValueError:
        return seg.replace('"', " ").replace("'", " ").split()


def base(t):
    b = re.split(r"[\\/]", t)[-1].lower()
    return b[:-4] if b.endswith(".exe") else b


def current_branch(cwd):
    try:
        r = subprocess.run(["git", "-C", cwd or ".", "branch", "--show-current"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        return r.stdout.strip() or None
    except Exception:
        return None


def git_alias(name, cfg_pairs, cwd):
    for k, v in cfg_pairs:
        if k.lower() == "alias." + name.lower():
            return v
    try:
        r = subprocess.run(["git", "-C", cwd or ".", "config", "--get", "alias." + name], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        return r.stdout.strip() or None
    except Exception:
        return None


def _git_globals(tk, cwd):
    """Skip git's own options (-C dir, -c key=value ...). Returns (index of the subcommand, -c pairs, folder)."""
    i, pairs = 1, []
    while i < len(tk) and tk[i].startswith("-"):
        t = tk[i]
        if t not in GIT_OPTS_WITH_ARG:
            i += 1; continue
        if t == "-C" and i + 1 < len(tk):
            cwd = tk[i + 1] if os.path.isabs(tk[i + 1]) else os.path.join(cwd or ".", tk[i + 1])
        if t == "-c" and i + 1 < len(tk) and "=" in tk[i + 1]:
            pairs.append(tuple(tk[i + 1].split("=", 1)))
        i += 2
    return i, pairs, cwd


def _judge_alias(val, cfg, cwd):
    """What a git alias would run: '!cmd' is a shell line, anything else more git."""
    return check_line(val[1:], cfg, cwd) if val.startswith("!") else check_git(["git"] + tokens(val), cfg, cwd)


def _git_alias_and_meta(sub, args, pairs, cfg, cwd):
    """Aliases, help and alias definitions. Returns (decided, reason)."""
    if sub not in KNOWN:
        al = git_alias(sub, pairs, cwd)
        if al:
            if al.startswith("!"):
                return True, check_line(al[1:] + " " + " ".join(shlex.quote(a) for a in args), cfg, cwd)
            return True, check_git(["git"] + tokens(al) + args, cfg, cwd)
    if BREAK("guard_round3"):
        return False, None
    if "--help" in args or sub == "help":
        return True, None                                     # git push --help only opens the manual
    kv = [a for a in args if not a.startswith("-")]
    if sub == "config" and len(kv) >= 2 and kv[0].lower().startswith("alias."):
        r = _judge_alias(kv[1], cfg, cwd)                     # git config alias.wipe '!git clean -fdx': judge what it would run
        if r:
            return True, "defining a git alias that would run something blocked: " + r
    return False, None


def _hookspath_change(args):
    """git config core.hooksPath X (or --unset): switches off the push check. Reading it is fine."""
    kv = [a for a in args if not a.startswith("-")]
    reading = any(a in ("--get", "--get-all", "--list", "-l", "--get-regexp", "--show-origin") for a in args)
    sets = len(kv) >= 2 or any(a.startswith("--unset") for a in args)
    return bool(kv) and kv[0].lower() == "core.hookspath" and not reading and sets


def _git_hook_skips(sub, args, pairs):
    """Ways round the push check: core.hooksPath and --no-verify."""
    if BREAK("guard_github"):
        return None
    if any(k.strip().lower() == "core.hookspath" for k, _ in pairs):
        return "pointing git at other hooks would skip the push check; not allowed."
    if sub == "config" and _hookspath_change(args):
        return "changing core.hooksPath would switch off the push check; not allowed."
    if sub == "push" and any(a == "--no-verify" or (a.startswith("--no-v") and "--no-verify".startswith(a)) for a in args):
        return "--no-verify skips the push check; not allowed."
    return None

class _Opts:
    """The options of one git command. git accepts any unambiguous start of a long option (--har = --hard), so a 4+
    letter start counts too; short options may be bundled (-fd)."""
    def __init__(self, args, cfg, cwd):
        self.args, self.cfg, self.cwd = args, cfg, cwd
        self.pos = [a for a in args if not a.startswith("-")]
        self.prot = [b.lower() for b in cfg["protected_branches"]]

    @staticmethod
    def _m(a, n):
        k = a.split("=", 1)[0]
        return k == n or (k.startswith("--") and len(k) >= 5 and n.startswith(k))

    def has(self, *names):
        return any(self._m(a, n) for a in self.args for n in names)

    def short(self, ch):
        return any(re.match(r"^-[A-Za-z]*" + ch, a) and not a.startswith("--") for a in self.args)

    def either(self, long, ch):
        return self.has(long) or self.short(ch)


def _push_refspecs(o):
    for p in o.pos[1:] if o.pos else []:
        if p.startswith("+"):
            return "a '+' refspec is a force push, which is never allowed."
        if p.startswith(":"):
            return "a ':' refspec deletes a remote branch or tag, which is not allowed."
        dst = p.split(":")[-1].replace("refs/heads/", "").lower()
        if dst in o.prot:
            return f"pushing to the protected branch '{dst}' is not allowed (it changes only through a reviewed pull request)."
    return None


def _git_push(o):
    if o.either("--dry-run", "n"):
        return None
    if not BREAK("guard_force") and (o.has("--force", "--force-with-lease", "--force-if-includes") or o.short("f")):
        return "force pushes are never allowed (they overwrite history others rely on)."
    if o.has("--mirror", "--prune"):
        return "mirror and prune pushes are never allowed (they can delete remote branches)."
    if o.either("--delete", "d"):
        return "deleting remote branches or tags is not allowed."
    r = _push_refspecs(o)
    if r:
        return r
    if o.cfg["push_only_via_wrapper"] and C.part(o.cfg, "push") == "on":
        return "push directly is not allowed. Push with `python fg/push.py` (on Windows, the Python path the kit's hooks use), which runs the gate and pushes only the commit that passed."
    br = current_branch(o.cwd) if len(o.pos) <= 1 else None
    if br and br.lower() in o.prot:
        return f"this folder is on the protected branch '{br}': pushing it is not allowed."
    return None


def _git_reset(o):
    if o.has("--hard", "--merge", "--keep"):
        return "reset --hard throws away uncommitted work and moves the branch; not allowed (commit the work first on a work branch, or use reset --soft; ask the owner if work should really go)."
    return None


def _git_clean(o):
    if o.either("--force", "f") and not o.either("--dry-run", "n"):
        return "clean -f deletes untracked files for good; not allowed (look first with `git clean -n`)."
    return None


def _git_branch(o):
    deleting, forced = o.either("--delete", "d"), o.either("--force", "f")
    if o.short("D") or (deleting and forced) or o.short("M") or (o.has("--move") and o.has("--force")):
        return "force-deleting or force-renaming branches is not allowed."
    if deleting and any(p.lower() in o.prot for p in o.pos):
        return "deleting a protected branch is not allowed."
    return None


# outside review 5 (Claude Fable, 13 Nov): this used to say "use git stash", but a stash that takes away a test is put
# back by the check after every step, and the stash pop then fails
KEEP_WORK = ("not allowed (use `git stash`)." if os.environ.get("FG_BREAK") == "stash_advice" else
             "not allowed (commit the work first on a work branch, or ask the owner; `git stash` is not a safe way round, "
             "because the kit puts back any test it takes away).")


HELD_BACK = []      # (copy's settings, files): a checkout that only takes back what the kit put back (F534)


def _only_held(o):
    """The game's PC, 23 Nov 04:40 UTC: the kit put a committed BUILD_ORDER.md back on disk in the night copy (held for
    the upload), which left the folder dirty, and then blocked `git checkout -- Docs/BUILD_ORDER.md`, the one command
    that cleared it. A checkout of named files, from the index, where each file is one the kit holds back at exactly
    the last commit's version, asks the owner instead."""
    if BREAK("held_checkout") or "--" not in o.args:
        return False
    i = o.args.index("--")
    before, files = o.args[:i], o.args[i + 1:]
    if len(files) != 1 or any(not a.startswith("-") for a in before) or any(any(c in f for c in "*?[:") or f in (".", "/") for f in files):
        return False
    try:
        top = subprocess.run(["git", "-C", o.cwd or ".", "rev-parse", "--show-toplevel"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
        if not top:
            return False
        import steps as SP
        c = C.load(top) if os.path.exists(os.path.join(top, "foundationguard.json")) else dict(o.cfg, _root=top)
        held, rels = SP.held(c), []
        for f in files:
            full = os.path.abspath(f if os.path.isabs(f) else os.path.join(o.cwd or top, f))
            rel = os.path.relpath(full, top).replace("\\", "/")
            v = subprocess.run(["git", "-C", top, "rev-parse", "-q", "--verify", "HEAD:" + rel], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
            if not v or held.get(rel) != v:
                return False
            rels.append(rel)
    except (OSError, ValueError):
        return False
    HELD_BACK[:] = [(c, rels)]
    return True


def _git_checkout(o):
    if o.either("--force", "f"):
        return "checkout -f throws away uncommitted changes; not allowed."
    if "--" in o.args and _only_held(o):
        return None
    if "--" in o.args or any(p in (".", "*", ":/") for p in o.pos):
        return "checking out files over the working tree throws away changes; " + KEEP_WORK
    return None


def _git_restore(o):
    if not o.either("--staged", "S") or o.either("--worktree", "W"):
        return "restore over the working tree throws away changes; " + KEEP_WORK
    return None


def _git_switch(o):
    if o.has("--discard-changes", "--force") or o.short("f"):
        return "switch --discard-changes throws away uncommitted changes; not allowed."
    return None


def _git_update_ref(o):
    return "deleting refs directly is not allowed." if o.has("-d") or o.has("--stdin") else None


def _git_reflog(o):
    if o.pos and o.pos[0] in ("expire", "delete"):
        return "expiring the reflog removes the way back from mistakes; not allowed."
    return None


def _git_prune(o):
    return None if BREAK("guard_round2") else "git prune deletes unreachable work for good; not allowed."


def _git_gc(o):
    return "gc --prune can delete unreachable work for good; not allowed." if any(a.startswith("--prune") for a in o.args) else None


def _git_tag(o):
    return "deleting tags is not allowed." if o.either("--delete", "d") else None


def _git_stash(o):
    first = o.pos[0] if o.pos else None
    if first == "drop" and not BREAK("guard_round3"):
        return "stash drop throws away saved work; not allowed (use `git stash pop` or `git stash apply`)."
    if first == "clear":
        return "stash clear throws away every stash; not allowed."
    return None


_REWRITE = lambda o: "rewriting history is not allowed."
GIT_SUBS = {"push": _git_push, "reset": _git_reset, "clean": _git_clean, "branch": _git_branch, "checkout": _git_checkout,
            "restore": _git_restore, "switch": _git_switch, "filter-branch": _REWRITE, "filter-repo": _REWRITE,
            "replace": _REWRITE, "update-ref": _git_update_ref, "reflog": _git_reflog, "prune": _git_prune, "gc": _git_gc,
            "tag": _git_tag, "stash": _git_stash}
CHANGES_BRANCH = ("commit", "merge", "rebase", "cherry-pick", "revert", "am", "pull")


def _git_protected(sub, o):
    """Work that changes the branch the folder is on, when that branch is protected."""
    moves = sub in CHANGES_BRANCH or (sub == "reset" and not o.has("--soft", "--mixed") and o.pos)
    if moves:
        br = current_branch(o.cwd)
        if br and br.lower() in o.prot and sub != "pull":
            return f"this folder is on the protected branch '{br}': it changes only through a reviewed pull request."
    if sub in ("checkout", "switch") and o.pos and o.pos[-1].lower() in o.prot and o.cfg.get("forbid_switch_to_protected"):
        return f"switching this folder to '{o.pos[-1]}' is not allowed."
    return None


def check_git(tk, cfg, cwd):
    """tk starts with git. Returns a reason to block, or None."""
    i, pairs, cwd = _git_globals(tk, cwd)
    if i >= len(tk):
        return None
    sub, args = tk[i], tk[i + 1:]
    decided, why = _git_alias_and_meta(sub, args, pairs, cfg, cwd)
    if decided:
        return why
    why = _git_hook_skips(sub, args, pairs)
    if why:
        return why
    o = _Opts(args, cfg, cwd)
    if sub in GIT_SUBS:
        why = GIT_SUBS[sub](o)
        if why or sub == "push":
            return why
    return _git_protected(sub, o)


KNOWN = {"push", "pull", "fetch", "reset", "clean", "branch", "checkout", "restore", "switch", "filter-branch",
         "filter-repo", "replace", "update-ref", "reflog", "gc", "tag", "stash", "commit", "merge", "rebase",
         "cherry-pick", "revert", "am", "status", "log", "diff", "add", "show", "blame", "rev-parse", "remote",
         "help", "config", "describe", "ls-files", "worktree", "shortlog", "check-ignore", "init", "clone", "mv", "rm",
         "grep", "bisect", "notes", "submodule", "archive", "format-patch", "apply", "cat-file", "ls-tree", "show-ref",
         "for-each-ref", "symbolic-ref", "merge-base", "rev-list", "name-rev", "range-diff", "sparse-checkout", "lfs"}


# GitHub's own protection: branch rules, rulesets, settings, who has access, keys, hooks, Actions and secrets
GH_SETTINGS = re.compile(r"(?i)(?:^|/)repos/[^/\s]+/[^/\s?]+(?:/?$|/(?:branches/[^\s]*/protection|protection|rulesets|rules|collaborators|"
                         r"invitations|teams|keys|hooks|actions/(?:permissions|secrets|variables|workflows/[^\s]*/(?:disable|enable))|"
                         r"environments|secrets|dependabot/secrets|codespaces/secrets|pages|transfer|topics|vulnerability-alerts|"
                         r"automated-security-fixes|private-vulnerability-reporting|tags/protection|autolinks|immutable-releases))"
                         r"|(?:^|/)orgs/[^/\s]+/(?:rulesets|members|memberships|actions|secrets|hooks|teams)")
WRITE_METHODS = ("PUT", "PATCH", "DELETE", "POST")


FIELD_OPTS = ("-f", "-F", "--field", "--raw-field", "--input")
VALUE_OPTS = ("-H", "--header", "-q", "--jq", "-t", "--template", "--hostname", "--cache", "-p", "--preview")


def _api_method(a, nxt):
    """The HTTP method an option of `gh api` sets: (method or None, extra words used)."""
    if a in ("-X", "--method") and nxt is not None:
        return nxt.upper(), 1
    if a.startswith("--method="):
        return a.split("=", 1)[1].upper(), 0
    if re.match(r"^-X[A-Za-z]+$", a):
        return a[2:].upper(), 0
    return None, 0


def gh_api_writes(tk):
    """For `gh api PATH ...`: (writes?, path)."""
    path, method, fields = None, None, False
    i = 2
    while i < len(tk):
        a = tk[i]
        m, used = _api_method(a, tk[i + 1] if i + 1 < len(tk) else None)
        if m is not None:
            method = m; i += 1 + used; continue
        if a in FIELD_OPTS or a.startswith(("--field=", "--raw-field=", "--input=")):
            fields = True
            i += 1 if a in FIELD_OPTS else 0
        elif a in VALUE_OPTS:
            i += 1
        elif not a.startswith("-") and path is None:
            path = a
        i += 1
    writes = (method in WRITE_METHODS) or (method is None and fields)
    return writes, (path or "")


DATA_OPTS = ("-d", "--data", "--data-raw", "--data-binary", "--json", "-F", "--form", "-Body", "--post-data", "--body-data")


def _http_method(tk, j, a):
    """The method one curl / wget / Invoke-RestMethod option sets, or None."""
    nxt = tk[j + 1].upper() if j + 1 < len(tk) else None
    if a in ("-X", "--request", "-Method", "--method"):
        return nxt
    if re.match(r"^-[A-Za-z]*X[A-Za-z]+$", a):
        return a.split("X", 1)[1].upper()
    if re.match(r"^-[a-zA-Z]*X$", a):
        return nxt
    if a.startswith(("--request=", "--method=")):
        return a.split("=", 1)[1].upper()
    return None


def check_http(tk):
    """curl / wget / Invoke-RestMethod writing to GitHub's settings API."""
    url = next((a for a in tk[1:] if "api.github.com" in a or "/api/v3/" in a), None)
    if not url:
        return None
    method = None
    for j, a in enumerate(tk):
        m = _http_method(tk, j, a)
        if m is not None:
            method = m
        elif a in DATA_OPTS and method is None:
            method = "POST"
    path = re.sub(r"^https?://[^/]+(?:/api/v3)?", "", url.strip("'\""))
    if method in WRITE_METHODS and GH_SETTINGS.search(path.split("?")[0]):
        return "changing GitHub's protection or settings is only for the owner, by hand on github.com."
    return None


GH_OWNER_ONLY = [  # (gh command, its subcommands, why) for GitHub settings only the owner changes by hand
    ("repo", ("edit", "rename", "archive", "unarchive"), "changing the repository's settings is only for the owner, by hand on github.com."),
    ("secret", ("set", "delete", "remove"), "changing the repository's secrets or variables is only for the owner."),
    ("variable", ("set", "delete", "remove"), "changing the repository's secrets or variables is only for the owner."),
    ("workflow", ("disable",), "switching off a GitHub check workflow is only for the owner.")]


def _gh_settings(tk):
    """gh commands that change GitHub's own protection or settings."""
    sub2 = tk[2] if len(tk) >= 3 else ""
    if tk[1] == "api":
        w, path = gh_api_writes(tk)
        if w and GH_SETTINGS.search(path.split("?")[0]):
            return "changing GitHub's protection or settings is only for the owner, by hand on github.com."
    for cmd, subs, why in GH_OWNER_ONLY:
        if tk[1] == cmd and sub2 in subs:
            return why
    if tk[1] == "ruleset" and sub2 not in ("list", "ls", "view", "check", ""):
        return "changing GitHub rulesets is only for the owner."
    if tk[1] == "repo" and sub2 == "deploy-key" and len(tk) >= 4 and tk[3] in ("add", "delete"):
        return "adding or removing deploy keys is only for the owner."
    return None


def _gh_merge(tk, cfg):
    if any(a in ("--admin", "--auto") for a in tk):
        return "merging with --admin or --auto is not allowed."
    sf = cfg.get("merge_signoff_file")
    if not sf:
        return None
    num = next((a for a in tk[3:] if a.isdigit()), None)
    path = os.path.join(cfg["_root"], sf)
    lines = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
    if not num or not any(l.strip().startswith("#" + num + " ") for l in lines):
        return f"merging needs the owner's sign-off for this pull request: a line '#<number> <date> <their words>' in {sf}."
    return None


def check_gh(tk, cfg, cwd):
    if not BREAK("guard_github") and len(tk) >= 2:
        why = _gh_settings(tk)
        if why:
            return why
    if len(tk) >= 3 and tk[1] == "pr" and tk[2] == "merge":
        return _gh_merge(tk, cfg)
    if len(tk) >= 3 and tk[1] == "repo" and tk[2] == "delete":
        return "deleting a repository is not allowed."
    return None

def running(names):
    try:
        if os.name == "nt":
            out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10).stdout.lower()
        else:
            out = subprocess.run(["ps", "-eo", "comm"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10).stdout.lower()
    except Exception:
        return None
    return [n for n in names if n.lower() in out]


def check_segment(seg, cfg, cwd, depth):
    tk = strip_prefixes(tokens(seg))
    if not tk:
        return None
    for inner in nested(tk):
        r = check_line(inner, cfg, cwd, depth + 1)
        if r:
            return r
    b = base(tk[0])
    if b == "git":
        return check_git(tk, cfg, cwd)
    if b == "gh":
        return check_gh(tk, cfg, cwd)
    if b in ("curl", "wget", "invoke-restmethod", "invoke-webrequest", "irm", "iwr", "http", "https") and os.environ.get("FG_BREAK") != "guard_github":
        return check_http(tk)
    return None


# The game's PC, 12 Nov (the owner said yes at 21:09 UTC): while Unreal ran, a grep or sed that only mentioned a check
# script was blocked as a heavy job. Only a part of the command that runs something counts now; a part that only reads,
# lists or prints text (grep, sed without -i, cat, Get-Content, git log ...) doesn't, unless its text is piped to a shell.
READERS = {"cat", "head", "tail", "less", "more", "nl", "ls", "dir", "wc", "grep", "egrep", "fgrep", "rg", "ag", "findstr",
           "type", "stat", "file", "diff", "cmp", "md5sum", "sha1sum", "sha256sum", "sort", "uniq", "cut", "tr", "column",
           "echo", "printf", "sed", "find", "get-content", "gc", "select-string", "sls", "get-childitem", "gci", "get-item",
           "test-path", "get-filehash", "write-output", "write-host"}
GIT_READS = {"status", "diff", "log", "show", "blame", "ls-files", "grep", "rev-parse", "cat-file"}
JOB_RUNS = re.compile(r"\$\(|`|[<>]\(")


def _only_reads(seg):
    tk = strip_prefixes(tokens(seg))
    if not tk or JOB_RUNS.search(seg):
        return False
    b = base(tk[0])
    if b == "git":
        return any(t in GIT_READS for t in tk[1:3])
    if b == "sed":
        return not any(t.startswith(("-i", "--in-place")) for t in tk[1:])
    if b == "find":
        return not any(t in ("-exec", "-execdir", "-ok", "-okdir", "-delete") for t in tk[1:])
    return b in READERS


def _runs_job(cmd, pats):
    """Does some part of the command that runs something name a heavy job?"""
    if BREAK("jobs_read_only"):
        return any(re.search(p, cmd, re.I) for p in pats)
    segs = split_chain(cmd)
    for k, seg in enumerate(segs):
        tk = strip_prefixes(tokens(seg))
        if k and tk and base(tk[0]) in SHELLS and len(tk) == 1 and any(re.search(p, segs[k - 1], re.I) for p in pats):
            return True                                       # cat full_gate.sh | bash runs it
        if _only_reads(seg) or not any(re.search(p, seg, re.I) for p in pats):
            continue
        if not tk and not BREAK("jobs_no_command"):             # only values set (drop=['full_gate.sh'], a line of a
            if "$(" in seg or "`" in seg or "<(" in seg:      # here-document fed to python): no command, unless one is
                return True                                   # run inside it (the game's PC, 16 Nov: IndexError)
            continue
        inner = nested(tk) if base(tk[0]) in SHELLS or base(tk[0]) == "eval" else []
        if inner:                                             # bash -c "grep full_gate.sh x": judge what it runs
            if any(_runs_job(t, pats) for t in inner):
                return True
            continue
        return True
    return False


def _doc_text_gone(cmd):
    """The command without the words of a document being written by cat or tee from a here-document (the game's PC,
    19 Nov: appending notes that mention a check script and hold `code marks` was blocked as a heavy job while the
    editor was open). The words stay when the shell would run something in them: an unquoted end word with $( ) or
    backticks in the text, a text piped on, or one read inside $( )."""
    if BREAK("jobs_doc_text"):
        return cmd
    def words_only(m):
        runs = not m.group(3) and re.search(r"\$\(|`", m.group(6))
        piped = re.search(r"\||>\(", m.group(2) + m.group(5))
        in_subst = re.search(r"\$\(\s*$|`\s*$", m.string[:m.start()])
        return m.group(0) if runs or piped or in_subst else f"{m.group(1)}{m.group(2)}{m.group(5)}"
    return HEREDOC.sub(words_only, cmd)


def _job_while_running(cmd, cfg):
    """No heavy jobs (builds, tests) while a listed program, such as the owner's game, runs."""
    if not cfg.get("block_while_running") or not _runs_job(_doc_text_gone(cmd), cfg.get("job_patterns", [])):
        return None
    r = running(cfg["block_while_running"])
    if r is None:
        return "the process check failed, so a heavy job can't be started safely now; try again shortly."
    if r:
        return f"{', '.join(r)} is running: no heavy jobs (builds, tests, captures) until it's closed."
    return None


def _echoed(m):
    """The words a $(echo ...) or $(printf ...) of plain words gives, written where it stood."""
    words = tokens(m.group(1) or m.group(2) or "")
    while words and words[0] in ("-n", "-e", "-E", "-ne", "-en"):
        words = words[1:]
    text = " ".join(words)
    if '"' in text or (m.group(0).lstrip("$(`").lstrip().startswith("printf") and "%" in text):
        return m.group(0)
    return '"' + text + '"' if m.string[:m.start()].endswith("=") else text


# Two outside reviews, 12 Nov: a command built on the same line went through, x="git push --force"; eval $x, or
# bash -c "$(echo git push --force)". Words that $(echo ...) gives and values set earlier on the line are now read in.
ECHOED = re.compile(r"""\$\(\s*(?:echo|printf)\s+([^()$`|;&<>\n]*)\)|`\s*(?:echo|printf)\s+([^()$`|;&<>\n]*)`""")
SETS = re.compile(r"^(?:export|declare|local|readonly|typeset)$")


PS_SET = re.compile(r"^\$([A-Za-z_]\w*)\s*=\s*(.+)$", re.S)                        # PowerShell: $x = "git push --force"
CMD_SET = re.compile(r"""^set\s+"?([A-Za-z_]\w*)=([^"]*?)"?\s*$""", re.I)          # cmd: set x=git push --force
FORMAT = re.compile(r"%[-+ 0#]*\d*(?:\.\d+)?([a-zA-Z%])")


def _printf(fmt, args):
    """What printf FORMAT ARGS writes, for %s and %b only (None when it can't be known)."""
    specs = [s for s in FORMAT.findall(fmt) if s != "%"]
    if any(s not in "sb" for s in specs):
        return None
    if not specs:
        return fmt.replace("%%", "%")
    out, args = "", list(args)
    while True:
        it = iter(args[:len(specs)] + [""] * len(specs))
        out += FORMAT.sub(lambda m: "%" if m.group(1) == "%" else next(it), fmt)
        args = args[len(specs):]
        if not args:
            return out


def _read_values(tk):
    """read [-r] [-a NAME] NAMES <<< "words": each name and the words it gets."""
    i = tk.index("<<<")
    words, opts, names, k = " ".join(tk[i + 1:]).split(), tk[1:i], [], 0
    while k < len(opts):
        o = opts[k]
        if o == "-a" and k + 1 < len(opts):
            return [(opts[k + 1], " ".join(words))]
        if o in ("-p", "-d", "-n", "-N", "-t", "-u", "-i"):
            k += 2; continue
        if not o.startswith("-"):
            names.append(o)
        k += 1
    names = names or ["REPLY"]
    return [(n, " ".join(words[j:]) if j == len(names) - 1 else (words[j] if j < len(words) else ""))
            for j, n in enumerate(names)]


def _line_value_sets(seg, tk):
    """(kind, name, value) for the ways a value is set on a line besides NAME=value: read <<<, printf -v, PowerShell's
    $x = ..., cmd's set x=..., and set -- for the positional words. Outside review 3 (Grok, 12 Nov)."""
    raw = re.sub(r"^\{\s*", "", seg.strip())
    if WIDER("windows_shells") and PS_SET.match(raw):
        m = PS_SET.match(raw)
        return [("ps", m.group(1), " ".join(tokens(m.group(2))))]
    if WIDER("windows_shells") and CMD_SET.match(raw):
        m = CMD_SET.match(raw)
        return [("cmd", m.group(1), m.group(2).strip())]
    if not tk or not WIDER("more_line_values") and not WIDER("shell_functions"):
        return []
    if tk[0] == "read" and "<<<" in tk:
        return [("sh", n, v) for n, v in _read_values(tk)]
    if tk[0] == "printf" and len(tk) >= 4 and tk[1] == "-v":
        return [("sh", tk[2], _printf(tk[3], tk[4:]))]
    if tk[0] == "set" and len(tk) > 1 and (tk[1] == "--" or not tk[1].startswith(("-", "+")) and "=" not in tk[1]):
        return [("pos", "", tk[2:] if tk[1] == "--" else tk[1:])]
    return []


def _with_known_values(cmd, calls=2):
    """The line again with each $NAME or ${NAME} set earlier on it (NAME=value) written in: a value set twice gives
    one text with its first values and one with its last. Empty when nothing is set and used. Also each call of a
    function defined on the line, with the words handed to it written into its body."""
    if not WIDER("same_line_values"):
        return []
    seen, refs, pos = {}, {}, None
    def pattern(kind, n):
        if kind == "cmd":
            return re.compile(r"%" + n + r"%|!" + n + r"!", re.I)
        return re.compile(r"\$(?:\{" + n + r"(?:\[[@*0]\])?\}|" + n + r"(?!\w))", re.I if kind == "ps" else 0)
    def put(text, pick, known):
        for r, target in refs.items():                      # declare -n r=x: $r is $x
            text = pattern("sh", r).sub("${" + target + "}", text)
        for (kind, n), v in known.items():
            text = pattern(kind, n).sub(lambda m: pick(v), text)
        return _put_positionals(text, pos) if pos is not None else text
    def learn(kind, name, value, sep=""):
        value = None if value is None else put(value, lambda v: v[-1], {n: v for n, v in seen.items() if v})
        if value is None or sep in ("$(", "(", "`") or re.search(r"[$`]", value) or (kind == "cmd" and "%" in value):
            seen[(kind, name)] = None                 # a value the kit can't know
        elif seen.get((kind, name), ()) is not None:
            seen.setdefault((kind, name), []).append(value)
    for seg, sep in split_chain(cmd, with_seps=True):
        tk = tokens(seg)
        while tk and WIDER("shell_words") and tk[0] in STRUCTURE:
            tk = tk[1:]
        for kind, name, value in _line_value_sets(seg, tk):
            if kind == "pos":
                pos = None if any(re.search(r"[$`]", w) for w in value) else value
            else:
                learn(kind, name, value)
        opts = []
        while tk and (SETS.match(tk[0]) or (tk[0].startswith("-") and len(tk) > 1)):
            opts.append(tk[0]); tk = tk[1:]
        if not tk or not all(ASSIGN.match(t) for t in tk):
            continue
        for t in tk:
            name, value = t.split("=", 1)
            if any(o.startswith("-") and "n" in o for o in opts) and WIDER("more_line_values"):
                refs[name] = value; continue          # declare -n r=x: a name for another name
            learn("sh", name, value, sep)
    known = {n: v for n, v in seen.items() if v}
    out = [put(cmd, lambda v: v[0], known), put(cmd, lambda v: v[-1], known)]
    for text in (_function_calls(cmd) if calls and WIDER("shell_functions") else []):
        out += [text] + _with_known_values(text, calls - 1)
    return [t for t in dict.fromkeys(out) if t != cmd]


FUNC_DEF = re.compile(r"(?:(?<![\w-])function\s+([A-Za-z_][\w-]*)(?:\s*\(\s*\))?|(?<![\w-])([A-Za-z_][\w-]*)\s*\(\s*\))\s*\{([^{}]*)\}")


def _function_calls(cmd):
    """f(){ git "$@"; }; f push --force: each call of a function defined on the line, as its body with the words
    handed to it written in. Outside review 3 (Grok, 12 Nov)."""
    funcs = {(m.group(1) or m.group(2)): m.group(3) for m in FUNC_DEF.finditer(cmd)} if "{" in cmd else {}
    out = []
    for seg in split_chain(cmd) if funcs else []:
        tk = strip_prefixes(tokens(seg))
        if tk and tk[0] in funcs:
            out.append(_put_positionals(funcs[tk[0]], tk[1:]))
    return out


# Outside review 3 (Grok, 12 Nov), and its neighbours: $'git' push --force (bash's $'...' quotes, which can spell a
# letter as \x67) and source <(echo git push --force) (a shell running the words echo gives) went through.
ANSI_C = re.compile(r"\$'((?:[^'\\]|\\.)*)'")
RUN_ECHOED = re.compile(r"""(?:\b(?:source|bash|sh|zsh|dash|ksh)|(?:^|(?<=[\s;&|({]))\.)\s+(?:<\s*)?"""
                        r"""<\(\s*(echo|printf)\s+([^()$`]*)\)""")


def _ansi_c(m):
    try:
        text = m.group(1).encode("latin-1", "backslashreplace").decode("unicode_escape")
    except (UnicodeDecodeError, UnicodeEncodeError, ValueError):
        return m.group(0)
    return shlex.quote(text)


def _run_echoed(m):
    words = [w for w in tokens(m.group(2)) if w not in ("-n", "-e", "-E")]
    if m.group(1) == "printf" and any("%" in w for w in words):
        return m.group(0)
    return " ".join(words)


def _unhide_names(cmd):
    """Command names computed on the line: "$(echo git) push" is git push, git $(echo push) is git push."""
    if WIDER("more_line_values"):
        cmd = RUN_ECHOED.sub(_run_echoed, ANSI_C.sub(_ansi_c, cmd))
    if WIDER("same_line_values"):
        cmd = ECHOED.sub(_echoed, cmd)
    if not BREAK("guard_round2"):
        cmd = re.sub(r"(^|[;&|]\s*)(?:\$\([^()]*\bgit\b[^()]*\)|`[^`]*\bgit\b[^`]*`)", r"\1git", cmd)
    if not BREAK("guard_round3"):
        cmd = re.sub(r"\$\(\s*(?:echo|printf)\s+['\"]?([\w./-]+)['\"]?\s*\)|`\s*(?:echo|printf)\s+['\"]?([\w./-]+)['\"]?\s*`",
                     lambda m: m.group(1) or m.group(2), cmd)
    return cmd


def _piped_code(seg, segs, k, cfg, cwd, depth):
    """echo 'git ...' | sh: the text piped into a shell is code."""
    tk = strip_prefixes(tokens(seg))
    if BREAK("guard_round2") or not k or not tk or base(tk[0]) not in SHELLS:
        return None
    if not all(t.startswith("-") and t not in ("-c",) for t in tk[1:]):
        return None
    prev = strip_prefixes(tokens(segs[k - 1]))
    if not prev or base(prev[0]) not in ("echo", "printf", "cat"):
        return None
    text = " ".join(t for t in prev[1:] if not t.startswith("-")).replace("\\n", "\n")
    return check_line(text, cfg, cwd, depth + 1)


def _with_alias(seg, aliases):
    first = seg.split(None, 1)
    if first and first[0] in aliases:
        return aliases[first[0]] + (" " + first[1] if len(first) > 1 else "")
    return seg


# Plan 2, part 5 (section 4): the GitHub logins on the owner's computer are the owner's. A helper reading a key could
# act as whoever owns it, and one changing a login could sign the computer in as the owner. A speed bump, not the lock
# (GitHub's own rules are the lock); the owner runs these in their own terminal.
LOGIN_WORDS = ("a command that reads or changes the GitHub logins on this computer (gh auth, git credential, the "
               "stored keys). Those are the owner's: a helper with a key can act as whoever owns it. If the owner wants "
               "it, they run it in their own terminal.")
GH_AUTH = {"token", "login", "logout", "refresh", "setup-git", "switch"}
GIT_CRED = {"fill", "approve", "reject", "store", "erase", "get"}


def _login_cmd(seg):
    if BREAK("guard_credential_read"):
        return None
    if re.search(r"\.git-credentials\b|\bcmdkey\b|\bfind-internet-password\b|\bhosts\.yml\b", seg):
        return LOGIN_WORDS
    t = [x for x in tokens(seg) if x]
    while t and ("=" in t[0] and not t[0].startswith("-") or os.path.basename(t[0]) in ("env", "sudo", "command", "exec")):
        t = t[1:]
    if not t:
        return None
    prog = os.path.basename(t[0]).lower().removesuffix(".exe")
    rest = t[1:]
    if prog == "gh" and rest[:1] == ["auth"]:
        sub = rest[1] if len(rest) > 1 else ""
        if sub in GH_AUTH or (sub == "status" and ({"--show-token", "-t"} & set(rest))):
            return LOGIN_WORDS
    if prog.startswith("git-credential") and (set(rest) & GIT_CRED or not rest):
        return LOGIN_WORDS
    if prog == "git":
        i = 0
        while i < len(rest) and rest[i].startswith("-"):
            i += 2 if rest[i] in ("-c", "-C") else 1
        sub = rest[i:]
        if sub[:1] == ["credential"] or (sub[:1] and sub[0].startswith("credential-")):
            return LOGIN_WORDS
        if sub[:1] == ["config"]:
            keys = [x for x in sub[1:] if not x.startswith("-")]
            reads = {"--get", "--get-all", "--list", "-l", "--get-regexp"} & set(sub)
            if keys and keys[0].lower().startswith("credential") and (not reads or "--unset" in sub):
                return LOGIN_WORDS
    return None


def _check_segments(segs, cfg, cwd, depth):
    aliases = {}
    for k, seg in enumerate(segs):
        am = re.match(r"^\s*alias\s+([\w.-]+)=(.*)$", seg)
        if am and not BREAK("guard_round3"):
            aliases[am.group(1)] = " ".join(tokens(am.group(2)))
            continue
        seg = _with_alias(seg, aliases)
        r = _login_cmd(seg) or check_segment(seg, cfg, cwd, depth) or _piped_code(seg, segs, k, cfg, cwd, depth)
        if r:
            return r
    return None


def check_line(cmd, cfg, cwd=None, depth=0, values=True):
    if depth > 5:
        return "the command nests too deeply to check safely."
    for rule in cfg.get("extra_block", []):
        if re.search(rule["pattern"], cmd):
            return rule["why"]
    r = _job_while_running(cmd, cfg) or GS.env_settings(cmd)     # git settings in the environment (review 7)
    if r:
        return r
    plain = _unhide_names(cmd)
    r = _check_segments(split_chain(plain), cfg, cwd, depth) or _lfs_pointer_write(plain, cwd)
    if r or not values:
        return r
    for wider in _with_known_values(plain):          # the same line with the values set on it written in
        r = check_line(wider, cfg, cwd, depth + 1, values=False)
        if r:
            return r
    return None


# The build thread, 12 Nov 16:29 UTC: AGENT_SETUP's own advice, "git show HEAD:path > path", writes Git LFS's small
# pointer file (about 130 bytes of text), not the file, when the path is kept in LFS (every .uasset and .umap in the
# game). git show and git cat-file give what git stores, and for an LFS file that is the pointer; git cat-file --filters
# runs LFS's filter and writes the real file. (git restore and git checkout, which also run it, are blocked above as
# work-destroying.) So a git show or cat-file whose output lands on a path LFS keeps is refused, with the safe command.
STDOUT_TO = re.compile(r"""(?:^|[^\d&>])(?:1|&)?>>?\|?\s*(?:"([^"]+)"|'([^']+)'|([^\s'"<>|;&()]+))""")
OUTPUT_OPT = re.compile(r"""(?:^|\s)--output(?:=|\s+)(?:"([^"]+)"|'([^']+)'|([^\s'"<>|;&()]+))""")


def _heredoc_data_gone(cmd):
    """The command without the text of a here-document fed to cat or tee: a doc being written, not code. A body piped on
    or read inside $( ) stays."""
    def data_only(m):
        piped = re.search(r"\||>\(", m.group(2) + m.group(5))
        in_subst = re.search(r"\$\(\s*$|`\s*$", m.string[:m.start()])
        return m.group(0) if piped or in_subst else f"{m.group(1)}{m.group(2)}{m.group(5)}"
    return HEREDOC.sub(data_only, cmd)


def _stdout_files(seg):
    """The files this part of a command sends its output into: > FILE, >> FILE, 1> FILE, &> FILE, --output=FILE."""
    hits = list(STDOUT_TO.finditer(seg)) + list(OUTPUT_OPT.finditer(seg))
    return [next(g for g in m.groups() if g) for m in hits]


def _lfs_kept(path, cwd):
    """Does git keep this path in LFS here (its filter attribute is lfs)?"""
    try:
        r = subprocess.run(["git", "-C", cwd, "check-attr", "-z", "filter", "--", P.shell_path(path)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0 and r.stdout.split("\0")[2:3] == ["lfs"]


def _lfs_pointer_write(cmd, cwd):
    """Why to refuse a git show / git cat-file whose output lands on a file LFS keeps, or None."""
    if BREAK("lfs_pointer") or not cwd:
        return None
    parts = split_chain(_harmless_gone(_heredoc_data_gone(cmd)), with_seps=True)
    for k, (seg, sep) in enumerate(parts):
        tk = strip_prefixes(tokens(seg))
        if not tk or base(tk[0]) != "git":
            continue
        i = _git_globals(tk, cwd)[0]
        if i >= len(tk) or tk[i] not in ("show", "cat-file") or "--filters" in tk[i + 1:]:
            continue
        dests = _stdout_files(seg)
        if sep == "|" and k + 1 < len(parts):
            nxt = strip_prefixes(tokens(parts[k + 1][0]))
            if nxt and base(nxt[0]) == "tee":
                dests += [t for t in nxt[1:] if not t.startswith("-")]
        for d in dests:
            if _lfs_kept(d, cwd):
                spec = next((a for a in tk[i + 1:] if ":" in a and not a.startswith("-")), "HEAD:" + d)
                return (f"'{d}' is kept in Git LFS, so git {tk[i]} would write LFS's small pointer file there, not the "
                        f"file. To get it back as it was, run: git cat-file --filters {spec} > {d}  (it runs LFS's "
                        "filter). In PowerShell, > turns the bytes into text, so run that line through bash or cmd /c.")
    return None

# open() for writing: a mode such as "w", "a", "x", "r+" or "wb" (the game's PC, 11 Nov: reading 'assets_baseline.json'
# asked the owner, because the file's name starts with an a)
OPEN_WRITE = (r"open\([^)]*['\"][wax+]" if os.environ.get("FG_BREAK") == "guard_reads_only" else
              r"\bopen\([^)]*['\"](?=[rbt]*[wax+])[rwaxbt+]{1,4}['\"]")
WRITEISH = re.compile(r"(>>?|\btee\b|\bsed\s+-i|\bperl\s+-[a-z]*i|\b(cp|mv|rm|rmdir|ln|truncate|dd|install|touch|chmod|unlink)\b|"
                      r"Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|Copy-Item|New-Item|"
                      + OPEN_WRITE + r"|write_text|write_bytes|writeFile|appendFile|unlinkSync|rmSync|"
                      r"\bgit\s+(checkout|restore|rm|mv|apply|am|cherry-pick|revert|stash\s+pop|reset)"
                      + ("" if os.environ.get("FG_BREAK") == "guard_missed_writes" else r"|\bgit\b[^;&|]*\s--output(?:=|\s)")
                      + ")")       # found on the way, 11 Nov: git diff --output=FILE writes FILE

# A command that only reads or lists (the game's PC, 11 Nov: "cat fg/install.py", "git diff -- fg/install.py" and
# "grep -n 'rm -rf' fg/guard.py" asked the owner, because the text held a word that looks like a write). Not one that
# runs other code or writes a file of its own: a $(...) or `...`, a redirect still in the text, rg --pre, git grep -O,
# git's --output.
READS_ONLY = re.compile(r"^(?:[A-Za-z_]\w*=\S*\s+)*(?:cat|head|tail|ls|dir|wc|grep|egrep|fgrep|rg|findstr|type|stat|diff|"
                        r"cmp|md5sum|sha1sum|sha256sum|Get-Content|gc|Select-String|sls|Get-ChildItem|gci|Get-Item|"
                        r"Test-Path|Get-FileHash|git\s+(?:-C\s+\S+\s+)?(?:--no-pager\s+)?(?:status|diff|log|show|blame|"
                        r"ls-files|grep|rev-parse|cat-file))(?=\s|$)")
RUNS_OR_WRITES = re.compile(r"\$\(|`|[<>]\(|>|--output|--pre\b|(?:^|\s)-O|--open-files-in-pager")
# The text given to the kit's own check (guard.py --check "...") is checked, never run, so it is data. Not when the
# shell would run code inside it ("$(...)" or `...` in double quotes).
KIT_CHECK = re.compile(r"""(\bguard\.py["']?\s+(?:--home\s+(?:"[^"]*"|'[^']*'|\S+)\s+)?--check\s+)"""
                       r"""("(?:[^"\\$`]|\\.)*"|'[^']*')""")


def _reads_only(seg):
    """Does this part of a command only read or list files?"""
    if os.environ.get("FG_BREAK") == "guard_reads_only":
        return False
    if RUNS_OR_WRITES.search(seg):
        return False
    if READS_ONLY.match(seg.strip()):
        return True
    return _sed_prints(seg) or bool(PRINTERS.match(seg.strip()))


# The game's PC and the owner, 15 Nov (friction log): "sed -n 1,30p fg/install.py | grep ... | cut ..." raised a box
# because "install" in the file's name looked like a write and sed wasn't known to only print. sed counts as reading when
# it has no -i and its script has no w (write), W or e (run) command; cut, tr and nl only print.
PRINTERS = re.compile(r"^(?:cut|tr|nl)(?=\s|$)" if os.environ.get("FG_BREAK") != "guard_sed_reads" else r"^(?!)")
SED_WRITES = re.compile(r"(?:^|[;{}\s/0-9$!])[wWe](?:\s|$)|/[a-zA-Z]*[we][a-zA-Z]*(?:\s|$)")


def _sed_writes(seg):
    """Found on the way, 15 Nov: sed's own w command ("s/a/b/w FILE", "1w FILE") wrote a guard file with no ask."""
    if os.environ.get("FG_BREAK") == "guard_sed_w":
        return False
    tk = strip_prefixes(tokens(seg))
    return bool(tk) and base(tk[0]) == "sed" and not _sed_prints(seg)


def _sed_prints(seg):
    if os.environ.get("FG_BREAK") == "guard_sed_reads":
        return False
    tk = strip_prefixes(tokens(seg))
    if not tk or base(tk[0]) != "sed":
        return False
    for t in tk[1:]:
        if t.startswith(("-i", "--in-place", "-f", "--file", "-s")) or (t.startswith("-") and not t.startswith("--") and "i" in t):
            return False
    scripts = [t for i, t in enumerate(tk[1:], 1) if tk[i - 1] in ("-e", "--expression")] or \
              [t for t in tk[1:] if not t.startswith("-")][:1]
    return bool(scripts) and not any(SED_WRITES.search(x) for x in scripts)


def _kit_check_text_gone(seg):
    return seg if os.environ.get("FG_BREAK") == "guard_reads_only" else KIT_CHECK.sub(lambda m: m.group(1) + '""', seg)


# Text that looks like a write but writes no file (weaker-AI test, 10 Nov: these made every "commit and push" ask the owner):
# copying one output stream into another (2>&1), throwing output away (>/dev/null), and a commit message's own text
# (an author line "<name@example.com>" holds a ">").
MESSAGE = (r"(?:-m|--message)" if os.environ.get("FG_BREAK") == "guard_reads_only" else
           r"(?:-[a-z]*m|--message)")         # 11 Nov: also git commit -qm / -am "..."
HARMLESS = re.compile(r"\d*>&\d+|&>>?\s*/dev/null|\d*>>?\s*/dev/null|"
                      r"(?<=\s)" + MESSAGE + r"(?:=|\s+)(?:\"(?:[^\"\\]|\\.)*\"|'[^']*')")


def _harmless_gone(cmd):
    if os.environ.get("FG_BREAK") == "guard_harmless_redirects":
        return cmd
    def keep_running_code(m):            # a message that runs code ($(...) or `...`) stays, unless it is only a here-document
        t = m.group(0)
        runs = "$(" in t or "`" in t
        heredoc_only = re.match(MESSAGE + r"""(?:=|\s+)"\$\(cat <<-?['"]?(\w+)['"]?\n(?:(?!\$\(|`).)*\n\1\n?\)"$""", t, re.S)
        return t if runs and not heredoc_only else " "
    return HARMLESS.sub(keep_running_code, cmd)


HEREDOC = re.compile(r"""\b(cat|tee)\b([^\n]*?)<<-?\s*(['"]?)(\w+)\3([^\n]*)\n(.*?)\n\4(?=\n|$)""", re.S)
REDIRECT = re.compile(r"(?<![<>&\d])\d*>>?\|?\s*([^\s;&|<>()]+)")


SEARCHERS = {"grep", "egrep", "fgrep", "rg", "ag", "ack", "findstr", "select-string", "sls", "zgrep", "pcregrep"}
QUOTE_RUNNERS = re.compile(r"(?:^|[\s;&|(`'\"/\\])(?:(?:ba|z|da|k|c|tc|fi)?sh|eval|cmd|powershell|pwsh|wsl|ssh|su|sudo|"
                           r"doas|runas|xargs|parallel|watch|script|expect|busybox|env|nohup|setsid|start|exec|source|CMD|PowerShell|Pwsh)"
                           r"(?:\.exe|\.EXE)?(?=[\s\"']|$)|-exec(?:dir)?\b|-c\s*[\"']|\.\s+[\"']")


def _plain_quoted_spans(text):
    """The game's PC, 21 Nov 04:50 UTC: grep -rn "PC->My[A-Z][A-Za-z]*(" Source asked the owner about a redirect into
    the game's project file, because the > of the search text "->" was read as a redirect into the pattern after it,
    and that pattern matched the project file. Text inside quotes is a character string to the shell: its > writes
    nothing. The (start, end) of each quoted string the shell runs nothing inside (no $(...) or `...`)."""
    if BREAK("redirect_in_quotes") or QUOTE_RUNNERS.search(text):
        return []                             # bash -c "... > x", eval "...", find -exec sh -c: the quotes are run
    try:
        tk = strip_prefixes(tokens(text))
    except Exception:
        return []
    word = base(tk[0]).lower() if tk else ""
    if word not in SEARCHERS and not (word == "git" and "grep" in tk[1:3]):
        return []                             # only a search's pattern: echo 'x > f' | bash runs its quoted text
    spans, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2; continue
        if c in "'\"":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if c == '"' and text[j] == "\\" else 1
            if j >= n:
                return spans                  # an unclosed quote: leave the rest as it is
            body = text[i + 1:j]
            if c == "'" or not ("$(" in body or "`" in body):
                spans.append((i, j + 1))
            i = j + 1; continue
        i += 1
    return spans


def _redirect_targets(text, globs, cwd, root, cfg=None):
    """(guard file a redirect writes to or None, the text with data-only here-documents and resolved redirects taken out).
    A here-document fed to cat or tee is data, not commands. A redirect whose target can't be read (a variable) is left in,
    so the old rule (any guard file named anywhere) still applies to it."""
    if os.environ.get("FG_BREAK") == "guard_redirect_targets":
        return None, text
    def data_only(m):                     # piped on, or inside $(...), the "data" may still be run as commands
        piped = re.search(r"\||>\(", m.group(2) + m.group(5))
        in_subst = re.search(r"\$\(\s*$|`\s*$", m.string[:m.start()])
        return m.group(0) if piped or in_subst else f"{m.group(1)}{m.group(2)}{m.group(5)}"
    text = HEREDOC.sub(data_only, text)
    hit = None
    quoted = _plain_quoted_spans(text)
    def take(m):
        nonlocal hit
        if any(a <= m.start() < z for a, z in quoted):
            return m.group(0).replace(">", " ")   # a > inside quoted text is a character, not a redirect (F521)
        t = P.shell_path(m.group(1).strip("'\""))
        if any(ch in t for ch in "*?[") and not any(ch in t for ch in "$`") and WIDER("variable_paths"):
            import glob as GL                     # echo x > APPROVED.m? writes the guard file the pattern matches
            for g in GL.glob(t if os.path.isabs(t) else os.path.join(cwd or root, t)):
                if P.matches(P.rel(g, root), globs):
                    hit = hit or P.rel(g, root)
        if any(ch in t for ch in "$`*?"):
            return m.group(0)
        full = t if os.path.isabs(t) else os.path.join(cwd or root, t)
        r = P.rel(full, root)
        if P.matches(r, globs) or P.matches(t, globs):
            hit = hit or r
        elif cfg:
            hit = hit or guard_elsewhere(full, cfg)
        return " "
    text = REDIRECT.sub(take, text)
    return hit, text


PARTS_MANY = re.compile(r"\bparts\.py\b\s+(only|preset|pick)\b([^|;&]*)")       # v0.8.5: the developer screen's other ways to switch features
RECORD = re.compile(r"\b(?:rules|structure|assets|tiny|docs)\.py\b[^|;&]*--(?:baseline|allow)\b|\bparts\.py\b[^|;&]*\bset\b"
                    + ("" if os.environ.get("FG_BREAK") == "parts_guard_many" else "|" + PARTS_MANY.pattern))


def _named_guard_file(scope, here, root, globs, cfg=None):
    """The first guard file named in this text, or None. A guard folder counts by its bare name too (found on the way,
    11 Nov: "rm -rf tests" deleted a guarded test folder without the kit asking, because "tests" has no / or .)."""
    folders = set() if os.environ.get("FG_BREAK") == "guard_missed_writes" else \
        {g[:-3] for g in globs if g.endswith("/**") and not any(c in g[:-3] for c in "*?[")}
    words = []
    for m in re.finditer(r"[\w./\\:-]+", scope):
        words.append(m.group(0))
        # found on the way, 19 Nov: cp x "$S/../$Q/fg/structure.py" went through, because the words after a variable
        # in the middle of a path start with a slash and read as a path from the drive's top
        w, pre = m.group(0), scope[:m.start()]
        if BREAK("after_a_variable"):
            continue
        if pre.endswith(("$", "${")) and re.search(r"[/\\]", w):            # $Q/fg/x: the words after the name
            words.append(re.split(r"[/\\]", w, maxsplit=1)[1].lstrip("/\\"))
        elif w[:1] in "/\\" and re.search(r"\$\{?\w+\}?[\"']?$", pre):     # ${Q}/fg/x, "$Q"/fg/x
            words.append(w.lstrip("/\\"))
    for w in words:
        if "/" in w or "." in w or "\\" in w or w.rstrip("/\\") in folders:
            w = P.shell_path(w)
            r2 = P.rel(os.path.join(here, w), root) if not os.path.isabs(w) else P.rel(w, root)
            if P.matches(r2, globs) or P.matches(w, globs):
                return r2
            there = cfg and guard_elsewhere(os.path.join(here, w), cfg)
            if there:
                return there
    return None


TOUCH = [""]                        # how guard_touch read its answer from the command, for the box and the catch log


# Outside review 3 (Claude, 12 Nov): echo '{"parts":{"guard":"off"}}' > "$PWD/foundationguard.json" switched the guard off
# with no ask, because a target written through a variable wasn't read (the kit's own hooks spell paths that way). The
# folders the kit knows are written in ($PWD, $CLAUDE_PROJECT_DIR, $HOME, ~ and PowerShell's forms), and a folder it
# can't know ("$D/APPROVED.md") is taken as the project, so the name after it is judged.
KNOWN_DIR = re.compile(r"\$\{?(PWD|CLAUDE_PROJECT_DIR|HOME|USERPROFILE)\}?(?!\w)|\$env:(CLAUDE_PROJECT_DIR|USERPROFILE|HOME)(?!\w)|"
                       r"(?<![\w/~.-])~(?=[/\\])", re.I)
UNKNOWN_DIR = re.compile(r"\$\{?[A-Za-z_]\w*\}?(?=[/\\])|\$env:[A-Za-z_]\w*(?=[/\\])", re.I)


def _known_places(cmd, cwd, root):
    """The command again with the folders named by a variable written in, for the guard-file checks."""
    if not WIDER("variable_paths") or "$" not in cmd and "~" not in cmd:
        return []
    def known(m):
        n = (m.group(1) or m.group(2) or "").upper()
        place = cwd or root if n == "PWD" else os.environ.get("CLAUDE_PROJECT_DIR") or root if n == "CLAUDE_PROJECT_DIR" \
            else os.path.expanduser("~")
        return place.replace("\\", "/")
    a = KNOWN_DIR.sub(known, cmd)
    b = UNKNOWN_DIR.sub(lambda m: root.replace("\\", "/"), a)
    return [t for t in dict.fromkeys([a, b]) if t != cmd]


# Outside review 3 (Claude, 12 Nov, finding 2): git apply and patch changed any file with no ask, guard files included,
# because the files a patch changes are named inside the patch, not on the line. The patch is read (a file, a here-document
# or < FILE) and every file it names is judged; a patch the kit can't read (piped, from a variable) counts as changing one.
PATCH_NAMES = re.compile(r"^(?:diff --git \"?(\S+?)\"? \"?(\S+?)\"?|(?:---|\+\+\+) \"?([^\t\n\"]+?)\"?(?:\t.*)?|"
                         r"(?:rename|copy) (?:from|to) (.+?)|Index: (.+?))\s*$", re.M)
ANY_HEREDOC = re.compile(r"""<<-?\s*(['"]?)([\w.-]+)\1([^\n]*)\n(.*?)\n[ \t]*\2[ \t]*(?=\n|$)""", re.S)
PATCH_LOOKS = {"--check", "--stat", "--numstat", "--summary"}
PATCH_VALUE = {"-d", "--directory", "-i", "--input", "-o", "--output", "-r", "--reject-file", "-B", "--prefix", "-D",
               "--ifdef", "-F", "--fuzz", "-p", "--strip", "-V", "--version-control", "-z", "--suffix", "-Y",
               "--basename-prefix", "-g", "--get", "--quoting-style"}


def _patch_names(text):
    out = []
    for m in PATCH_NAMES.finditer(text):
        for g in m.groups():
            g = (g or "").strip()
            if g and g != "/dev/null":
                out += [g] + ([g.split("/", 1)[1]] if "/" in g else [])      # a/x and b/x: with and without the first part
    return out


def _patch_args(tk):
    """(the folder it works in, the files it reads the patch from, files it names as targets, look-only) for git apply,
    git am or patch; None when the words aren't one of them."""
    while tk and (ASSIGN.match(tk[0]) or tk[0] in ("sudo", "command", "exec", "nohup", "time", "env")):
        tk = tk[1:]
    if not tk:
        return None
    b, sub = base(tk[0]), ""
    if b == "git":
        rest = tk[1:]
        while rest[:1] and rest[0].startswith("-"):
            if rest[0] == "-C" and len(rest) > 1:
                sub = os.path.join(sub, rest[1])
            rest = rest[2:] if rest[0] in ("-C", "-c") else rest[1:]
        if not rest or rest[0] not in ("apply", "am"):
            return None
        args = rest[1:]
        look = (rest[0] == "apply" and bool(PATCH_LOOKS & set(args)) and "--apply" not in args) or \
               (rest[0] == "am" and bool({"--abort", "--quit", "--show-current-patch"} & set(args)))
        d = next((a.split("=", 1)[1] for a in args if a.startswith("--directory=")), "")
        return os.path.join(sub, d), [a for a in args if not a.startswith("-")], [], look
    if b != "patch":
        return None
    args, src, targets, i, pos, d = tk[1:], [], [], 0, [], ""
    while i < len(args):
        a, nxt = args[i], args[i + 1] if i + 1 < len(args) else ""
        if a in PATCH_VALUE:
            if a in ("-i", "--input"):
                src.append(nxt)
            elif a in ("-o", "--output"):
                targets.append(nxt)
            elif a in ("-d", "--directory"):
                d = nxt
            i += 2; continue
        if a.startswith("--input=") or (a.startswith("-i") and len(a) > 2 and not a.startswith("--")):
            src.append(a.split("=", 1)[1] if a.startswith("--") else a[2:])
        elif a.startswith("--output="):
            targets.append(a.split("=", 1)[1])
        elif a.startswith("--directory="):
            d = a.split("=", 1)[1]
        elif not a.startswith("-") or a == "-":
            pos.append(a)
        i += 1
    if pos:
        targets.append(pos[0])                         # patch FILE [PATCHFILE]: the first names the file it changes
    return d, src + pos[1:2], targets, "--dry-run" in args


def _patch_touch(text, cfg, cwd, depth=0):
    """The guard file a git apply, git am or patch would change, or None."""
    if not WIDER("patch_files") or not re.search(r"\b(?:apply|am|patch)\b", text):
        return None
    root = cfg["_root"]
    bodies = [m.group(4) for m in ANY_HEREDOC.finditer(text)]
    flat = ANY_HEREDOC.sub(lambda m: "<<" + m.group(2) + m.group(3), text)
    parts = split_chain(flat, with_seps=True)
    for seg, _ in parts:
        inner = [t for t in nested(tokens(seg)) if t and t != seg][:4] if depth < 3 else []
        for t in inner:                                # bash -c 'git apply x.patch', eval ...
            hit = _patch_touch(t, cfg, cwd, depth + 1)
            if hit:
                return hit
        redir = re.search(r"(?<![<\d])<(?![<(])\s*(['\"]?)([^\s'\"|;&<>]+)\1", seg)
        heredoc = re.search(r"<<<?", seg)
        got = _patch_args(tokens(re.sub(r"\d?<<?<?\s*\S+", " ", seg)))
        if not got or got[3]:
            continue
        d, src, targets, _ = got
        here = os.path.join(cwd or root, d) if d else (cwd or root)
        names, unread = list(targets), False
        if redir:
            src.append(redir.group(2))
        made_here = False
        for s in src:
            full = os.path.join(cwd or root, os.path.expanduser(P.shell_path(s)))
            if not os.path.isfile(full) and s != "-" and "$" not in s and "`" not in s and not BREAK("patch_made_here") \
                    and re.search(r">\s*['\"]?" + re.escape(s) + r"['\"]?(?:\s|$)", flat):
                made_here = True                       # the game's PC, 16 Nov: the patch is written earlier in this command
                got_names = [x for b in bodies for x in _patch_names(b)]
                names += got_names
                unread = unread or not got_names
                continue
            if s == "-" or "$" in s or "`" in s or not os.path.isfile(full):
                unread = True; continue
            try:
                with open(full, encoding="utf-8", errors="replace") as f:
                    names += _patch_names(f.read(2_000_000))
            except OSError:
                unread = True
        if heredoc and "<<<" not in seg:
            names += [x for b in bodies for x in _patch_names(b)]
        elif not src and not redir:
            unread = True                              # piped in, a here-string, or a patch given some other way
        for name in names:
            for at in dict.fromkeys([here, root, cwd or root]):
                hit = _guarded(os.path.normpath(os.path.join(at, P.shell_path(name))), cfg)
                if hit:
                    TOUCH[0] = "a file the patch changes (" + name + ")"
                    return hit[1]
        if unread and made_here:
            TOUCH[0] = ("a patch written in this same command, which the kit can't read yet, so it may change any file. "
                        "Write the patch in its own step first, then apply it")
            return "(the files a patch changes: the patch is made in this same command)"
        if unread:
            TOUCH[0] = "a patch the kit can't read, so it may change any file"
            return "(the files a patch changes: the kit can't read this patch)"
    return None


def guard_touch(cmd, cfg, cwd):
    """The guard file a shell command would write to, or None. Text check: a mention of a guard path plus a write."""
    if os.environ.get("FG_BREAK") == "guard_self":
        return None
    if RECORD.search(cmd) and os.environ.get("FG_BREAK") != "rules_guard":
        TOUCH[0] = "a command that re-records a record or lets something new in"
        return "the size, rule and licence records (structure_baseline.json / rules_baseline.json / assets_baseline.json)"   # rewriting a record or allowing a dependency
    hit = _patch_touch(cmd, cfg, cwd)
    if hit:
        return hit
    globs = C.guard_globs(cfg)
    root = cfg["_root"]
    text = _harmless_gone(cmd)
    if not WRITEISH.search(text) and not re.search(r"\bpy(?:thon[\d.]*)?(?:\.exe)?['\"]?\s", text) and \
            not any(_sed_writes(x) for x in split_chain(text)):
        return None
    parts, pieces = _write_segments(text, cwd or root)
    for seg, here, i in parts:
        if here is None:
            TOUCH[0] = "a write after cd into a folder named by a variable (it could be any folder)"
            return "(a file in a folder named by a variable, after cd)"
        for one in _put_in(seg, i, pieces, text) or [seg]:     # the part, or each way the line's own words fill it
            hit = _part_touch(one, here, root, globs, text, cfg)
            if hit and _free_test_move(one, here, cfg):
                CL.log(cfg, "moved or copied tests (no ask)", hit, one)
                STEP["free"] += _step_free_paths(one, here, cfg)
                continue
            if hit:
                return hit
    return None


def _python_inline(seg):
    """python -c '...' or python - <<'EOF' ... EOF: judged by fg/pywrites.py, or as a write when it can't follow it."""
    return bool(re.search(r"\bpy|\$", seg)) and PW.program(seg.strip(), tokens) is not None


def _python_unclear(seg):
    """An inline Python program (python -c, python - <<'EOF') whose writes the kit can't follow: it may write any file,
    so it counts as a write (found on the way, 12 Nov: os.remove, os.rename, shutil and Path.unlink changed a guard file
    without the kit asking, because none of them looked like a write)."""
    if BREAK("guard_python_calls") or "python" not in seg and "py " not in seg:
        return False
    got = PW.program(seg.strip(), tokens)
    return got is not None and PW.writes(got[1]) is None


def _python_touch(seg, here, root, globs, cfg):
    """(True, the guard file it writes or None) for a short Python program whose writes the kit can follow
    (fg/pywrites.py); (False, None) when it can't, and the old rule applies."""
    got = None if BREAK("python_writes") else PW.program(seg.strip(), tokens)
    targets = PW.writes(got[1]) if got else None
    if targets is None:
        return False, None
    for x in got[0]:                                  # cd Docs && python - <<'EOF': the cd moves where its paths point
        m = re.match(r"(?:pushd|cd)\s+(['\"]?)([^\s'\";&|]+)\1\s*$", x)
        if m and not VARIABLE.search(m.group(2)) and m.group(2) != "-":
            here = os.path.normpath(os.path.join(here, os.path.expanduser(P.shell_path(m.group(2)))))
        elif m or WRITEISH.search(x) or VARIABLE.search(x):
            return False, None
    for t in targets:
        full = os.path.normpath(t if os.path.isabs(t) else os.path.join(here, t))
        r = P.rel(full, root)
        hit = r if P.matches(r, globs) else (cfg and guard_elsewhere(full, cfg))
        if hit:
            TOUCH[0] = "a file the Python program in it writes (" + t + ")"
            return True, hit
    return True, None


# the owner's choice, 12 Nov (the game's PC: moving a new test out to scratch and back, or restoring one with git show, asked
# every time): a test that isn't committed yet guards nothing yet, so moving or deleting it goes through; a file copied
# into a guarded test's place (cp, mv, git show REV:PATH > FILE, git cat-file --filters REV:PATH > FILE, cat FILE > FILE)
# is judged by the text it puts there, exactly as the editing tools' Write is (new tests add freely, F171). Any other
# shell write to a test still asks.
MOVE_FLAGS = {"rm": {"-f", "-v", "--force", "--verbose", "-fv", "-vf"},
              "mv": {"-f", "-v", "-n", "--force", "--verbose", "--no-clobber", "-fv", "-vf"},
              "cp": {"-f", "-v", "-p", "--force", "--verbose", "--preserve", "-fv", "-vf", "-pv", "-vp"}}
COPY_IN = re.compile(r"""^\s*(?:git\s+(?:--no-pager\s+)?show\s+([^\s'"]+:[^\s'"]+)|cat\s+([^\s'"<>|]+)|"""
                     r"""git\s+(?:--no-pager\s+)?cat-file\s+--filters\s+([^\s'"]+:[^\s'"]+))\s*>\s*([^\s'"<>|&;]+)\s*$""")


def _guarded(full, cfg):
    """(the settings that guard this file, its path there) when it is a guard file here or in another copy, else None."""
    r = P.rel(full, cfg["_root"])
    if P.matches(r, C.guard_globs(cfg)):
        return cfg, r
    there = guard_elsewhere(full, cfg)
    return (there.cfg, there.rel) if there else None


def _uncommitted_test(own, rel, full):
    """A test file the owner's own guard covers, that isn't in the last commit (new, or only staged) and is that file itself."""
    return AD.uncommitted(own, rel, full)


def _lands_like_write(full, text, cfg):
    """A file whose new text is put at full: free (True) when the editing tools' Write of that text would be."""
    if os.path.islink(full):
        return False                                  # it could write through to any file
    g = _guarded(full, cfg)
    if not g:
        return True
    return text is not None and AD.free_reason(g[0], g[1], "Write", {"content": text}, full) is None


def _read(full):
    try:
        if os.path.isfile(full) and os.path.getsize(full) < 4_000_000:
            return open(full, encoding="utf-8", errors="replace").read()
    except OSError:
        pass
    return None


def _step_free_paths(seg, here, cfg):
    """The files a free move, copy or delete of tests names, for the check after the step."""
    return [os.path.normpath(os.path.join(here, P.shell_path(t))) for t in tokens(seg)[1:]
            if t and not t.startswith("-") and t not in (">", ">>")]


def _free_test_move(seg, here, cfg):
    """True when this part of a command only moves, deletes or copies tests the way the owner allowed on 12 Nov."""
    if BREAK("tests_free_until_commit") or VARIABLE.search(seg) or re.search(r"[*?\[\]{}~`]", seg) or "\n" in seg.strip():
        return False
    full = lambda t: os.path.normpath(os.path.join(here, P.shell_path(t)))
    m = COPY_IN.match(seg)
    if m:
        if any((x or "").startswith("-") for x in m.groups()):
            return False                              # an option, not a file (git show --output=... writes one)
        dest = full(m.group(4))
        if m.group(3) and BREAK("restore_by_filters"):
            return False
        if m.group(1) or m.group(3):          # the build thread, 12 Nov: the LFS-safe restore (git cat-file --filters) too
            how = ["show", m.group(1)] if m.group(1) else ["cat-file", "--filters", m.group(3)]
            try:
                r = subprocess.run(["git", "-C", here] + how, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=20)
            except (OSError, subprocess.SubprocessError):
                return False
            text = r.stdout if r.returncode == 0 else None
        else:
            text = _read(full(m.group(2)))
        return _lands_like_write(dest, text, cfg)
    tk = strip_prefixes(tokens(seg))
    b = base(tk[0]) if tk else ""
    if b not in MOVE_FLAGS or not all(t in MOVE_FLAGS[b] for t in tk[1:] if t.startswith("-")):
        return False
    if "--" in tk:
        return False
    args = [full(t) for t in tk[1:] if not t.startswith("-")]
    if any(os.path.islink(a) for a in args):
        return False
    if b == "rm":
        return bool(args) and all((_guarded(a, cfg) is None) or _uncommitted_test(*_guarded(a, cfg), a) for a in args)
    if len(args) != 2:
        return False
    src, dest = args
    if os.path.isdir(dest):
        dest = os.path.join(dest, os.path.basename(src))
    g = _guarded(src, cfg)
    if b == "mv" and g and not _uncommitted_test(*g, src):
        return False                                  # moving a committed test (or another guard file) away asks
    return _lands_like_write(dest, _read(src), cfg)


def _part_touch(seg, here, root, globs, text, cfg=None):
    sure, hit = _python_touch(seg, here, root, globs, cfg)
    if sure:
        return hit
    unclear = _python_unclear(seg)
    hit, seg = _redirect_targets(_kit_check_text_gone(seg), globs, here, root, cfg)
    if hit:
        TOUCH[0] = "a redirect (> or >>) into it"
        return hit
    if not (WRITEISH.search(seg) or unclear or _sed_writes(seg)) or _reads_only(seg):    # only redirects, none into a guard file; or only reading
        return None
    if not unclear and not _sed_writes(seg) and _write_word_apart(seg, here, root, globs, cfg):
        return None
    var = VARIABLE.search(re.sub(r"'[^']*'", "", QUOTED_BODY.sub("", seg)))
    if var and _copy_from_variable(seg, here):
        var = None                                     # cp "$f" plain/path: a copy writes only where it lands
    scope = (_line_so_far(seg, text) if var else _sed_files_only(seg))   # a shell variable could point anywhere: the whole line counts
    hit = _named_guard_file(scope, here, root, globs, cfg)
    if not hit:
        hit = _lands_in_folder(seg, here, cfg)
        if hit:
            TOUCH[0] = "a copy or move into its folder of a file with its name"
            return hit
    if hit:
        if var and text != seg and not BREAK("variable_write_words"):
            name = os.path.basename(str(getattr(hit, "rel", hit)))
            TOUCH[0] = (f"a write whose place is spelled with a shell variable ({_short(seg)}), so the kit can't tell "
                        f"where it lands; '{name}' is named elsewhere in the same command, so it counts. It may well "
                        "not change at all: writing each path out plainly (or cp -- \"$f\" plain/path) lets the kit see")
        else:
            TOUCH[0] = ("its name somewhere in a line whose write goes through a shell variable (so the whole line counts)"
                        if var and text != seg else
                        "its name in a part of the command that writes (the kit can't tell whether that part writes this "
                        "file or only names it)")
    return hit


QUOTED_WORD = re.compile(r'"(?:[^"\\]|\\.)*"|\'[^\']*\'')
HANDS_ON = re.compile(r"\b(xargs|find|parallel|eval|source|exec)\b|(?:^|\s)\.\s|\s-(?:c|e|Command|EncodedCommand)\b|\s/[cCkK]\b")


def _write_word_apart(seg, here, root, globs, cfg=None):
    """The game's PC, 23 Nov: bash Tools/Scripts/session_wait.sh 90 "the kit install (x.bat) or the rotation"
    "! git diff --quiet -- fg/" asked the owner, because "install" in the quoted reason text looked like a write and
    fg/ was named in the other, read-only argument. A write word only inside quoted arguments that name no guard file,
    with none outside the quotes, writes nothing the kit guards: each quoted argument is one word to the program. Not
    when a quoted argument starts with the write word, or has it right after ; & | or (, as a command would, or holds
    a $ or ` (it could take its target from another argument), or when the command runs its words as code (-c, -e,
    -Command, /c, xargs, find, eval, exec, source, .), and only for quotes that are whole words (F538)."""
    if BREAK("write_word_apart"):
        return False
    found = list(QUOTED_WORD.finditer(seg))
    if not found or "<<" in seg or any((m.start() and not seg[m.start() - 1].isspace())
                                       or (m.end() < len(seg) and not seg[m.end()].isspace()) for m in found):
        return False    # quotes inside code (open('x', 'w')) or a here-document: not whole words given to a program
    quoted = [m.group(0) for m in found]
    rest = QUOTED_WORD.sub(" ", seg)
    if WRITEISH.search(rest) or HANDS_ON.search(rest):
        return False
    for q in quoted:
        m = WRITEISH.search(q)
        if m and (re.search(r"[$`]", q) or not q[1:m.start()].strip() or re.search(r"[;&|(]\s*$", q[1:m.start()])
                  or _named_guard_file(q[1:-1], here, root, globs, cfg)):
            return False        # "install x" / "a; rm y" begin a command, so they may be one; prose has words before
    return True


SED_PLAIN_OPTS = {"-i", "--in-place", "-E", "-r", "--regexp-extended", "-n", "--quiet", "--silent"}


def _sed_files_only(seg):
    """The game's PC, 21 Nov: sed -i "s|old|... not in Docs/APPROVED.md, which ...|" Docs/items/n8.md asked the owner,
    because the replacement TEXT named a guard file. sed -i writes only the files given after its script, so for one
    plain substitution (no w or e flag, nothing the shell would run inside it) the script's text is left out and only
    the files count. Anything else about the command is read as before."""
    if BREAK("sed_script_text"):
        return seg
    tk = strip_prefixes(tokens(seg))
    if not tk or base(tk[0]) != "sed" or any(c in seg for c in "<>|&;`") and len(split_chain(seg)) != 1:
        return seg
    rest = tk[1:]
    opts = [t for t in rest if t.startswith("-")]
    words = [t for t in rest if not t.startswith("-")]
    if not opts or not all(t in SED_PLAIN_OPTS for t in opts) or not ({"-i", "--in-place"} & set(opts)) or len(words) < 2:
        return seg
    script, files = words[0], words[1:]
    if any(c in f for f in files for c in "$`*?[{~"):
        return seg
    if "`" in script or re.search(r"\$[({A-Za-z_]", script) or len(script) < 4 or script[0] != "s" or script[1].isalnum() \
            or script[1] in "\\\n ":
        return seg
    parts = re.split(r"(?<!\\)" + re.escape(script[1]), script[2:])
    if len(parts) != 3 or not re.fullmatch(r"[gpiIm0-9]*", parts[2]):
        return seg
    return "sed -i " + " ".join('"%s"' % f.replace('"', '\\"') for f in files)


def _lands_in_folder(seg, here, cfg):
    """Found on the way, 19 Nov: cp x/Game.uproject . put a new project file in place with no ask, because the place
    it lands (the folder plus the copied file's own name) is not written on the line. The guard file a cp, mv, install
    or ln into a folder would land on, or None."""
    if BREAK("lands_in_folder") or not cfg:
        return None
    import glob
    tk = strip_prefixes(tokens(seg))
    if not tk or base(tk[0]) not in ("cp", "mv", "install", "ln"):
        return None
    args, dest, k = [], None, 1
    while k < len(tk):
        t = tk[k]
        if t in (">", ">>", "2>", "2>>", "&>", "<") or re.fullmatch(r"\d*>&?\d*", t):
            break
        if t in ("-t", "--target-directory") and k + 1 < len(tk):
            dest = tk[k + 1]; k += 2; continue
        if t.startswith("--target-directory=") or (t.startswith("-t") and len(t) > 2 and not t.startswith("--")):
            dest = t.split("=", 1)[1] if "=" in t else t[2:]; k += 1; continue
        if not t.startswith("-") or t == "-":
            args.append(t)
        k += 1
    if dest is None:
        if len(args) < 2:
            return None
        dest, args = args[-1], args[:-1]
    full = os.path.normpath(os.path.join(here or ".", P.shell_path(dest)))
    if not (os.path.isdir(full) or dest.endswith(("/", "\\")) or dest in (".", "..") or len(args) > 1):
        return None
    for a in args:
        if VARIABLE.search(a):
            continue                                   # a variable is judged by the whole line, as before
        src = os.path.join(here or ".", P.shell_path(a))
        for one in (glob.glob(src)[:500] if re.search(r"[*?\[]", a) else [src]):
            hit = _guarded(os.path.join(full, os.path.basename(os.path.normpath(one))), cfg)
            if hit:
                return hit[1]
    return None


LATER_FEEDS = re.compile(r"<<|\bfunction\b|\)\s*\{|(?<![\w./-])(?:eval|source|trap|alias|exec|coproc|wait|fg|bg)(?![\w./-])|"
                         r"(?:^|[\s;&|(])\.\s|\bPROMPT_COMMAND\b|(?<![>&<])&(?![&>])")


def _line_so_far(seg, text):
    """The game's PC, 19 Nov: B=...; cp -p "$B"/* Saved/x/; ...; python fg/structure.py asked about structure.py on
    every such line, 79 asks in a week. The shell runs a line from left to right, so a write's variables can hold only
    what the line said up to that write: a guard file named only after it can't be where it lands. The whole line
    still counts when later words can reach back: inside a loop, with a function, eval, source, trap, a here-document
    or a job in the background on the line."""
    if BREAK("variable_write_later_words") or LATER_FEEDS.search(text) or text.count(seg) != 1:
        return text
    before = text[:text.index(seg)]
    loops = len(re.findall(r"(?<![\w./-])(?:for|while|until|select)(?![\w./-])", before))
    if loops != len(re.findall(r"(?<![\w./-])done(?![\w./-])", before)) or re.search(r"[{(]\s*$", before):
        return text                                    # the write is inside a loop: its later words run before it again
    return before + seg


def _short(seg, n=70):
    seg = " ".join(seg.split())
    return seg if len(seg) <= n else seg[:n - 3] + "..."


def _copy_from_variable(seg, here):
    """The build thread, 17 Nov: cp "$f" Saved/x.png named every path in the command as written. A plain cp whose
    variables are only in what it copies FROM writes only its last, plain path (the copy never changes its source). Not
    into a folder (the file's name comes from the variable), and only with each variable in double quotes and either
    after -- or behind a plain start ("./$f"), so it can't become an option such as -t."""
    if BREAK("copy_from_variable"):
        return False
    tk = strip_prefixes(tokens(seg))
    if not tk or base(tk[0]) != "cp" or any(t.startswith("-t") or t.startswith("--target") for t in tk[1:]):
        return False
    if VARIABLE.search(re.sub(r'"[^"]*"', "", seg)):
        return False                                   # an unquoted variable can split into more paths or options
    dash = "--" in tk
    args = tk[tk.index("--") + 1:] if dash else [t for t in tk[1:] if not t.startswith("-")]
    if not dash and any(VARIABLE.match(t) for t in args):
        return False                                   # "$f" could be -t somewhere: an option, not a file
    raw = seg.rstrip().rstrip(";").rstrip()
    return (len(args) >= 2 and not VARIABLE.search(args[-1]) and not re.search(r"[*?\[\]{}~]", args[-1])
            and raw.endswith((args[-1], f'"{args[-1]}"', f"'{args[-1]}'")) and not args[-1].endswith(("/", "\\"))
            and not os.path.isdir(os.path.join(here or ".", P.shell_path(args[-1]))))


# Found on the way, 12 Nov: "set -- APPROVED.md; rm $1" and "rm \"$@\"" changed a guard file without the kit asking,
# because $1, $@ and $* didn't count as variables.
VARIABLE = re.compile(r"\$\{?[A-Za-z_]|\$\(|`" + ("" if os.environ.get("FG_BREAK") == "guard_positionals" else
                                               r"|\$\{?[0-9@*]|\$\{[#!]"))
QUOTED_BODY = re.compile(r"""<<-?\s*(['"])(\w+)\1[^\n]*\n.*?\n\2(?=\n|$)""", re.S)   # the shell expands nothing in a <<'EOF' body


HEREDOC_BLOCK = re.compile(r"""[^\n]*<<-?\s*(['"]?)(\w+)\1[^\n]*\n.*?\n\2(?=\n|$)""", re.S)


def _write_segments(text, start):
    """The parts of a command line that write something. A write and a guard-file name only count together inside one
    part (weaker-AI test, 10 Nov: "git checkout -b x && ... && python fg/push.py" asked the owner). A here-document
    and the line that feeds it stay one part."""
    if os.environ.get("FG_BREAK") == "guard_segments":
        return [(text, start, 0)], [(text, "")]
    blocks = []
    def hold(m):
        blocks.append(m.group(0)); return f" \x00{len(blocks) - 1}\x00 "
    held = re.sub(r">\|", ">", HEREDOC_BLOCK.sub(hold, text))          # ">|" (overwrite anyway) is one redirect, not a pipe
    back = lambda t: re.sub(r"\x00(\d+)\x00", lambda m: blocks[int(m.group(1))], t)
    out, here = [], start
    pieces = [(back(x), sep) for x, sep in split_chain(held, with_seps=True)]
    for i, (x, _) in enumerate(pieces):
        m = re.match(r"(?:pushd|cd)\s+(['\"]?)([^\s'\";&|]+)\1\s*$", x)
        if m:                                     # a cd changes where later file names point (also a gap before v0.8.4)
            if VARIABLE.search(m.group(2)) or m.group(2) == "-":
                here = None
                continue
            to = os.path.expanduser(P.shell_path(m.group(2)))
            if BREAK("cd_after_variable"):
                here = os.path.normpath(os.path.join(here, to)); continue
            if here is None and not os.path.isabs(to):
                continue                          # still somewhere a variable named (found 12 Nov: this crashed, so blocked)
            here = os.path.normpath(os.path.join(here or "", to))
            continue
        if WRITEISH.search(x) or _python_inline(x) or _sed_writes(x):
            out.append((x, here, i))
    return out, pieces


# The game's PC, 12 Nov: "for A in 10000 4000 1200; do cp Saved/a_${A}.png Saved/x_$1_${A}.png; done", in the same line
# as "bash Tools/Scripts/height_check.sh", asked the owner to change that script on every run of the PC's own
# check: a variable in a write made the whole line count, and the script's name was in it. A variable that the line's
# own loop (for NAME in WORDS) or set -- gives plain words can hold only those words, so such a write is judged with each
# of its words put in, like any other write. A variable set any other way, or used outside the loop that sets it, could
# still point anywhere, and the whole line still counts for it.
REF = re.compile(r"\$(?:\{([A-Za-z_]\w*|[1-9])\}|([A-Za-z_]\w*|[1-9]))")
EXPANDS = re.compile(r"[$`*?\[\]{}~\\<>]")
WORD = re.compile(r"""(?:"(?:[^"\\]|\\.)*"|'[^']*'|[^\s"'])+""")
KEYWORDS = re.compile(r"^(?:(?:do|then|else|elif|!|time)(?:\s+|$))+")
SHELL_SET = {"_", "IFS", "PWD", "OLDPWD", "REPLY", "RANDOM", "SRANDOM", "SECONDS", "LINENO", "OPTARG", "OPTIND", "BASHPID"}


def _words(raw):
    """raw's words as the shell hands them on (quotes taken off), or None if it would expand any of them: a variable,
    $(...), `...`, a wildcard, braces or ~."""
    if WORD.sub("", raw).strip():
        return None
    out = []
    for m in WORD.finditer(raw):
        val = ""
        for part in re.findall(r""""(?:[^"\\]|\\.)*"|'[^']*'|[^"']+""", m.group(0)):
            body = part[1:-1] if part[0] in "'\"" else part
            if (re.search(r"[$`\\]", body) if part[0] == '"' else part[0] != "'" and EXPANDS.search(body)):
                return None
            val += body
        out.append(val)
    return out


def _line_sets(pieces, line):
    """What the line's own loops and set -- give its variables: ({name or "@": [(part, block, words or text or None)]},
    each part's block). None when the line could set them in a way the kit can't read: eval, source, a subshell, a
    function, a here-document, IFS."""
    unquoted = re.sub(r'"(?:[^"\\]|\\.)*"|\'[^\']*\'', '""', line)
    if "<<" in line or re.search(r"[()`]", unquoted) or "IFS" in line:
        return None
    stack, n, blocks, sets = [], 0, [], {}
    for i, (seg, sep) in enumerate(pieces):
        lead = KEYWORDS.match(seg)
        body = seg[lead.end():] if lead else seg
        if lead and re.search(r"\b(?:else|elif)\b", lead.group(0)):     # another branch: what one branch set, the other didn't
            if not stack:
                return None
            n += 1; stack[-1] = n
        while re.match(r"\{\s", body):                         # { a; b; }: a block of its own
            n += 1; stack.append(n); body = body[1:].lstrip()
        first = (body.split() or [""])[0]
        if first in ("done", "fi", "esac", "}"):
            if not stack:
                return None
            stack.pop()
        elif first in ("for", "select", "while", "until", "if", "case", "{"):
            n += 1; stack.append(n)
        blocks.append(tuple(stack))
        words = [w for w in body.split() if not ASSIGN.match(w)]
        if words[:1] in (["command"], ["builtin"]):
            words = words[1:]
        if words[:1] and words[0] in (".", "source", "eval", "exec", "function"):
            return None
        piped = sep in ("|", "&") or i and pieces[i - 1][1] in ("|", "&")      # in a pipe or the background: a subshell
        if first in ("for", "select"):
            m = re.match(r"(?:for|select)\s+([A-Za-z_]\w*)\s+in\b(.*)$", body, re.S)
            if not m:
                return None                                   # for NAME (over $@) or for ((...)): not read here
            sets.setdefault(m.group(1), []).append((i, blocks[-1], _words(m.group(2))))
        elif first == "set" and not re.fullmatch(r"set(?:\s+[-+][a-zA-Z]+|\s+[-+]o\s+\w+)*", body):
            m = re.match(r"set\s+--(?:\s+(.*))?$", body, re.S)
            sets.setdefault("@", []).append((i, blocks[-1], (m.group(1) or "") if m and not piped else None))
        elif first == "shift":
            sets.setdefault("@", []).append((i, blocks[-1], None))
        elif PLAIN_SET.match(body.strip()) and not BREAK("line_plain_values"):
            # the game's PC, 19 Nov: S='C:/.../scratchpad'; ...; cp Saved/x.log "$S/x.log" asked about every guard file
            # the line named. A variable the line itself sets to plain words (NAME=words, a step of its own) holds them.
            m = PLAIN_SET.match(body.strip())
            w = None if piped else _words(m.group(2))
            sets.setdefault(m.group(1), []).append((i, blocks[-1], w if w and len(w) == 1 and not EXPANDS.search(w[0]) else None))
    return sets, blocks


PLAIN_SET = re.compile(r"""([A-Za-z_]\w*)=((?:"(?:[^"\\]|\\.)*"|'[^']*'|[^\s"'])+)$""")


def _values(name, i, sets, blocks, line):
    """The words variable name (or $1..$9) can hold at part i of the line, or None if it could hold anything."""
    digit = name.isdigit()
    defs = sets.get("@" if digit else name, [])
    if name in SHELL_SET or not any(j < i and blocks[i][:len(b)] == b for j, b, _ in defs):
        return None                                           # not surely set by the line before this part
    if not digit:
        bare = len(re.findall(r"(?<![\w-])" + name + r"(?!\w)", REF.sub(" ", line)))
        if bare != len(defs) or any(w is None for _, _, w in defs):
            return None                                       # also set some other way (read, A=..., export, a loop over files)
        return sorted({w for _, _, ws in defs for w in ws})
    out = set()
    for j, _, text in defs:
        if text is None:
            return None
        m = re.fullmatch(r"\$(?:\{([A-Za-z_]\w*)\}|([A-Za-z_]\w*))", text.strip())
        if m:                                                 # set -- $R: the words of R, split at spaces
            vals = _values(m.group(1) or m.group(2), j, sets, blocks, line)
            fields = None if vals is None else [v.split() for v in vals]
        else:
            fields = _words(text)
            fields = None if fields is None else [fields]
        if fields is None:
            return None
        for f in fields:
            w = f[int(name) - 1] if len(f) >= int(name) else ""
            if EXPANDS.search(w):
                return None
            out.add(w)
    return sorted(out)


def _put_in(seg, i, pieces, line):
    """The ways part i of the line reads with each of its variables' words put in; None when it has no variable, or one
    that could hold anything."""
    if os.environ.get("FG_BREAK") == "guard_line_variables":
        return None
    if VARIABLE.search("".join(re.findall(r"'[^']*'", seg))) or not REF.search(seg) or VARIABLE.search(REF.sub("", seg)):
        return None                       # one in single quotes is another shell's; $(...), ${A:-x}, $@ can't be read
    facts = _line_sets(pieces, line)
    if facts is None:
        return None
    vals = {}
    for m in REF.finditer(seg):
        name = m.group(1) or m.group(2)
        if name not in vals:
            vals[name] = _values(name, i, *facts, line)
            if vals[name] is None:
                return None
    bare = re.sub(r'"(?:[^"\\]|\\.)*"', "", seg)
    if any(re.search(r"\s", w) for n, v in vals.items() for w in v
           if re.search(r"\$\{?" + n + r"(?!\w)", bare)):
        return None                       # words with a space, used outside double quotes: the shell would split them
    ways = 1
    for v in vals.values():
        ways *= len(v)
    if not ways or ways > 64:
        return None
    out = []
    for pick in itertools.product(*vals.values()):
        chosen = dict(zip(vals, pick))
        out.append(REF.sub(lambda m: chosen[m.group(1) or m.group(2)], seg))
    return out



# The game's PC, 12 Nov: sessions open in the play copy (C:\MyGame) and work in the project (C:\MyGameWT). The hook
# judged every path by the play copy's own, older settings, so an edit to the project's check scripts went through
# with no box. A path inside another copy of a project is now judged by that copy's own foundationguard.json (or, for
# a checkout of the same project with none, by this one's), as a session opened there would judge it.
class Elsewhere(str):
    """A guard file in another copy: shown by its full path, judged by that copy's settings (cfg) as rel."""
    def __new__(cls, full, cfg, rel):
        s = str.__new__(cls, full.replace("\\", "/"))
        s.cfg, s.rel = cfg, rel
        return s


_COPIES = {}


def other_copy(full, cfg):
    """The settings of the other copy of a project that full lies in, or None: inside this project, in no project, or
    in a folder that is neither kit-guarded nor a checkout of this project."""
    if BREAK("copies_own_settings"):
        return None
    full = os.path.abspath(P.shell_path(full))
    inside = P.rel(full, cfg["_root"])
    if not (inside == ".." or inside.startswith("../") or os.path.isabs(inside) or re.match(r"^[A-Za-z]:/", inside)):
        return None
    top = C.find_root(os.path.dirname(full))
    if top in _COPIES:
        return _COPIES[top]
    found = None
    if os.path.exists(os.path.join(top, "foundationguard.json")):
        found = C.load(top)
    elif os.path.exists(os.path.join(top, ".git")):
        import copies as CP                       # a checkout of this project with no settings of its own
        if CP.same_project(cfg["_root"], top):
            found = C.load(top, cfg["_root"])
    _COPIES[top] = found
    return found


def guard_elsewhere(full, cfg):
    """An Elsewhere for full when it is a guard file of another copy, else None."""
    other = other_copy(full, cfg)
    if not other:
        return None
    full = os.path.abspath(P.shell_path(full))
    rel = P.rel(full, other["_root"])
    return Elsewhere(full, other, rel) if P.matches(rel, C.guard_globs(other)) else None


def file_touch(path, cfg, cwd):
    if os.environ.get("FG_BREAK") == "guard_self" or not path:
        return None
    r = P.rel(path if os.path.isabs(path) else os.path.join(cwd or cfg["_root"], path), cfg["_root"])
    return r if P.matches(r, C.guard_globs(cfg)) else None


CALL = ["", ""]                     # the tool being judged and its file or command, for the catch log


def _write_down(cfgs, kind, reason, rule):
    """The box's whole text, the call and the rule, in the catch log of each copy concerned (the game's PC, 12 Nov: the
    helper can't see the box the owner sees, nor which rule raised it)."""
    text = (LABEL + AG.one_line("ask" if kind == "asked owner" else "block", reason)) if CL.WHOLE else reason
    what = (CALL[0] + ": " + CALL[1]) if CALL[0] and CL.WHOLE else ""
    seen = set()
    for c in cfgs:
        if c and c["_root"] not in seen:
            seen.add(c["_root"]); CL.log(c, kind, text, what, rule if CL.WHOLE else "")


def decide(why_file, cfg, reasons=None, special=None, rule=None, extra=""):
    """Ask the owner (the agent can't answer its own permission prompt). The prompt says plainly when it looks weaker."""
    reason = special or (W.prompt_text(why_file, reasons or []) if os.environ.get("FG_BREAK") != "weaken_prompt"
                         else f"may the helper change '{why_file}'? Why: it is a guard file, so it needs your own OK.")
    reason += extra
    rule = rule or ("a guard file" + (", looks weaker" if reasons else ""))
    looks_weaker = (bool(reasons) if BREAK("lead_change_is_weaker") else                 # the game's PC, 19 Nov: switching a
                    any(not r.startswith((W.UNSURE, W.CHANGE)) for r in reasons or []))  # stricter setting ON read "weaker"
    looks_weaker = looks_weaker or "WEAKER" in reason
    BX.PLAIN_NOW[0] = BX.plain(reasons)                                               # the game's PC, 27 Nov
    reason = BX.lead(rule, getattr(why_file, "rel", why_file), looks_weaker) + reason   # the owner, 16 Nov
    key, here = why_file, cfg
    if isinstance(why_file, Elsewhere):                    # another copy's file: its own settings, its own catch log
        cfg, key = why_file.cfg, why_file.rel
    import tiers as T
    tier = T.kind(str(key), cfg)
    if special is None and tier == "own" and not BREAK("own_no_put_back") and _github_guards(cfg):
        weak = [r for r in reasons or [] if not r.startswith((W.UNSURE, W.CHANGE))]   # Plan 2 PR 7: GitHub asks the owner
        CL.log(cfg, "for GitHub", reason)
        STEP["free"].append(os.path.join(cfg["_root"], str(key)))
        if weak and not BREAK("own_said_loudly"):
            STEP["loud"].append(f"{key}: {weak[0]}")
        return
    if special is None and AD.gathering(cfg, key, any(not r.startswith((W.UNSURE, W.CHANGE)) for r in reasons or [])):   # answered at one sitting, or by the reviewer, at the upload
        CL.log(cfg, "for the reviewer" if RV.on(cfg) and not cfg.get("gather_asks") else "gathered for the owner", reason)
        STEP["free"].append(os.path.join(cfg["_root"], key))
        STEP["gathered"].append(str(getattr(key, "rel", key)).replace("\\", "/"))
        return
    if C.decision_for(cfg, key) == "deny":
        reason = (f"a helper may not change '{why_file}': the owner set it to deny in foundationguard.json "
                  "(guard_decisions). Only the owner changes it, by hand.")
        _write_down([cfg, here], "blocked", reason, rule + ", set to deny"); _say("block", reason)
    AB.box(why_file, cfg, sys.modules[__name__], special is not None)
    shown = reason
    if cfg.get("chat_first") and not AB.ON[0] and AG.asks(AGENT, SHELL_CALL):   # gate line 1: the question in the chat first
        name, weaker = getattr(why_file, "rel", why_file), looks_weaker
        stop, note = BX.chat_first(cfg, rule, name, weaker, reason.split(" Details: ", 1)[-1],
                                   (STEP["data"] or {}).get("transcript_path"))
        if stop:
            _write_down([cfg, here], "question sent to the chat first", stop, rule); _say("block", stop)
        long = note == "told" or (note == "unseen" and BREAK("chat_short_always"))   # told: no chat record to trust
        shown = BX.WHERE[note] + " " + reason if long else BX.short(rule, name, weaker, note)   # unseen: short too (F499)
    _write_down([cfg, here], "asked owner", reason, rule)
    _say("ask", shown)


def _github_guards(cfg):
    try:
        import lockmode as LM
        return LM.on(cfg)
    except Exception:                                    # noqa: BLE001  unsure: the boxes stay
        return False


def edit_change(tool, ti, path):
    """(old text, new text) an editing tool would make to a file."""
    if tool == "Edit":
        return ti.get("old_string", ""), ti.get("new_string", "")
    if tool == "MultiEdit":
        e = ti.get("edits") or []
        return "\n".join(x.get("old_string", "") for x in e), "\n".join(x.get("new_string", "") for x in e)
    if tool == "Write":
        try:
            old = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            old = ""
        return old, ti.get("content", "")
    return "", ""


BREAK_GLASS = re.compile(r"\bpush\.py\b[^|;&]*--break-glass\b")
RECORD_TEXT = ("re-records the frozen size, rule or licence numbers, or lets a new plugin, library or maths call in. "
               "If any number goes up or anything new is let in, THIS MAKES A CHECK WEAKER. ")


BREAK_GLASS_TEXT = ("BREAK GLASS: may the helper push once WITHOUT the gate? Why: this push skips every check, and it is "
                   "written into BREAKGLASS.md for the change report. Say yes only if the guard itself is wrongly "
                   "blocking and you want this pushed anyway; otherwise say no.")


def _spoken(cmd):
    """The command without words that are only written down, never run: a commit message, a here-document fed to cat or
    tee, a comment, and the words echo or printf send into a file (the game's PC, 16 Nov: "steps.py --accept" and
    "away.py off" in a changelog line and a commit message were read as the helper running them, and asked the owner).
    Words piped on into a shell, or read in $( ), stay."""
    if BREAK("owner_words_quoted"):
        return cmd
    t = _harmless_gone(_heredoc_data_gone(cmd.replace("\\\n", " ")))
    t = re.sub(r"(^|\s)#[^\n]*", r"\1", t)
    return ECHO_TO_FILE.sub(lambda m: m.group(1) + m.group(2), t)


ECHO_TO_FILE = re.compile(r"""(^|[;&|(\n]\s*)(?<![$`(])\b(?:echo|printf)\s+(?:-[neE]+\s+)?(?:"(?:[^"\\$`]|\\.)*"|'[^']*'|[^\s;&|<>()$`'"]+)"""
                          r"""(?:\s+(?:"(?:[^"\\$`]|\\.)*"|'[^']*'|[^\s;&|<>()$`'"]+))*\s*(>>?\s*[^\s;&|<>()]+)(?=\s*(?:$|[;&\n]))""")


def _runs_owner_ok(cmd):
    """Does the command run fg/ownerok.py --give? (fg/ownerwords.py)"""
    if BREAK("owner_ok_spoken"):
        return OW.runs("", spoken=cmd)
    if PW.VARIABLES and not BREAK("owner_ok_python_variable"):
        # the game's PC, 27 Nov: "$PY" -I fg/ownerok.py only listed what waits for a yes, but $PY was a word the kit
        # couldn't see, so it opened the owner's yes box, and the owner later answered a second box for --give. A
        # variable the owner named in "python_variables" is read as python
        names = "|".join(re.escape(v) for v in PW.VARIABLES)
        cmd = re.sub(r"""(["']?)\$(?:\{(?:%s)\}|(?:%s)\b)\1""" % (names, names), "python", cmd)
    return OW.runs(_said_only_gone(re.sub(r"(^|\s)#[^\n]*", r"\1", _harmless_gone(_heredoc_data_gone(cmd.replace("\\\n", " "))))))


RUNS_WORDS = {"eval", "xargs", "ssh", "su", "sudo", "env", "exec", "nohup", "timeout", "watch", "script", "expect", "unbuffer",
              "iex", "invoke-expression", "start-process", "wsl", "git", "find", "parallel", "time", "command", "builtin"}
SAID = re.compile(r""""(?:[^"\\$`]|\\.)*\bownerok\.py\b(?:[^"\\$`]|\\.)*"|'[^']*\bownerok\.py\b[^']*'""")
RUNS_FLAG = re.compile(r"-\w*c\w*|/c|-command|-encodedcommand", re.I)
INTERPRETER = re.compile(r"py(thon[\d.]*)?w?(\.exe)?|perl|ruby|node|php", re.I)


def _said_only_gone(cmd):
    """The game's PC, 19 Nov: bash Tools/Scripts/session_wait.sh 90 "the owner's OK (fg/ownerok.py --give in his window)"
    opened the yes box; the owner allowed it, the waiter ran, and no yes was recorded, because nothing ran the yes
    script. Words in quotes handed to a program that is not a shell told to run them (-c), an interpreter, eval, xargs
    and the like are only said. Reading less here can't let a yes through: with no box there is no note, and --give
    refuses without one."""
    if BREAK("owner_ok_said") or "ownerok.py" not in cmd:
        return cmd
    out = []
    for seg, sep in split_chain(cmd, with_seps=True):
        tk = strip_prefixes(tokens(seg))
        b = base(tk[0]).lower() if tk else ""
        runs = (not tk or b in RUNS_WORDS or INTERPRETER.fullmatch(b) is not None
                or (b in SHELLS and (len(tk) < 2 or any(RUNS_FLAG.fullmatch(t) for t in tk[1:])))
                or "$(" in seg or "`" in seg or "<(" in seg or sep == "|")      # piped on: a shell may run the words
        if not runs and all(re.search(r"\s", m.group(0)) for m in SAID.finditer(seg)):
            seg = SAID.sub('""', seg)
        out.append(seg + " " + (sep or "") + " ")
    return "".join(out)


def _runs_upload(texts, cfg):
    """Does the command run the kit's upload (fg/push.py, or the project's own push_command)? The game's PC, 19 Nov: the
    AI tool's own safety check refused to let the helper run fg/ownerok.py, so the owner's yes had no box to land in. The
    upload a helper runs anyway now opens that box itself when a yes is missing."""
    pats = [r"(?<![\w-])push\.py(?![\w-])"]
    own = " ".join(str(cfg.get("push_command") or "").split())
    if own:
        pats.append(r"\s+".join(re.escape(w) for w in own.split()))
        last = os.path.basename(own.split()[-1].replace("\\", "/"))
        if "." in last:
            pats.append(r"(?<![\w-])" + re.escape(last) + r"(?![\w-])")
    # the game's PC, 20 Nov: notes appended with cat >> file <<'EOF' named the upload script, and the yes box was asked
    doc = (lambda t: t) if BREAK("upload_doc_text") else _doc_text_gone
    # the game's PC, 21 Nov 15:33 UTC: a Python program fed by a here-document, writing notes that said "one safe_push.sh
    # upload", opened the upload's yes box (F525)
    fed = (lambda t: t) if BREAK("upload_fed_text") else _fed_words_gone
    return any(_runs_job(fed(doc(t)), pats) for t in texts)


def _fed_words_gone(cmd):
    """_fed_text_gone, keeping the text when the shell would run something in it: an unquoted end word with $( ) or
    backticks in the text."""
    def gone(m):
        body = m.group(0).split("\n", 1)[1] if "\n" in m.group(0) else ""
        if not m.group(2) and re.search(r"\$\(|`", body):
            return m.group(0)
        tk = strip_prefixes(tokens(split_chain(m.group(1))[-1] if m.group(1).strip() else ""))
        shell = tk and (base(tk[0]) in SHELLS or base(tk[0]) in ("eval", "xargs", "source", ".", "cat", "tee"))
        return m.group(0) if shell or "|" in m.group(4) else m.group(1) + m.group(4)    # cat and tee: _doc_text_gone's
    return FED.sub(gone, cmd)


STEPS_ACCEPT = re.compile(r"\bsteps\.py\b[^|;&\n]*--(?:accept|keep)\b")     # --keep: one put-back file (review 7)
STEPS_ACCEPT_TEXT = ("may the helper take guard files as they are now (all, or with --keep the one named, as it was changed) "
                     "as the accepted state? Why: the kit puts back any change to a guard file made without your yes; after "
                     "this, they are what it puts back to. Say yes only if you changed them yourself.")
# 12 Nov: two kit commands that write guard files went through with no box; the check after every step would put their
# writes back, so the kit's box asks for them like the other owner-only commands (and the owner sees what they do)
KIT_SETTINGS = re.compile(r"\bcopies\.py\b[^|;&\n]*--cover\b|\block\.py\b[^|;&\n]*--confirm\b|\baway\.py\b[^|;&\n]*\b(?:on|off)\b|"
                          r"(?<![.\w-])py(?:thon[\d.]*)?(?:\.exe)?[\"']?\s[^|;&\n]*\b(?:install|setup|update)\.py\b")
# the game's PC, 20 Nov: "$PY" .../fg/update.py (Python kept in a variable, the spelling the kit's own install note gave)
# opened no box, so the update was copied and then partly put back. The same commands with a variable or the file itself
# as the command word ask too.
KIT_RUN = re.compile(r"(?:^|[;&|({\n]|\b(?:do|then|else)\s)\s*[\"']?(?:\$\{?\w+\}?[\"']?\s[^|;&\n]*|[\w./\\:~-]*)"
                     r"(?<![\w-])(?:install|setup|update)\.py\b")
FED = re.compile(r"""([^\n]*)<<-?\s*(['"]?)(\w+)\2([^\n]*)\n.*?\n\3(?=\n|$)""", re.S)


def _fed_text_gone(cmd):
    """The command without the text of a here-document fed to a program that is not a shell (a Python program editing
    notes that name the kit's files is not the kit's command being run)."""
    def gone(m):
        tk = strip_prefixes(tokens(split_chain(m.group(1))[-1] if m.group(1).strip() else ""))
        shell = tk and (base(tk[0]) in SHELLS or base(tk[0]) in ("eval", "xargs", "source", "."))
        return m.group(0) if shell or "|" in m.group(4) else m.group(1) + m.group(4)
    return FED.sub(gone, cmd)


KIT_SETTINGS_TEXT = ("may the helper {what}? Why: it writes {where}, which only you can OK. Say yes if you asked for it.")
ALLOW_LIST = re.compile(r"\ballowlist\.py\b[^|;&]*--apply\b|\bsetup\.py\b[^|;&]*--allow-routine\b")
ALLOW_TEXT = ("may the helper write the kit's recommended list into your AI tool's settings? Why: it lets ordinary edits "
              "in this project, routine reading, building and testing, and the kit's push script go without your AI "
              "tool's own box; guard files, settings, deletes, other pushes, installs and anything outside the project "
              "still ask, and the kit still checks everything (the list: python fg/allowlist.py). Say yes if you want "
              "a helper to keep working without you at every step.")


SIZE_NOTE = [""]


LIST = {}


def _missing_in_time(cfg):
    """The changes waiting for the owner's yes (fg/ownerok.py), worked out once in this check, or None when the list
    can't be made within "owner_ok_list_s" (8 s by default) from the start of the check. The game's PC, 26 Nov: after
    a merge of 38 test files the list took past the AI tool's 20 s limit, the guard failed safe and blocked the upload;
    now the box asks instead (F554)."""
    import threading, ownerok as OK
    if BREAK("ownerok_in_time"):
        return OK.missing(cfg)
    if "t" not in LIST:
        LIST["t"] = threading.Thread(target=lambda: LIST.setdefault("v", OK.missing(cfg)), daemon=True)
        LIST["t"].start()
    LIST["t"].join(max(0.0, float(cfg.get("owner_ok_list_s", 8)) - (time.time() - T0)))
    return LIST.get("v")


def _size_check_in_time(cfg, ST):
    """The game's PC, 23 Nov 20:55 UTC: on the game's repo the size check takes over 100 s, past the AI tool's 20 s
    limit for this hook, so the guard failed safe and blocked every upload that needed the owner's yes. The check now
    gets "size_check_before_yes_s" (8 s by default) and is skipped, with a note in the box, when it can't finish (F539).
    It runs in a daemon thread: one left running ends with the hook."""
    import threading
    limit = min(float(cfg.get("size_check_before_yes_s", 8)), max(0.0, _time_limit() * 0.7 - (time.time() - T0)))
    if BREAK("size_check_in_time"):
        limit = 10 ** 6
    out = []
    t = threading.Thread(target=lambda: out.append(ST.check(cfg, cached=True)), daemon=True)
    t.start(); t.join(limit)
    return out[0] if out else (None, limit)


def _size_before_yes(cfg):
    """The game's PC, 21 Nov: the owner said yes at the upload, then the size check stopped it (two test files past
    their recorded size); the helper split them and the owner was asked a second yes for the same work. When a yes is
    missing, the size check runs first, and the upload stops before the box if it would fail, so one yes covers it."""
    if BREAK("size_before_yes") or not cfg.get("structure") or AB.ON[0]:
        return
    import ownerok as OK, structure as ST
    try:
        if not _missing_in_time(cfg):                  # none waits for a yes, or the list ran out of time (F554)
            return
        ok, rep = _size_check_in_time(cfg, ST)
    except Exception:
        return                                        # the upload's own gate still runs the check
    if ok is None:
        SIZE_NOTE[0] = (" The size check was not run before this box: it takes longer here than the box may wait (%g s); "
                        "the upload's gate still runs it, so a size fault can still stop the upload after this yes." % rep)
        return
    if ok:
        return
    fails = [l.strip()[5:] for l in rep.split("\n") if l.strip().startswith("FAIL ")]
    _say("block", "FoundationGuard: NO BOX YET: the size check would stop this upload after the owner's yes: " +
         "; ".join(fails[:3]) + ("; and %d more" % (len(fails) - 3) if len(fails) > 3 else "") +
         ". Fix that first (python fg/structure.py shows it), then upload again; one yes then covers all of it.")


def _owner_ok_prompt(cfg):
    """The helper asks for the owner's yes to a changed guard: the hook leaves a one-time note that it is asking, then asks
    the owner in the AI tool's own permission box. fg/ownerok.py --give accepts the yes only with that fresh note (or in a
    real terminal), so where this hook isn't running a helper cannot give the yes."""
    import ownerok as OK
    todo = _missing_in_time(cfg) if not AB.ON[0] else [("", "", "")]   # --about: the yes the step may have given since
    if todo is None:                                  # the list ran out of time: ask, never block (F554)
        if not BREAK("ownerok_note"):
            OK.write_note(cfg)
        decide("owner ok", cfg, special="YOUR YES TO A CHANGED GUARD: the kit couldn't list this upload's guard changes "
               "in time (it takes longer here than the box may wait). A yes covers every guard change in this upload "
               "that waits for your yes. To see them first, say no and run python fg/ownerok.py in your own window. "
               + W.RULE, rule="the owner's yes to a changed guard")
        return
    if not todo and not BREAK("owner_ok_spoken"):     # nothing waits for a yes: no box (and no note for a later --give)
        OK._take_note(cfg)
        return
    if not BREAK("ownerok_note") and not AB.ON[0]:
        OK.write_note(cfg)
    what = (OK.brief(cfg, todo) if todo[0][0] else "") or "nothing at the moment"
    decide("owner ok", cfg, special="YOUR YES TO A CHANGED GUARD: may the upload include what the helper changed: " + what +
           "? Why: it guards your project, so it may catch less from now on. Say yes only if you asked for this; if you "
           "didn't, say no and ask the helper to put it back." + SIZE_NOTE[0] + " " + W.RULE, rule="the owner's yes to a changed guard")


def _edit_tool(tool, ti, cfg, cwd):
    """An editing tool writing a guard file: ask the owner, saying plainly if the change looks weaker."""
    fp = ti.get("file_path") or ti.get("notebook_path")
    f = file_touch(fp, cfg, cwd)
    full = (fp if os.path.isabs(fp) else os.path.join(cwd or cfg["_root"], fp)) if fp else ""
    if not f and fp:
        f = guard_elsewhere(full, cfg)
    if f:
        own, key = (f.cfg, f.rel) if isinstance(f, Elsewhere) else (cfg, f)
        not_free = AD.free_reason(own, key, tool, ti, full)
        if not not_free:                                # 11 Nov: only new tests added; no need to ask the owner
            new_file = not BREAK("tests_edit_until_commit") and os.path.exists(full) and AD.uncommitted(own, key, full)
            CL.log(own, "changed a test not committed yet (no ask)" if new_file else "added tests (no ask)", f)
            STEP["free"].append(full)
            return
        old, new = edit_change(tool, ti, full)
        test = AD.is_test_file(key, own) and not BREAK("asks_written_whole")
        decide(f, cfg, W.for_the_box(key, old, new), rule="a guard file, changed with " + tool + (", not only new tests" if test else ""),
               extra=(" It is not only new tests, because " + not_free + ".") if test else "")


def _parts_text(pm):
    weaker = pm.group(2).lower() in ("warn", "off")
    tail = ("THIS MAKES A CHECK WEAKER. " + W.RULE) if weaker else "it changes the guard, but doesn't weaken anything."
    return f"may the helper switch the kit's '{pm.group(1)}' part to {pm.group(2)}? Why: " + tail


def _many_text(many):
    what = (many.group(1) + many.group(2)).strip()
    return (f"may the helper switch several of the kit's features at once ('{what}')? Why: any feature it turns to warn "
            "or off MAKES A CHECK WEAKER. " + W.RULE)


def _shell_tool(cmd, cfg, cwd):
    r = check_line(cmd, cfg, cwd)
    if r:
        _write_down([cfg], "blocked", r, "a blocked command")
        _say("block", r)
    if HELD_BACK:
        hc, rels = HELD_BACK[0]
        decide(rels[0], hc, special="may the helper take back '" + "', '".join(rels) + "' as the last commit has it? Why: the "
               "kit put it back on disk because no one said yes to it in this folder, which leaves the folder changed. "
               "Yes keeps the commit's version here; your yes for the upload is still asked there.",
               rule="a file the kit put back, taken back")
    texts = [cmd] + _with_known_values(_unhide_names(cmd))      # also with the values set on the line written in
    for t in _known_places(cmd, cwd, cfg["_root"]):              # and with the folders named by a variable written in
        texts += [t] + _with_known_values(_unhide_names(t))
    AB.TEXTS[:], AB.CWD[0] = texts, cwd or ""
    if any(BREAK_GLASS.search(t) for t in texts) and not BREAK("break_glass"):
        decide("break glass", cfg, special=BREAK_GLASS_TEXT, rule="a push without the gate (break glass)")
    if any(_runs_owner_ok(t) for t in texts):
        _owner_ok_prompt(cfg)
    if _runs_upload(texts, cfg) and AG.asks(AGENT, SHELL_CALL) and not BREAK("upload_asks"):
        _size_before_yes(cfg)
        _owner_ok_prompt(cfg)                         # asks only when a yes is missing; fg/push.py takes it (F506)
    sa = next((m for m in (STEPS_ACCEPT.search(_spoken(t)) for t in texts) if m), None)
    if sa and not BREAK("steps_check"):                                              # the record the check after a step keeps
        decide(".git/foundationguard/steps", cfg, special=STEPS_ACCEPT_TEXT, rule="the accepted state of the guard files",
               extra="" if BREAK("accept_quote") else OW.read_as(sa.group(0)))
    if any(ALLOW_LIST.search(t) for t in texts) and not BREAK("allowlist_guard"):   # the AI tool's settings: the owner's call
        decide(".claude/settings.json", cfg, special=ALLOW_TEXT, rule="the AI tool's own settings")
    ks = next((m for m in (KIT_SETTINGS.search(_spoken(t)) for t in texts) if m), None)
    if not ks and not BREAK("kit_run_through_a_variable"):
        ks = next((m for m in (KIT_RUN.search(_fed_text_gone(_spoken(t))) for t in texts) if m), None)
    if ks and not BREAK("kit_settings_ask"):
        f, what, where = OW.kit_setting(ks.group(0))
        decide(f, cfg, special=KIT_SETTINGS_TEXT.format(what=what, where=where), rule="a kit command that writes guard files")
    TOUCH[0] = ""
    f = next((hit for hit in (guard_touch(t, cfg, cwd) for t in texts) if hit), None)
    if f:
        how = TOUCH[0] or "a write to a guard file"
        pm = re.search(r"\bparts\.py\b[^|;&]*\bset\s+(\w+)\s+(\w+)", cmd)
        if pm:
            decide(f, cfg, special=_parts_text(pm), rule="a kit part switched")
        many = PARTS_MANY.search(cmd)
        if many:
            decide(f, cfg, special=_many_text(many), rule="several kit parts switched")
        if RECORD.search(cmd):
            decide(f, cfg, special="may the helper re-record '" + f + "'? Why: this command " + RECORD_TEXT + W.RULE,
                   rule="a record re-recorded")
        decide(f, cfg, rule="a shell command: " + how,
               extra="" if BREAK("asks_written_whole") else " The kit read this from the command as " + how + ".")


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--check":
        # "--check -" reads the command from the input (the Godot game test, 11 Nov: Windows PowerShell 5 strips the inner
        # quotes of an argument, so --check 'bash -c "git push --force"' wrongly said ALLOW; piped text arrives whole)
        line = sys.stdin.read().strip() if sys.argv[2] == "-" and not BREAK("check_stdin") else sys.argv[2]
        cfg = C.load(); r = check_line(line, cfg, os.getcwd())
        print(("BLOCK: " + r) if r else "ALLOW"); sys.exit(2 if r else 0)
    global AGENT, SHELL_CALL
    home = sys.argv[sys.argv.index("--home") + 1] if "--home" in sys.argv[:-1] else None   # a copy guarded from another folder's kit
    if "--status" in sys.argv[1:]:                    # the first line of every AI session: is the guard live here?
        import copies as CP
        root = C.find_root(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        line = CP.status_line(root)
        try:
            line += " " + CL.today_words(C.load(root))     # the owner's daily ask budget (the owner, 16 Nov)
        except Exception:
            pass
        print(line); sys.exit(0)
    AGENT = _agent_flag() or AGENT                    # known before the input is read, so a failure answers that tool
    AB.on(sys.argv)                                   # --about: the check after the step asks what the box names
    data = json.load(sys.stdin)
    AGENT = AG.detect(data, sys.argv[sys.argv.index("--agent") + 1] if "--agent" in sys.argv[:-1] else None)
    calls, cwd = AG.normalise(AGENT, data)
    cfg = C.load(C.find_root(cwd), home)
    PW.VARIABLES[:] = [str(v) for v in cfg.get("python_variables") or []]
    if C.part(cfg, "guard") == "off" and not AB.ON[0] and isinstance(data, dict):   # review 6 (F263): a switch-off
        import steps as SP                            # written between steps is judged first, then read again
        SP.between_first(cfg, data); cfg = C.load(C.find_root(cwd), home)
    if C.part(cfg, "guard") == "off":
        sys.exit(0)                                   # the owner switched the command guard off in parts
    STEP.update(cfg=cfg, data=data if isinstance(data, dict) else {})
    for tool, ti in calls:                            # one Codex patch can touch several files
        SHELL_CALL = tool not in ("Edit", "Write", "MultiEdit", "NotebookEdit")
        CALL[:] = [tool, ti.get("command") or ti.get("file_path") or ti.get("notebook_path") or ""]
        if SHELL_CALL:
            _shell_tool(ti.get("command", ""), cfg, cwd)
        else:
            _edit_tool(tool, ti, cfg, cwd)
    if not BREAK("owner_note_kept"):                 # a step that isn't the owner's yes: an unused note from an earlier
        import ownerok as OK                          # box (a "no") ends here, so the longer wait for a yes stays safe
        OK.clear_note(cfg)
    _step_note(False)
    if AB.ON[0]:
        AB.say("allow")
    sys.exit(0)

if __name__ == "__main__" and {"--help", "-h"} & set(__import__("sys").argv[1:]) and __import__("os").environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)                  # v0.8.5: asking for help never runs the command

if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:                      # 0 = allowed or answered, 2 = blocked; anything else is a failure
        if e.code in (0, 2, None) or BREAK("guard_fail_closed"):
            raise
        _fail_closed(str(e.code)[:300])
