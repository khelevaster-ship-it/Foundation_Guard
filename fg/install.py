"""FoundationGuard installer (AI-made, Claude, 2026-11-08). Run once from the repo root: python fg/install.py
- adds the guard as a Claude Code PreToolUse hook in .claude/settings.json (merging with what's there);
- installs the git pre-push hook;
- writes a starter foundationguard.json and APPROVED.md if they don't exist.
Other AI agents: call `python fg/guard.py --check "<command>"` before running a shell command (exit 2 = blocked)."""
import json, os, stat, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import paths as P


def _same_call(c, end):
    """The command calls the kit's script: its path ends the same, after a '/' or a quote (the game's case and a kit on
    another drive, whose path is a full one: Windows CI, 14 Nov)."""
    c = str(c).replace("\\", "/")
    return c.endswith(end) and c[:-len(end)][-1:] in ("/", '"')


def _respell(e, cmd, end, matcher):
    e["hooks"] = [h for h in e.get("hooks", []) if h.get("command") == cmd or not _same_call(h.get("command", ""), end)]
    if any(h.get("command") == cmd for h in e["hooks"]):
        e["matcher"] = matcher


def _place(event, matcher, tail, off=None):
    """The kit's hook calling '<kit>/<script> <args>': an older spelling of the same call (a bare "python", no -I) is
    replaced, not doubled, and an older install's matcher is upgraded."""
    if off and os.environ.get("FG_BREAK") == off:
        return
    script, _, args = tail.partition(" ")
    rest = " " + args if args else ""
    end, cmd = f'{fg}/{script}"' + rest, f'{hpy} "{top}/{script}"' + rest
    entries = data.setdefault("hooks", {}).setdefault(event, [])
    for e in entries:
        _respell(e, cmd, end, matcher)
    data["hooks"][event] = entries = [e for e in entries if e.get("hooks")]
    if not any(h.get("command") == cmd for e in entries for h in e["hooks"]):
        entries.append({"matcher": matcher, "hooks": [{"type": "command", "command": cmd}]})


def main():
    """Everything the install writes. The game's PC, 20 Nov: a check that only loaded each kit file as a module ran the
    whole install, which rewrote the helper rules and another copy's settings (the kit put them back). Loading this file
    now writes nothing."""
    global root, fg, py, s, data, hpy, top, M, START, before
    root = os.getcwd(); fg = P.kit_dir(root)
    py = C.python_cmd()
    s = os.path.join(root, ".claude", "settings.json"); os.makedirs(os.path.dirname(s), exist_ok=True)
    data = json.load(open(s, encoding="utf-8-sig")) if os.path.exists(s) else {}
    hpy = C.hook_python()                          # 13 Nov (the game's PC): the hooks run Python isolated (-I)
    top = P.from_top('$CLAUDE_PROJECT_DIR', fg)
    # 12 Nov: Claude Code's Monitor tool runs a shell command too (in the background), so the guard reads it like Bash
    M = "Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit" + ("" if os.environ.get("FG_BREAK") == "monitor_tool" else "|Monitor")
    START = "startup|resume|compact|clear"
    import agents as AG
    import door as D                                # Fable's beta plan, line 3: each file the install changes gets a door line
    _mine = [".claude/settings.json", "foundationguard.json", "APPROVED.md", ".git/hooks/pre-push"]
    before = D.ids([os.path.join(root, f) for f in _mine + list(AG.hook_files(fg, hpy)) + list(AG.rules_files(""))])
    _place("PreToolUse", M, "guard.py")
    _place("PostToolUse", M, "steps.py --after", "steps_hook")   # 12 Nov: guard files changed without a yes are put back
    _place("SessionStart", START, "docs.py --core", "docs_hook")  # v0.8: every session starts by reading the core docs
    _place("SessionStart", START, "guard.py --status")            # 11 Nov: whether the guard is live in this folder
    _place("SessionStart", START, "night.py --hook", "night_install")   # 13 Nov: the night's work that didn't happen
    _place("SessionStart", START, "ready.py --hook", "ready_install")   # 13 Nov: missing programs, the lock, too many boxes
    json.dump(data, open(s, "w", encoding="utf-8"), indent=2)
    hook = os.path.join(root, ".git", "hooks", "pre-push")
    if os.path.isdir(os.path.dirname(hook)):
        open(hook, "w", newline="\n").write(f"#!/bin/sh\nexec {py} {fg}/prepush.py \"$@\"\n")
        os.chmod(hook, os.stat(hook).st_mode | stat.S_IEXEC)
    if not os.path.exists("foundationguard.json"):
        json.dump({"protected_branches": ["main", "master"], "gate_command": py + " -m pytest -q --junitxml=.foundationguard/junit.xml",
                   "test_log": ".foundationguard/junit.xml", "check_command": py + " -m pytest -q -k {check}"}, open("foundationguard.json", "w"), indent=2)
    if not os.path.exists("APPROVED.md"):
        open("APPROVED.md", "w").write("| ID | Behaviour | Owner's words | Check | Break |\n|---|---|---|---|---|\n")
    # v0.8.2: the same guard for GitHub Copilot CLI, OpenAI Codex CLI and Cursor, and the helper rules in the files they read
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import agents as AG
    others = AG.write_all(root, fg, hpy)
    import copies as CP
    covered = CP.cover(root, hpy)                  # the other checkouts of this project (11 Nov: one ran unguarded)
    import compileall                             # 13 Nov (the game's PC): the first guarded step compiled the whole kit
    if os.environ.get("FG_BREAK") != "install_compile":     # and ran past the guard's time limit, so it was refused
        compileall.compile_dir(os.path.dirname(os.path.abspath(__file__)), quiet=1, maxlevels=0)
    if os.environ.get("FG_BREAK") != "install_manifest":     # so the check after the step (or the next one) keeps them
        D.wrote_changed(C.load(root), before, "the kit's install (python fg/install.py)")
    print("FoundationGuard installed: Claude Code hook, git pre-push hook, foundationguard.json, APPROVED.md"
          + ("; other AI tools: " + ", ".join(others) if others else "") + ".")
    if covered:
        print("Also guarded, from this folder's kit and settings: " + ", ".join(covered) + ".")
    if others:
        print("Codex CLI runs a project's hooks only after you trust them once: open Codex in this folder and type /hooks.")


if __name__ == "__main__" and {"--help", "-h"} & set(sys.argv[1:]) and os.environ.get("FG_BREAK") != "help_flag":
    print(__doc__.strip()); raise SystemExit(0)

if __name__ == "__main__" or os.environ.get("FG_BREAK") == "install_on_load":
    main()
